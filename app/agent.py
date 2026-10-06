"""Claude tool-use loop. The conversation lives in the browser and is sent on every turn."""
import copy
import os

import anthropic

from . import tools
from .prompts import SYSTEM_PROMPT

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5"
MODELS = [m.strip() for m in (os.environ.get("CLAUDE_MODELS")
          or "claude-sonnet-5,claude-opus-5-5,claude-haiku-4-5-20251001").split(",") if m.strip()]
if DEFAULT_MODEL not in MODELS:
    MODELS.insert(0, DEFAULT_MODEL)


def list_models(api_key=None):
    """Every model the key can use (Sonnet, Opus, Haiku and any other), falling back to the configured list."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            found = [{"id": m.id, "name": getattr(m, "display_name", None) or m.id}
                     for m in anthropic.Anthropic(api_key=key).models.list(limit=1000)]
            if found:
                return found, "api"
        except Exception:
            pass
    return [{"id": m, "name": m} for m in MODELS], "configured"


MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "4096"))
MAX_STEPS = 12


class AgentError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def _prune_images(messages):
    """Keep plot images only in the newest user turn; older ones become a short note."""
    msgs = copy.deepcopy(messages)
    last_user = max((i for i, m in enumerate(msgs) if m["role"] == "user"), default=-1)
    for i, m in enumerate(msgs):
        if i == last_user or not isinstance(m["content"], list):
            continue
        for block in m["content"]:
            if block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                block["content"] = [b if b.get("type") != "image"
                                    else {"type": "text", "text": "[plot shown earlier]"}
                                    for b in block["content"]]
    return msgs


def _dump(block):
    d = block.model_dump(exclude_none=True)
    d.pop("citations", None)
    return d


def chat_stream(messages, api_key=None, model=None):
    """Run Claude until it answers without tool calls, yielding events as they happen.

    Events: text, tool_start, tool_done, then done (full message list) or error.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        yield {"type": "error", "status": 401,
               "error": "No API key. Paste a key from console.anthropic.com or set ANTHROPIC_API_KEY."}
        return
    client = anthropic.Anthropic(api_key=key)
    model = model or DEFAULT_MODEL
    messages = list(messages)
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

    for _ in range(MAX_STEPS):
        try:
            resp = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=system,
                                          tools=tools.TOOLS, messages=_prune_images(messages))
        except anthropic.AuthenticationError:
            yield {"type": "error", "status": 401, "error": "The API key was rejected. Check it in console.anthropic.com."}
            return
        except anthropic.NotFoundError:
            yield {"type": "error", "status": 400, "error": f"Model '{model}' is not available for this key."}
            return
        except anthropic.RateLimitError:
            yield {"type": "error", "status": 429, "error": "Rate limit reached. Wait a moment and send again."}
            return
        except anthropic.APIStatusError as e:
            yield {"type": "error", "status": 502, "error": f"Claude API error {e.status_code}: {e.message}"}
            return
        except anthropic.APIConnectionError:
            yield {"type": "error", "status": 502, "error": "Could not reach the Claude API. Check the network connection."}
            return

        messages.append({"role": "assistant", "content": [_dump(b) for b in resp.content]})
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                yield {"type": "text", "text": block.text}
        if resp.stop_reason != "tool_use":
            yield {"type": "done", "messages": messages}
            return

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            yield {"type": "tool_start", "id": block.id, "name": block.name, "input": block.input or {}}
            try:
                out, event = tools.call(block.name, block.input or {})
                is_error = '"ok": false' in out if isinstance(out, str) else False
            except Exception as e:  # tool failure goes back to Claude, not to the user
                out, event, is_error = f"tool failed: {e}", {"tool": block.name, "error": str(e)}, True
            yield {"type": "tool_done", "id": block.id, "event": event, "is_error": is_error}
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": out, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    messages.append({"role": "assistant", "content": [
        {"type": "text", "text": "I stopped after too many tool calls in one turn. Tell me how to continue."}]})
    yield {"type": "done", "messages": messages}


def chat(messages, api_key=None, model=None):
    """Blocking version of chat_stream. Returns (messages, tool events)."""
    events = []
    for ev in chat_stream(messages, api_key, model):
        if ev["type"] == "tool_done":
            events.append(ev["event"])
        elif ev["type"] == "error":
            raise AgentError(ev["error"], ev["status"])
        elif ev["type"] == "done":
            return ev["messages"], events
    raise AgentError("The conversation ended without an answer.", 500)
