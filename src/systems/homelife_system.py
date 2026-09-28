"""Home life -- the house gets a heartbeat: a cat, a real fish tank, plants
that grow.

Owner: Home Life (2026-09-28). Plugs in through the hook bus; the only seam
edits are tiny and generic:
  * homeiso.draw_room collects ``_home_actors_*`` -> [(tile_x, tile_y, fn)] and
    depth-sorts them with the furniture and the farmers (the cat);
  * isofurn.LIVE_ART paints the aquarium's water box and the growth stages of
    the plant / mini cactus / flower vase (stock art when ``Placed.data`` is
    empty, so old saves look the same);
  * HomeMixin._home_client_interact asks ``_life_client_interact`` first (LAN).

* The cat  -- needs a Cat Tower in the house. Wanders the free floor, hops up
             the tower, naps on sofas / armchairs / the foot of the bed / rugs
             (never on a farmer's seat), grooms, stretches, greets you at the
             door and tags along now and then. Face it (or its tower) and press
             Action to pet it: purr, hearts, a meow, energy and a saved daily
             affection count. The tower opens a little card to call or rename
             the cat (default "Mochi"). The host simulates; the LAN client gets
             the cat in every snapshot and pets it through the host.
* Aquarium -- a parchment "Aquarium" menu that only takes FISH (6 per tank,
             kept in ``Placed.store`` so selling the tank gives them back).
             The fish really swim inside the glass in the room; Feed makes them
             rush up to the flakes. Watching / feeding relaxes you once a day.
* Plants   -- plant / cactus_small / vase_flowers: water them once a day
             (Action or the watering can) and they grow through lush / tall /
             in-bloom stages over the nights (sparkle + toast on bloom). A vase
             you've started caring for wilts after 3 dry days until you swap in
             fresh flowers from your bag (daffodil, dandelion, sweet pea, crocus,
             holly).
"""
import math
import random
import weakref

import pygame

from ..settings import TILE, MAX_ENERGY, AREA_HOME
from .. import furniture as F
from .. import homelife as L

CAT_NAME = "Mochi"
CAT_WALK, CAT_TROT, CAT_RUN = 1.3, 1.9, 2.7      # tiles / second
PET_ENERGY, PET_ENERGY_TIMES = 8, 3               # +8 energy for the first 3 pets a day
LOVE_MAX = 100
RELAX_ENERGY = 12
PLANT_KINDS = ("plant", "cactus_small", "vase_flowers")
VASE_FLOWERS = ("daffodil", "dandelion", "sweet_pea", "crocus", "holly")
WILT_DAYS = 3
_FACES = ((1, 0), (0, 1), (-1, 0), (0, -1))
_NAP_Z = {"sofa": 16, "armchair": 16, "bed": 20, "cat_tower": 40}
_CUR = None                                        # the game drawing the room right now


def _live_art(surf, P, kind, where, base, color):
    """isofurn.LIVE_ART: route to the game whose room is being drawn."""
    g = _CUR() if _CUR is not None else None
    if g is None:
        return False
    return g._life_art(surf, P, kind, where, base, color)


def _install_art(game):
    global _CUR
    _CUR = weakref.ref(game)
    try:
        from .. import isofurn
        isofurn.LIVE_ART = _live_art
    except Exception:
        pass


def _now():
    return pygame.time.get_ticks() / 1000.0


class Cat:
    """The house cat's state (host: simulated; client: mirrored + smoothed)."""

    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z
        self.tx, self.ty, self.tz = x, y, z        # LAN client: snapshot targets
        self.face = (1, 0)
        self.mode = "sit"
        self.t = 2.0
        self.path = []                             # [(x, y), ...] points to walk
        self.speed = CAT_WALK
        self.next = None                           # what to do on arrival
        self.perch = None                          # (piece, x, y, z) while up on something
        self.hop = None                            # [sx, sy, sz, ex, ey, ez, dur, k]
        self.hop_perch = None
        self.target = None                         # farmer index (follow / come)
        self.retarget = 0.0
        self.after = None                          # after 'happy': "hopdown"
        self.anim = random.uniform(0, 5)
        self.pose = "sit"

    def frame(self):
        a, p = self.anim, self.pose
        if p == "walk":
            return int(a * (10 if self.speed > CAT_WALK else 7)) % 4
        return int(a * {"sit": 0.8, "sleep": 0.6, "groom": 3.2, "happy": 3.0}.get(p, 1)) % 2


