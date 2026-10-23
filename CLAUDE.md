# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A minimal moderngl harness — a starting point for shader/visual projects. It opens a
GLFW window, renders [shader.frag](shader.frag) on a fullscreen quad via moderngl, and
overlays an imgui control panel. There is no application logic beyond that; the point
is to be the smallest useful scaffold to build on.

## Commands

```bash
# Activate venv (Python 3.13)
.venv\Scripts\activate

# Install deps (already present in .venv)
pip install -r requirements.txt

# Run
python app.py
```

No build step, linter, or test framework is configured.

## Architecture

Everything lives in [app.py](app.py):

- **Window/events**: GLFW, requesting an OpenGL 3.3 core profile. vsync on via
  `swap_interval(1)`.
- **Rendering**: a moderngl context draws a 4-vertex `TRIANGLE_STRIP` covering clip
  space (`vbo`), with the vertex shader inlined as `VERT_SHADER` and the fragment
  shader read from `shader.frag` at reload time.
- **UI**: `imgui_bundle` with the `GlfwRenderer` backend. The imgui frame is built
  mid-loop (`new_frame` → widgets → `render`), but `renderer.render(...)` is called
  *after* the scene draw so the UI composites on top.
- **Docking**: enabled via `ConfigFlags_.docking_enable` plus a
  `dock_space_over_viewport()` call right after `new_frame()`. The
  `passthru_central_node` flag keeps the central node transparent so the shader shows
  through where nothing is docked — without it the dockspace paints over the scene.
  The flag alone does nothing; the dockspace call is what makes panels dockable.
- **Shader reload**: `compile_shader()` returns `(prog, vao, error)` rather than
  raising, so a GLSL syntax error leaves the previous working program on screen and
  shows the compiler message in the UI. Triggered by `R` or the Reload button.
- **Uniforms**: `set_uniform()` checks `name in prog` before assigning. GLSL compilers
  drop unused uniforms, so this lets the harness offer `resolution`, `mouse`, and
  `time` without requiring every shader to declare them.
- **Input gating**: keyboard shortcuts check `io.want_capture_keyboard` so typing in an
  imgui field doesn't fire them. Do the same (`io.want_capture_mouse`) for any mouse
  shortcuts added later.

## Conventions

- Time is accumulated manually (`anim_time += wall_dt * time_speed`) rather than read
  from `glfw.get_time()`, so pause and speed scaling work. Pass `anim_time` to shaders,
  not wall time.
- `mouse` is normalised to 0..1 with y flipped to point up, matching GLSL convention.
- `imgui.ini` (saved window layout) is generated at runtime and gitignored.
