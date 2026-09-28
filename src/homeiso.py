"""Isometric render of the HOME interior, shared by the play view AND Build mode
so decorating looks exactly like playing.

The world stays a normal top-down grid -- movement, collision and furniture data
are unchanged. This module only PROJECTS the home into an isometric view: a
diamond parquet floor with two angled walls you can decorate, like a cosy
LINE-PLAY room. Build mode reuses the same projection for the grid, the placement
ghost and selection so the two views match.
"""
import math
import pygame
from .settings import SCREEN_W, SCREEN_H
from . import furniture as F
from . import isofurn
from . import wallart
from . import tabletop
from .assets import chars

TW, TH = 64, 32        # iso tile diamond (width, height)
WALLH = 72             # wall height in px


class _Cam:
    """A throwaway camera so we can reuse Player.draw() at an iso position."""
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y


# ---------------------------------------------------------------- projection
def origin(area):
    cx = (area.w - 1) / 2.0
    cy = (area.h - 1) / 2.0
    ox = SCREEN_W // 2 - int((cx - cy) * (TW // 2))
    oy = SCREEN_H // 2 - int((cx + cy) * (TH // 2)) + 28
    return ox, oy


def proj(ox, oy, gx, gy):
    return (ox + int((gx - gy) * (TW // 2)), oy + int((gx + gy) * (TH // 2)))


def screen_to_point(area, sx, sy):
    """Inverse projection to FRACTIONAL tile coords (no floor) -- lets Build
    mode know exactly where inside a tile the mouse points (corner slots)."""
    ox, oy = origin(area)
    u = (sx - ox) / (TW / 2.0)
    v = (sy - oy) / (TH / 2.0)
    return (u + v) / 2.0, (v - u) / 2.0


def screen_to_cell(area, sx, sy):
    """Inverse projection: which floor tile is under a screen point."""
    gx, gy = screen_to_point(area, sx, sy)
    return int(math.floor(gx)), int(math.floor(gy))


def foot_quad(ox, oy, gx, gy, fw, fh):
    """The four iso corners bounding a (fw x fh) footprint at (gx,gy)."""
    return [proj(ox, oy, gx, gy), proj(ox, oy, gx + fw, gy),
            proj(ox, oy, gx + fw, gy + fh), proj(ox, oy, gx, gy + fh)]


def wall_anchor(ox, oy, area, gx, gy):
    """Screen midpoint for a wall-decor cell: (gx,0)->back wall, (0,gy)->left wall."""
    x0, y0 = 1, 1
    if gy == 0:                                  # back (top-right) wall
        c = max(x0, min(area.w - 2, gx))
        a, b = proj(ox, oy, c, y0), proj(ox, oy, c + 1, y0)
    else:                                        # left (top-left) wall
        c = max(y0, min(area.h - 2, gy))
        a, b = proj(ox, oy, x0, c), proj(ox, oy, x0, c + 1)
    return ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2 - WALLH // 2)


def _shades(world):
    wall = F.WALL_COLORS[world.home_wall_idx]
    floor = F.FLOOR_COLORS[world.home_floor_idx]
    return {
        "wall": wall, "wlt": tuple(min(255, c + 16) for c in wall),
        "wdk": tuple(max(0, c - 34) for c in wall),
        "fl1": tuple(min(255, c + 14) for c in floor), "fl2": floor,
        "fed": tuple(max(0, c - 26) for c in floor),
    }


# ---------------------------------------------------------------- pieces
def billboard_metrics(ox, oy, gx, gy, fw, fh, spr):
    cx = (proj(ox, oy, gx, gy)[0] + proj(ox, oy, gx + fw, gy + fh)[0]) // 2
    base = proj(ox, oy, gx + fw, gy + fh)[1]
    w = max(10, int((fw + fh) * TW * 0.32))
    h = max(10, int(spr.get_height() * w / spr.get_width()))
    return cx, base, w, h


def blit_piece(scr, ox, oy, gx, gy, fw, fh, spr, lay, alpha=255):
    cx, base, w, h = billboard_metrics(ox, oy, gx, gy, fw, fh, spr)
    s = pygame.transform.smoothscale(spr, (w, h))
    if alpha < 255:
        s = s.copy()
        s.set_alpha(alpha)
    if lay != "floor":
        sh = pygame.Surface((w, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 55), (3, 3, w - 6, 11))
        scr.blit(sh, (cx - w // 2, base - 9))
    scr.blit(s, (cx - w // 2, base - h + 3))


def outline(scr, ox, oy, gx, gy, fw, fh, color, width=3, fill=None, lift=0):
    """Highlight a footprint. `lift` raises the quad (px) -- used so tabletop
    decor highlights sit ON the furniture's top, not on the floor."""
    quad = [(px, py - lift) for (px, py) in foot_quad(ox, oy, gx, gy, fw, fh)]
    if fill is not None:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.polygon(ov, fill, quad)
        scr.blit(ov, (0, 0))
    pygame.draw.polygon(scr, color, quad, width)


def draw_grid(scr, ox, oy, area):
    x0, x1, y0, y1 = 1, area.w - 1, 1, area.h - 1
    col = (255, 255, 255, 40)
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for gx in range(x0, x1 + 1):
        pygame.draw.line(ov, col, proj(ox, oy, gx, y0), proj(ox, oy, gx, y1), 1)
    for gy in range(y0, y1 + 1):
        pygame.draw.line(ov, col, proj(ox, oy, x0, gy), proj(ox, oy, x1, gy), 1)
    scr.blit(ov, (0, 0))


# ---------------------------------------------------------------- room
def draw_shell(scr, world, ox, oy, grid=False, sky=None, minutes=None, bare=()):
    """Floor + two walls + (optional) build grid + wall decor. `sky`
    (wallart.sky_key) tints the window glass, `minutes` sets the clock."""
    area = world.areas[world.current] if hasattr(world, "areas") else world.area
    c = _shades(world)
    x0, x1, y0, y1 = 1, area.w - 1, 1, area.h - 1

    # two back walls (behind the floor)
    for gx in range(x0, x1):
        a, b = proj(ox, oy, gx, y0), proj(ox, oy, gx + 1, y0)
        quad = [(a[0], a[1] - WALLH), (b[0], b[1] - WALLH), (b[0], b[1]), (a[0], a[1])]
        pygame.draw.polygon(scr, c["wall"] if gx % 2 else c["wlt"], quad)
        pygame.draw.polygon(scr, c["wdk"], quad, 1)
    for gy in range(y0, y1):
        a, b = proj(ox, oy, x0, gy), proj(ox, oy, x0, gy + 1)
        quad = [(a[0], a[1] - WALLH), (b[0], b[1] - WALLH), (b[0], b[1]), (a[0], a[1])]
        pygame.draw.polygon(scr, c["wlt"] if gy % 2 else c["wall"], quad)
        pygame.draw.polygon(scr, c["wdk"], quad, 1)
    cp = proj(ox, oy, x0, y0)
    pygame.draw.line(scr, c["wdk"], (cp[0], cp[1] - WALLH), cp, 2)

    # diamond parquet floor
    for gy in range(y0, y1):
        for gx in range(x0, x1):
            q = [proj(ox, oy, gx, gy), proj(ox, oy, gx + 1, gy),
                 proj(ox, oy, gx + 1, gy + 1), proj(ox, oy, gx, gy + 1)]
            pygame.draw.polygon(scr, c["fl1"] if (gx + gy) % 2 == 0 else c["fl2"], q)
            pygame.draw.polygon(scr, c["fed"], q, 1)

    # ---- depth dressing (makes the flat room read as a 3D diorama) ----
    def _dkc(col, f):
        return tuple(max(0, int(v * f)) for v in col)

    # 1) the floor is a SLAB: visible thickness along the south + east edges
    for a, b in ((proj(ox, oy, x0, y1), proj(ox, oy, x1, y1)),
                 (proj(ox, oy, x1, y1), proj(ox, oy, x1, y0))):
        quad = [a, b, (b[0], b[1] + 12), (a[0], a[1] + 12)]
        pygame.draw.polygon(scr, _dkc(c["fl2"], 0.45), quad)
        pygame.draw.polygon(scr, _dkc(c["fl2"], 0.30), quad, 1)
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    bb0, bb1 = proj(ox, oy, x0, y0), proj(ox, oy, x1, y0)    # wall feet
    lb1 = proj(ox, oy, x0, y1)
    gh = int(WALLH * 0.30)
    # 2) walls darken toward their base (cheap vertical gradient)
    pygame.draw.polygon(ov, (30, 26, 40, 26),
                        [(bb0[0], bb0[1] - gh), (bb1[0], bb1[1] - gh), bb1, bb0])
    pygame.draw.polygon(ov, (30, 26, 40, 26),
                        [(bb0[0], bb0[1] - gh), (lb1[0], lb1[1] - gh), lb1, bb0])
    # 3) ambient occlusion: the floor is darkest where it meets the walls
    ao = 0.45
    pygame.draw.polygon(ov, (30, 26, 40, 30),
                        [bb0, bb1, proj(ox, oy, x1, y0 + ao),
                         proj(ox, oy, x0 + ao, y0 + ao)])
    pygame.draw.polygon(ov, (30, 26, 40, 30),
                        [bb0, lb1, proj(ox, oy, x0 + ao, y1),
                         proj(ox, oy, x0 + ao, y0 + ao)])
    scr.blit(ov, (0, 0))

    if grid:
        draw_grid(scr, ox, oy, area)

    # wall-mounted decor: real 3D pieces modelled in the wall's own plane
    # (frames with thickness, a recessed window, a shelf that sticks out...)
    for pl in world.home_furniture:
        if F.CAT[pl.kind]["layer"] != "wall":
            continue
        # wall lights default ON until the player toggles them; other wall
        # decor has no power state so it always renders lit
        won = pl.on or pl.kind not in F.TOGGLE
        blit_wall(scr, ox, oy, area, pl.kind, pl.color, pl.gx, pl.gy, on=won,
                  sky=sky, minutes=minutes, bare=id(pl) in bare)


def wall_side(gx, gy):
    """Which wall a wall-decor cell hangs on (matches wall_anchor)."""
    return "back" if gy == 0 else "left"


def blit_wall(scr, ox, oy, area, kind, color, gx, gy, on=True, alpha=255,
              sky=None, minutes=None, bare=False):
    """Draw one wall piece on its wall cell (the room and Build's ghost)."""
    x0, y0 = 1, 1
    if wall_side(gx, gy) == "back":
        c = max(x0, min(area.w - 2, gx))
        foot = proj(ox, oy, c, y0)
    else:
        c = max(y0, min(area.h - 2, gy))
        foot = proj(ox, oy, x0, c + 1)
    wallart.blit(scr, foot, kind, color, wall_side(gx, gy), on=on,
                 sky=sky or ("day", "sunny"), minutes=minutes, alpha=alpha,
                 bare=bare)


# ---- tabletop feel: items dropped in Build land with a little bounce, and an
# item held in the hand floats above its spot (Build sets these) ----
DROP = {}            # id(item) -> ticks (ms) it was put down
LIFT = {}            # id(item) -> px it is held above its surface


def _drop_puff(scr, ox, oy, pl, x, y, h):
    """A soft ring of dust where a dropped item just landed."""
    t0 = DROP.get(id(pl))
    if t0 is None:
        return
    t = (pygame.time.get_ticks() - t0) / 1000.0
    if not 0.12 <= t < 0.42:
        return
    k = (t - 0.12) / 0.30
    cx, cy = proj(ox, oy, x, y)
    cy -= h
    r = 5 + 9 * k
    lay = pygame.Surface((int(r * 2 + 4), int(r + 4)), pygame.SRCALPHA)
    pygame.draw.ellipse(lay, (255, 250, 236, int(150 * (1 - k))),
                        (2, 2, int(r * 2), int(r)), 2)
    scr.blit(lay, (cx - r - 2, cy - r / 2 - 2))


def top_lift(pl):
    """Extra height (px) for a tabletop item right now: held = floating,
    just dropped = a quick fall + two small bounces."""
    k = id(pl)
    if k in LIFT:
        return LIFT[k]
    t0 = DROP.get(k)
    if t0 is None:
        return 0
    t = (pygame.time.get_ticks() - t0) / 1000.0
    if t >= 0.42:
        DROP.pop(k, None)
        return 0
    if t < 0.14:                                # the fall
        return int(9 * (1 - t / 0.14) ** 2)
    t2 = t - 0.14                               # damped bounces
    return int(abs(math.sin(t2 * 22)) * 3 * math.exp(-t2 * 9))


# seat-front distance from the seat centre per kind (tile units): the knees
# land a touch PAST it, so the shins hang just clear of the seat's edge
_SEAT_EDGE = {"chair": 0.30, "stool": 0.30, "piano_bench": 0.30, "bench": 0.34,
              "sofa": 0.36, "armchair": 0.36}
_KNEE_OVER = 0.06               # knees overhang the front edge (real sitting)
_LEG_HALF = 0.062               # half-width of one leg, across the lap
_LEG_GAP = 0.085                # leg centre offset from the body's mid-line
# the trousers/shoes as lit 3D boxes: a notch lighter than the flat standing
# sprite's PANTS/SHOE so the lap's top face and the shin sides still read
_LEG_COL = (78, 68, 98)
_SHOE_COL = (56, 48, 64)


def _leg_boxes(sx, sy, st, f, kind):
    """The seated legs as real tile-space boxes (thigh along the seat, shin
    straight down in front of the knee, shoe on the floor): [(x0,y0,x1,y1,z0,
    z1,color)], far leg first. `f` = the facing (unit grid vector)."""
    knee = _SEAT_EDGE.get(kind, 0.30) + _KNEE_OVER
    if f == (0, 1):
        knee -= 0.06            # camera-facing sitters already slid forward
    lx, ly = abs(f[1]), abs(f[0])               # lateral axis (toward camera = +)
    # chibi shins are short: on a tall seat the feet dangle a little above the
    # floor (cute, and it reads as SITTING); on low seats they rest on it
    foot = max(0, st - 12)

    def rect(a0, a1, b0, b1):
        """Box spanning a0..a1 along the facing and b0..b1 across it."""
        xs = [sx + f[0] * a + lx * b for a in (a0, a1) for b in (b0, b1)]
        ys = [sy + f[1] * a + ly * b for a in (a0, a1) for b in (b0, b1)]
        return min(xs), min(ys), max(xs), max(ys)

    out = []
    for side in (-1, 1):                         # -lateral leg is the far one
        c = side * _LEG_GAP
        b0, b1 = c - _LEG_HALF, c + _LEG_HALF
        out.append(rect(knee - 0.11, knee + 0.06, b0 - 0.01, b1 + 0.01)
                   + (foot, foot + 3, _SHOE_COL))
        out.append(rect(knee - 0.09, knee, b0, b1) + (foot + 3, st, _LEG_COL))
        out.append(rect(-0.04, knee, b0, b1) + (st, st + 4, _LEG_COL))
    return out


def _draw_leg_boxes(scr, ox, oy, boxes):
    def P(a, b):
        return proj(ox, oy, a, b)
    for x0, y0, x1, y1, z0, z1, col in boxes:
        isofurn._box(scr, P, x0, y0, x1, y1, z1 - z0, col, base=z0)


def _sitter_ops(scr, ox, oy, p, sx, sy, st, kind="chair"):
    """[(bbox, draw-fn), ...] ops for a seated player, slotted into the seat
    piece's OWN depth-sorted parts: backrest behind the body, armrests / the
    front edge over the hips. The pose follows the room's diagonals (see
    chars._draw_seated): an upper-body sprite on top of 3D leg boxes. When the
    player faces AWAY ('up'/'left') the legs hang on the FAR side, so they are
    a separate op that sorts before the seat -- the seat hides the shins and
    only the feet peek out underneath.
    Each fn carries a .role ('body' / 'legs' / 'ghost') for tests & callers."""
    d = ("up" if p.fy < 0 else "down" if p.fy > 0
         else "left" if p.fx < 0 else "right")
    fx = 1 if d == "right" else -1 if d == "left" else 0
    fy = 1 if d == "down" else -1 if d == "up" else 0
    isx, isy = proj(ox, oy, sx, sy)
    top_left = (isx - chars.seated_frames(p.appearance)[d].get_width() // 2,
                isy - st - chars.SEATED_HIP_Y)
    legs = _leg_boxes(sx, sy, st, (fx, fy), kind)
    away = d in ("up", "left")

    def body():
        if not away:                            # lap + shins in front: under the
            _draw_leg_boxes(scr, ox, oy, legs)  # torso, which then rests its
        scr.blit(chars.seated_frames(p.appearance)[d], top_left)   # hands on them
    body.role = "body"
    ops = []
    if away:
        def legs_fn():
            _draw_leg_boxes(scr, ox, oy, legs)
        legs_fn.role = "legs"
        # the shins' real box, clipped at the seat's front edge so every seat
        # part sorts in front of it (the far chair legs too)
        edge = _SEAT_EDGE.get(kind, 0.30)
        knee = edge + _KNEE_OVER
        w = _LEG_GAP + _LEG_HALF + 0.01
        if fy:
            lb = (sx - w, sy - knee - 0.07, sx + w, sy - edge)
        else:
            lb = (sx - knee - 0.07, sy - w, sx - edge, sy + w)
        ops.append((lb + (0, st), legs_fn))
    # the body sits ON the cushion (z starts at the seat top, so the cushion
    # cleanly z-sorts below it).
    # small leggy seats: the sitter's box must OVERLAP the thin legs (so they sort
    # as "below" by z) -- a box that merely touches a front leg would make that
    # leg, and everything flushed after it (the seat!), paint over the torso
    hw = 0.21 if kind in ("chair", "stool", "piano_bench") else 0.18
    # ...but toward the BACKREST the box may only reach as far as the seat's
    # back cushion / backrest face: a symmetric box overlapped the sofa's back
    # cushion (it ends exactly at the seat centre), the depth fallback then
    # ranked that cushion nearer and it painted over the whole torso (rot 0
    # left cushion, rot 3 far cushion -- the default house sofa). Stopping the
    # box at the cushion face lets the x/y rule separate them cleanly: back
    # cushion behind a camera-facing sitter, in front of an away-facing one.
    bk = _BACK_REACH.get(kind, hw)
    box = (sx - (bk if fx > 0 else hw), sy - (bk if fy > 0 else hw),
           sx + (bk if fx < 0 else hw), sy + (bk if fy < 0 else hw))
    ops.append((box + (st, st + 34), body))
    if away and kind in _BACK_REACH:
        # facing AWAY: the backrest sits between the camera and the sitter
        # and hides everything but the head. Paint a see-through silhouette
        # of the HIDDEN part of the body over it (Sims-style x-ray) so the
        # farmer visibly sits IN the seat; the box lies past every part of
        # the piece, so this op always flushes last.
        def ghost():
            _blit_ghost(scr, p.appearance, d, top_left)
        ghost.role = "ghost"
        ops.append(((sx + 9, sy + 9, sx + 9.1, sy + 9.1, 0, 1), ghost))
    return ops


# how far a sitter's depth box may reach toward the backrest, per seat kind
# with a back: sofa/armchair back cushions end exactly at the seat centre, the
# chair's thin backrest face sits 0.20 behind it (backless seats: symmetric)
_BACK_REACH = {"sofa": 0.0, "armchair": 0.0, "chair": 0.20}

_GHOSTS = {}
GHOST_CUT = chars.SEATED_HIP_Y - 2      # ghost rows stop above the resting hands
GHOST_FADE = (0.55,)                    # alpha factor(s) of the last row(s), bottom up
GHOST_LIGHT = 0.30                      # how far the x-ray colours lift toward white


def _ghost_frame(appearance, d, fill_a=176, line_a=190):
    """(image, mask) for the x-ray silhouette of a seated body: the UPPER body
    only (rows above the hands -- the dangling legs and hands really are
    hidden by the seat), colours lifted ~30% toward white so it reads the
    same on a navy or a pink cushion, ringed by a 1px dark outline so it
    still reads on a white one; the bottom row fades. Cached per look."""
    key = (tuple(sorted((k, v) for k, v in appearance.items() if k != "name")), d)
    got = _GHOSTS.get(key)
    if got is None:
        src = chars.seated_frames(appearance)[d]
        w, h = src.get_size()
        cut = pygame.Rect(0, 0, w, GHOST_CUT)
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        img.blit(src, (0, 0), cut)
        # lerp GHOST_LIGHT toward white (c*(1-k) + 255k), opaque alpha -> fill_a
        keep = int(round(255 * (1 - GHOST_LIGHT)))
        img.fill((keep, keep, keep, fill_a), special_flags=pygame.BLEND_RGBA_MULT)
        img.fill((255 - keep,) * 3 + (0,), special_flags=pygame.BLEND_RGBA_ADD)
        # outline = silhouette minus its 4-neighbour erosion (of the FULL body,
        # so the crop line itself gets no outline), kept above the cut
        full = pygame.mask.from_surface(src)
        er = full.copy()
        for off in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            er = er.overlap_mask(full, off)
        edge = full.copy()
        edge.erase(er, (0, 0))
        edge = edge.overlap_mask(pygame.mask.Mask(cut.size, fill=True), (0, 0))
        edge.to_surface(img, setcolor=(44, 34, 58, line_a), unsetcolor=None)
        for i, k in enumerate(GHOST_FADE):         # soft fade into the seat
            img.fill((255, 255, 255, int(255 * k)),
                     pygame.Rect(0, GHOST_CUT - 1 - i, w, 1),
                     special_flags=pygame.BLEND_RGBA_MULT)
        mask = pygame.mask.from_surface(src).overlap_mask(
            pygame.mask.Mask(cut.size, fill=True), (0, 0))
        got = (img, mask)
        if len(_GHOSTS) > 32:
            _GHOSTS.clear()
        _GHOSTS[key] = got
    return got


def _blit_ghost(scr, appearance, d, top_left):
    """Paint the x-ray silhouette ONLY where the seated body (already drawn at
    top_left) ended up covered by the seat: pixels that no longer match the
    body frame. The visible head stays crisp; the torso behind the backrest
    shows through as a light, outlined silhouette."""
    img, mask = _ghost_frame(appearance, d)
    frame = chars.seated_frames(appearance)[d]
    r = pygame.Rect(top_left, frame.get_size())
    if not scr.get_rect().contains(r):
        return                          # half off-screen: skip the nicety
    same = pygame.mask.from_threshold(scr.subsurface(r), (0, 0, 0, 0),
                                      (4, 4, 4, 255), othersurface=frame)
    hidden = mask.copy()
    hidden.erase(same, (0, 0))
    if hidden.count():
        scr.blit(hidden.to_surface(setsurface=img, unsetcolor=(0, 0, 0, 0)), r)


def top_height(kind):
    """Re-export of isofurn.surface_height for Build mode."""
    return isofurn.surface_height(kind)


def draw_top_piece(scr, ox, oy, x, y, kind, color, base, alpha=255, rot=0, on=False):
    """Draw one tabletop item (used by the room and the Build ghost)."""
    def Pf(a, b):
        return proj(ox, oy, a, b)
    if alpha >= 255:
        isofurn.draw_top(scr, Pf, x, y, kind, color, base, on=on, rot=rot)
    else:
        tmp = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        isofurn.draw_top(tmp, Pf, x, y, kind, color, base, on=on, rot=rot)
        tmp.set_alpha(alpha)
        scr.blit(tmp, (0, 0))


def draw_group_piece(scr, ox, oy, kind, color, cells, rot=0, alpha=255, on=False):
    """Draw a merged group (used by Build mode's merge-preview ghost)."""
    def Pf(a, b):
        return proj(ox, oy, a, b)
    if alpha >= 255:
        isofurn.draw_group(scr, Pf, kind, color, cells, rot, on=on)
    else:
        tmp = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        isofurn.draw_group(tmp, Pf, kind, color, cells, rot, on=on)
        tmp.set_alpha(alpha)
        scr.blit(tmp, (0, 0))


def draw_piece(scr, ox, oy, gx, gy, fw, fh, kind, color, alpha=255, rot=0,
               on=False):
    """Draw one iso 3D furniture piece (used by the room and the Build ghost)."""
    def Pf(a, b):
        return proj(ox, oy, a, b)
    if alpha >= 255:
        isofurn.draw(scr, Pf, gx, gy, fw, fh, kind, color, rot, on=on)
    else:
        tmp = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        isofurn.draw(tmp, Pf, gx, gy, fw, fh, kind, color, rot, on=on)
        tmp.set_alpha(alpha)
        scr.blit(tmp, (0, 0))


def draw_room(game, build=False, players=True):
    scr = game.screen
    world = game.world
    area = world.area
    ox, oy = origin(area)
    t = getattr(game, "time", None)
    minutes = getattr(t, "minutes", None)
    surfs = tabletop.surfaces(world)
    bare = set()                                 # wall shelves someone decorated
    for q in world.home_furniture:
        if F.CAT[q.kind]["layer"] == "top":
            sp = tabletop.support_of(q, surfs)
            if sp is not None and sp.wall:
                bare.add(sp.sid)
    draw_shell(scr, world, ox, oy, grid=build, minutes=minutes,
               sky=wallart.sky_key(minutes, getattr(game, "weather", None)),
               bare=bare)

    def Pf(a, b):
        return proj(ox, oy, a, b)

    # mergeable pieces (same kind+colour, touching) fuse into seamless groups:
    # rugs lose their inner seams, chests/counters/tables become one long piece
    grouped = {}                                # id(piece) -> its merge group
    for grp in F.merge_groups(world.home_furniture):
        if len(grp) > 1:
            for pl in grp:
                grouped[id(pl)] = grp
    done = set()                                # groups already drawn this frame

    def _group_rot(grp):
        """The group's facing = most common rot of its pieces (ties -> lowest);
        lets a merged sofa keep the direction the player rotated it to."""
        rots = [q.rot % 4 for q in grp]
        return max(sorted(set(rots)), key=rots.count)

    def group_of(pl):
        """The piece's merge group if it should be drawn as one (first member
        encountered draws the whole group, the rest are skipped)."""
        grp = grouped.get(id(pl))
        if grp is None:
            return None
        if id(grp[0]) in done:
            return ()                           # already drawn -> skip piece
        done.add(id(grp[0]))
        return grp

    # rugs (floor layer) lie flat under everything
    for pl in world.home_furniture:
        if F.CAT[pl.kind]["layer"] != "floor":
            continue
        grp = group_of(pl)
        if grp == ():
            continue
        if grp:
            isofurn.draw_group(scr, Pf, pl.kind, pl.color, F.group_cells(grp),
                               _group_rot(grp), on=any(q.on for q in grp))
        else:
            fw, fh = F.footprint(pl.kind, pl.rot)
            isofurn.draw(scr, Pf, pl.gx, pl.gy, fw, fh, pl.kind, pl.color,
                         pl.rot, on=pl.on)

    # soft contact shadows under every solid piece + the players, drawn over
    # the rugs but under the furniture itself. pygame.draw on a SRCALPHA layer
    # WRITES alpha (no blending), so overlapping shadows never double-darken.
    sh = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for pl in world.home_furniture:
        if F.CAT[pl.kind]["layer"] != "ground":
            continue
        fw, fh = F.footprint(pl.kind, pl.rot)
        sx, sy = pl.gx + pl.ox, pl.gy + pl.oy
        for grow, a in ((0.16, 22), (0.05, 40)):    # soft fringe + dark core
            qx0, qy0 = sx - grow + 0.08, sy - grow + 0.08
            qx1, qy1 = sx + fw + grow + 0.08, sy + fh + grow + 0.08
            pygame.draw.polygon(sh, (24, 20, 34, a),
                                [proj(ox, oy, qx0, qy0), proj(ox, oy, qx1, qy0),
                                 proj(ox, oy, qx1, qy1), proj(ox, oy, qx0, qy1)])
    if players:
        for p in game.players:
            if getattr(p, "sitting", None):
                continue                # seated: the furniture's shadow covers it
            pt = proj(ox, oy, p.x / 48.0, p.y / 48.0)
            pygame.draw.ellipse(sh, (24, 20, 34, 44),
                                (pt[0] - 10, pt[1] - 5, 20, 10))
    scr.blit(sh, (0, 0))

    # players seated on furniture are rendered INSIDE their seat's part list
    # (backrest behind, armrests/front edge in front) -- collect them per piece
    sitters = {}
    if players:
        for p in game.players:
            sit = getattr(p, "sitting", None)
            if sit and any(q is sit[0] for q in world.home_furniture):
                sitters.setdefault(id(sit[0]), []).append(
                    (p, sit[1], sit[2], F.SEAT_TOP.get(sit[0].kind, 16),
                     sit[0].kind))

    # depth-sorted ground furniture + players (the bed is a normal piece now,
    # drawn from home_furniture like everything else)
    items = []
    for pl in world.home_furniture:
        lay = F.CAT[pl.kind]["layer"]
        if lay in ("wall", "floor"):
            continue
        if lay == "top":
            # tabletop decor: drawn at its surface's top height, depth-keyed a
            # hair PAST the surface (and by its own spot among its neighbours)
            # so it paints right after the piece it stands on
            sup = tabletop.support_of(pl, surfs)
            px, py = tabletop.pos(pl)
            if sup:
                kx, ky, sfw, sfh = sup.key
                base = sup.h
                dgx, dgy = kx + 0.01 + (px + py) * 1e-4, ky + 0.01
            else:
                sfw = sfh = 1
                base = 0
                dgx, dgy = pl.gx, pl.gy
            items.append((dgx, dgy, pl.kind, pl.color, sfw, sfh, "top",
                          (px, py, base + top_lift(pl), pl.on, pl.rot, pl), 0))
            continue
        grp = group_of(pl)
        if grp == ():
            continue
        if grp:
            cells = F.group_cells(grp)
            x0 = min(c[0] for c in cells)
            y0 = min(c[1] for c in cells)
            bw = max(c[0] for c in cells) + 1 - x0
            bh = max(c[1] for c in cells) + 1 - y0
            gsit = [s for q in grp for s in sitters.get(id(q), ())]
            items.append((x0, y0, pl.kind, pl.color, bw, bh, "group",
                          (cells, any(q.on for q in grp), gsit), _group_rot(grp)))
        else:
            # gx/gy carry the half-tile centre-snap offset so a snapped chair
            # draws (and depth-sorts) exactly where it sits
            cont = tuple(pl.store)[:9] if (pl.kind == "fridge" and pl.on) else None
            items.append((pl.gx + pl.ox, pl.gy + pl.oy, pl.kind, pl.color,
                          *F.footprint(pl.kind, pl.rot), lay,
                          (pl.on, sitters.get(id(pl)), cont), pl.rot))
    if players:
        for p in game.players:
            # (p.x, p.y) IS the player's feet point in pixels (entities.rect()/
            # target_tile() are built around it), so pass it through UNCHANGED.
            # fw=fh=0 so depth() compares the feet point itself against each
            # furniture centre, which orders a standing player correctly.
            # A SITTING player renders at the seat point instead (their real
            # position is untouched, so save/collision/net stay consistent).
            if id(p) in {id(s[0]) for ss in sitters.values() for s in ss}:
                continue                # seated: drawn as part of the seat piece
            items.append((p.x / 48.0, p.y / 48.0, None, None, 0, 0,
                          "player", p, 0))

    def depth(it):
        return it[0] + it[1] + (it[4] + it[5]) / 2.0

    for it in sorted(items, key=depth):
        gx, gy, kind, col, fw, fh, lay, obj, rot = it
        if lay == "player":
            isx, isy = proj(ox, oy, gx, gy)     # feet -> same iso point, no shift
            obj.draw(scr, _Cam(obj.x - isx, obj.y - isy))
        elif lay == "group":
            # merged seats: sitters are depth-sorted INTO the group's parts,
            # exactly like a single piece (away-facing bodies behind the
            # backrest, their x-ray ghost last; camera-facing ones in front)
            isofurn.draw_group(scr, Pf, kind, col, obj[0], rot, on=obj[1],
                               extra_ops=[op for s in obj[2]
                                          for op in _sitter_ops(scr, ox, oy, *s)])
        elif lay == "top":
            isofurn.draw_top(scr, Pf, obj[0], obj[1], kind, col, obj[2],
                             on=obj[3], rot=obj[4])
            if len(obj) > 5:
                _drop_puff(scr, ox, oy, obj[5], obj[0], obj[1], obj[2])
        else:
            onv, sits, cont = obj
            extra = ([op for s in sits for op in _sitter_ops(scr, ox, oy, *s)]
                     if sits else None)
            isofurn.draw(scr, Pf, gx, gy, fw, fh, kind, col, rot,
                         on=bool(onv), extra_ops=extra, contents=cont)
