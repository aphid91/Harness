void astroA(float t, out vec3 pos, out mat3 rot) {
    if (t >= 0.0 && t < 0.6) {
        float dt = t - 0.0;
        pos = vec3(-2.0, 0.0, 0.0) + vec3(-0.25, 0.0625, 0.0) * dt + 0.5 * vec3(0.0, 0.0, 0.0) * dt * dt;
        float theta = 0.16 * dt;
        float c = cos(theta);
        float s_ = sin(theta);
        vec3 u = vec3(0.0, 0.0, 1.0);
        mat3 K = mat3(vec3(0.0, u.z, -u.y), vec3(-u.z, 0.0, u.x), vec3(u.y, -u.x, 0.0));
        mat3 Rdelta = mat3(1.0) + s_ * K + (1.0 - c) * K * K;
        rot = Rdelta * mat3(vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(0.0, 0.0, 1.0));
    }
    else if (t >= 0.6) {
        float dt = t - 0.6;
        pos = vec3(-2.15, 0.0375, 0.0) + vec3(-0.25, 0.0625, 0.0) * dt + 0.5 * vec3(0.0, 0.0, 0.0) * dt * dt;
        float theta = 0.16 * dt;
        float c = cos(theta);
        float s_ = sin(theta);
        vec3 u = vec3(0.0, 0.0, 1.0);
        mat3 K = mat3(vec3(0.0, u.z, -u.y), vec3(-u.z, 0.0, u.x), vec3(u.y, -u.x, 0.0));
        mat3 Rdelta = mat3(1.0) + s_ * K + (1.0 - c) * K * K;
        rot = Rdelta * mat3(vec3(0.99539554, 0.095852612, 0.0), vec3(-0.095852612, 0.99539554, 0.0), vec3(0.0, 0.0, 1.0));
    }
}

void astroB(float t, out vec3 pos, out mat3 rot) {
    if (t >= 0.0 && t < 0.6) {
        float dt = t - 0.0;
        pos = vec3(2.0, 0.0, 0.0) + vec3(0.0, 0.0, 0.0) * dt + 0.5 * vec3(0.0, 0.0, 0.0) * dt * dt;
        rot = mat3(vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(0.0, 0.0, 1.0));
    }
    else if (t >= 0.6) {
        float dt = t - 0.6;
        pos = vec3(2.0, 0.0, 0.0) + vec3(0.25, -0.0625, 0.0) * dt + 0.5 * vec3(0.0, 0.0, 0.0) * dt * dt;
        float theta = 0.06 * dt;
        float c = cos(theta);
        float s_ = sin(theta);
        vec3 u = vec3(0.0, 0.0, -1.0);
        mat3 K = mat3(vec3(0.0, u.z, -u.y), vec3(-u.z, 0.0, u.x), vec3(u.y, -u.x, 0.0));
        mat3 Rdelta = mat3(1.0) + s_ * K + (1.0 - c) * K * K;
        rot = Rdelta * mat3(vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(0.0, 0.0, 1.0));
    }
}

void ball(float t, out vec3 pos, out mat3 rot) {
    if (t >= 0.0 && t < 0.6) {
        float dt = t - 0.0;
        pos = vec3(-1.0, 0.8, 0.0) + vec3(3.3333333, -0.83333333, 0.0) * dt + 0.5 * vec3(0.0, 0.0, 0.0) * dt * dt;
        float theta = 1.25 * dt;
        float c = cos(theta);
        float s_ = sin(theta);
        vec3 u = vec3(0.0, 0.0, 1.0);
        mat3 K = mat3(vec3(0.0, u.z, -u.y), vec3(-u.z, 0.0, u.x), vec3(u.y, -u.x, 0.0));
        mat3 Rdelta = mat3(1.0) + s_ * K + (1.0 - c) * K * K;
        rot = Rdelta * mat3(vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(0.0, 0.0, 1.0));
    }
    else if (t >= 0.6) {
        float dt = t - 0.6;
        pos = vec3(1.0, 0.3, 0.0) + vec3(0.0, 0.0, 0.0) * dt + 0.5 * vec3(0.0, 0.0, 0.0) * dt * dt;
        float theta = 0.64933576 * dt;
        float c = cos(theta);
        float s_ = sin(theta);
        vec3 u = vec3(0.0, 0.0, 1.0);
        mat3 K = mat3(vec3(0.0, u.z, -u.y), vec3(-u.z, 0.0, u.x), vec3(u.y, -u.x, 0.0));
        mat3 Rdelta = mat3(1.0) + s_ * K + (1.0 - c) * K * K;
        rot = Rdelta * mat3(vec3(0.73168887, 0.68163876, 0.0), vec3(-0.68163876, 0.73168887, 0.0), vec3(0.0, 0.0, 1.0));
    }
}
