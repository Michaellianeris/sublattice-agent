"""Smoke tests: parameter parsing, a short real run, the HTTP API and the agent loop (mocked Claude)."""
import json
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    monkeypatch_module.setenv("WORKSPACE", str(tmp_path_factory.mktemp("ws")))
    monkeypatch_module.setenv("MAX_PARALLEL", "2")
    from fastapi.testclient import TestClient
    from app.server import app
    return TestClient(app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def wait_done(client, run_id, timeout=60):
    for _ in range(timeout * 2):
        r = client.get(f"/api/runs/{run_id}").json()
        if r["status"] not in ("queued", "running"):
            return r
        time.sleep(0.5)
    raise TimeoutError(run_id)


def test_examples_are_valid():
    from app import params
    for f in (ROOT / "examples").glob("*.txt"):
        assert params.validate(f.read_text())["ok"], f.name


def test_parser_errors_match_original():
    from app import params
    assert "invalid float value" in params.validate("--Ku=abc")["error"]
    assert "unrecognized arguments" in params.validate("--nope=1")["error"]


def test_run_and_api(client):
    out = client.post("/api/runs", json={"parameters_text": "--t=0.2e-9 --SOT_DC_Amp=0", "label": "t"}).json()
    r = wait_done(client, out["run_id"])
    assert r["status"] == "done"
    assert r["summary"]["points"] == 2000
    assert client.get(f"/api/runs/{r['id']}/files/Two_Spin_Dynamics.png").status_code == 200
    assert client.get(f"/api/runs/{r['id']}/files/meta.json").status_code == 404


def test_upload_and_chat_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    up = client.post("/api/files", files={"file": ("c.txt", b"--t=1e-10", "text/plain")}).json()
    assert up["check"]["ok"]
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 401


def test_agent_loop_with_fake_claude(client):
    from app import agent

    class Block:
        def __init__(self, **kw): self.__dict__.update(kw)
        def model_dump(self, exclude_none=True): return dict(self.__dict__)

    replies = iter([
        ("tool_use", [Block(type="tool_use", id="a", name="start_simulation",
                            input={"parameters_text": "--t=0.1e-9 --SOT_DC_Amp=0"})]),
        ("end_turn", [Block(type="text", text="started")]),
    ])

    class Fake:
        def __init__(self, api_key):
            self.messages = types.SimpleNamespace(
                create=lambda **kw: types.SimpleNamespace(**dict(zip(("stop_reason", "content"), next(replies)))))

    real = agent.anthropic.Anthropic
    agent.anthropic.Anthropic = Fake
    try:
        msgs, events = agent.chat([{"role": "user", "content": "go"}], api_key="k")
    finally:
        agent.anthropic.Anthropic = real
    assert events[0]["tool"] == "start_simulation" and events[0]["run_id"].startswith("r")
    result = json.loads(msgs[2]["content"][0]["content"])
    assert result["ok"]
    assert wait_done(client, result["run_id"])["status"] == "done"
