"""Free-form tabletop placement (Build mode + room render), 2026-09-28.

Small "top" decor (mugs, lamps, frames...) used to hop between four fixed
quarter-cell slots. Now it sits ANYWHERE on a surface, like Unpacking / The
Sims:

* **Surfaces** are every flat-topped piece (furniture.SURFACES), MERGED groups
  as one continuous top (a row of counters is one long worktop, no seams), and
  WALL SHELVES. Each surface is a set of real tile-space rects at a height.
* **Items** have a footprint radius (furniture.top_radius) and never overlap:
  dragging into a crowded spot SLIDES the item to the nearest free place
  instead of refusing, and a full surface finds the closest gap.
* **Snapping**: positions snap to a 1/16-tile grid and MAGNET onto the
  surface's centre lines and the rows/columns of neighbouring items (guide
  lines are returned so Build can draw them). Shift = free placement.
* **Aiming** ray-casts the mouse onto each surface's top plane (tallest /
  nearest first) with a forgiving "sticky" fallback, so pointing at a table
  top really lands on it -- not on the floor tile behind it.

Positions: an item's point is (gx + 0.5 + ox, gy + 0.5 + oy); gx/gy stay the
integer cell under it (so Placed.cells() / furniture_at keep working) and
``data["h"]`` remembers which height it sits at (a shelf over a nightstand).
"""
import math

from . import furniture as F
from . import isofurn

WALL_SHELF_H = 37            # wallart's shelf board top (px above the floor)
WALL_SHELF_D = 0.30          # how far the board sticks out of the wall (tiles)
MAGNET = 0.045               # align-to-neighbour distance (tiles)
PACK = 0.9                   # items may nestle this tight (x sum of radii)


class Surface:
    """One continuous top: rects [(x0, y0, x1, y1, outer)] in tile space,
    `outer` = (left, top, right, bottom) flags -- True where the rect edge is
    a real edge (items keep their radius inside it), False where it joins a
    merged neighbour (items may straddle the seam)."""
    __slots__ = ("kind", "pieces", "rects", "h", "key", "wall", "sid")

    def __init__(self, kind, pieces, rects, h, key, wall=False):
        self.kind = kind
        self.pieces = pieces
        self.rects = rects
        self.h = h
        self.key = key              # (x, y, w, h) depth key of the drawn piece
        self.wall = wall
        self.sid = id(pieces[0])

    # ---- geometry ----
    def contains(self, x, y, slack=0.0):
        return any(r[0] - slack <= x <= r[2] + slack and r[1] - slack <= y <= r[3] + slack
                   for r in self.rects)

    def _inner(self, r, rad):
        x0, y0, x1, y1, (ol, ot, orr, ob) = r
        a, b = x0 + (rad if ol else 0), y0 + (rad if ot else 0)
        c, d = x1 - (rad if orr else 0), y1 - (rad if ob else 0)
        if a > c:
            a = c = (x0 + x1) / 2
        if b > d:
            b = d = (y0 + y1) / 2
        return a, b, c, d

    def fits(self, x, y, rad):
        e = 1e-6
        return any(a - e <= x <= c + e and b - e <= y <= d + e
                   for a, b, c, d in (self._inner(r, rad) for r in self.rects))

    def clamp(self, x, y, rad):
        """Nearest point to (x, y) where an item of radius `rad` fits."""
        best, bd = (x, y), None
        for r in self.rects:
            a, b, c, d = self._inner(r, rad)
            px, py = min(max(x, a), c), min(max(y, b), d)
            dd = (px - x) ** 2 + (py - y) ** 2
            if bd is None or dd < bd:
                best, bd = (px, py), dd
        return best

    def centre(self):
        xs = [r[0] for r in self.rects] + [r[2] for r in self.rects]
        ys = [r[1] for r in self.rects] + [r[3] for r in self.rects]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

    def bounds(self):
        return (min(r[0] for r in self.rects), min(r[1] for r in self.rects),
                max(r[2] for r in self.rects), max(r[3] for r in self.rects))

    def depth(self):
        x, y, w, h = self.key
        return x + y + (w + h) / 2.0


