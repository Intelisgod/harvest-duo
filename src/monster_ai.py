"""AI behaviours for the biome monsters and the deep bosses (Chat 1).

Registered into ``monsters.BEHAVIORS``; entities.Monster calls
``fn(mon, dt, players, area, target, ux, uy, dist) -> (ux, uy) | None`` every
frame and then moves the monster ``mon.speed`` px/s along the returned
direction. State lives on the monster (``mon.ai`` dict), projectiles in
``mon.shots`` (drawn by monster_shapes), and one-shot effects the game should
play (SFX / particles / shake) are queued in ``mon.fx`` as tuples that
systems/combat_system.py drains each frame:

  ("roar", x, y)            boss roar / phase change
  ("fire", x, y)            a projectile was launched
  ("burst", x, y, color)    a projectile popped
  ("blink", x, y, color)    teleport puff
  ("charge", x, y)          a charge/lunge started
  ("slam", x, y, radius)    ground slam impact
  ("ember", x, y)           a little trail ember

No drawing here (see monster_shapes.py); only distance maths.
"""
import math
import random

from . import monsters as M
from .settings import TILE


# ---------------------------------------------------------------- helpers
def _st(mon, **init):
    st = mon.__dict__.get("ai")
    if st is None:
        st = dict(init)
        st.setdefault("base", mon.speed)
        mon.ai = st
    return st


def _fx(mon, *ev):
    q = mon.__dict__.get("fx")
    if q is None:
        q = mon.fx = []
    if len(q) < 24:
        q.append(ev)


def _shots(mon):
    s = mon.__dict__.get("shots")
    if s is None:
        s = mon.shots = []
    return s


def _norm(x, y):
    n = math.hypot(x, y) or 1.0
    return x / n, y / n


def shoot(mon, x, y, vx, vy, dmg, kind="fire", r=6, life=2.4):
    """Launch a projectile owned by ``mon`` (updated by update_shots)."""
    _shots(mon).append({"x": x, "y": y, "vx": vx, "vy": vy, "dmg": dmg,
                        "kind": kind, "r": r, "life": life, "t": 0.0})


SHOT_COLOR = {"fire": (255, 150, 60), "void": (176, 110, 240), "snow": (220, 240, 255)}


