"""Logar physics animation tuning tool.

Renders a user-provided fragment shader (scene.frag) on a fullscreen quad with
physics GLSL injected from the engine. Provides imgui controls for tweaking
the event schedule and shader parameters.

Controls:
  R         — reset time to 0 and recompile shader
  Refresh   — recompile shader (keeps current time)
"""

import numpy as np
import glfw
import moderngl
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

from engine import Body, impulse, set_force, emit_scene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOW_W, WINDOW_H = 1280, 720
FRAG_PATH = "scene.frag"
EMISSION_MARKER = "//PHYSICS EMISSION HERE"

VERT_SHADER = """
#version 330
in vec2 in_pos;

out VertexData
{
    vec2 v_texcoord;
} outData;

void main() {
    outData.v_texcoord = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Default scene (matches test_demo.py)
# ---------------------------------------------------------------------------

def _body(pos, mass=1.0, inertia=0.1):
    return Body(
        pos=np.array(pos, float), vel=np.zeros(3), rot=np.eye(3),
        omega=np.zeros(3), mass=mass, inertia=inertia, force=np.zeros(3),
    )


def make_default_scene():
    bodies = [
        _body([-2, 0, 0], mass=8.0, inertia=10.0),
        _body([ 2, 0, 0], mass=8.0, inertia=10.0),
        _body([-1, 0.8, 0], mass=0.6, inertia=0.02),
    ]
    names = ["astroA", "astroB", "ball"]
    schedule = [
        [0.0, None],
        [0.0, impulse(2, [2.0, -0.5, 0.0], [-0.05, 0.0, 0.0])],
        [0.0, impulse(0, [-2.0, 0.5, 0.0], [0.0, 0.8, 0.0])],
        [0.6, impulse(2, [-2.0, 0.5, 0.0], [0.0, 0.0, 0.0])],
        [0.6, impulse(1, [2.0, -0.5, 0.0], [0.0, 0.3, 0.0])],
    ]
    return bodies, names, schedule

# ---------------------------------------------------------------------------
# Shader compilation
# ---------------------------------------------------------------------------

def compile_shader(ctx, vbo, bodies, schedule, names):
    """Read scene.frag, inject physics GLSL, compile. Returns (prog, vao, err)."""
    try:
        with open(FRAG_PATH) as f:
            frag_src = f.read()
    except FileNotFoundError:
        return None, None, f"{FRAG_PATH} not found"

    # Build sorted schedule as tuples for the engine
    sched_sorted = sorted(
        [(entry[0], entry[1]) for entry in schedule],
        key=lambda e: e[0],
    )

    try:
        physics_glsl = emit_scene(bodies, sched_sorted, names)
    except Exception as e:
        return None, None, f"Physics emission error: {e}"

    if EMISSION_MARKER not in frag_src:
        return None, None, f"Marker '{EMISSION_MARKER}' not found in {FRAG_PATH}"

    frag_src = frag_src.replace(EMISSION_MARKER, physics_glsl)

    try:
        prog = ctx.program(vertex_shader=VERT_SHADER, fragment_shader=frag_src)
    except Exception as e:
        return None, None, f"Shader compile error:\n{e}"

    vao = ctx.vertex_array(prog, [(vbo, "2f", "in_pos")])
    return prog, vao, None


def set_uniform(prog, name, value):
    if name in prog:
        prog[name].value = value

# ---------------------------------------------------------------------------
# Schedule UI helpers
# ---------------------------------------------------------------------------

def _event_label(ev, names):
    """Short display string for a schedule event."""
    if ev is None:
        return "anchor"
    kind = ev[0]
    body_i = ev[1]
    bname = names[body_i] if body_i < len(names) else f"body{body_i}"
    if kind == "impulse":
        J = ev[2]
        return f"impulse  {bname}  J=[{J[0]:.2f},{J[1]:.2f},{J[2]:.2f}]"
    elif kind == "force":
        F = ev[2]
        return f"force  {bname}  F=[{F[0]:.2f},{F[1]:.2f},{F[2]:.2f}]"
    return "unknown"


def _rebuild_event(entry, kind, body_i, vecs):
    """Rebuild the event tuple in-place inside the schedule entry list."""
    if kind == "impulse":
        entry[1] = ("impulse", body_i, vecs[0].copy(), vecs[1].copy())
    elif kind == "force":
        entry[1] = ("force", body_i, vecs[0].copy())

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not glfw.init():
        raise RuntimeError("Failed to initialise GLFW")

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

    window = glfw.create_window(WINDOW_W, WINDOW_H, "Logar", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Failed to create GLFW window")

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    # --- moderngl ---
    ctx = moderngl.create_context()
    ctx.enable(moderngl.BLEND)

    # Fullscreen quad
    vbo = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))

    # --- imgui ---
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.ConfigFlags_.docking_enable
    renderer = GlfwRenderer(window)

    # --- scene state ---
    bodies, names, schedule = make_default_scene()
    t_reset = glfw.get_time()
    dials = [0.0] * 16
    program = None
    vao = None
    compile_error = "Press R or Refresh to compile"
    r_was_pressed = False
    delete_index = -1  # deferred deletion

    # --- main loop ---
    while not glfw.window_should_close(window):
        glfw.poll_events()
        renderer.process_inputs()
        imgui.new_frame()

        # Time and mouse
        t_now = glfw.get_time() - t_reset
        w, h = glfw.get_framebuffer_size(window)
        mx, my = glfw.get_cursor_pos(window)
        mouse_norm = (mx / max(w, 1), 1.0 - my / max(h, 1))

        # ================================================================
        # Controls window
        # ================================================================
        imgui.begin("Controls")

        if imgui.button("Refresh Animation"):
            program, vao, compile_error = compile_shader(
                ctx, vbo, bodies, schedule, names
            )

        imgui.same_line()
        if imgui.button("Reset Time"):
            t_reset = glfw.get_time()

        imgui.text(f"Time: {t_now:.2f}    FPS: {io.framerate:.0f}")

        if compile_error:
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(1, 0.3, 0.3, 1))
            imgui.text_wrapped(compile_error)
            imgui.pop_style_color()

        # Dial sliders
        dial_names = ["Dials 1", "Dials 2", "Dials 3", "Dials 4"]
        for bank in range(4):
            if imgui.collapsing_header(dial_names[bank]):
                for j in range(4):
                    idx = bank * 4 + j
                    changed, val = imgui.slider_float(
                        f"##{bank}_{j}", dials[idx], -10.0, 10.0
                    )
                    if changed:
                        dials[idx] = val

        imgui.end()

        # ================================================================
        # Schedule window
        # ================================================================
        imgui.begin("Schedule")

        # Menu bar
        if imgui.begin_menu_bar():
            imgui.end_menu_bar()

        # Use a child menu bar via buttons at top
        if imgui.button("Add Impulse"):
            schedule.append([0.0, impulse(0, [0, 0, 0], [0, 0, 0])])
        imgui.same_line()
        if imgui.button("Add Force"):
            schedule.append([0.0, set_force(0, [0, 0, 0])])

        imgui.separator()

        # Build display list (skip None anchors), sorted by time
        display = []
        for i, entry in enumerate(schedule):
            if entry[1] is not None:
                display.append((i, entry))
        display.sort(key=lambda x: x[1][0])

        delete_index = -1
        for di, (sched_idx, entry) in enumerate(display):
            ev = entry[1]
            label = f"t={entry[0]:.3f}  {_event_label(ev, names)}"
            imgui.push_id(di)

            # Selectable row — click opens popup
            if imgui.selectable(label, False)[0]:
                imgui.open_popup("event_edit")

            # Context menu popup
            if imgui.begin_popup("event_edit"):
                # Delete
                if imgui.button("Delete"):
                    delete_index = sched_idx
                    imgui.close_current_popup()

                imgui.separator()

                # Time
                changed, new_t = imgui.drag_float("Time", entry[0], 0.01, 0.0, 100.0)
                if changed:
                    entry[0] = new_t

                # Target body
                body_i = ev[1]
                if imgui.begin_combo("Body", names[body_i] if body_i < len(names) else f"body{body_i}"):
                    for bi, bname in enumerate(names):
                        selected = (bi == body_i)
                        if imgui.selectable(bname, selected)[0]:
                            body_i = bi
                    imgui.end_combo()

                kind = ev[0]
                if kind == "impulse":
                    J = np.array(ev[2], dtype=float)
                    r = np.array(ev[3], dtype=float)

                    ch, vals = imgui.drag_float3("J (impulse)", list(J), 0.01)
                    if ch:
                        J = np.array(vals, dtype=float)

                    ch2, vals2 = imgui.drag_float3("r (lever arm)", list(r), 0.01)
                    if ch2:
                        r = np.array(vals2, dtype=float)

                    _rebuild_event(entry, "impulse", body_i, [J, r])

                elif kind == "force":
                    F = np.array(ev[2], dtype=float)

                    ch, vals = imgui.drag_float3("F (force)", list(F), 0.01)
                    if ch:
                        F = np.array(vals, dtype=float)

                    _rebuild_event(entry, "force", body_i, [F])

                imgui.end_popup()

            imgui.pop_id()

        # Deferred delete
        if delete_index >= 0:
            del schedule[delete_index]

        imgui.end()

        # ================================================================
        # R key — reset time + recompile
        # ================================================================
        r_pressed = glfw.get_key(window, glfw.KEY_R) == glfw.PRESS
        if r_pressed and not r_was_pressed and not io.want_capture_keyboard:
            t_reset = glfw.get_time()
            program, vao, compile_error = compile_shader(
                ctx, vbo, bodies, schedule, names
            )
        r_was_pressed = r_pressed

        # ================================================================
        # Render
        # ================================================================
        imgui.render()
        ctx.clear(0.12, 0.12, 0.14)

        if program is not None and vao is not None:
            set_uniform(program, "resolution", (float(w), float(h)))
            set_uniform(program, "mouse", (float(mouse_norm[0]), float(mouse_norm[1])))
            set_uniform(program, "time", float(t_now))
            set_uniform(program, "dials",  tuple(dials[0:4]))
            set_uniform(program, "dials2", tuple(dials[4:8]))
            set_uniform(program, "dials3", tuple(dials[8:12]))
            set_uniform(program, "dials4", tuple(dials[12:16]))
            vao.render(moderngl.TRIANGLE_STRIP)

        renderer.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    # cleanup
    renderer.shutdown()
    imgui.destroy_context()
    glfw.terminate()


if __name__ == "__main__":
    main()
