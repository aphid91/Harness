"""
Demo: two astronauts and a basketball.

t = 0:  gravity off for all bodies (zero-g).  Astronaut A gives the ball an
        impulse (throw) with a lever arm so it also spins.
t = 2:  Astronaut B catches it (equal-and-opposite impulse stops it), and
        we flip gravity on for the ball just to exercise the force-change event.

We then emit GLSL and cross-check a handful of times by evaluating the
python Rodrigues/kinematics and comparing with a manual GLSL-like eval.
"""

import numpy as np
from engine import (Body, impulse, set_force, build_segments,
                    emit_scene, rodrigues, advance)

def make_body(pos, mass=1.0, inertia=0.1):
    return Body(
        pos=np.array(pos, float),
        vel=np.zeros(3),
        rot=np.eye(3),
        omega=np.zeros(3),
        mass=mass, inertia=inertia,
        force=np.zeros(3),
    )

astroA    = make_body([-2, 0, 0], mass=8.0, inertia=10.0)
astroB    = make_body([ 2, 0, 0], mass=8.0, inertia=10.0)
ball      = make_body([-1.,.8, 0], mass=0.6, inertia=0.02)

bodies = [astroA, astroB, ball]
names  = ['astroA', 'astroB', 'ball']

# Schedule.  Initial conditions apply from t = 0 onward.
# Ball at t=0: throw impulse of [2,0.5,0] => velocity [2,0.5,0]/0.6 = [3.33,0.83,0].
# At t=2 we want to stop it, so catch impulse = -mass*velocity = -[2,0.5,0].
schedule = [
    (0.0, None),                                  # anchor: t0
    (0.0, impulse(2, [2.0, -0.5, 0.0],             # Force on ball...
                     [-.050, 0.0, 0.0])),          
    (0.0, impulse(0, [-2.0, 0.5, -0.0],             # A throws the ball...
                     [0.00, .8, 0.0])),
    (.60, impulse(2, [-2.0, 0.5, 0.0],           # catch: cancel ball's momentum
                     [0., 0., 0.0])),
    (.60, impulse(1, [2.0, -0.5, 0.0],             # throw the ball...
                     [0.00, 0.30, 0.0])),
]

segs = build_segments(bodies, schedule)

print('=== segment summary ===')
for i, name in enumerate(names):
    print(f'\nbody {name}:')
    for s in segs[i]:
        print(f'  t in [{s.t_start}, {s.t_end})  '
              f'pos0={s.pos0}  vel0={s.vel0}  |w|={np.linalg.norm(s.omega0):.4f}')

# --------- self-check: evaluate in python along each segment and make sure
# it matches stepping via `advance()` from the initial conditions. ---------
print('\n=== self-check ===')

def eval_segment(s, t):
    dt = t - s.t_start
    pos = s.pos0 + s.vel0*dt + 0.5*s.accel*dt*dt
    rot = rodrigues(s.omega0, dt) @ s.rot0
    return pos, rot

def eval_body(seglist, t):
    # find segment containing t
    for s in seglist:
        if s.t_start <= t < s.t_end:
            return eval_segment(s, t)
    return eval_segment(seglist[-1], t)

# Independent "ground truth": re-run the schedule step by step and stop at t.
def ground_truth(bodies_init, schedule, t_query, body_i):
    times = sorted({t for t,_ in schedule})
    groups = {tt: [ev for (tq,ev) in schedule if tq==tt] for tt in times}
    state = [b.copy() for b in bodies_init]
    # apply events at times[0] before any propagation, matching the engine
    for ev in groups[times[0]]:
        if ev is None: continue
        kind = ev[0]
        if kind == 'impulse':
            _, i, J, r_body = ev
            b = state[i]
            r_world = b.rot @ r_body
            b.vel   += J / b.mass
            b.omega += np.cross(r_world, J) / b.inertia
        elif kind == 'force':
            _, i, F_new = ev
            state[i].force = F_new.copy()
    # integrate across events
    for k, tk in enumerate(times):
        t_next = times[k+1] if k+1 < len(times) else float('inf')
        if t_query < t_next:
            # evaluate inside [tk, t_next)
            dt = t_query - tk
            b = state[body_i]
            pos = b.pos + b.vel*dt + 0.5*(b.force/b.mass)*dt*dt
            rot = rodrigues(b.omega, dt) @ b.rot
            return pos, rot
        # else advance to t_next and apply events
        dt = t_next - tk
        state = [advance(b, dt) for b in state]
        for ev in groups[t_next]:
            if ev is None: continue
            kind = ev[0]
            if kind == 'impulse':
                _, i, J, r_body = ev
                b = state[i]
                r_world = b.rot @ r_body
                b.vel += J / b.mass
                b.omega += np.cross(r_world, J) / b.inertia
            elif kind == 'force':
                _, i, F_new = ev
                state[i].force = F_new.copy()
    # past last event
    b = state[body_i]
    dt = t_query - times[-1]
    pos = b.pos + b.vel*dt + 0.5*(b.force/b.mass)*dt*dt
    rot = rodrigues(b.omega, dt) @ b.rot
    return pos, rot

max_err = 0.0
for body_i in range(len(bodies)):
    for t in [0.0, 0.5, 1.0, 1.999, 2.001, 3.0, 5.0]:
        p1, R1 = eval_body(segs[body_i], t)
        p2, R2 = ground_truth(bodies, schedule, t, body_i)
        err = max(np.max(np.abs(p1-p2)), np.max(np.abs(R1-R2)))
        max_err = max(max_err, err)
print(f'segment eval vs ground truth: max abs error = {max_err:.2e}')
assert max_err < 1e-10, "segment builder disagrees with stepwise simulation!"

# --------- check continuity across event boundaries ---------
print('\n=== continuity checks across event boundaries ===')
eps = 1e-6
for body_i, name in enumerate(names):
    for s in segs[body_i][:-1]:
        t_b = s.t_end
        p_lo, R_lo = eval_segment(s, t_b - eps)
        # next segment
        ns = next(x for x in segs[body_i] if x.t_start == t_b)
        p_hi, R_hi = eval_segment(ns, t_b + eps)
        dp = np.linalg.norm(p_hi - p_lo)
        dR = np.max(np.abs(R_hi - R_lo))
        print(f'  {name} @ t={t_b}: |dpos|={dp:.2e}, |dR|={dR:.2e}   '
              f'(position must be continuous; velocity/omega may jump)')

# --------- emit GLSL ---------
print('\n=== generated GLSL ===')
glsl = emit_scene(bodies, schedule, names)
print(glsl)

with open('outputs/scene.glsl', 'w') as f:
    f.write(glsl)