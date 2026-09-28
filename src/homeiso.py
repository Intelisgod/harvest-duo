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
def draw_shell(scr, world, ox, oy, grid=False):
    """Floor + two walls + (optional) build grid + wall decor."""
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

    # wall-mounted decor, sheared to lie in each wall's plane
    for pl in world.home_furniture:
        if F.CAT[pl.kind]["layer"] != "wall":
            continue
        mid = wall_anchor(ox, oy, area, pl.gx, pl.gy)
        # wall lights default ON until the player toggles them; other wall
        # decor has no power state so it always renders lit
        won = pl.on or pl.kind not in F.TOGGLE
        s = wall_decor_sprite(pl.kind, pl.color, pl.rot,
                              "left" if pl.gx == 0 else "back", on=won)
        scr.blit(s, (mid[0] - 17, mid[1] - s.get_height() // 2))


_wall_cache = {}


def wall_decor_sprite(kind, color, rot, side, on=True):
    """Wall decor SHEARED into the wall plane: the back wall slopes down-right
    (+1px y per 2px x) and the left wall down-left, so paintings, windows and
    clocks visually lie ON the wall instead of floating upright in front of it.
    Built by blitting 1px columns of the flat sprite at sloping y offsets."""
    key = (kind, color, rot, side, on)
    sp = _wall_cache.get(key)
    if sp is None:
        base = pygame.transform.smoothscale(F.sprite(kind, color, rot, on=on),
                                            (34, 34))
        w, h = base.get_size()
        sp = pygame.Surface((w, h + w // 2 + 1), pygame.SRCALPHA)
        for x in range(w):
            yoff = (x // 2) if side == "back" else ((w - 1 - x) // 2)
            sp.blit(base, (x, yoff), pygame.Rect(x, 0, 1, h))
        _wall_cache[key] = sp
    return sp


def _sitter_ops(scr, ox, oy, p, sx, sy, st, kind="chair"):
    """[(bbox, draw-fn), ...] ops for a seated player, slotted into the seat
    piece's OWN depth-sorted parts: backrest behind the body, armrests / the
    front edge over the hips. When the player faces AWAY ('up'/'left') the
    legs hang on the FAR side, so they are a separate LOW op the seat itself
    occludes -- only the feet peek out underneath (Stardew draw-tile style)."""
    d = ("up" if p.fy < 0 else "down" if p.fy > 0
         else "left" if p.fx < 0 else "right")
    isx, isy = proj(ox, oy, sx, sy)

    def body():
        frame = chars.seated_frames(p.appearance)[d]
        scr.blit(frame, (isx - frame.get_width() // 2,
                         isy - st - chars.SEATED_HIP_Y))
    ops = []
    if d == "up":
        def legs():
            fr = chars.seated_leg_frames()[d]
            # +7px: the feet reach past the seat's bottom edge and peek out
            # underneath while the seat occludes the shins
            scr.blit(fr, (isx - fr.get_width() // 2,
                          isy - st - chars.SEATED_HIP_Y + 7))
        # low + thin box: every seat surface (bases at z>=11) sorts in front
        ops.append(((sx - 0.14, sy - 0.14, sx + 0.14, sy + 0.14, 2, 10), legs))
    # the body sits ON the cushion (z starts at the seat top, so the cushion
    # cleanly z-sorts below it).
    if kind == "chair" and d == "left":
        # SIDE-facing chair: the narrow backrest lands camera-side and would
        # swallow the whole torso. Lift the body's z floor above the backrest
        # top (29px) AND stretch its box over the backrest's x-range so the
        # x-rule can't pre-empt the z-rule -- the player then visibly sits
        # leaning against the backrest instead of hiding behind it.
        ops.append(((sx - 0.18, sy - 0.18, sx + 0.48, sy + 0.18, 30, 64), body))
    else:
        ops.append(((sx - 0.18, sy - 0.18, sx + 0.18, sy + 0.18, st, st + 34),
                    body))
    return ops


def top_height(kind):
    """Re-export of isofurn.surface_height for Build mode."""
    return isofurn.surface_height(kind)


def draw_top_piece(scr, ox, oy, x, y, kind, color, base, alpha=255):
    """Draw one tabletop item (used by the room and the Build ghost)."""
    def Pf(a, b):
        return proj(ox, oy, a, b)
    if alpha >= 255:
        isofurn.draw_top(scr, Pf, x, y, kind, color, base)
    else:
        tmp = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        isofurn.draw_top(tmp, Pf, x, y, kind, color, base)
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
    draw_shell(scr, world, ox, oy, grid=build)

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
            # tabletop decor: drawn at its support's top height, depth-keyed a
            # hair PAST the support so it always paints right after it
            sup = next((q for q in reversed(world.home_furniture)
                        if F.CAT[q.kind]["layer"] == "ground"
                        and q.kind in F.SURFACES and (pl.gx, pl.gy) in q.cells()),
                       None)
            base = isofurn.surface_height(sup.kind) if sup else 0
            if sup:
                sfw, sfh = F.footprint(sup.kind, sup.rot)
                dgx, dgy = sup.gx + 0.01, sup.gy + 0.01
            else:
                sfw = sfh = 1
                dgx, dgy = pl.gx, pl.gy
            items.append((dgx, dgy, pl.kind, pl.color, sfw, sfh, "top",
                          (pl.gx + 0.5 + pl.ox, pl.gy + 0.5 + pl.oy, base,
                           pl.on), 0))
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
            isofurn.draw_group(scr, Pf, kind, col, obj[0], rot, on=obj[1])
            for s in obj[2]:                    # merged seats: sitter on top
                for _, fn in _sitter_ops(scr, ox, oy, *s):
                    fn()
        elif lay == "top":
            isofurn.draw_top(scr, Pf, obj[0], obj[1], kind, col, obj[2],
                             on=obj[3])
        else:
            onv, sits, cont = obj
            extra = ([op for s in sits for op in _sitter_ops(scr, ox, oy, *s)]
                     if sits else None)
            isofurn.draw(scr, Pf, gx, gy, fw, fh, kind, col, rot,
                         on=bool(onv), extra_ops=extra, contents=cont)
