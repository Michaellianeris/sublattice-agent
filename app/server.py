"""HTTP API and static UI."""
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from . import agent
from . import params as P
from . import simulations as S

WEB = Path(__file__).resolve().parent.parent / "web"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
MAX_UPLOAD = 200_000

app = FastAPI(title="Sublattice Agent")
S.recover_interrupted()


class ChatIn(BaseModel):
    messages: list
    model: str | None = None
    mode: str | None = None


class ParamsIn(BaseModel):
    parameters_text: str
    label: str = ""


class SaveIn(BaseModel):
    name: str
    parameters_text: str


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/config")
def config():
    return {"model": agent.DEFAULT_MODEL, "models": agent.MODELS,
            "has_server_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "defaults": P.defaults(), "max_parallel": S.MAX_PARALLEL, "max_sweep_runs": S.MAX_SWEEP_RUNS}


@app.get("/api/models")
def models(x_api_key: str | None = Header(default=None)):
    found, source, error = agent.list_models(x_api_key)
    return {"models": found, "source": source, "error": error, "default": agent.DEFAULT_MODEL}


@app.post("/api/chat")
def chat(body: ChatIn, x_api_key: str | None = Header(default=None)):
    """Streams newline-delimited JSON events while Claude works."""
    if body.model and not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", body.model):
        raise HTTPException(400, f"invalid model name {body.model}")
    if not (x_api_key or os.environ.get("ANTHROPIC_API_KEY")):
        return JSONResponse({"error": "No API key. Paste a key from console.anthropic.com "
                                      "or set ANTHROPIC_API_KEY."}, status_code=401)

    def stream():
        try:
            for ev in agent.chat_stream(body.messages, api_key=x_api_key, model=body.model, mode=body.mode):
                yield json.dumps(ev, default=str) + "\n"
        except Exception as e:  # keep the stream well-formed for the page
            yield json.dumps({"type": "error", "status": 500, "error": f"Unexpected error: {e}"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---- parameter files

@app.post("/api/files")
async def upload(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "file larger than 200 kB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "the file is not UTF-8 text")
    name = S.save_input(file.filename or "parameters.txt", text)
    return {"name": name, "text": text, "check": P.validate(text, S.sec_per_step())}


@app.post("/api/files/save")
def save(body: SaveIn):
    return {"name": S.save_input(body.name, body.parameters_text)}


@app.get("/api/files")
def files():
    return {"files": S.list_inputs()}


@app.get("/api/files/{name}")
def get_file(name: str):
    text = S.read_input(name)
    if text is None:
        raise HTTPException(404, "file not found")
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="{S.safe_name(name)}"'})


@app.get("/api/examples")
def examples():
    return {"examples": [{"name": p.name, "text": p.read_text()} for p in sorted(EXAMPLES.glob("*.txt"))]}


@app.post("/api/validate")
def validate(body: ParamsIn):
    out = P.validate(body.parameters_text, S.sec_per_step())
    out.pop("cleaned_text", None)
    return out


# ---- runs and sweeps

@app.post("/api/runs")
def start(body: ParamsIn):
    out = S.start_run(body.parameters_text, body.label)
    if not out["ok"]:
        raise HTTPException(400, out["error"])
    return out


@app.get("/api/runs")
def runs(limit: int = 50):
    return {"runs": S.list_runs(limit), "sweeps": S.list_sweeps()}


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    info = S.run_info(run_id, full=True)
    if not info:
        raise HTTPException(404, "run not found")
    return info


@app.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str):
    return S.cancel(run_id)


@app.get("/api/runs/{run_id}/series")
def run_series(run_id: str, points: int = 1200, t0_ns: float | None = None, t1_ns: float | None = None):
    out = S.run_series(run_id, points, t0_ns, t1_ns)
    if out is None:
        raise HTTPException(404, "no trajectory for this run")
    return out


@app.get("/api/runs/{run_id}/files/{name}")
def run_file(run_id: str, name: str):
    path = S.run_file(run_id, name)
    if not path:
        raise HTTPException(404, "file not found")
    return FileResponse(path, filename=f"{run_id}_{name}")


@app.get("/api/sweeps/{sweep_id}")
def sweep(sweep_id: str, discard_fraction: float = 0.0):
    info = S.sweep_info(sweep_id, discard_fraction)
    if not info:
        raise HTTPException(404, "sweep not found")
    return info


@app.get("/api/sweeps/{sweep_id}/plot")
def sweep_plot(sweep_id: str):
    path = S.sweep_file(sweep_id, "sweep_neel_z.png")
    if not path:
        raise HTTPException(404, "plot not ready")
    return FileResponse(path)
