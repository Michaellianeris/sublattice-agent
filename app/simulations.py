"""Background simulation runs and parameter sweeps, stored under WORKSPACE."""
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import params as P

REPO = Path(__file__).resolve().parent.parent
WORKSPACE = Path(os.environ.get("WORKSPACE", REPO / "workspace")).resolve()
RUNS = WORKSPACE / "runs"
SWEEPS = WORKSPACE / "sweeps"
INPUTS = WORKSPACE / "inputs"
for d in (RUNS, SWEEPS, INPUTS):
    d.mkdir(parents=True, exist_ok=True)

MAX_PARALLEL = int(os.environ.get("MAX_PARALLEL") or max(1, (os.cpu_count() or 2) - 1))
MAX_SWEEP_RUNS = int(os.environ.get("MAX_SWEEP_RUNS", "400"))
RESULT_FILES = ["Two_Spin_Dynamics.png", "output1.dat", "output2.dat", "neel_z.dat",
                "parameters.txt", "summary.json", "simulation_parameters.log", "stderr.log"]

_lock = threading.Lock()
_procs = {}
_pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL)


# ---------- storage helpers

def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def _write(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def _next_id(folder, prefix):
    with _lock:
        nums = [int(m.group(1)) for p in folder.iterdir()
                if (m := re.fullmatch(prefix + r"(\d+)", p.name))]
        new = folder / f"{prefix}{(max(nums) + 1 if nums else 1):04d}"
        new.mkdir()
        return new.name


def _meta(run_id):
    return _read(RUNS / run_id / "meta.json")


def _update(run_id, **kw):
    with _lock:
        m = _meta(run_id) or {}
        m.update(kw)
        _write(RUNS / run_id / "meta.json", m)
        return m


def sec_per_step():
    """Median speed of finished runs; falls back to the default estimate."""
    vals = []
    for d in RUNS.iterdir():
        m, s = _read(d / "meta.json"), _read(d / "summary.json")
        if m and s and m.get("status") == "done" and m.get("steps"):
            vals.append(s["runtime_s"] / m["steps"])
    if not vals:
        return P.DEFAULT_SEC_PER_STEP
    vals.sort()
    return vals[len(vals) // 2]


def recover_interrupted():
    """Runs left queued/running by a previous server process cannot resume."""
    for d in RUNS.iterdir():
        m = _read(d / "meta.json")
        if m and m.get("status") in ("queued", "running"):
            m["status"] = "interrupted"
            _write(d / "meta.json", m)


# ---------- single runs

def _execute(run_id):
    run_dir = RUNS / run_id
    if (_meta(run_id) or {}).get("status") == "cancelled":
        return
    env = dict(os.environ, PYTHONPATH=str(REPO), MPLBACKEND="Agg")
    _update(run_id, status="running", started=time.time())
    with open(run_dir / "stdout.log", "w") as out, open(run_dir / "stderr.log", "w") as err:
        proc = subprocess.Popen([sys.executable, "-m", "app.runner"], cwd=run_dir,
                                stdout=out, stderr=err, env=env)
        _procs[run_id] = proc
        code = proc.wait()
    _procs.pop(run_id, None)
    if (_meta(run_id) or {}).get("status") == "cancelled":
        return
    ok = code == 0 and (run_dir / "summary.json").exists()
    _update(run_id, status="done" if ok else "failed", finished=time.time(), returncode=code)


def start_run(parameters_text, label="", sweep_id=None, sweep_value=None):
    check = P.validate(parameters_text, sec_per_step())
    if not check["ok"]:
        return {"ok": False, "error": check["error"]}
    run_id = _next_id(RUNS, "r")
    run_dir = RUNS / run_id
    (run_dir / "parameters.txt").write_text(check["cleaned_text"])
    _write(run_dir / "meta.json", {
        "id": run_id, "label": label or "", "status": "queued", "created": time.time(),
        "steps": check["steps"], "estimated_runtime_s": check["estimated_runtime_s"],
        "changed_from_defaults": check["changed_from_defaults"], "warnings": check["warnings"],
        "sweep_id": sweep_id, "sweep_value": sweep_value,
    })
    _pool.submit(_execute, run_id)
    return {"ok": True, "run_id": run_id, "steps": check["steps"],
            "estimated_runtime_s": check["estimated_runtime_s"], "warnings": check["warnings"]}


def cancel(run_id):
    m = _meta(run_id) if _valid(run_id, "r") else None
    if not m:
        return {"ok": False, "error": f"no run {run_id}"}
    if m["status"] not in ("queued", "running"):
        return {"ok": False, "error": f"{run_id} is already {m['status']}"}
    _update(run_id, status="cancelled", finished=time.time())
    proc = _procs.get(run_id)
    if proc:
        proc.terminate()
    return {"ok": True, "run_id": run_id, "status": "cancelled"}


def _valid(item_id, prefix):
    return bool(re.fullmatch(prefix + r"\d{4,}", str(item_id)))


def run_info(run_id, full=False):
    if not _valid(run_id, "r"):
        return None
    run_dir = RUNS / run_id
    m = _meta(run_id)
    if not m:
        return None
    info = dict(m)
    prog = _read(run_dir / "progress.json")
    if m["status"] == "running" and prog:
        info["progress"] = round(prog["step"] / max(prog["total"], 1), 4)
        rate = prog["elapsed"] / max(prog["step"], 1)
        info["eta_s"] = round(rate * (prog["total"] - prog["step"]), 1)
    elif m["status"] == "done":
        info["progress"] = 1.0
    else:
        info["progress"] = 0.0 if m["status"] == "queued" else (prog or {}).get("step", 0) / max(m["steps"], 1)
    info["summary"] = _read(run_dir / "summary.json")
    info["files"] = [f for f in RESULT_FILES if (run_dir / f).exists()]
    if full:
        info["parameters_text"] = (run_dir / "parameters.txt").read_text()
        err = run_dir / "stderr.log"
        if err.exists() and m["status"] == "failed":
            info["error_tail"] = err.read_text()[-2000:]
    return info


def list_runs(limit=50):
    ids = sorted((d.name for d in RUNS.iterdir() if (d / "meta.json").exists()), reverse=True)
    return [run_info(i) for i in ids[:limit]]


def run_file(run_id, name):
    if name not in RESULT_FILES or not _valid(run_id, "r"):
        return None
    path = RUNS / run_id / name
    return path if path.exists() else None


# ---------- sweeps

def start_sweep(parameters_text, parameter, values, label=""):
    if parameter not in P.float_params():
        return {"ok": False, "error": f"'{parameter}' is not a scalar parameter that can be swept"}
    values = [float(v) for v in values]
    if not values:
        return {"ok": False, "error": "no values given"}
    if len(values) > MAX_SWEEP_RUNS:
        return {"ok": False, "error": f"{len(values)} runs exceeds MAX_SWEEP_RUNS={MAX_SWEEP_RUNS}"}
    base = P.validate(parameters_text, sec_per_step())
    if not base["ok"]:
        return {"ok": False, "error": base["error"]}
    sweep_id = _next_id(SWEEPS, "s")
    run_ids = []
    for v in values:
        r = start_run(P.with_override(parameters_text, parameter, v),
                      label=f"{label or sweep_id} {parameter}={v:g}", sweep_id=sweep_id, sweep_value=v)
        if not r["ok"]:
            return {"ok": False, "error": f"{parameter}={v:g}: {r['error']}"}
        run_ids.append(r["run_id"])
    _write(SWEEPS / sweep_id / "meta.json", {
        "id": sweep_id, "label": label, "parameter": parameter, "values": values,
        "run_ids": run_ids, "created": time.time(),
    })
    total = base["estimated_runtime_s"] * len(values) / MAX_PARALLEL
    return {"ok": True, "sweep_id": sweep_id, "runs": len(run_ids), "parallel": MAX_PARALLEL,
            "estimated_wall_time_s": round(total, 1)}


def sweep_info(sweep_id, discard_fraction=0.0):
    if not _valid(sweep_id, "s"):
        return None
    m = _read(SWEEPS / sweep_id / "meta.json")
    if not m:
        return None
    rows, counts = [], {}
    for rid, v in zip(m["run_ids"], m["values"]):
        r = run_info(rid) or {"status": "missing"}
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        row = {"run_id": rid, "value": v, "status": r["status"]}
        if r["status"] == "done":
            row["neel_z_abs_mean"] = _neel_mean(rid, discard_fraction)
            s = r.get("summary") or {}
            row["dominant_freq_neel_z_GHz"] = s.get("dominant_freq_neel_z_GHz")
        rows.append(row)
    info = dict(m, status_counts=counts, rows=rows, discard_fraction=discard_fraction)
    if counts.get("done") and not counts.get("running") and not counts.get("queued"):
        info["plot"] = _sweep_plot(sweep_id, m["parameter"], rows)
    return info


def _neel_mean(run_id, discard_fraction):
    import numpy as np
    data = np.loadtxt(RUNS / run_id / "neel_z.dat")
    start = int(len(data) * max(0.0, min(discard_fraction, 0.95)))
    return float(np.mean(data[start:, 1]))


def _sweep_plot(sweep_id, parameter, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pts = sorted((r["value"], r["neel_z_abs_mean"]) for r in rows if "neel_z_abs_mean" in r)
    x = [p[0] for p in pts]
    scale, unit = (1e9, " (GHz)") if parameter.endswith("Fr") else (1.0, "")
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=150)
    ax.plot([v / scale for v in x], [p[1] for p in pts], "o-", color="#1F4FD1", ms=3, lw=1.2)
    ax.set_xlabel(parameter + unit)
    ax.set_ylabel(r"average $|n_z|$")
    ax.grid(True, lw=0.4, alpha=0.5)
    fig.tight_layout()
    name = "sweep_neel_z.png"
    fig.savefig(SWEEPS / sweep_id / name)
    plt.close(fig)
    return name


def sweep_file(sweep_id, name):
    if not _valid(sweep_id, "s"):
        return None
    path = SWEEPS / sweep_id / name
    return path if name == "sweep_neel_z.png" and path.exists() else None


def list_sweeps():
    out = []
    for d in sorted(SWEEPS.iterdir(), reverse=True):
        m = _read(d / "meta.json")
        if m:
            done = sum((_meta(r) or {}).get("status") == "done" for r in m["run_ids"])
            out.append({"id": m["id"], "label": m["label"], "parameter": m["parameter"],
                        "runs": len(m["run_ids"]), "done": done, "created": m.get("created")})
    return out


# ---------- uploaded / saved input files

def safe_name(name):
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:80] or "parameters.txt"
    return name if name.endswith(".txt") else name + ".txt"


def save_input(name, text):
    name = safe_name(name)
    (INPUTS / name).write_text(text)
    return name


def read_input(name):
    path = INPUTS / safe_name(name)
    return path.read_text() if path.exists() else None


def list_inputs():
    return sorted(p.name for p in INPUTS.glob("*.txt"))