# ------------------------------------------------------------------ surfaces
def _to_real(q, lx, ly):
    """Canonical (rot 0) footprint point -> real tile point for piece q."""
    d = F.CAT[q.kind]
    cw, ch = d["w"], d["h"]
    fw, fh = F.footprint(q.kind, q.rot)
    u, v = lx / cw, ly / ch
    r = q.rot % 4
    gx, gy = q.gx + q.ox, q.gy + q.oy
    if r == 0:
        return gx + u * fw, gy + v * fh
    if r == 1:
        return gx + (1 - v) * fw, gy + u * fh
    if r == 2:
        return gx + (1 - u) * fw, gy + (1 - v) * fh
    return gx + v * fw, gy + (1 - u) * fh


def _piece_rect(q, group_cells=None):
    d = F.CAT[q.kind]
    x0, y0, x1, y1 = F.surface_top_rect(q.kind, d["w"], d["h"])
    ax, ay = _to_real(q, x0, y0)
    bx, by = _to_real(q, x1, y1)
    rx0, ry0, rx1, ry1 = min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
    outer = [True, True, True, True]
    if group_cells:
        # a side that touches another member of the merged group runs right
        # up to the cell edge, so the worktop is seamless across the join
        fw, fh = F.footprint(q.kind, q.rot)
        X0, Y0 = q.gx + q.ox, q.gy + q.oy
        X1, Y1 = X0 + fw, Y0 + fh
        cy = int(math.floor((Y0 + Y1) / 2))
        cx = int(math.floor((X0 + X1) / 2))
        if (int(math.floor(X0)) - 1, cy) in group_cells:
            rx0, outer[0] = X0, False
        if (int(math.ceil(X1)), cy) in group_cells:
            rx1, outer[2] = X1, False
        if (cx, int(math.floor(Y0)) - 1) in group_cells:
            ry0, outer[1] = Y0, False
        if (cx, int(math.ceil(Y1))) in group_cells:
            ry1, outer[3] = Y1, False
    return (rx0, ry0, rx1, ry1, tuple(outer))


def surfaces(world):
    """Every surface in the home right now (merged groups fused)."""
    pieces = world.home_furniture
    out = []
    grouped = {}
    for grp in F.merge_groups(pieces):
        if len(grp) > 1 and grp[0].kind in F.SURFACES:
            for q in grp:
                grouped[id(q)] = grp
    done = set()
    for q in pieces:
        lay = F.CAT[q.kind]["layer"]
        if lay == "ground" and q.kind in F.SURFACES:
            h = isofurn.surface_height(q.kind)
            if not h:
                continue
            grp = grouped.get(id(q))
            if grp:
                if id(grp[0]) in done:
                    continue
                done.add(id(grp[0]))
                cells = F.group_cells(grp)
                rects = [_piece_rect(m, cells) for m in grp]
                x0 = min(c[0] for c in cells)
                y0 = min(c[1] for c in cells)
                key = (x0, y0, max(c[0] for c in cells) + 1 - x0,
                       max(c[1] for c in cells) + 1 - y0)
                out.append(Surface(q.kind, list(grp), rects, h, key))
            else:
                fw, fh = F.footprint(q.kind, q.rot)
                out.append(Surface(q.kind, [q], [_piece_rect(q)], h,
                                   (q.gx + q.ox, q.gy + q.oy, fw, fh)))
        elif lay == "wall" and q.kind == "wall_shelf":
            if q.gy == 0:                    # back wall: along +x, out toward +y
                c = max(1, q.gx)
                r = (c + 0.10, 1.0, c + 0.90, 1.0 + WALL_SHELF_D,
                     (True, True, True, True))
                key = (c, 0.4, 1, 0)
            else:                            # left wall: along +y, out toward +x
                c = max(1, q.gy)
                r = (1.0, c + 0.10, 1.0 + WALL_SHELF_D, c + 0.90,
                     (True, True, True, True))
                key = (0.4, c, 0, 1)
            out.append(Surface(q.kind, [q], [r], WALL_SHELF_H, key, wall=True))
    return out


# ------------------------------------------------------------------ items
def pos(item):
    return item.gx + 0.5 + item.ox, item.gy + 0.5 + item.oy


