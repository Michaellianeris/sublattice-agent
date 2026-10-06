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


def chat(messages, api_key=None, model=None):
    """Run Claude until it answers without tool calls. Returns (messages, events)."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise AgentError("No API key. Paste a key from console.anthropic.com or set ANTHROPIC_API_KEY.", 401)
    client = anthropic.Anthropic(api_key=key)
    model = model or DEFAULT_MODEL
    messages = list(messages)
    events = []
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

    for _ in range(MAX_STEPS):
        try:
            resp = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=system,
                                          tools=tools.TOOLS, messages=_prune_images(messages))
        except anthropic.AuthenticationError:
            raise AgentError("The API key was rejected. Check it in console.anthropic.com.", 401)
        except anthropic.NotFoundError:
            raise AgentError(f"Model '{model}' is not available for this key.", 400)
        except anthropic.RateLimitError:
            raise AgentError("Rate limit reached. Wait a moment and send again.", 429)
        except anthropic.APIStatusError as e:
            raise AgentError(f"Claude API error {e.status_code}: {e.message}", 502)
        except anthropic.APIConnectionError:
            raise AgentError("Could not reach the Claude API. Check the network connection.", 502)

        content = [_dump(b) for b in resp.content]
        messages.append({"role": "assistant", "content": content})
        if resp.stop_reason != "tool_use":
            return messages, events

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            try:
                out, event = tools.call(block.name, block.input or {})
                is_error = '"ok": false' in out if isinstance(out, str) else False
            except Exception as e:  # tool failure goes back to Claude, not to the user
                out, event, is_error = f"tool failed: {e}", {"tool": block.name, "error": str(e)}, True
            events.append(event)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": out, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    messages.append({"role": "assistant", "content": [
        {"type": "text", "text": "I stopped after too many tool calls in one turn. Tell me how to continue."}]})
    return messages, events
