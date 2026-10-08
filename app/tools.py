"""Tools exposed to Claude."""
import base64
import json

from . import params as P
from . import simulations as S

TEXT = {"type": "string"}

TOOLS = [
    {
        "name": "list_input_files",
        "description": "List parameter .txt files uploaded by the user or saved earlier.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_input_file",
        "description": "Read a parameter .txt file by name.",
        "input_schema": {"type": "object", "properties": {"name": TEXT}, "required": ["name"]},
    },
    {
        "name": "save_input_file",
        "description": "Save parameter text as a .txt file the user can download and reuse.",
        "input_schema": {"type": "object",
                         "properties": {"name": TEXT, "parameters_text": TEXT},
                         "required": ["name", "parameters_text"]},
    },
    {
        "name": "validate_parameters",
        "description": "Parse parameter text with the simulator's own parser. Returns errors, the values "
                       "that differ from the defaults, step count, estimated runtime and warnings.",
        "input_schema": {"type": "object", "properties": {"parameters_text": TEXT},
                         "required": ["parameters_text"]},
    },
    {
        "name": "start_simulation",
        "description": "Start one simulation in the background. Returns a run id immediately.",
        "input_schema": {"type": "object",
                         "properties": {"parameters_text": TEXT,
                                        "label": {"type": "string", "description": "short description"}},
                         "required": ["parameters_text"]},
    },
    {
        "name": "start_sweep",
        "description": "Start one run per value of a scalar parameter (e.g. Fr for a frequency sweep). "
                       "Other parameters come from parameters_text.",
        "input_schema": {"type": "object",
                         "properties": {"parameters_text": TEXT, "parameter": TEXT,
                                        "values": {"type": "array", "items": {"type": "number"}},
                                        "label": TEXT},
                         "required": ["parameters_text", "parameter", "values"]},
    },
    {
        "name": "wait_for_run",
        "description": "Wait until a run has finished (up to timeout_s, at most 120). Call it right after "
                       "start_simulation, then get_run with include_plot=true to report the result.",
        "input_schema": {"type": "object",
                         "properties": {"run_id": TEXT, "timeout_s": {"type": "number"}},
                         "required": ["run_id"]},
    },
    {
        "name": "wait_for_sweep",
        "description": "Wait until every run of a sweep has finished (up to timeout_s, at most 120). "
                       "Then call get_sweep. Rows carry mean |n_z|, neel_z_sign_changes, order_final and "
                       "neel_z_final, which are what a threshold search needs.",
        "input_schema": {"type": "object",
                         "properties": {"sweep_id": TEXT, "timeout_s": {"type": "number"}},
                         "required": ["sweep_id"]},
    },
    {
        "name": "get_run",
        "description": "Status, progress, parameters and result summary of a run. Set include_plot=true "
                       "to also receive the magnetization dynamics plot of a finished run.",
        "input_schema": {"type": "object",
                         "properties": {"run_id": TEXT, "include_plot": {"type": "boolean"}},
                         "required": ["run_id"]},
    },
    {
        "name": "get_sweep",
        "description": "Status of a sweep and, when finished, mean |n_z| per value and a plot. "
                       "discard_fraction drops the initial transient (0-0.95) before averaging.",
        "input_schema": {"type": "object",
                         "properties": {"sweep_id": TEXT, "discard_fraction": {"type": "number"},
                                        "include_plot": {"type": "boolean"}},
                         "required": ["sweep_id"]},
    },
    {
        "name": "list_runs",
        "description": "Most recent runs with their status.",
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
    {
        "name": "cancel_run",
        "description": "Stop a queued or running simulation.",
        "input_schema": {"type": "object", "properties": {"run_id": TEXT}, "required": ["run_id"]},
    },
]


def _image(path):
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


def _brief(run):
    keep = ("id", "label", "status", "progress", "eta_s", "steps", "estimated_runtime_s",
            "sweep_id", "sweep_value", "warnings", "changed_from_defaults", "summary",
            "parameters_text", "error_tail", "files")
    return {k: run[k] for k in keep if k in run and run[k] is not None}


def call(name, args):
    """Run a tool. Returns (content for Claude, event for the UI)."""
    if name == "list_input_files":
        out = {"files": S.list_inputs()}
    elif name == "read_input_file":
        text = S.read_input(args["name"])
        out = {"name": args["name"], "text": text} if text is not None else {"error": "file not found"}
    elif name == "save_input_file":
        out = {"saved": S.save_input(args["name"], args["parameters_text"])}
    elif name == "validate_parameters":
        out = P.validate(args["parameters_text"], S.sec_per_step())
        out.pop("cleaned_text", None)
    elif name == "start_simulation":
        out = S.start_run(args["parameters_text"], args.get("label", ""))
    elif name == "start_sweep":
        out = S.start_sweep(args["parameters_text"], args["parameter"], args["values"], args.get("label", ""))
    elif name == "wait_for_run":
        run = S.wait_for_run(args["run_id"], float(args.get("timeout_s") or 60))
        out = _brief(run) if run else {"error": f"no run {args['run_id']}"}
    elif name == "wait_for_sweep":
        out = S.wait_for_sweep(args["sweep_id"], float(args.get("timeout_s") or 60)) \
            or {"error": f"no sweep {args['sweep_id']}"}
    elif name == "get_run":
        run = S.run_info(args["run_id"], full=True)
        if not run:
            out = {"error": f"no run {args['run_id']}"}
        else:
            out = _brief(run)
            png = S.run_file(run["id"], "Two_Spin_Dynamics.png")
            if args.get("include_plot") and png:
                return [{"type": "text", "text": json.dumps(out)}, _image(png)], \
                    {"tool": name, "run_id": run["id"]}
    elif name == "get_sweep":
        info = S.sweep_info(args["sweep_id"], float(args.get("discard_fraction") or 0.0))
        if not info:
            out = {"error": f"no sweep {args['sweep_id']}"}
        else:
            out = info
            png = S.sweep_file(info["id"], info.get("plot") or "")
            if args.get("include_plot") and png:
                return [{"type": "text", "text": json.dumps(out)}, _image(png)], \
                    {"tool": name, "sweep_id": info["id"]}
    elif name == "list_runs":
        out = {"runs": [{k: r.get(k) for k in ("id", "label", "status", "progress")}
                        for r in S.list_runs(int(args.get("limit") or 20))]}
    elif name == "cancel_run":
        out = S.cancel(args["run_id"])
    else:
        out = {"error": f"unknown tool {name}"}

    event = {"tool": name}
    for key in ("run_id", "sweep_id", "runs", "saved", "ok", "error"):
        if isinstance(out, dict) and key in out:
            event[key] = out[key]
    if name in ("get_run", "wait_for_run") and isinstance(out, dict) and "id" in out:
        event["run_id"] = out["id"]
    return json.dumps(out, default=str), event