def set_pos(item, x, y, h=None):
    gx, gy = int(math.floor(x)), int(math.floor(y))
    item.gx, item.gy = gx, gy
    item.ox, item.oy = x - gx - 0.5, y - gy - 0.5
    if h is not None:
        item.data["h"] = h


def support_of(item, surfs):
    """The surface a top item rests on (None = orphaned). Prefers the height
    it was placed at, so a mug on a nightstand never jumps up to the shelf."""
    x, y = pos(item)
    hit = [s for s in surfs if s.contains(x, y, 0.03)]
    if not hit:
        # legacy saves: quarter slots were anchored to their cell only
        hit = [s for s in surfs if not s.wall
               and any((item.gx, item.gy) in p.cells() for p in s.pieces)]
        if not hit:
            return None
    want = item.data.get("h") if isinstance(getattr(item, "data", None), dict) else None
    if want is not None:
        same = [s for s in hit if s.h == want]
        if same:
            return same[0]
    ground = [s for s in hit if not s.wall]
    return (ground or hit)[0]


def items_on(surf, world, surfs, ignore=None):
    return [q for q in world.home_furniture
            if q is not ignore and F.CAT[q.kind]["layer"] == "top"
            and support_of(q, surfs) is surf]


# ------------------------------------------------------------------ solving
def _collides(x, y, rad, others):
    for ox_, oy_, orad in others:
        if (x - ox_) ** 2 + (y - oy_) ** 2 < ((rad + orad) * PACK) ** 2 - 1e-9:
            return True
    return False


def resolve(surf, kind, x, y, others, snap=True):
    """Best free spot for a `kind` item wanted at (x, y) on `surf`.

    others = [(x, y, radius)] already on the surface. Returns
    (x, y, ok, guides) where guides are [(axis, value, a, b)] alignment lines
    ('x' = the line x=value from y=a to b, 'y' likewise) for Build to draw."""
    rad = F.top_radius(kind)
    guides = []
    if snap:
        g = F.TOP_SNAP
        x, y = round(x / g) * g, round(y / g) * g
        # magnets: surface centre lines + neighbours' rows / columns
        cx, cy = surf.centre()
        bx0, by0, bx1, by1 = surf.bounds()
        cand_x = [(cx, (by0, by1))] + [(ox_, (min(oy_, y), max(oy_, y)))
                                        for ox_, oy_, _ in others]
        cand_y = [(cy, (bx0, bx1))] + [(oy_, (min(ox_, x), max(ox_, x)))
                                        for ox_, oy_, _ in others]
        bxs = min(cand_x, key=lambda c: abs(c[0] - x))
        if abs(bxs[0] - x) <= MAGNET:
            x = bxs[0]
            guides.append(("x", x, *bxs[1]))
        bys = min(cand_y, key=lambda c: abs(c[0] - y))
        if abs(bys[0] - y) <= MAGNET:
            y = bys[0]
            guides.append(("y", y, *bys[1]))
    x, y = surf.clamp(x, y, rad)
    # push out of neighbours (slides along them), re-clamping each pass
    for _ in range(14):
        moved = False
        for ox_, oy_, orad in others:
            need = (rad + orad) * PACK
            dx, dy = x - ox_, y - oy_
            d = math.hypot(dx, dy)
            if d < need - 1e-9:
                if d < 1e-6:
                    dx, dy, d = 0.6, 0.8, 1.0
                x, y = ox_ + dx / d * need, oy_ + dy / d * need
                x, y = surf.clamp(x, y, rad)
                moved = True
        if not moved:
            break
    if not _collides(x, y, rad, others) and surf.fits(x, y, rad):
        # a guide only counts if the item really stayed on it
        guides = [gd for gd in guides
                  if abs((x if gd[0] == "x" else y) - gd[1]) < 1e-6]
        return x, y, True, guides
    # crowded: nearest free spot on a spiral around the wish
    sx, sy = surf.clamp(x, y, rad)
    best = None
    for ring in range(1, 30):
        r = ring * 0.035
        n = 8 + ring * 2
        for i in range(n):
            a = i * 2 * math.pi / n
            px, py = surf.clamp(sx + math.cos(a) * r, sy + math.sin(a) * r, rad)
            if not _collides(px, py, rad, others) and surf.fits(px, py, rad):
                dd = (px - sx) ** 2 + (py - sy) ** 2
                if best is None or dd < best[0]:
                    best = (dd, px, py)
        if best:
            return best[1], best[2], True, []
    return sx, sy, False, []


