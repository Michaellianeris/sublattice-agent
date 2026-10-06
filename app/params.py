"""Parse and validate parameter files with the original argparse parser."""
import contextlib
import io
import re
import shlex
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parent.parent / "macrospin"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import importdata  # noqa: E402  (original parser)
from conf import conFile  # noqa: E402

_ARGV_LOCK = threading.Lock()

VECTOR_PARAMS = {"Hex_DC", "Hex_AC", "m1", "m2", "p", "Demag", "u_ani", "u_ani_AC", "SOT_pol"}
FLAG_PARAMS = {"flagShape", "flag0", "flag1", "flag2", "flag3", "flag4", "flag5", "flagSinc", "flagTempVarying"}

# measured ~0.6-0.9 ms per Heun step on one core; refined from finished runs
DEFAULT_SEC_PER_STEP = 0.8e-3


def clean_text(text):
    """Drop '#' comments and blank lines so files can be annotated."""
    lines = []
    for line in text.replace("\r", "").split("\n"):
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"


def defaults():
    c = conFile()
    out = {}
    for k, v in vars(c).items():
        out[k] = v.tolist() if isinstance(v, np.ndarray) else v
    return out


def _parse(text):
    """Run the original parse_arguments() on text. Returns (args, error)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(clean_text(text))
        path = f.name
    err = io.StringIO()
    with _ARGV_LOCK:
        old = sys.argv
        sys.argv = ["main.py", "--input-file", path]
        try:
            with contextlib.redirect_stderr(err):
                args = importdata.parse_arguments()
            return args, None
        except SystemExit:
            msg = err.getvalue().strip().splitlines()
            return None, msg[-1] if msg else "could not parse the parameter file"
        finally:
            sys.argv = old
            Path(path).unlink(missing_ok=True)


def validate(text, sec_per_step=DEFAULT_SEC_PER_STEP):
    try:
        shlex.split(clean_text(text))
    except ValueError as e:
        return {"ok": False, "error": f"quoting error: {e}"}

    args, error = _parse(text)
    if error:
        return {"ok": False, "error": error}

    base = defaults()
    resolved = {k: (list(v) if isinstance(v, (list, tuple)) else v) for k, v in vars(args).items()
                if k not in ("input_file",)}
    changed = {}
    for k, v in resolved.items():
        if k == "gaussian":
            if v:
                changed[k] = v
            continue
        d = base.get(k)
        if isinstance(v, list) or isinstance(d, list):
            if d is None or not np.allclose(np.asarray(v, float), np.asarray(d, float)):
                changed[k] = v
        elif v != d:
            changed[k] = v

    warnings = []
    for k in VECTOR_PARAMS & set(resolved):
        if len(resolved[k]) != 3:
            warnings.append(f"{k} should have 3 components, got {len(resolved[k])}")
    if args.h <= 0 or args.t <= 0:
        return {"ok": False, "error": "t and h must be positive"}
    steps = int(args.t / args.h)
    if args.flag0 and args.flagTempVarying:
        warnings.append("flag0 and flagTempVarying both use Temp: as noise temperature and as the "
                        "amplitude of the temperature cycle around 370 K")
    if args.flagTempVarying and args.A0 < 0:
        warnings.append("flagTempVarying multiplies A0 by -1 below the transition; with a negative A0 "
                        "the coupling becomes ferromagnetic below 370 K (inverted with respect to FeRh)")
    if args.flag5 and args.SOT_DC_Amp and "--SOT_DC_Amp" not in clean_text(text):
        warnings.append(f"a default SOT current of {args.SOT_DC_Amp:g} A/cm^2 is applied (flag5 is on by "
                        "default and cannot be switched off from a file); set SOT_DC_Amp=0 to disable it")
    if steps > 5_000_000:
        warnings.append(f"{steps:,} steps is very long")

    return {
        "ok": True,
        "steps": steps,
        "estimated_runtime_s": round(steps * sec_per_step, 1),
        "changed_from_defaults": changed,
        "warnings": warnings,
        "cleaned_text": clean_text(text),
    }


def float_params():
    """Names of scalar float parameters that can be swept."""
    args, _ = _parse("")
    return sorted(k for k, v in vars(args).items()
                  if isinstance(v, float) and k not in FLAG_PARAMS)


def with_override(text, name, value):
    """Append --name=value; argparse keeps the last occurrence."""
    return clean_text(text).rstrip("\n") + f"\n--{name}={float(value)!r}\n"
