# Sublattice Agent

An AI agent, powered by Claude, that runs the two-sublattice macrospin simulator.
Give it a parameter `.txt` file or describe the conditions in words; it checks them with the
simulator's own parser, launches the run in the background and explains the results.

The physics code in `macrospin/` is the original code, unchanged.

## Quick start (Docker)

1. Create an API key at https://console.anthropic.com (Settings, API keys).
2. Configure and start:

   ```bash
   cp .env.example .env        # paste the key into ANTHROPIC_API_KEY (optional, see below)
   docker compose up --build
   ```

3. Open http://localhost:8000

If you leave `ANTHROPIC_API_KEY` empty, paste the key into the field at the top of the page instead.
It is kept only in that browser tab (sessionStorage) and sent to your local server with each message.

Results persist in the `sublattice-data` Docker volume. To see them on disk instead, replace the
volume line in `docker-compose.yml` with `- ./workspace:/data`.

## Without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # optional
uvicorn app.server:app --port 8000
```

Tests: `pip install -r requirements-dev.txt && pytest -q`

## Parameter files

Same format as `main.py --input-file`: command-line options, one or many per line.
Lines starting with `#` are comments (stripped before the run).

```text
# 5 ns of SOT-driven dynamics
--t=5e-9
--SOT_DC_Amp=20e6
--SOT_pol=0,1,0
--flag0 --Temp=300
```

`examples/` contains four ready files. The full parameter list with units is in `app/prompts.py`.

## What you can do

- **Chat**: attach a `.txt` (button or drag and drop) or describe a run. The assistant validates, reports
  step count and estimated runtime, starts the run, and analyses it when asked. Its steps appear live
  as they happen (checking, starting, looking at a run). It receives the dynamics plot as an image, so
  its comments are based on the actual curves. Parameter files it writes have **Copy** and
  **Open in editor** buttons.
- **Trajectory viewer**: a finished run opens an interactive plot of m₁, m₂ and the Néel vector.
  Toggle components, click to move a playhead, drag to zoom (the window is re-read from the raw data,
  so fast oscillations that look blurred in the full view resolve), double-click to reset. A dial shows
  the sublattice orientations in the x–z plane at the playhead, and **Play** animates the run.
- **Sweeps**: "sweep Fr from 10 to 40 GHz in 5 GHz steps" starts one run per value (the original
  `prepare.py` / `run_sim.py` / `avg_neel.py` workflow) and plots mean |n_z| against the parameter.
  Click a point to open that run; the transient can be excluded from the average.
- **Without the assistant**: the Parameters tab has an editor with Check and Run, so the app is
  usable even with no API key.

Each run gets its own folder with the original outputs (`output1.dat`, `output2.dat`,
`Two_Spin_Dynamics.png`, logs) plus `neel_z.dat` and `summary.json`: final m1, m2 and Neel vector,
mean |n_z|, n_z sign changes (switching) and the dominant oscillation frequency.

## How it works

```
browser (web/index.html)
   │  conversation kept in the page, sent each turn; answer streamed back as events
   ▼
FastAPI (app/server.py) ──► Claude tool-use loop (app/agent.py, app/tools.py)
   │                                   │ validate / start / sweep / get_run / cancel
   ▼                                   ▼
run queue (app/simulations.py) ──► python -m app.runner  (one process per run, cwd = run folder)
                                       └─ imports macrospin/main.py unchanged
```

`app/runner.py` wraps the original code without changing its equations: it counts Heun steps for
the progress bar, silences the per-step print of the temperature-dependent branch, adds a font
fallback, and writes the summary. Parameter files are parsed with the original `importdata.py`.

Runs execute in parallel up to `MAX_PARALLEL` (default: CPU cores − 1). On one core a Heun step
takes about 0.6–1 ms, so the default 10 ns (100 000 steps) takes roughly 1–2 minutes. The runtime
estimate is recalibrated from finished runs.

## Behaviour of the original code worth knowing

The assistant is told about these and mentions them when relevant.

- `flag5` (SOT) is on by default and cannot be switched off from a file; use `--SOT_DC_Amp=0`.
- With `flagTempVarying`, A0 is multiplied by −1 below 370 K, so a negative A0 becomes
  ferromagnetic below the transition (inverted with respect to FeRh). Use a positive A0.
- `Temp` is used both as the noise temperature (`flag0`) and as the temperature-cycle amplitude
  (`flagTempVarying`).
- The thermal field direction comes from `np.random.rand(3)`, so it always lies in the
  +x+y+z octant and is not zero-mean.
- `H_Amp` is added to the DC field amplitude before the `flag3` branch; keep `Hex_AC` orthogonal to
  `Hex_DC`.
- The chirp current is not multiplied by `SHE_angle`, unlike the SOT current.
- `p`, `T` and `gamma` are parsed but not used by the solver; `RK4` exists but `Heun` is used.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | empty | server-side key; otherwise paste it in the page |
| `CLAUDE_MODEL` | `claude-sonnet-5` | default model |
| `CLAUDE_MODELS` | sonnet, opus, haiku | models offered in the page |
| `MAX_PARALLEL` | cores − 1 | simultaneous runs |
| `MAX_SWEEP_RUNS` | 400 | largest sweep |
| `WORKSPACE` | `/data` in Docker | where runs, sweeps and files are stored |

## Security

Built for local use: there is no login. Do not expose port 8000 to the internet, since anyone
reaching it could start simulations and use the server-side API key.

## Layout

```
app/          server, agent loop, tools, run manager, runner, prompts
macrospin/    original simulation code (unchanged)
original_scripts/  original batch scripts (prepare, run_sim, avg_neel, neel_vector_generate)
web/index.html     the interface
examples/     parameter files
tests/        smoke tests
```
