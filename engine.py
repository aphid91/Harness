"""
Analytic physics engine -> GLSL.

Between events each body has:
  - constant linear acceleration a = F/m
  - constant angular velocity omega  (scalar moment of inertia, no torque)

So on segment [t_k, t_{k+1}]:
  p(t) = p_k + v_k*(t-t_k) + 0.5*a_k*(t-t_k)^2
  R(t) = Rodrigues(omega_k, t-t_k) @ R_k

Events:
  ('impulse', body_i, J_world, r_body)    # r is in the body frame at event time
  ('force',   body_i, F_world_new)

We precompute the state of every body at every event boundary in Python,
then emit one GLSL function per body that is a big if/else over t.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import numpy as np


# ---------- data ----------

@dataclass
class Body:
    pos:       np.ndarray            # (3,)
    vel:       np.ndarray            # (3,)
    rot:       np.ndarray            # (3,3), orthonormal
    omega:     np.ndarray            # (3,) world-frame angular velocity
    mass:      float
    inertia:   float                 # scalar moment of inertia
    force:     np.ndarray            # (3,) constant world-frame force

    def copy(self):
        return Body(self.pos.copy(), self.vel.copy(),
                    self.rot.copy(), self.omega.copy(),
                    self.mass, self.inertia, self.force.copy())


# Event constructors (kept as tuples so schedules are easy to write)
def impulse(body_i, J, r_body):
    return ('impulse', body_i, np.asarray(J, float), np.asarray(r_body, float))

def set_force(body_i, F):
    return ('force', body_i, np.asarray(F, float))


# ---------- math ----------

def rodrigues(omega: np.ndarray, dt: float) -> np.ndarray:
    """Rotation matrix for rotating at angular velocity omega for time dt."""
    theta = np.linalg.norm(omega) * dt
    if theta < 1e-12:
        return np.eye(3)
    u = omega / np.linalg.norm(omega)
    K = np.array([[    0, -u[2],  u[1]],
                  [ u[2],     0, -u[0]],
                  [-u[1],  u[0],    0]])
    return np.eye(3) + np.sin(theta)*K + (1 - np.cos(theta)) * (K @ K)


def advance(body: Body, dt: float) -> Body:
    """Propagate a body forward by dt under its current constant force and omega."""
    a = body.force / body.mass
    out = body.copy()
    out.pos = body.pos + body.vel * dt + 0.5 * a * dt * dt
    out.vel = body.vel + a * dt
    out.rot = rodrigues(body.omega, dt) @ body.rot
    # omega unchanged (no torque between events)
    return out


# ---------- simulate the discrete schedule ----------

@dataclass
class Segment:
    """State of one body on [t_start, t_end).  t_end = +inf on the last."""
    t_start: float
    t_end:   float
    pos0:    np.ndarray
    vel0:    np.ndarray
    rot0:    np.ndarray
    omega0:  np.ndarray
    accel:   np.ndarray      # F/m, constant on this segment


def build_segments(bodies_init: List[Body],
                   schedule: List[Tuple]) -> List[List[Segment]]:
    """
    schedule is a list of (t, event) pairs sorted by t.
    Returns segments[body_i] = list of Segment.
    The first entry in schedule should be the t=-inf-ish "initial conditions"
    marker, but we actually just use the earliest t as t_start for segment 0.

    Convention: schedule entries are (t, event_or_None).  A None event just
    establishes a time anchor (useful as t0).  Multiple events may share a t;
    we apply them in list order, all instantaneously.
    """
    # group events by time, preserving order
    times = []
    events_at = []
    for t, ev in schedule:
        if times and times[-1] == t:
            events_at[-1].append(ev)
        else:
            times.append(t)
            events_at.append([ev])

    n = len(bodies_init)
    # current state of each body, valid "just after the last processed event"
    state = [b.copy() for b in bodies_init]
    segments: List[List[Segment]] = [[] for _ in range(n)]

    # Apply any events scheduled at the very first time BEFORE emitting
    # segment 0, so that "initial conditions" events (gravity-on, starting
    # impulse, etc.) take effect from t=times[0] onward.
    for ev in events_at[0]:
        if ev is None:
            continue
        kind = ev[0]
        if kind == 'impulse':
            _, i, J, r_body = ev
            b = state[i]
            r_world = b.rot @ r_body
            b.vel   = b.vel + J / b.mass
            b.omega = b.omega + np.cross(r_world, J) / b.inertia
        elif kind == 'force':
            _, i, F_new = ev
            state[i].force = F_new.copy()
        else:
            raise ValueError(f'unknown event {kind}')

    for k in range(len(times)):
        t_k = times[k]
        t_next = times[k+1] if k+1 < len(times) else float('inf')

        # emit a segment for each body covering [t_k, t_next)
        for i, b in enumerate(state):
            segments[i].append(Segment(
                t_start=t_k, t_end=t_next,
                pos0=b.pos.copy(), vel0=b.vel.copy(),
                rot0=b.rot.copy(), omega0=b.omega.copy(),
                accel=b.force / b.mass,
            ))

        # advance every body to t_next (end of this segment)
        if t_next != float('inf'):
            dt = t_next - t_k
            state = [advance(b, dt) for b in state]
            # apply all events scheduled at t_next
            for ev in events_at[k+1]:
                if ev is None:
                    continue
                kind = ev[0]
                if kind == 'impulse':
                    _, i, J, r_body = ev
                    b = state[i]
                    r_world = b.rot @ r_body
                    b.vel   = b.vel + J / b.mass
                    b.omega = b.omega + np.cross(r_world, J) / b.inertia
                elif kind == 'force':
                    _, i, F_new = ev
                    state[i].force = F_new.copy()
                else:
                    raise ValueError(f'unknown event {kind}')

    return segments


# ---------- GLSL emission ----------

def _f(x: float) -> str:
    """Format a float as a GLSL literal."""
    if not np.isfinite(x):
        raise ValueError("non-finite constant in emission")
    s = f'{x:.8g}'
    if '.' not in s and 'e' not in s and 'E' not in s:
        s += '.0'
    return s

def _vec3(v: np.ndarray) -> str:
    return f'vec3({_f(v[0])}, {_f(v[1])}, {_f(v[2])})'

def _mat3(M: np.ndarray) -> str:
    # GLSL mat3 is column-major: mat3(col0, col1, col2)
    c0, c1, c2 = M[:,0], M[:,1], M[:,2]
    return f'mat3({_vec3(c0)}, {_vec3(c1)}, {_vec3(c2)})'


def emit_body_glsl(segments: List[Segment], func_name: str = 'body') -> str:
    """
    Produces the BODY of a GLSL function with signature:
        void <func_name>(float t, out vec3 pos, out mat3 rot) { ... }
    i.e. the returned string is what goes between the braces.
    """
    lines = []
    # precompute per-segment: Rodrigues axis (unit) and |omega|, or mark zero.
    # We compute R(t) in GLSL using the same Rodrigues formula.

    for idx, s in enumerate(segments):
        is_first = (idx == 0)
        is_last  = (idx == len(segments) - 1)
        kw = 'if' if is_first else 'else if'

        # branch predicate
        if is_last:
            cond = 't >= ' + _f(s.t_start)
        else:
            cond = f't >= {_f(s.t_start)} && t < {_f(s.t_end)}'

        lines.append(f'    {kw} ({cond}) {{')
        lines.append(f'        float dt = t - {_f(s.t_start)};')

        # position: p0 + v0*dt + 0.5*a*dt^2
        lines.append(f'        pos = {_vec3(s.pos0)} '
                     f'+ {_vec3(s.vel0)} * dt '
                     f'+ 0.5 * {_vec3(s.accel)} * dt * dt;')

        # rotation
        w = s.omega0
        wmag = float(np.linalg.norm(w))
        R0 = s.rot0
        if wmag < 1e-12:
            # constant rotation on this segment
            lines.append(f'        rot = {_mat3(R0)};')
        else:
            u = w / wmag
            lines.append(f'        float theta = {_f(wmag)} * dt;')
            lines.append(f'        float c = cos(theta);')
            lines.append(f'        float s_ = sin(theta);')
            lines.append(f'        vec3 u = {_vec3(u)};')
            # K = [[0,-uz,uy],[uz,0,-ux],[-uy,ux,0]]
            # Rodr = I + s*K + (1-c)*K*K
            # Build Rodr as mat3 explicitly (column-major) then rot = Rodr * R0
            lines.append('        mat3 K = mat3('
                         'vec3(0.0, u.z, -u.y), '        # col 0
                         'vec3(-u.z, 0.0, u.x), '        # col 1
                         'vec3(u.y, -u.x, 0.0));')       # col 2
            lines.append('        mat3 Rdelta = mat3(1.0) + s_ * K + (1.0 - c) * K * K;')
            lines.append(f'        rot = Rdelta * {_mat3(R0)};')

        lines.append('    }')

    return '\n'.join(lines)


def emit_scene(bodies_init: List[Body],
               schedule: List[Tuple],
               names: List[str]) -> str:
    """
    Produce one GLSL function per body, concatenated.
    `names` is a list of base function names (e.g. ['astronautA','basketball']).
    """
    segs = build_segments(bodies_init, schedule)
    out = []
    for i, (name, seglist) in enumerate(zip(names, segs)):
        body_src = emit_body_glsl(seglist, name)
        out.append(
            f'void {name}(float t, out vec3 pos, out mat3 rot) {{\n'
            f'{body_src}\n'
            f'}}\n'
        )
    return '\n'.join(out)