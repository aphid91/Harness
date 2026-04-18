"""Minimal moderngl + imgui harness using glfw."""

import glfw
import moderngl
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

WINDOW_W, WINDOW_H = 1280, 720


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
    glfw.swap_interval(1)  # vsync

    # --- moderngl context from the active GL context ---
    ctx = moderngl.create_context()
    ctx.enable(moderngl.BLEND)

    # --- imgui setup ---
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.ConfigFlags_.docking_enable
    renderer = GlfwRenderer(window)

    # -- demo state --
    clear_color = [0.12, 0.12, 0.14]
    show_demo = False

    while not glfw.window_should_close(window):
        glfw.poll_events()
        renderer.process_inputs()
        imgui.new_frame()

        # ---- UI ----
        imgui.begin("Logar")
        _, clear_color = imgui.color_edit3("bg colour", clear_color)
        _, show_demo = imgui.checkbox("Show demo window", show_demo)
        imgui.text(f"FPS: {io.framerate:.0f}")
        imgui.end()

        if show_demo:
            imgui.show_demo_window()

        # ---- Render ----
        imgui.render()
        ctx.clear(*clear_color)
        renderer.render(imgui.get_draw_data())

        glfw.swap_buffers(window)

    # cleanup
    renderer.shutdown()
    imgui.destroy_context()
    glfw.terminate()


if __name__ == "__main__":
    main()