def update_shots(mon, dt, players, area):
    """Move / collide every projectile of ``mon``. Hits a player -> damage."""
    shots = mon.__dict__.get("shots")
    if not shots:
        return
    keep = []
    for s in shots:
        s["t"] += dt
        s["life"] -= dt
        s["x"] += s["vx"] * dt
        s["y"] += s["vy"] * dt
        col = SHOT_COLOR.get(s["kind"], (255, 200, 120))
        if s["life"] <= 0:
            _fx(mon, "burst", s["x"], s["y"], col)
            continue
        if area is not None and area.is_solid(int(s["x"] // TILE), int(s["y"] // TILE)):
            _fx(mon, "burst", s["x"], s["y"], col)
            continue
        hit = False
        for p in players:
            if (p.x - s["x"]) ** 2 + (p.y - 4 - s["y"]) ** 2 < (s["r"] + 12) ** 2:
                p.take_damage(s["dmg"])
                _fx(mon, "burst", s["x"], s["y"], col)
                hit = True
                break
        if not hit:
            keep.append(s)
    mon.shots = keep


def _free_tile_near(area, x, y, rmin, rmax, tries=14):
    for _ in range(tries):
        a = random.uniform(0, math.tau)
        d = random.uniform(rmin, rmax)
        nx, ny = x + math.cos(a) * d, y + math.sin(a) * d
        gx, gy = int(nx // TILE), int(ny // TILE)
        if area is None or not area.is_solid(gx, gy):
            return gx * TILE + TILE / 2, gy * TILE + TILE / 2
    return None


def _enraged(mon, st, label="ENRAGED"):
    """Boss phase 2 below half health: one roar, remembered in st."""
    if not st.get("phase2") and mon.hp <= mon.max_hp * 0.5:
        st["phase2"] = True
        _fx(mon, "roar", mon.x, mon.y)
        _fx(mon, "phase", mon.x, mon.y, label)
    return st.get("phase2", False)


# ---------------------------------------------------------------- behaviours
def swoop(mon, dt, players, area, target, ux, uy, dist):
    """Frost Bat: circles the nearest player, then dives straight through them."""
    st = _st(mon, mode="circle", t=random.uniform(1.0, 2.0), orbit=random.choice((-1, 1)))
    st["t"] -= dt
    base = st["base"]
    if st["mode"] == "circle":
        mon.speed = base
        want = TILE * 2.6
        px, py = -uy * st["orbit"], ux * st["orbit"]          # tangent
        radial = (dist - want) / TILE                          # >0: too far -> close in
        dx, dy = px + ux * radial * 0.8, py + uy * radial * 0.8
        if st["t"] <= 0 and dist < TILE * 5:
            st["mode"], st["t"] = "tell", 0.3              # hover + eye flash = the tell
        return _norm(dx, dy)
    if st["mode"] == "tell":
        mon.speed = 0
        if st["t"] <= 0:
            st["mode"], st["t"] = "dive", 0.55
            st["aim"] = (ux, uy)
            _fx(mon, "charge", mon.x, mon.y)
        return None
    if st["mode"] == "dive":
        mon.speed = base * 2.5
        if st["t"] <= 0:
            st["mode"], st["t"] = "recover", 0.5
        return st["aim"]
    mon.speed = base * 0.8                                      # recover: back off
    if st["t"] <= 0:
        st["mode"], st["t"] = "circle", random.uniform(1.2, 2.2)
        st["orbit"] = random.choice((-1, 1))
    return (-ux, -uy)


def lob(mon, dt, players, area, target, ux, uy, dist):
    """Snow Golem: plods after you; from mid range it raises a snowball over its
    head (telegraph) and lobs it -- slow and easy to sidestep."""
    st = _st(mon, cd=random.uniform(2.0, 3.0), charge=0.0)
    update_shots(mon, dt, players, area)
    if st["charge"] > 0:
        st["charge"] -= dt
        mon.speed = 0
        if st["charge"] <= 0:
            sp = 150.0
            ax, ay = _norm(target.x - mon.x, target.y - 4 - (mon.y - mon.size))
            shoot(mon, mon.x, mon.y - mon.size, ax * sp, ay * sp,
                  max(1, int(mon.damage * 0.8)), "snow", r=6, life=2.2)
            _fx(mon, "fire", mon.x, mon.y - mon.size)
            st["cd"] = random.uniform(2.8, 3.8)
        return None
    st["cd"] -= dt
    mon.speed = st["base"]
    if st["cd"] <= 0 and TILE * 2.2 < dist < TILE * 6:
        st["charge"] = 0.7
        return None
    return (ux, uy)


def hop(mon, dt, players, area, target, ux, uy, dist):
    """Magma Slime: bouncy lunging hops that leave little embers."""
    st = _st(mon, ember=0.0)
    mon.phase += dt * 4.2
    k = math.sin(mon.phase)
    mon.speed = st["base"] * (0.25 + 1.5 * max(0.0, k))
    st["ember"] -= dt
    if st["ember"] <= 0 and k > 0.6:
        st["ember"] = 0.35
        _fx(mon, "ember", mon.x, mon.y + mon.size * 0.6)
    return (ux, uy)


def imp(mon, dt, players, area, target, ux, uy, dist):
    """Fire Imp: keeps its distance, strafes, and throws telegraphed fireballs."""
    st = _st(mon, cd=random.uniform(1.4, 2.4), charge=0.0, strafe=random.choice((-1, 1)))
    update_shots(mon, dt, players, area)
    mon.phase += dt
    if st["charge"] > 0:                                   # winding up: hover still
        st["charge"] -= dt
        if st["charge"] <= 0:
            sp = 185.0
            hx = mon.x + (8 if ux > 0 else -8)
            hy = mon.y - 10
            ax, ay = _norm(target.x - hx, target.y - 4 - hy)
            shoot(mon, hx, hy, ax * sp, ay * sp, mon.damage, "fire", r=6)
            _fx(mon, "fire", hx, hy)
            st["cd"] = random.uniform(2.2, 3.0)
        mon.speed = st["base"] * 0.15
        return (ux, uy)
    st["cd"] -= dt
    if st["cd"] <= 0 and dist < TILE * 7:
        st["charge"] = 0.65                                # telegraph: fireball grows
        return None
    mon.speed = st["base"]
    if dist < TILE * 2.6:
        return (-ux, -uy)
    if dist > TILE * 4.8:
        return (ux, uy)
    if random.random() < dt * 0.4:
        st["strafe"] *= -1
    return _norm(-uy * st["strafe"] + ux * 0.1, ux * st["strafe"] + uy * 0.1)


def blink(mon, dt, players, area, target, ux, uy, dist):
    """Prism Wisp: drifts in, flickers (telegraph) and teleports beside you."""
    st = _st(mon, cd=random.uniform(2.0, 3.2), blink=0.0)
    mon.phase += dt * 3.0
    if st["blink"] > 0:
        st["blink"] -= dt
        if st["blink"] <= 0:
            spot = _free_tile_near(area, target.x, target.y, TILE * 1.6, TILE * 2.6)
            if spot:
                _fx(mon, "blink", mon.x, mon.y, mon.color)
                mon.x, mon.y = spot
                _fx(mon, "blink", mon.x, mon.y, mon.color)
            st["cd"] = random.uniform(2.6, 3.6)
            st["dash"] = 0.45
        return None
    st["cd"] -= dt
    if st["cd"] <= 0:
        st["blink"] = 0.5
        return None
    if st.get("dash", 0) > 0:                               # brief lunge after arriving
        st["dash"] -= dt
        mon.speed = st["base"] * 1.8
        return (ux, uy)
    mon.speed = st["base"]
    wob = math.sin(mon.phase) * 0.8
    return _norm(ux - uy * wob, uy + ux * wob)


def stalk(mon, dt, players, area, target, ux, uy, dist):
    """Shadow Stalker: prowls, winds up (visible aim line), then charges fast."""
    st = _st(mon, mode="prowl", t=0.0, cd=random.uniform(1.0, 2.0))
    st["t"] -= dt
    base = st["base"]
    mode = st["mode"]
    if mode == "windup":
        mon.speed = 0
        if st["t"] <= 0:
            st["mode"], st["t"] = "charge", 0.5
            _fx(mon, "charge", mon.x, mon.y)
        return None
    if mode == "charge":
        mon.speed = base * 4.4
        ax, ay = st["aim"]
        nx, ny = mon.x + ax * TILE * 0.6, mon.y + ay * TILE * 0.6
        if area is not None and area.is_solid(int(nx // TILE), int(ny // TILE)):
            st["t"] = 0
        if st["t"] <= 0:
            st["mode"], st["t"] = "rest", 0.9
            _fx(mon, "dust", mon.x, mon.y)
        return st["aim"]
    if mode == "rest":
        mon.speed = 0
        if st["t"] <= 0:
            st["mode"] = "prowl"
            st["cd"] = random.uniform(1.4, 2.4)
        return None
    st["cd"] -= dt
    mon.speed = base * 0.75
    if st["cd"] <= 0 and dist < TILE * 5.0:
        st["mode"], st["t"] = "windup", 0.75
        st["aim"] = (ux, uy)
        return None
    return (ux, uy)


def lunge(mon, dt, players, area, target, ux, uy, dist):
    """Cursed Knight: marches in, raises its blade (telegraph), then lunges."""
    st = _st(mon, mode="walk", t=0.0, cd=1.5)
    st["t"] -= dt
    base = st["base"]
    if st["mode"] == "raise":
        mon.speed = 0
        if st["t"] <= 0:
            st["mode"], st["t"] = "lunge", 0.26
            _fx(mon, "charge", mon.x, mon.y)
        return None
    if st["mode"] == "lunge":
        mon.speed = base * 3.4
        if st["t"] <= 0:
            st["mode"], st["t"] = "walk", 0.0
            st["cd"] = random.uniform(1.8, 2.6)
        return st["aim"]
    st["cd"] -= dt
    mon.speed = base
    if st["cd"] <= 0 and dist < TILE * 2.4:
        st["mode"], st["t"] = "raise", 0.45
        st["aim"] = (ux, uy)
        return None
    return (ux, uy)


# ---------------------------------------------------------------- bosses
WYRM_SEGMENTS = 7
WYRM_GAP = 5            # trail samples between two body segments


def _trail(mon, st):
    tr = st.setdefault("trail", [])
    if not tr or (tr[0][0] - mon.x) ** 2 + (tr[0][1] - mon.y) ** 2 > 16:
        tr.insert(0, (mon.x, mon.y))
        del tr[WYRM_SEGMENTS * WYRM_GAP + 2:]


def wyrm(mon, dt, players, area, target, ux, uy, dist):
    """Abyss Wyrm: weaving serpent. Alternates a telegraphed charge and a fan
    of void orbs; below half health it gets faster and spits wider fans."""
    st = _st(mon, mode="slither", t=0.0, cd=2.5, n=0)
    _trail(mon, st)
    st["face"] = -1 if ux < 0 else 1
    update_shots(mon, dt, players, area)
    mad = _enraged(mon, st, "The Wyrm writhes in fury!")
    st["t"] -= dt
    base = st["base"] * (1.2 if mad else 1.0)
    mode = st["mode"]
    mon.phase += dt * 3.0
    if mode == "coil":                                    # charge telegraph
        mon.speed = base * 0.12
        if st["t"] <= 0:
            st["mode"], st["t"] = "charge", 0.85
            _fx(mon, "charge", mon.x, mon.y)
        return st["aim"]
    if mode == "charge":
        mon.speed = base * 3.1
        ax, ay = st["aim"]
        nx, ny = mon.x + ax * TILE * 0.7, mon.y + ay * TILE * 0.7
        if area is not None and area.is_solid(int(nx // TILE), int(ny // TILE)):
            st["t"] = 0
            _fx(mon, "slam", mon.x, mon.y, TILE * 0.8)
        if st["t"] <= 0:
            st["mode"], st["cd"] = "slither", (1.6 if mad else 2.4)
        return st["aim"]
    if mode == "gape":                                    # spit telegraph (mouth glows)
        mon.speed = 0
        if st["t"] <= 0:
            n = 7 if mad else 5
            spread = 0.95 if mad else 0.7
            a0 = math.atan2(target.y - mon.y, target.x - mon.x)
            for i in range(n):
                a = a0 + spread * (i / (n - 1) - 0.5)
                shoot(mon, mon.x, mon.y - 6, math.cos(a) * 165, math.sin(a) * 165,
                      max(1, int(mon.damage * 0.7)), "void", r=8, life=2.6)
            _fx(mon, "fire", mon.x, mon.y)
            st["mode"], st["cd"] = "slither", (1.5 if mad else 2.3)
        return None
    st["cd"] -= dt
    mon.speed = base
    if st["cd"] <= 0:
        st["n"] += 1
        if st["n"] % 2 and dist < TILE * 7:
            st["mode"], st["t"] = "coil", 0.8
            st["aim"] = (ux, uy)
            _fx(mon, "roar", mon.x, mon.y)
        else:
            st["mode"], st["t"] = "gape", 0.7
        return None
    wob = math.sin(mon.phase) * 0.9
    return _norm(ux - uy * wob, uy + ux * wob)


COLOSSUS_R = TILE * 2.6          # slam radius (phase 2: x1.3)
SLAM_CAP = 64                    # heaviest single slam (~43% of a max-level player's HP)


def colossus_radius(mon):
    st = mon.__dict__.get("ai") or {}
    return COLOSSUS_R * (1.3 if st.get("phase2") else 1.0)


def colossus(mon, dt, players, area, target, ux, uy, dist):
    """Ruin Colossus: slow walker. Raises both fists while a ring fills on the
    ground (walk out of it!), then slams: everyone inside takes a big hit and a
    shockwave ring rolls out. Enraged: bigger ring, faster wind-up, double slam."""
    st = _st(mon, mode="walk", t=0.0, cd=2.8, wave=None, combo=0)
    mad = _enraged(mon, st, "The Colossus awakens fully!")
    st["t"] -= dt
    if st.get("wave") is not None:                        # cosmetic shockwave ring
        st["wave"] += dt
        if st["wave"] > 0.8:
            st["wave"] = None
    if st["mode"] == "windup":
        mon.speed = 0
        st["prog"] = 1.0 - max(0.0, st["t"]) / st["dur"]
        if st["t"] <= 0:
            r = colossus_radius(mon)
            for p in players:
                if (p.x - mon.x) ** 2 + (p.y - mon.y) ** 2 <= r * r:
                    p.hurt_cd = 0.0                       # a slam always lands
                    p.take_damage(min(SLAM_CAP, int(mon.damage * 1.4)))
            _fx(mon, "slam", mon.x, mon.y + mon.size * 0.5, r)
            st["wave"] = 0.0
            if mad and st["combo"] == 0:
                st["combo"] = 1
                st["mode"], st["t"], st["dur"] = "windup", 0.7, 0.7
            else:
                st["combo"] = 0
                st["mode"], st["t"] = "recover", 0.9
        return None
    if st["mode"] == "recover":
        mon.speed = 0
        if st["t"] <= 0:
            st["mode"], st["cd"] = "walk", (2.0 if mad else 3.0)
        return None
    st["cd"] -= dt
    mon.speed = st["base"] * (1.25 if mad else 1.0)
    if st["cd"] <= 0 and dist < TILE * 4:
        dur = 0.95 if mad else 1.25
        st["mode"], st["t"], st["dur"], st["prog"] = "windup", dur, dur, 0.0
        return None
    return (ux, uy)


M.BEHAVIORS.update({
    "swoop": swoop, "hop": hop, "lob": lob, "imp": imp, "blink": blink, "stalk": stalk,
    "lunge": lunge, "wyrm": wyrm, "colossus": colossus,
})


# ---------------------------------------------------------------- online sync
_NET_KEYS = ("mode", "t", "dur", "prog", "aim", "charge", "blink", "phase2", "wave", "face")


def net_pack(mon):
    """JSON-safe visual state (telegraphs + projectiles) for the LAN snapshot.
    Core can append ``monster_ai.net_pack(m)`` to each snapshot "M" row and call
    ``net_unpack(obj, row[7])`` on the client so it sees wind-ups and fireballs."""
    st = mon.__dict__.get("ai") or {}
    a = {k: (list(v) if isinstance(v, tuple) else v) for k, v in st.items()
         if k in _NET_KEYS and v is not None}
    if st.get("trail"):
        a["trail"] = [[round(x, 1), round(y, 1)] for x, y in st["trail"][::2]]
    shots = [[round(s["x"], 1), round(s["y"], 1), round(s["vx"]), round(s["vy"]),
              s["kind"], s["r"]] for s in (mon.__dict__.get("shots") or ())]
    return [a, shots]


def net_unpack(mon, data):
    try:
        a, shots = data
    except (TypeError, ValueError):
        return
    st = dict(a or {})
    if "aim" in st and isinstance(st["aim"], list):
        st["aim"] = tuple(st["aim"])
    if "trail" in st:
        tr = []
        for x, y in st["trail"]:
            tr += [(x, y), (x, y)]
        st["trail"] = tr
    mon.ai = st
    mon.shots = [{"x": s[0], "y": s[1], "vx": s[2], "vy": s[3], "kind": s[4], "r": s[5],
                  "dmg": 0, "life": 1.0, "t": 0.0} for s in (shots or ())]
