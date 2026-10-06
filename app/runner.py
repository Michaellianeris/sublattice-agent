"""Run the original macrospin code in the current directory.

Called as: python -m app.runner   (cwd = run folder containing parameters.txt)
The physics code in macrospin/ is not modified. This wrapper only:
  - counts Heun steps to report progress
  - silences the per-step print in the temperature-dependent branch
  - adds a font fallback (Times New Roman is missing in Docker)
  - writes summary.json and neel_z.dat when the run ends
"""
import json
import os
import sys
import time
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent / "macrospin"
sys.path.insert(0, str(CODE_DIR))

PROGRESS_EVERY = 500


def write_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def patch_progress(total_steps):
    import solver as solver_mod

    original = solver_mod.solver.Heun
    state = {"n": 0, "t0": time.time()}

    def heun(self, m1, m2, t0):
        state["n"] += 1
        if state["n"] % PROGRESS_EVERY == 0:
            write_json("progress.json", {
                "step": state["n"], "total": total_steps,
                "elapsed": time.time() - state["t0"],
            })
        return original(self, m1, m2, t0)

    solver_mod.solver.Heun = heun
    return state


def dominant_frequency(t, y):
    # peak of the FFT magnitude, ignoring the DC bin
    import numpy as np
    if len(t) < 16:
        return None
    dt = float(np.mean(np.diff(t)))
    y = y - np.mean(y)
    if np.allclose(y, 0):
        return None
    spec = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(len(y), dt)
    k = int(np.argmax(spec[1:]) + 1)
    return float(freqs[k])


def summarise(runtime):
    import numpy as np
    d1 = np.loadtxt("output1.dat")
    d2 = np.loadtxt("output2.dat")
    t = d1[:, 0]
    m1, m2 = d1[:, 1:4], d2[:, 1:4]
    neel = (m1 - m2) / 2.0
    mnet = (m1 + m2) / 2.0

    # same definition as original_scripts/neel_vector_generate.py
    neel_z = np.abs((m1[:, 2] - m2[:, 2]) / 2.0)
    np.savetxt("neel_z.dat", np.column_stack((t, neel_z)), fmt="%.6e")

    sign = np.sign(neel[:, 2])
    flips = np.where(np.diff(sign) != 0)[0]
    half = len(t) // 2

    def vec(a):
        return [round(float(x), 6) for x in a]

    summary = {
        "points": int(len(t)),
        "t_end_s": float(t[-1]),
        "runtime_s": round(runtime, 2),
        "m1_initial": vec(m1[0]), "m1_final": vec(m1[-1]),
        "m2_initial": vec(m2[0]), "m2_final": vec(m2[-1]),
        "neel_initial": vec(neel[0]), "neel_final": vec(neel[-1]),
        "net_m_final": vec(mnet[-1]),
        "neel_z_abs_mean": float(np.mean(neel_z)),
        "neel_z_abs_mean_second_half": float(np.mean(neel_z[half:])),
        "net_m_z_mean": float(np.mean(mnet[:, 2])),
        "neel_z_sign_changes": int(len(flips)),
        "first_neel_z_sign_change_s": float(t[flips[0] + 1]) if len(flips) else None,
        "dominant_freq_m1x_GHz": None,
        "dominant_freq_neel_z_GHz": None,
    }
    for key, series in (("dominant_freq_m1x_GHz", m1[half:, 0]),
                        ("dominant_freq_neel_z_GHz", neel[half:, 2])):
        f = dominant_frequency(t[half:], series)
        summary[key] = round(f / 1e9, 4) if f else None
    write_json("summary.json", summary)
    return summary


def main():
    os.environ.setdefault("MPLBACKEND", "Agg")
    import matplotlib
    matplotlib.use("Agg")

    from importdata import parse_arguments
    sys.argv = ["main.py", "--input-file", "parameters.txt"]
    args = parse_arguments()
    total = int(args.t / args.h)

    patch_progress(total)

    if os.environ.get("MACROSPIN_VERBOSE") != "1":
        import current
        current.print = lambda *a, **k: None  # per-step debug print

    import main as main_mod
    import matplotlib.pyplot as plt
    plt.rcParams["font.serif"] = ["Times New Roman", "Liberation Serif", "DejaVu Serif"]
    plt.show = lambda *a, **k: None

    t0 = time.time()
    main_mod.MAIN().main()
    runtime = time.time() - t0
    write_json("progress.json", {"step": total, "total": total, "elapsed": runtime})
    summarise(runtime)


if __name__ == "__main__":
    main()
