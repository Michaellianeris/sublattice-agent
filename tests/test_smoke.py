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


def test_series_endpoint_downsamples_and_zooms(client):
    out = client.post("/api/runs", json={"parameters_text": "--t=0.3e-9 --SOT_DC_Amp=0"}).json()
    run = wait_done(client, out["run_id"])
    s = client.get(f"/api/runs/{run['id']}/series?points=100").json()
    assert s["n_total"] == 3000 and s["n_returned"] <= 100
    assert len(s["t_ns"]) == len(s["m1z"]) == len(s["m2x"])
    z = client.get(f"/api/runs/{run['id']}/series?t0_ns=0.1&t1_ns=0.2&points=5000").json()
    assert 0.099 <= z["t_ns"][0] <= 0.101 and z["n_returned"] == z["n_window"]
    assert client.get("/api/runs/r9999/series").status_code == 404


def test_chat_streams_events_in_order(client):
    from app import agent

    class Block:
        def __init__(self, **kw): self.__dict__.update(kw)
        def model_dump(self, exclude_none=True): return dict(self.__dict__)

    replies = iter([
        ("tool_use", [Block(type="text", text="Checking."),
                      Block(type="tool_use", id="a", name="validate_parameters",
                            input={"parameters_text": "--t=1e-10"})]),
        ("end_turn", [Block(type="text", text="Valid.")]),
    ])

    class Fake:
        def __init__(self, api_key):
            self.messages = types.SimpleNamespace(
                create=lambda **kw: types.SimpleNamespace(**dict(zip(("stop_reason", "content"), next(replies)))))

    real = agent.anthropic.Anthropic
    agent.anthropic.Anthropic = Fake
    try:
        with client.stream("POST", "/api/chat", json={"messages": [{"role": "user", "content": "go"}]},
                           headers={"x-api-key": "k"}) as r:
            assert r.status_code == 200
            events = [json.loads(line) for line in r.iter_lines() if line]
    finally:
        agent.anthropic.Anthropic = real
    assert [e["type"] for e in events] == ["text", "tool_start", "tool_done", "text", "done"]
    assert events[-1]["messages"][-1]["role"] == "assistant"
