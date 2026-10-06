Sublattice Model:

This model treats two interacting magnetic sublattices (m1 and m2), representing distinct spin populations, such as in antiferromagnets or exchange-coupled ferromagnets.

- Each sublattice follows the LLG equation with its own magnetization dynamics.
- Coupling between sublattices affects their time evolution.
- Numerical methods (Heun & RK4) track their interaction over time.

Main Components:

1) main.py – Orchestrates the entire simulation.
2) conf.py – Defines physical parameters for two sublattices.
3) current.py – Implements time-dependent effects for external fields, currents, and anisotropies acting on each sublattice separately.
4) solver.py – Computes sublattice magnetization dynamics:
   -m1 and m2 evolve separately but are coupled via exchange interactions.
   -Uses Heun’s method and Runge-Kutta (RK4) for integration.
5) run.py – Manages time evolution for both sublattices and stores results.
6) output.py – Saves and visualizes the evolution of both sublattices.

Key Highlights:

Sublattice Model: Tracks two distinct spin sublattices (m1, m2).
✅ Coupled Magnetization Dynamics: Interactions affect each other’s evolution.
✅ Time-Dependent External Influences: Includes current, anisotropy, and external fields for each sublattice.
✅ Numerical Stability: Uses Heun’s method & RK4 for accuracy.
✅ Data Output & Visualization: Saves .dat files and generates magnetization plots.
