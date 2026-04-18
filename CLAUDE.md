# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Logar is an analytic physics engine that precomputes rigid-body motion in Python and emits GLSL shader functions for real-time playback. Instead of running physics each frame on the GPU, it bakes piecewise-analytic trajectories (position via constant-acceleration kinematics, rotation via Rodrigues formula) into GLSL `if/else` chains over time segments.

## Commands

```bash
# Activate venv (Python 3.13)
.venv\Scripts\activate

# Run the demo scene (outputs GLSL to outputs/scene.glsl and prints self-check results)
python test_demo.py
```

There is no build step, linter, or test framework configured. `test_demo.py` serves as both demo and validation — it asserts segment evaluation matches stepwise ground-truth simulation (`max abs error < 1e-10`) and prints continuity checks at event boundaries.

## Architecture

**Single-file engine** — all physics and code generation live in [engine.py](engine.py).

The pipeline has three stages:

1. **Scene definition**: Create `Body` dataclasses (pos, vel, rot, omega, mass, inertia, force) and a time-sorted `schedule` of `(t, event)` tuples. Events are either `impulse(body_i, J, r_body)` (instantaneous momentum change with angular coupling via lever arm) or `set_force(body_i, F)` (change the constant force on a body).

2. **Segment building** (`build_segments`): Walks the schedule chronologically, advancing bodies between events with `advance()` (constant-acceleration position + Rodrigues rotation). Produces `segments[body_i]` — a list of `Segment` objects, each capturing the initial state and acceleration for one time interval.

3. **GLSL emission** (`emit_scene` / `emit_body_glsl`): Converts each body's segment list into a GLSL function `void name(float t, out vec3 pos, out mat3 rot)` containing a branching chain over time. Position uses `p0 + v0*dt + 0.5*a*dt²`; rotation reconstructs the Rodrigues matrix in-shader when omega is nonzero, or emits a constant `mat3` when the body isn't spinning.

Key physics conventions:
- Between events: constant linear acceleration (`F/m`), constant angular velocity (no torque)
- Impulses apply to both linear velocity (`J/m`) and angular velocity (`cross(r_world, J) / inertia`) where `r_body` is in body frame at event time
- GLSL `mat3` is column-major; `_mat3()` handles the transpose
- All rotation math uses world-frame angular velocity and the Rodrigues rotation formula

## Output

Generated GLSL goes to [outputs/](outputs/). Each body becomes a standalone function suitable for pasting into a fragment shader — the caller provides `t` (animation time) and gets back `pos` and `rot`.