class HomeLifeMixin:
    """The house cat, the aquarium and growing house plants."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_life(self):
        self.cat = None
        self.cat_name = CAT_NAME
        self.cat_love = 0
        self._cat_day = None                       # [y, s, d] of the pet counters
        self._cat_pets = [0, 0]
        self._life_relax = [None, None]            # day each farmer last relaxed at a tank
        self._aqua_feed = {}                       # (gx, gy) -> feed start (local clock)
        self.aqua_menu = None
        self.cat_card = None
        _install_art(self)

    def _on_save_life(self):
        return {"cat_name": self.cat_name, "cat_love": int(self.cat_love),
                "cat_day": list(self._cat_day) if self._cat_day else None,
                "cat_pets": [int(n) for n in self._cat_pets],
                "life_relax": [list(d) if d else None for d in self._life_relax]}

    def _on_load_life(self, d):
        nm = d.get("cat_name")
        self.cat_name = self._cat_clean_name(nm) if isinstance(nm, str) else CAT_NAME
        try:
            self.cat_love = max(0, min(LOVE_MAX, int(d.get("cat_love", 0))))
        except (TypeError, ValueError):
            self.cat_love = 0
        cd = d.get("cat_day")
        self._cat_day = tuple(cd) if isinstance(cd, (list, tuple)) and len(cd) == 3 else None
        cp = d.get("cat_pets")
        self._cat_pets = ([int(x) for x in cp[:2]] if isinstance(cp, list) and len(cp) >= 2
                          else [0, 0])
        rl = d.get("life_relax")
        self._life_relax = [tuple(x) if isinstance(x, (list, tuple)) and len(x) == 3 else None
                            for x in (rl if isinstance(rl, list) and len(rl) == 2 else [None, None])]
        if not getattr(self, "_net_applying_world", False):
            self.cat = None                        # a fresh load: the cat respawns at home
        _install_art(self)

    def _today(self):
        t = self.time
        return (t.year, t.season_idx, t.day)

    @staticmethod
    def _cat_clean_name(name):
        name = "".join(ch for ch in str(name) if ch.isalnum() or ch in " -'").strip()
        return name[:12] or CAT_NAME

    # ------------------------------------------------------------ sounds
    def _life_sfx(self, name, fallback):
        a = getattr(self.audio, "_real", None) or self.audio
        ready = getattr(a, "sfx", {}).get(name) is not None
        self.audio.play(name if ready else fallback)

    def _life_build_sfx(self):
        a = getattr(self, "audio", None)
        a = getattr(a, "_real", None) or a
        if (not a or not getattr(a, "enabled", False) or a.sfx.get("cat_meow") is not None
                or getattr(a, "_life_sfx_busy", False)):
            return
        a._life_sfx_busy = True
        import threading
        threading.Thread(target=self._life_synth_sfx, args=(a,), daemon=True).start()

    @staticmethod
    def _life_synth_sfx(a):
        try:
            R, S = a._render, a._to_sound
            # meow: a rising "mi" into a falling "aow", vibrato on the vowel
            a.sfx["cat_meow"] = S(a._seq(
                R(0.07, [520, 1040, 1560], "tri", 0.16, attack=0.02, sweep=0.35),
                R(0.20, [700, 1400, 2100], "tri", 0.18, sweep=-0.30, vibrato=6, release=0.3),
                R(0.12, [500, 1000], "sine", 0.12, sweep=-0.35, release=0.8)))
            a.sfx["cat_mrrp"] = S(a._seq(
                R(0.05, [380, 760], "tri", 0.14, noise=0.2, sweep=0.6),
                R(0.10, [640, 1280], "tri", 0.15, sweep=0.2, vibrato=9, release=0.7)))
            # purr: a soft buzzing rumble that breathes in and out
            n = int(a.freq * 1.3)
            pur = a._render(1.3, [26, 52], "saw", 0.22, noise=0.55, attack=0.12, release=0.35)
            for i in range(n):
                t = i / a.freq
                pur[i] *= 0.35 + 0.65 * math.sin(math.pi * 1.5 * t) ** 2
            a.sfx["cat_purr"] = S(pur)
            a.sfx["aqua_feed"] = S(a._seq(
                R(0.04, [1300], "sine", 0.16, sweep=0.5), a._silence(0.05),
                R(0.04, [1600], "sine", 0.14, sweep=0.5), a._silence(0.06),
                R(0.05, [1150], "sine", 0.12, sweep=0.6, release=0.8)))
        except Exception:
            pass
        finally:
            a._life_sfx_busy = False

    # ------------------------------------------------------------ helpers
    def _home_area(self):
        return self.world.areas[AREA_HOME]

    def _cat_tower(self):
        return next((q for q in self.world.home_furniture if q.kind == "cat_tower"), None)

    def _cat_free(self, gx, gy):
        home = self._home_area()
        return 1 <= gx <= home.w - 2 and 1 <= gy <= home.h - 2 and not home.is_solid(gx, gy)

    def _cat_here_players(self):
        """[(index, player)] standing in the home right now (unparked)."""
        here = getattr(self, "player_here", None)
        return [(i, p) for i, p in enumerate(self.players) if here is None or here(i)]

    def _life_say(self, p, text):
        """A line for the farmer who pressed (LAN host: Player 2's too)."""
        self.ui.log(text)
        if (getattr(self, "net_mode", None) == "host" and p is self.players[1]
                and getattr(self, "_ctx_view_saved", None) is None):
            self._net_toast(text)

    def _life_toast(self, title, body, icon=None, color=(250, 226, 170)):
        t = getattr(self, "toast", None)
        if t:
            try:
                t(title, body, icon=icon, color=color)
            except Exception:
                pass

    def _cat_icon(self):
        try:
            return L.cat_frame("happy", (1, 0), 0)
        except Exception:
            return None

    @staticmethod
    def _raise(wx, wy, z):
        """World point lifted ``z`` screen px in the iso room (particles)."""
        return wx - 1.5 * z, wy - 1.5 * z

    # ------------------------------------------------------------ path finding
    def _cat_bfs(self, start):
        par = {start: None}
        q = [start]
        i = 0
        while i < len(q):
            c = q[i]
            i += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + dx, c[1] + dy)
                if n not in par and self._cat_free(*n):
                    par[n] = c
                    q.append(n)
        return par

    def _cat_route(self, c, cell, off=(0.0, 0.0)):
        """Walk points from the cat to ``cell`` (None if unreachable)."""
        start = (int(c.x), int(c.y))
        par = self._cat_bfs(start)
        if cell not in par:
            return None
        cells = []
        k = cell
        while k is not None and k != start:
            cells.append(k)
            k = par[k]
        cells.reverse()
        pts = [(gx + 0.5, gy + 0.5) for gx, gy in cells]
        goal = (cell[0] + 0.5 + off[0], cell[1] + 0.5 + off[1])
        if pts:
            pts[-1] = goal
        else:
            pts = [goal]
        return pts

    def _cat_walk(self, c, cell, then=None, speed=CAT_WALK, off=None):
        if off is None:
            off = (random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15))
        pts = self._cat_route(c, cell, off)
        if pts is None:
            return False
        c.path, c.next, c.speed = pts, then, speed
        c.mode = "walk"
        return True

    def _cat_nearest_free(self, x, y):
        home = self._home_area()
        best = None
        for gx in range(1, home.w - 1):
            for gy in range(1, home.h - 1):
                if self._cat_free(gx, gy):
                    d = (gx + 0.5 - x) ** 2 + (gy + 0.5 - y) ** 2
                    if best is None or d < best[0]:
                        best = (d, (gx, gy))
        return best[1] if best else None

    def _cat_beside(self, c, cell, toward=None):
        """A free, reachable cell orthogonally next to ``cell`` (nearest the
        cat, or nearest ``toward``)."""
        par = self._cat_bfs((int(c.x), int(c.y))) if c.z <= 0.5 else None
        ref = toward or (c.x, c.y)
        best = None
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            n = (cell[0] + dx, cell[1] + dy)
            if not self._cat_free(*n) or (par is not None and n not in par):
                continue
            d = (n[0] + 0.5 - ref[0]) ** 2 + (n[1] + 0.5 - ref[1]) ** 2
            if best is None or d < best[0]:
                best = (d, n)
        return best[1] if best else None

    # ------------------------------------------------------------ nap spots
    def _cat_spot_taken(self, x, y):
        for p in self.players:
            s = getattr(p, "sitting", None)
            if s and (s[1] - x) ** 2 + (s[2] - y) ** 2 < 0.5 ** 2:
                return True
        return False

    @staticmethod
    def _bed_foot(q):
        fw, fh = F.footprint(q.kind, q.rot)
        u, v = 0.74, 0.5                       # canonical: headboard at x0, foot at x1
        rot = q.rot % 4
        gx, gy = q.gx + q.ox, q.gy + q.oy
        if rot == 0:
            return gx + u * fw, gy + v * fh
        if rot == 1:
            return gx + (1 - v) * fw, gy + u * fh
        if rot == 2:
            return gx + (1 - u) * fw, gy + (1 - v) * fh
        return gx + v * fw, gy + (1 - u) * fh

    def _cat_perches(self, night=False):
        """[(weight, piece, x, y, z)] places to curl up (z=0: a rug cell)."""
        out = []
        for q in self.world.home_furniture:
            k = q.kind
            if k in ("sofa", "armchair"):
                fw, fh = F.footprint(k, q.rot)
                for i in range(fw):
                    for j in range(fh):
                        x, y = q.gx + q.ox + i + 0.5, q.gy + q.oy + j + 0.5
                        if not self._cat_spot_taken(x, y):
                            out.append((3.0, q, x, y, _NAP_Z[k]))
            elif k == "bed":
                x, y = self._bed_foot(q)
                if not self._cat_spot_taken(x, y):
                    out.append((6.0 if night else 3.0, q, x, y, _NAP_Z[k]))
            elif k == "cat_tower":
                out.append((3.5, q, q.gx + 0.5, q.gy + 0.5, _NAP_Z[k]))
            elif k == "rug":
                for (cx, cy) in q.cells():
                    if self._cat_free(cx, cy):
                        out.append((0.8, None, cx + 0.5, cy + 0.5, 0))
        return out

    # ------------------------------------------------------------ spawn / despawn
    def _cat_spawn(self):
        tw = self._cat_tower()
        if tw is None:
            return None
        c = Cat(tw.gx + 0.5, tw.gy + 0.5, _NAP_Z["cat_tower"])
        c.perch = (tw, c.x, c.y, c.z)
        c.mode, c.t = "sleep", random.uniform(4, 9)
        c.face = random.choice(_FACES[:2])
        self.cat = c
        return c

    def _cat_sync_presence(self):
        """The cat lives here only while a Cat Tower stands in the house."""
        if self._cat_tower() is None:
            if self.cat is not None:
                self.cat = None
            return None
        return self.cat or self._cat_spawn()

    # ------------------------------------------------------------ simulation
    def _on_area_update_life(self, dt):
        if self.world.current != AREA_HOME:
            return
        c = self._cat_sync_presence()
        if c is None:
            return
        self._cat_update(c, dt)

    def _on_area_enter_life(self):
        if self.world.current == AREA_HOME:
            self._life_build_sfx()

    def _on_event_life(self, event, data):
        """A farmer walked in: the cat trots over to say hello (if awake)."""
        if event != "warp" or data.get("area") != AREA_HOME:
            return
        if getattr(self, "net_mode", None) == "client":
            return
        c = self._cat_sync_presence() if self.world.current == AREA_HOME else self.cat
        if c is None or c.hop:
            return
        if c.mode == "sleep" and random.random() < 0.5:
            return                                 # lazy cat: opens one eye
        # who just came in: a farmer in the house, standing by its door (P2's
        # own warp fires while the host still simulates P1's area)
        doors = [(w["gx"] + 0.5, w["gy"] + 0.5) for w in self._home_area().warps]
        indep = getattr(self, "independent", lambda: False)()
        came = [i for i, p in enumerate(self.players)
                if (not indep or self.p_area[i] == AREA_HOME)
                and any((p.x / TILE - dx) ** 2 + (p.y / TILE - dy) ** 2 < 2.5 ** 2
                        for dx, dy in doors)]
        if came:
            self._cat_go_to_player(c, came[0], then=("greet", came[0]), speed=CAT_RUN)

    def _cat_update(self, c, dt):
        c.anim += dt
        self._cat_validate(c)
        if c.hop:
            self._cat_hop_step(c, dt)
        elif c.path:
            self._cat_walk_step(c, dt)
        elif c.mode == "follow":
            self._cat_follow_step(c, dt)
        else:
            c.t -= dt
            if c.t <= 0:
                self._cat_think(c)
        c.pose = self._cat_pose(c)

    @staticmethod
    def _cat_pose(c):
        if c.hop:
            return "hop"
        if c.path:
            return "walk"
        return {"sleep": "sleep", "groom": "groom", "stretch": "stretch",
                "happy": "happy"}.get(c.mode, "sit")

    def _cat_validate(self, c):
        home = self.world.home_furniture
        if c.perch is not None and not c.hop:
            q = c.perch[0]
            if q is not None and not any(q is o for o in home):
                self._cat_drop(c)                  # its perch was sold / moved away
            elif q is not None and q.kind in F.SEATS and self._cat_spot_taken(c.x, c.y):
                self._cat_hop_down(c, startled=True)   # a farmer sat down right here
        elif not c.hop and c.z <= 0.5 and not self._cat_free(int(c.x), int(c.y)):
            self._cat_drop(c)

    def _cat_drop(self, c):
        cell = self._cat_nearest_free(c.x, c.y)
        c.perch, c.hop, c.path = None, None, []
        if cell is not None:
            c.x, c.y = cell[0] + 0.5, cell[1] + 0.5
        c.z = 0.0
        c.mode, c.t = "sit", 1.5

    def _cat_walk_step(self, c, dt):
        tx, ty = c.path[0]
        dx, dy = tx - c.x, ty - c.y
        d = math.hypot(dx, dy)
        step = c.speed * dt
        if abs(dx) > 1e-3 or abs(dy) > 1e-3:
            c.face = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))
        if d <= step:
            c.x, c.y = tx, ty
            c.path.pop(0)
            if not c.path:
                self._cat_arrive(c)
        else:
            c.x += dx / d * step
            c.y += dy / d * step

    def _cat_hop(self, c, ex, ey, ez, perch=None, then=None, dur=0.5):
        c.hop = [c.x, c.y, c.z, ex, ey, ez, dur, 0.0]
        c.hop_perch = perch
        c.next = then
        c.path = []
        c.mode = "hop"
        dx, dy = ex - c.x, ey - c.y
        if abs(dx) > 1e-3 or abs(dy) > 1e-3:
            c.face = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))

    def _cat_hop_step(self, c, dt):
        h = c.hop
        h[7] = min(1.0, h[7] + dt / h[6])
        k = h[7]
        e = k * k * (3 - 2 * k)
        c.x = h[0] + (h[3] - h[0]) * e
        c.y = h[1] + (h[4] - h[1]) * e
        c.z = h[2] + (h[5] - h[2]) * k + math.sin(math.pi * k) * (9 + 0.3 * abs(h[5] - h[2]))
        if k >= 1.0:
            c.x, c.y, c.z = h[3], h[4], h[5]
            c.hop = None
            c.perch = c.hop_perch
            c.hop_perch = None
            self._cat_arrive(c)

    def _cat_hop_down(self, c, startled=False, toward=None):
        cell = self._cat_beside(c, (int(c.x), int(c.y)), toward)
        if cell is None:
            cell = self._cat_nearest_free(c.x, c.y)
        c.perch = None
        c.mode = "sit"
        if cell is None:
            c.z = 0.0
            return
        self._cat_hop(c, cell[0] + 0.5, cell[1] + 0.5, 0.0, None, ("rest", "sit"), dur=0.42)
        if startled:
            self._life_sfx("cat_mrrp", "ui_move")

    def _cat_arrive(self, c):
        nxt, c.next = c.next, None
        kind = nxt[0] if nxt else None
        if kind == "perch":
            _w, q, x, y, z = nxt[1]
            if z > 0:
                self._cat_hop(c, x, y, z, (q, x, y, z), ("rest", nxt[2]), dur=0.55)
            else:
                c.mode, c.t = nxt[2], self._cat_rest_time(nxt[2])
        elif kind == "rest":
            c.mode, c.t = nxt[1], self._cat_rest_time(nxt[1])
        elif kind == "goto":
            if not self._cat_go_to_player(c, nxt[1], nxt[2], nxt[3]) and nxt[2]                     and nxt[2][0] == "pet":
                self._cat_pet(nxt[1], arrived=True)
        elif kind == "follow":
            c.mode = "follow"
            p = self.players[nxt[1]] if 0 <= nxt[1] < len(self.players) else None
            if p is not None:
                self._cat_face_point(c, p.x / TILE, p.y / TILE)
        elif kind in ("greet", "sitface", "pet"):
            idx = nxt[1]
            p = self.players[idx] if 0 <= idx < len(self.players) else None
            if p is not None:
                self._cat_face_point(c, p.x / TILE, p.y / TILE)
            if kind == "pet":
                self._cat_pet(idx, arrived=True)
            else:
                c.mode, c.t = "sit", random.uniform(3.0, 5.0)
                if kind == "greet":
                    self._life_sfx("cat_meow", "emote_happy")
                    x, y = self._raise(c.x * TILE, c.y * TILE, c.z + 22)
                    self.parts.heart_float(x, y)
        else:
            c.mode, c.t = "sit", random.uniform(1.5, 3.5)

    def _cat_rest_time(self, mode):
        night = self._cat_night()
        return {"sleep": random.uniform(55, 130) if night else random.uniform(12, 26),
                "groom": random.uniform(3.0, 5.0), "sit": random.uniform(3.0, 6.0),
                "stretch": 1.3, "happy": 2.4}.get(mode, 3.0)

    def _cat_night(self):
        m = int(getattr(self.time, "minutes", 12 * 60))
        return m >= 21 * 60 or m < 7 * 60

    @staticmethod
    def _cat_face_point(c, x, y):
        dx, dy = x - c.x, y - c.y
        if abs(dx) > 1e-3 or abs(dy) > 1e-3:
            c.face = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))

    def _cat_go_to_player(self, c, idx, then=None, speed=CAT_TROT):
        """Head for a free cell beside farmer ``idx`` (hopping down first)."""
        p = self.players[idx]
        pc = (int(p.x // TILE), int(p.y // TILE))
        if c.perch is not None or c.z > 0.5:
            c.target = idx
            self._cat_hop_down(c, toward=(p.x / TILE, p.y / TILE))
            if c.hop:                              # carry on once down on the floor
                c.next = ("goto", idx, then, speed)
                return True
        cell = self._cat_beside(c, pc)
        if cell is None:
            cell = pc if self._cat_free(*pc) else None
        if cell is None:
            return False
        return self._cat_walk(c, cell, then, speed)

    def _cat_follow_step(self, c, dt):
        c.t -= dt
        c.retarget -= dt
        idx = c.target
        if c.t <= 0 or idx is None or not any(i == idx for i, _ in self._cat_here_players()):
            c.mode, c.t, c.target = "sit", random.uniform(2, 4), None
            return
        if c.retarget > 0:
            return
        c.retarget = 0.8
        p = self.players[idx]
        if (p.x / TILE - c.x) ** 2 + (p.y / TILE - c.y) ** 2 > 1.7 ** 2:
            pc = (int(p.x // TILE), int(p.y // TILE))
            cell = self._cat_beside(c, pc)
            if cell is not None:
                pts = self._cat_route(c, cell, (random.uniform(-0.15, 0.15),
                                                random.uniform(-0.15, 0.15)))
                if pts:
                    c.path, c.speed, c.next = pts, CAT_TROT, ("follow", idx)
        else:
            self._cat_face_point(c, p.x / TILE, p.y / TILE)

    def _cat_think(self, c):
        """Pick what to do next -- a small weighted cat brain."""
        night = self._cat_night()
        if c.mode == "sleep":                      # waking up: a big stretch first
            c.mode, c.t = "stretch", self._cat_rest_time("stretch")
            return
        if c.mode == "happy" and c.after == "hopdown":
            c.after = None
            self._cat_hop_down(c)
            return
        c.after = None
        if c.perch is not None:
            r = random.random()
            if r < 0.35:
                c.mode = random.choice(("groom", "sit", "sleep"))
                c.t = self._cat_rest_time(c.mode)
            else:
                self._cat_hop_down(c)
            return
        here = self._cat_here_players()
        opts = [("wander", 3.0), ("groom", 1.6), ("sit", 1.4),
                ("nap", 6.0 if night else 1.3)]
        if here:
            opts.append(("follow", 1.6))
        if self._cat_tower() is not None:
            opts.append(("tower", 1.2))
        tot = sum(w for _, w in opts)
        r = random.uniform(0, tot)
        pick = opts[-1][0]
        for name, w in opts:
            r -= w
            if r <= 0:
                pick = name
                break
        if pick in ("groom", "sit"):
            c.mode, c.t = pick, self._cat_rest_time(pick)
        elif pick == "follow":
            c.mode, c.t, c.retarget = "follow", random.uniform(12, 20), 0.0
            c.target = random.choice(here)[0]
        elif pick in ("nap", "tower"):
            spots = self._cat_perches(night)
            if pick == "tower":
                spots = [s for s in spots if s[1] is not None and s[1].kind == "cat_tower"]
            if not self._cat_go_perch(c, spots, "sleep" if pick == "nap" else
                                      random.choice(("sit", "groom", "sleep"))):
                c.mode, c.t = ("sleep", self._cat_rest_time("sleep")) if pick == "nap" \
                    else ("sit", 2.0)
        else:
            self._cat_wander(c)

    def _cat_go_perch(self, c, spots, rest):
        random.shuffle(spots)
        spots.sort(key=lambda s: -s[0] * random.uniform(0.5, 1.5))
        for spot in spots[:4]:
            _w, q, x, y, z = spot
            if z <= 0:                             # a rug: just walk there
                if self._cat_walk(c, (int(x), int(y)), ("rest", rest), CAT_WALK, off=(0, 0)):
                    return True
                continue
            cell = self._cat_beside(c, (int(x), int(y)))
            if cell is None:
                continue
            if (int(c.x), int(c.y)) == cell:
                self._cat_arrive_perch(c, spot, rest)
                return True
            if self._cat_walk(c, cell, ("perch", spot, rest), CAT_WALK, off=(0, 0)):
                return True
        return False

    def _cat_arrive_perch(self, c, spot, rest):
        c.next = ("perch", spot, rest)
        self._cat_arrive(c)

    def _cat_wander(self, c):
        par = self._cat_bfs((int(c.x), int(c.y)))
        taken = {(int(p.x // TILE), int(p.y // TILE)) for _, p in self._cat_here_players()}
        opts = [k for k in par if k not in taken
                and 2 <= abs(k[0] - int(c.x)) + abs(k[1] - int(c.y)) <= 7]
        if not opts:
            c.mode, c.t = "sit", 2.0
            return
        self._cat_walk(c, random.choice(opts), ("rest", random.choice(("sit", "sit", "groom"))))

    # ------------------------------------------------------------ petting
    def _cat_in_front(self, p, reach=0.8):
        """True if the cat is right in front of farmer ``p``."""
        c = self.cat
        if c is None:
            return False
        tx, ty = p.target_tile()
        if (int(c.x), int(c.y)) == (tx, ty):
            return True
        fx = p.x / TILE + p.fx * 0.8
        fy = p.y / TILE + p.fy * 0.8
        return (c.x - fx) ** 2 + (c.y - fy) ** 2 < reach ** 2

    def _cat_pet(self, idx, arrived=False):
        """Pet the cat (host side). Returns the line shown to the farmer."""
        c = self.cat
        if c is None:
            return ""
        p = self.players[idx]
        today = self._today()
        if self._cat_day != today:
            self._cat_day, self._cat_pets = today, [0, 0]
        n = self._cat_pets[idx] = self._cat_pets[idx] + 1
        first = n == 1
        if first:
            self.cat_love = min(LOVE_MAX, self.cat_love + 1)
        gain = PET_ENERGY if n <= PET_ENERGY_TIMES else 0
        if gain:
            p.energy = min(MAX_ENERGY, p.energy + gain)
        was_asleep = c.mode == "sleep"
        c.path, c.next = [], None
        if c.hop is None:
            if c.z <= 0.5:
                self._cat_face_point(c, p.x / TILE, p.y / TILE)
            c.mode, c.t = "happy", self._cat_rest_time("happy")
            q = c.perch[0] if c.perch else None
            c.after = "hopdown" if (q is not None and q.kind in F.SEATS) else None
        self._cat_pet_fx(c.x, c.y, c.z, first)
        if getattr(self, "net_mode", None) == "host" and self.p_area[1] == AREA_HOME:
            self._net_send_fx("catpet", x=round(c.x, 3), y=round(c.y, 3), z=round(c.z, 1),
                              first=first)
        nm = self.cat_name
        wake = f"{nm} blinks awake and " if was_asleep else f"{nm} "
        line = (f"{p.name} pets {nm}. {wake}purrs happily" + (f" (+{gain} energy)" if gain else "")
                + (f"  - affection {self.cat_love}" if first else ""))
        self._life_say(p, line)
        if first:
            self._life_toast(f"{nm} purrs <3", f"{p.name}'s first pet today  -  affection "
                             f"{self.cat_love}/{LOVE_MAX}" + (f", +{gain} energy" if gain else ""),
                             icon=self._cat_icon(), color=(255, 196, 206))
        self.emit("animal_petted", p=p, animal="cat")
        return line

    def _cat_pet_fx(self, x, y, z, first):
        wx, wy = self._raise(x * TILE, y * TILE, z + 20)
        for i in range(3 if not first else 4):
            self.parts.heart_float(wx + random.uniform(-6, 6), wy - i * 4)
        if first:
            hb = getattr(self.parts, "heart_burst", None)
            if hb:
                hb(wx, wy, n=10)
        self._life_sfx("cat_meow", "emote_happy")
        self._life_sfx("cat_purr", "ui_select")

    def _cat_call(self, idx):
        """The tower card's 'call for pets': the cat comes running to ``idx``."""
        c = self._cat_sync_presence() if self.world.current == AREA_HOME else self.cat
        if c is None:
            return False
        p = self.players[idx]
        if (p.x / TILE - c.x) ** 2 + (p.y / TILE - c.y) ** 2 < 1.4 ** 2 and c.z <= 0.5 \
                and not c.hop:
            self._cat_pet(idx)
            return True
        self._life_sfx("cat_mrrp", "ui_select")
        if not self._cat_go_to_player(c, idx, then=("pet", idx), speed=CAT_RUN):
            self._cat_pet(idx)
        return True

    # ------------------------------------------------------------ interaction
    def _life_facing_piece(self, p):
        """The home piece this press is aimed at (same rule as the furniture
        branch of player_action)."""
        facing = self.world.furniture_at(*p.target_tile())
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)
        return facing or self.world.furniture_at(pgx, pgy)

    def _interact_early_40_life(self, idx, p):
        if self.world.current != AREA_HOME or getattr(p, "sitting", None):
            return False
        remote = getattr(self, "net_mode", None) == "host" and idx == 1
        fr = self._life_facing_piece(p)
        if self.cat is not None and self._cat_in_front(p):
            if (fr is not None and fr.kind == "cat_tower" and self.cat.mode == "happy"
                    and not remote):
                self._open_cat_card(idx)           # purring on its tower: 2nd press = card
            else:
                self._cat_pet(idx)
            return True
        if fr is None:
            return False
        if fr.kind == "cat_tower":
            if remote:                             # the client shows its own card
                self._cat_call(idx)
            else:
                self._open_cat_card(idx)
            return True
        if fr.kind == "aquarium":
            if remote:
                self._aqua_relax(idx, fr)
            else:
                self._open_aquarium(idx, fr)
            return True
        if fr.kind in PLANT_KINDS:
            self._plant_tend(idx, p, fr)
            return True
        return False

    def _life_client_interact(self, p, fr):
        """LAN client: True = handled here, None = let the host run the press
        (petting / watering happen host-side), False = not ours."""
        if self.cat is not None and self._cat_in_front(p):
            if fr.kind == "cat_tower" and self.cat.pose == "happy":
                self._open_cat_card(1, client=True)
                return True
            return None
        if fr.kind == "aquarium":
            self._open_aquarium(1, fr, client=True)
            return True
        if fr.kind == "cat_tower":
            self._open_cat_card(1, client=True)
            return True
        if fr.kind in PLANT_KINDS:
            return None
        return False

    # ------------------------------------------------------------ plants
    @staticmethod
    def _plant_stage(q):
        return L.stage_of(int(q.data.get("g", 0) or 0))

    def _plant_label(self, q):
        return F.CAT.get(q.kind, {}).get("label", "Plant")

    def _plant_tend(self, idx, p, q):
        d = q.data
        label = self._plant_label(q)
        entry = p.inv.selected_entry() if p.inv else None
        held = entry[1] if entry else None
        cx, cy = (q.gx + 0.5 + q.ox) * TILE, (q.gy + 0.5 + q.oy) * TILE
        if q.kind == "vase_flowers" and held in VASE_FLOWERS and entry[0] == "item":
            p.inv.remove(held, 1)
            try:
                from ..forage import FORAGE
                col = FORAGE.get(held, (None, 0, None))[2]
            except Exception:
                col = None
            if col is None:
                from ..crops import CROPS
                col = CROPS.get(held, {}).get("color", (236, 120, 130))
            for k in ("wilt", "dry", "g", "w"):
                d.pop(k, None)
            d["fc"] = [int(v) for v in col[:3]]
            d["g"] = 1
            self.parts.sparkle(*self._raise(cx, cy, 30), n=10, color=tuple(col[:3]))
            self._life_sfx("forage", "harvest")
            from ..fridge import label as _lab
            self._life_say(p, f"{p.name} arranges fresh {_lab(held)} in the vase. Lovely!")
            return
        if d.get("wilt"):
            self._life_sfx("ui_move", "ui_move")
            self._life_say(p, f"The flowers have wilted... hold fresh flowers (daffodil, "
                               f"sweet pea, crocus...) and press Action to swap them in.")
            return
        if held == "watering_can" and entry[0] == "tool":
            p.trigger_swing()
        if d.get("w"):
            self._life_sfx("ui_move", "ui_move")
            self._life_say(p, f"The {label} is already watered today. It grows overnight.")
            return
        d["w"] = 1
        d.pop("dry", None)
        p.energy = min(MAX_ENERGY, p.energy + 3)
        self.parts.splash(*self._raise(cx, cy, 16), n=6)
        self.parts.sparkle(*self._raise(cx, cy, 26), n=4, color=(150, 210, 250))
        self._life_sfx("water", "ui_select")
        st = self._plant_stage(q)
        how = ("it's in full bloom!" if st >= 3 else "it will grow a little overnight")
        self._life_say(p, f"{p.name} waters the {label} (+3 energy) - {how}.")

    def _on_new_day_life(self):
        bloomed, grew = [], []
        for q in self.world.home_furniture:
            if q.kind not in PLANT_KINDS:
                continue
            d = q.data
            before = self._plant_stage(q)
            if d.pop("w", None):
                if not d.get("wilt"):
                    d["g"] = min(9, int(d.get("g", 0) or 0) + 1)
                d.pop("dry", None)
            elif q.kind == "vase_flowers" and (d.get("g") or d.get("fc")) and not d.get("wilt"):
                d["dry"] = int(d.get("dry", 0) or 0) + 1
                if d["dry"] >= WILT_DAYS:
                    d["wilt"] = 1
                    d.pop("dry", None)
            after = self._plant_stage(q)
            if after > before:
                (bloomed if after >= 3 else grew).append(q)
        for q in bloomed:
            label = self._plant_label(q)
            self._life_toast(f"{label} in bloom!", "Your daily watering paid off - "
                             "it's blossoming beautifully.", color=(250, 200, 220))
            self._net_toast(f"The {label} is in full bloom!")
            if self.world.current == AREA_HOME:
                cx, cy = (q.gx + 0.5 + q.ox) * TILE, (q.gy + 0.5 + q.oy) * TILE
                sb = getattr(self.parts, "star_burst", None)
                if sb:
                    sb(*self._raise(cx, cy, 30), (255, 214, 236), n=10)
                self.parts.sparkle(*self._raise(cx, cy, 30), n=16, color=(255, 220, 240))
        for q in grew:
            self.ui.log(f"The {self._plant_label(q)} looks {L.STAGE_NAME[self._plant_stage(q)]}"
                        f"er today!" if self._plant_stage(q) == 1 else
                        f"The {self._plant_label(q)} grew taller overnight - buds are forming!")
        # the cat starts the day curled up on the bed (or its tower)
        c = self.cat
        if c is not None and not c.hop:
            spots = [s for s in self._cat_perches(True) if s[1] is not None
                     and s[1].kind in ("bed", "cat_tower")]
            if spots:
                _w, q, x, y, z = max(spots, key=lambda s: s[0])
                c.x, c.y, c.z = x, y, z
                c.perch, c.path, c.next = (q, x, y, z), [], None
                c.mode, c.t = "sleep", random.uniform(6, 14)

    # ------------------------------------------------------------ aquarium
    @staticmethod
    def _tank_fish(q):
        return [f for f in sorted(q.store) for _ in range(max(0, int(q.store[f])))][:L.TANK_CAP]

    def _aqua_is_fish(self, item):
        try:
            from ..fishing import FISH
        except Exception:
            return False
        return item in FISH

    def _aqua_op(self, pidx, fr, op, item="", client=False):
        """put / take / feed for the aquarium menu (and the LAN host for a
        client). Returns (ok, message)."""
        p = self.players[pidx]
        if p.inv is None:
            return False, ""
        from ..fridge import label as _lab
        if op == "put":
            if not self._aqua_is_fish(item):
                self.audio.play("ui_move")
                return False, f"Only fish can live in the aquarium!"
            if len(self._tank_fish(fr)) >= L.TANK_CAP:
                self.audio.play("ui_move")
                return False, f"The tank is full - {L.TANK_CAP} fish is plenty!"
            if p.inv.count(item) <= 0:
                return False, ""
            p.inv.remove(item, 1)
            fr.store[item] = fr.store.get(item, 0) + 1
            self._life_sfx("splash", "ui_select")
            msg = f"Splash! The {_lab(item)} swims off to explore."
        elif op == "take":
            if fr.store.get(item, 0) <= 0:
                return False, ""
            fr.store[item] -= 1
            if fr.store[item] <= 0:
                del fr.store[item]
            p.inv.add(item, 1)
            self.audio.play("sell")
            msg = f"Scooped the {_lab(item)} back into your bag."
        elif op == "feed":
            self._aqua_feed[(fr.gx, fr.gy)] = _now()
            self._life_sfx("aqua_feed", "water")
            n = len(self._tank_fish(fr))
            msg = ("A pinch of flakes - the fish rush up to the surface!" if n else
                   "You sprinkle flakes... an empty tank. Add some fish!")
            if not client:
                self._aqua_relax(pidx, fr)
                if getattr(self, "net_mode", None) == "host" and self.p_area[1] == AREA_HOME:
                    self._net_send_fx("aqfeed", gx=fr.gx, gy=fr.gy)
        elif op == "watch":
            if not client:
                self._aqua_relax(pidx, fr)
            return True, ""
        else:
            return False, ""
        if client:
            self._net_send_menu({"m": "aquarium", "op": op, "item": item,
                                 "gx": fr.gx, "gy": fr.gy})
        return True, msg

    def _aqua_relax(self, pidx, fr):
        """Watching the fish unwinds you -- once a day per farmer."""
        today = self._today()
        if self._life_relax[pidx] == today:
            return False
        self._life_relax[pidx] = today
        p = self.players[pidx]
        p.energy = min(MAX_ENERGY, p.energy + RELAX_ENERGY)
        if hasattr(p, "add_buff"):
            p.add_buff("regen", 90, 0.2, "Relaxed")
        n = len(self._tank_fish(fr))
        what = f"{n} fish drifting by" if n else "the bubbles rising"
        self._life_say(p, f"{p.name} relaxes watching {what} (+{RELAX_ENERGY} energy, Relaxed)")
        self._life_toast("So calming...", f"{p.name} watches {what}. +{RELAX_ENERGY} energy",
                         icon=None, color=(170, 214, 240))
        return True

    def _open_aquarium(self, idx, fr, client=False):
        from .. import homelife_ui
        self.aqua_menu = homelife_ui.AquariumMenu(self, idx, fr, client=client)
        self.state = "aquarium"
        self.audio.play("ui_select")
        self._life_build_sfx()
        if client:
            self._net_send_menu({"m": "aquarium", "op": "watch", "item": "",
                                 "gx": fr.gx, "gy": fr.gy})
        else:
            self._aqua_relax(idx, fr)

    def _aqua_closed(self, menu):
        self.aqua_menu = None
        if self.state == "aquarium":
            self.state = "play"

    # ------------------------------------------------------------ cat card
    def _open_cat_card(self, idx, client=False):
        from .. import homelife_ui
        if not client:
            self._cat_sync_presence()
        self.cat_card = homelife_ui.CatTowerCard(self, idx, client=client)
        self.state = "cattower"
        self.audio.play("ui_select")
        self._life_build_sfx()

    def _cat_card_call(self, card):
        if card.client:
            self._net_send_menu({"m": "life", "op": "call"})
        else:
            self._cat_call(card.pidx)

    def _cat_card_rename(self, card, name):
        self.cat_name = self._cat_clean_name(name)
        if card.client:
            self._net_send_menu({"m": "life", "op": "name", "name": self.cat_name})
        self.ui.log(f"The cat's name is now {self.cat_name}. Mrrp!")
        self._life_sfx("cat_mrrp", "ui_select")

    def _cat_card_closed(self, card):
        self.cat_card = None
        if self.state == "cattower":
            self.state = "play"

    # ------------------------------------------------------------ custom states
    def _life_menu(self):
        return {"aquarium": getattr(self, "aqua_menu", None),
                "cattower": getattr(self, "cat_card", None)}.get(self.state)

    def _life_state_event(self, e):
        m = self._life_menu()
        if m is None:
            self.state = "play"
            return
        m.handle_event(e)

    def _life_state_update(self, dt):
        m = self._life_menu()
        if m is None:
            self.state = "play"
            return
        m.update(dt)

    def _life_state_draw(self):
        m = self._life_menu()
        if m is not None:
            m.draw(self.screen)

    _state_event_aquarium = _state_event_cattower = _life_state_event
    _state_update_aquarium = _state_update_cattower = _life_state_update
    _state_draw_aquarium = _state_draw_cattower = _life_state_draw

    # ------------------------------------------------------------ room drawing
    def _home_actors_life(self):
        """homeiso.draw_room seam: the cat, depth-sorted with the furniture."""
        _install_art(self)
        c = self.cat
        if c is None or self.world.current != AREA_HOME:
            return []
        if c.z <= 0.5 and not c.hop and not self._cat_free(int(c.x), int(c.y)):
            return []                              # Build just put a piece on it
        ax, ay = c.x, c.y
        if c.z > 1.0:                              # up on a piece: paint right after it
            q = next((o for o in self.world.home_furniture
                      if F.CAT[o.kind]["layer"] == "ground"
                      and (int(c.x), int(c.y)) in o.cells()), None)
            if q is not None:
                fw, fh = F.footprint(q.kind, q.rot)
                ax, ay = q.gx + q.ox + fw / 2.0 + 0.01, q.gy + q.oy + fh / 2.0 + 0.01

        def draw(scr, ox, oy, c=c):
            from ..homeiso import proj
            sx, sy = proj(ox, oy, c.x, c.y)
            base = c.z
            if c.hop:
                h = c.hop
                base = h[2] + (h[5] - h[2]) * h[7]
            L.draw_cat(scr, sx, sy - c.z, c.pose, c.face, c.frame(), shadow_y=sy - base)
            if c.pose == "sleep":                  # little z's drifting up
                for i in range(2):
                    k = ((c.anim * 0.45) + i * 0.5) % 1.0
                    zx = sx + 8 + k * 8 + math.sin(k * 6) * 2
                    zy = sy - c.z - 18 - k * 14
                    s = 2 + int(k * 2)
                    col = (120, 110, 150) if k < 0.8 else (170, 160, 190)
                    pygame.draw.lines(scr, col, False, [(zx - s, zy - s), (zx + s, zy - s),
                                                        (zx - s, zy + s), (zx + s, zy + s)], 1)
        return [(ax, ay, draw)]

    def _life_art(self, surf, P, kind, where, base, color):
        """isofurn.LIVE_ART for this game's room. True = painted."""
        home = self.world.home_furniture
        if kind == "aquarium":
            cells = set(where)
            fish, feed = {}, {}
            now = _now()
            for q in home:
                if q.kind == "aquarium" and (q.gx, q.gy) in cells:
                    fish[(q.gx, q.gy)] = self._tank_fish(q)
                    t0 = self._aqua_feed.get((q.gx, q.gy))
                    if t0 is not None:
                        feed[(q.gx, q.gy)] = now - t0
            L.paint_tank(surf, P, cells, fish, now, feed)
            return True
        if kind not in PLANT_KINDS:
            return False
        x, y = where
        q = None
        for o in home:
            if o.kind != kind:
                continue
            fw, fh = F.footprint(o.kind, o.rot)
            if F.CAT[o.kind]["layer"] == "top":
                ox_, oy_ = o.gx + 0.5 + o.ox, o.gy + 0.5 + o.oy
            else:
                ox_, oy_ = o.gx + o.ox + fw / 2.0, o.gy + o.oy + fh / 2.0
            if abs(ox_ - x) < 0.02 and abs(oy_ - y) < 0.02:
                q = o
                break
        if q is None or not q.data:
            return False
        st = self._plant_stage(q)
        seed = (q.gx * 7 + q.gy * 13 + q.ci) & 0xff
        t = _now()
        if kind == "vase_flowers":
            wilt = bool(q.data.get("wilt"))
            fc = q.data.get("fc")
            if st == 0 and not wilt and not fc:
                return False
            L.paint_vase(surf, P, x, y, base, color, max(1, st), wilt=wilt, t=t,
                         fcol=tuple(fc) if isinstance(fc, list) and len(fc) == 3 else None,
                         seed=seed)
            return True
        if st == 0:
            return False
        if kind == "plant":
            L.paint_plant(surf, P, x, y, st, t=t, seed=seed)
        else:
            L.paint_cactus(surf, P, x, y, base, st, t=t, seed=seed)
        return True

    # ------------------------------------------------------------ LAN
    def _net_snap_out_life(self):
        c = self.cat
        if c is None:
            return {"CAT": None}
        return {"CAT": [round(c.x, 3), round(c.y, 3), round(c.z, 1),
                        _FACES.index(c.face) if c.face in _FACES else 0, c.pose]}

    def _net_snap_in_life(self, d):
        if "CAT" not in d:
            return
        row = d.get("CAT")
        if not row:
            self.cat = None
            return
        try:
            x, y, z, fi, pose = float(row[0]), float(row[1]), float(row[2]), int(row[3]), str(row[4])
        except (TypeError, ValueError, IndexError):
            return
        c = self.cat
        if c is None:
            c = self.cat = Cat(x, y, z)
        c.tx, c.ty, c.tz = x, y, z
        c.face = _FACES[fi % 4]
        c.pose = pose if pose in L.FRAMES else "sit"
        c.speed = CAT_RUN if pose == "walk" and math.hypot(x - c.x, y - c.y) > 0.3 else CAT_WALK

    def _on_client_update_life(self, dt):
        c = self.cat
        if c is None:
            return
        c.anim += dt
        if (c.tx - c.x) ** 2 + (c.ty - c.y) ** 2 > 4.0:
            c.x, c.y, c.z = c.tx, c.ty, c.tz       # teleported (new day): snap
            return
        k = min(1.0, dt * 14)
        c.x += (c.tx - c.x) * k
        c.y += (c.ty - c.y) * k
        c.z += (c.tz - c.z) * k

    def _net_fx_life(self, m):
        kind = m.get("kind")
        if kind == "catpet":
            if self.world.current == AREA_HOME:
                try:
                    self._cat_pet_fx(float(m.get("x", 0)), float(m.get("y", 0)),
                                     float(m.get("z", 0)), bool(m.get("first")))
                except (TypeError, ValueError):
                    pass
            return True
        if kind == "aqfeed":
            try:
                self._aqua_feed[(int(m.get("gx")), int(m.get("gy")))] = _now()
            except (TypeError, ValueError):
                pass
            return True
        return False

    def _net_menu_life(self, mm, m):
        """Host: a client's aquarium op / cat card action for Player 2."""
        if mm == "aquarium":
            gx, gy = m.get("gx"), m.get("gy")
            fr = next((q for q in self.world.home_furniture
                       if q.kind == "aquarium" and q.gx == gx and q.gy == gy), None)
            if fr is not None:
                op = m.get("op", "")
                self._aqua_op(1, fr, op, str(m.get("item", "")))
            self._net_world_t = 99.0               # resync the client right away
            return True
        if mm == "life":
            op = m.get("op")
            if op == "call":
                self._cat_call(1)                  # (already in Player 2's area context)
            elif op == "name" and isinstance(m.get("name"), str):
                self.cat_name = self._cat_clean_name(m["name"])
                self.ui.log(f"{self.players[1].name} renamed the cat {self.cat_name}!")
                self._net_world_t = 99.0
            return True
        return False