def others_on(surf, world, surfs, ignore=None):
    return [(*pos(q), F.top_radius(q.kind))
            for q in items_on(surf, world, surfs, ignore)]


# ------------------------------------------------------------------ aiming
def aim(area, surfs, sx, sy, screen_to_point, proj_fn, sticky_px=30):
    """(surface, x, y) the mouse points at, or (None, fx, fy) on the floor.

    Every surface's top plane is intersected with the mouse ray; the hit
    nearest the camera wins (a lamp on the front table, not the shelf behind
    it). Missing every top by a little still sticks to the closest one."""
    hits = []
    for s in surfs:
        fx, fy = screen_to_point(area, sx, sy + s.h)
        if s.contains(fx, fy, 0.05):
            hits.append((s.depth() + s.h * 1e-3, s, fx, fy))
    if hits:
        _, s, fx, fy = max(hits, key=lambda h: h[0])
        return s, fx, fy
    best = None
    for s in surfs:
        fx, fy = screen_to_point(area, sx, sy + s.h)
        px, py = s.clamp(fx, fy, 0.0)
        qx, qy = proj_fn(px, py)
        d = math.hypot(qx - sx, qy - s.h - sy)
        if d <= sticky_px and (best is None or d < best[0]):
            best = (d, s, px, py)
    if best:
        return best[1], best[2], best[3]
    fx, fy = screen_to_point(area, sx, sy)
    return None, fx, fy


def carry_on_rotate(world, piece, old_rot):
    """A surface was rotated in place: turn its tabletop items with it (about
    the piece centre, facing too), then settle them inside the new top."""
    fw0, fh0 = F.footprint(piece.kind, old_rot)
    fw1, fh1 = F.footprint(piece.kind, piece.rot)
    x0, y0 = piece.gx + piece.ox, piece.gy + piece.oy
    old = F.Placed(piece.kind, piece.gx, piece.gy, old_rot, piece.ci,
                   ox=piece.ox, oy=piece.oy)
    world_old = _Shim([q for q in world.home_furniture if q is not piece] + [old])
    surfs_old = surfaces(world_old)
    s_old = next((s for s in surfs_old if old in s.pieces), None)
    if s_old is None:
        return
    moved = [q for q in world.home_furniture
             if F.CAT[q.kind]["layer"] == "top" and support_of(q, surfs_old) is s_old]
    if not moved:
        return
    cx0, cy0 = x0 + fw0 / 2, y0 + fh0 / 2
    cx1, cy1 = x0 + fw1 / 2, y0 + fh1 / 2
    turns = (piece.rot - old_rot) % 4
    for q in moved:
        x, y = pos(q)
        dx, dy = x - cx0, y - cy0
        for _ in range(turns):               # +90deg in iso tile space
            dx, dy = -dy, dx
        set_pos(q, cx1 + dx, cy1 + dy)
        q.rot = (q.rot + turns) % 4
    settle(world)


def settle(world, only=None):
    """Re-seat tabletop items so none overlap or hang off an edge (after a
    table moved/rotated or an old save loaded)."""
    surfs = surfaces(world)
    by_surf = {}
    for q in world.home_furniture:
        if F.CAT[q.kind]["layer"] != "top" or (only is not None and q not in only):
            continue
        s = support_of(q, surfs)
        if s is not None:
            by_surf.setdefault(s.sid, (s, []))[1].append(q)
    for s, qs in by_surf.values():
        placed = [(*pos(q), F.top_radius(q.kind)) for q in world.home_furniture
                  if F.CAT[q.kind]["layer"] == "top" and q not in qs
                  and support_of(q, surfs) is s]
        for q in qs:
            x, y = pos(q)
            nx, ny, ok, _ = resolve(s, q.kind, x, y, placed, snap=False)
            if ok:
                set_pos(q, nx, ny, s.h)
                placed.append((nx, ny, F.top_radius(q.kind)))


class _Shim:
    __slots__ = ("home_furniture",)

    def __init__(self, pieces):
        self.home_furniture = pieces
