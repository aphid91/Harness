#version 330

in vec2 v_texcoord;
out vec4 fragColor;

uniform vec2 resolution;
uniform vec2 mouse;
uniform float time;

void main() {
    // Aspect-corrected coords, centred, roughly -1..1 on the short axis.
    vec2 uv = (gl_FragCoord.xy * 2.0 - resolution) / min(resolution.x, resolution.y);

    float d = length(uv - (mouse * 2.0 - 1.0));
    vec3 col = 0.5 + 0.5 * cos(time + d * 4.0 + vec3(0.0, 2.0, 4.0));

    fragColor = vec4(col, 1.0);
}
