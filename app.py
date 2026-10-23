"""Minimal moderngl harness: glfw window + fullscreen-quad fragment shader + imgui.

A starting point for shader/visual projects. The fragment shader lives in
shader.frag and is reloaded when you press R or click Reload.

Uniforms available to the fragment shader (all optional):
  vec2  resolution   framebuffer size in pixels
  vec2  mouse        cursor position, normalised 0..1, y up
  float time         seconds since start (pausable, scalable)

Controls:
  R   reload the fragment shader
  G   toggle pause
"""

import numpy as np
import glfw
import moderngl
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

WINDOW_W, WINDOW_H = 1280, 720
WINDOW_TITLE = "moderngl harness"
FRAG_PATH = "shader.frag"

VERT_SHADER = """
#version 330
in vec2 in_pos;
out vec2 v_texcoord;

void main() {
    v_texcoord = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""


def compile_shader(ctx, vbo):
    """Load FRAG_PATH and build a program + vao. Returns (prog, vao, error)."""
    try:
        with open(FRAG_PATH) as f:
            frag_src = f.read()
    except FileNotFoundError:
        return None, None, f"{FRAG_PATH} not found"

    try:
        prog = ctx.program(vertex_shader=VERT_SHADER, fragment_shader=frag_src)
    except Exception as e:
        return None, None, f"Shader compile error:\n{e}"

    vao = ctx.vertex_array(prog, [(vbo, "2f", "in_pos")])
    return prog, vao, None


def set_uniform(prog, name, value):
    """Set a uniform only if the shader actually declares (and uses) it."""
    if name in prog:
        prog[name].value = value


def main():
    if not glfw.init():
        raise RuntimeError("Failed to initialise GLFW")

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

    window = glfw.create_window(WINDOW_W, WINDOW_H, WINDOW_TITLE, None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Failed to create GLFW window")

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    # --- moderngl ---
    ctx = moderngl.create_context()
    ctx.enable(moderngl.BLEND)

    # Fullscreen quad as a triangle strip in clip space.
    vbo = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4"))

    # --- imgui ---
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.ConfigFlags_.docking_enable
    renderer = GlfwRenderer(window)

    # --- state ---
    program, vao, compile_error = compile_shader(ctx, vbo)
    time_speed = 1.0
    paused = False
    anim_time = 0.0
    last_wall = glfw.get_time()
    r_was_pressed = False
    g_was_pressed = False

    while not glfw.window_should_close(window):
        glfw.poll_events()
        renderer.process_inputs()
        imgui.new_frame()

        # Dockspace over the whole viewport so panels can be docked to any edge.
        # passthru_central_node leaves the centre transparent, so the shader
        # stays visible wherever no window is docked.
        imgui.dock_space_over_viewport(
            0, imgui.get_main_viewport(),
            imgui.DockNodeFlags_.passthru_central_node,
        )

        wall_now = glfw.get_time()
        wall_dt = wall_now - last_wall
        last_wall = wall_now
        if not paused:
            anim_time += wall_dt * time_speed

        w, h = glfw.get_framebuffer_size(window)
        mx, my = glfw.get_cursor_pos(window)
        mouse_norm = (mx / max(w, 1), 1.0 - my / max(h, 1))

        # --- UI ---
        imgui.begin("Controls")
        imgui.text(f"Time: {anim_time:.2f}    FPS: {io.framerate:.0f}")

        _, time_speed = imgui.slider_float("Speed", time_speed, -5.0, 5.0)

        if imgui.button("Reload Shader (R)"):
            program, vao, compile_error = compile_shader(ctx, vbo)
        imgui.same_line()
        if imgui.button("Reset Time"):
            anim_time = 0.0
        imgui.same_line()
        if imgui.button("PAUSED (G)" if paused else "Playing (G)"):
            paused = not paused

        if compile_error:
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(1, 0.3, 0.3, 1))
            imgui.text_wrapped(compile_error)
            imgui.pop_style_color()

        imgui.end()

        # --- keys (ignored while imgui has keyboard focus) ---
        r_pressed = glfw.get_key(window, glfw.KEY_R) == glfw.PRESS
        if r_pressed and not r_was_pressed and not io.want_capture_keyboard:
            program, vao, compile_error = compile_shader(ctx, vbo)
        r_was_pressed = r_pressed

        g_pressed = glfw.get_key(window, glfw.KEY_G) == glfw.PRESS
        if g_pressed and not g_was_pressed and not io.want_capture_keyboard:
            paused = not paused
        g_was_pressed = g_pressed

        # --- render ---
        imgui.render()
        ctx.clear(0.12, 0.12, 0.14)

        if program is not None and vao is not None:
            set_uniform(program, "resolution", (float(w), float(h)))
            set_uniform(program, "mouse", (float(mouse_norm[0]), float(mouse_norm[1])))
            set_uniform(program, "time", float(anim_time))
            vao.render(moderngl.TRIANGLE_STRIP)

        renderer.render(imgui.get_draw_data())
        glfw.swap_buffers(window)

    renderer.shutdown()
    imgui.destroy_context()
    glfw.terminate()


if __name__ == "__main__":
    main()
