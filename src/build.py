"""Sims-style Build & Buy mode for the house interior.

Mouse-driven with keyboard fallbacks:
  - Click a catalogue item to pick it up, then click in the room to place it.
  - R rotates, colour swatches recolour, Wall/Floor buttons recolour the room.
  - With no item picked, click an existing piece to select it (drag to move,
    R to rotate, a swatch to recolour, Sell to remove for half its price).
  - Esc clears the current item/selection, or exits build mode.
"""
import math
import pygame
from .settings import TILE, SCREEN_W, SCREEN_H, WHITE, GOLD, UI_BORDER
from . import furniture as F
from . import homeiso as HI
from . import isofurn as IF
from . import tabletop as TT
from .world import FLOOR

PANEL_X = 992
PANEL_W = SCREEN_W - PANEL_X
BAR_Y = 632
ACCENT = (96, 206, 130)
ITEM_TOP = 140                      # y of the first catalogue row (under 2 tab rows + counter)
ITEM_PITCH = 54                     # row stride
# rows that fit in the full-height catalogue card (it runs past BAR_Y: the
# bottom bar only spans the room side)
VIS = (SCREEN_H - 20 - ITEM_TOP) // ITEM_PITCH
TAB_COLS = 3                        # catalogue tabs: two rows of three, every label fits
# the record player is a remote for this PC's Spotify: a new one arrives OFF
# (switching it on is what starts the music), unlike the lights/appliances
_ARRIVE_OFF = {"record_player"}


def _arrives_on(kind):
    """Is a freshly bought ``kind`` placed switched on?"""
    return kind in F.TOGGLE and kind not in _ARRIVE_OFF


class BuildMode:
    def __init__(self, game):
        self.g = game
        self.tab = 0
        self.sel = 0
        self.scroll = 0          # first visible catalogue row (reset on tab switch)
        self.brush = None        # catalogue id being placed, or None (=select mode)
        self.rot = 0
        self.ci = 0              # colour index
        self.cur = (8, 6)
        self.cur_pt = (8.5, 6.5)  # fractional mouse tile point (corner aiming)
        self.undo = []            # snapshots for Ctrl+Z (capped at 40)
        # free-form tabletop placement: where the item in hand would land
        # (surface, x, y, ok, guides), its on-screen ghost (smoothed toward
        # that spot every frame) and the spot a dragged item came from
        self.top_target = None
        self._ghost = None
        self._ghost_t = None
        self._drag_from = None
        self._hover = None
        self.selected = None     # a Placed being edited
        self.dragging = False
        self.msg = ""
        self.font = game.ui.font
        self.small = game.ui.small
        self.tiny = game.ui.tiny
        self.big = game.ui.big

    # ---------- helpers ----------
    def tab_items(self):
        cat = F.CATEGORIES[self.tab]
        return [c[0] for c in F.CATALOG if F.CAT[c[0]]["cat"] == cat]

    def _clamp_scroll(self):
        n = len(self.tab_items())
        self.scroll = max(0, min(self.scroll, max(0, n - VIS)))

    def _scroll_to_sel(self):
        """Nudge the window so the keyboard cursor (self.sel) stays visible."""
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + VIS:
            self.scroll = self.sel - VIS + 1
        self._clamp_scroll()

    def _clamp_cell(self, gx, gy, item=None):
        area = self.g.world.area
        if item and F.CAT[item]["layer"] == "wall":
            # wall decor snaps onto the nearer feature wall: back (top) or left column
            if gx < gy:
                return 0, max(1, min(area.h - 2, gy))
            return max(1, min(area.w - 2, gx)), 0
        if item:
            fw, fh = F.footprint(item, self.rot)
            gx = max(1, min(area.w - 1 - fw, gx))
            gy = max(1, min(area.h - 1 - fh, gy))
        else:
            # no brush: the cursor is a PICKER, so let it reach the wall rows
            # (0, gy)/(gx, 0) where wall decor lives, for keyboard selection
            gx = max(0, min(area.w - 2, gx))
            gy = max(0, min(area.h - 2, gy))
        return gx, gy

    def blocked_cells(self, ignore=None):
        cells = set()
        for pl in self.g.world.home_furniture:
            if pl is ignore:
                continue
            if F.CAT[pl.kind]["layer"] == "ground":
                cells.update(pl.cells())
        # never let furniture block an exit door (would trap the players inside)
        for wdef in self.g.world.area.warps:
            cells.add((wdef["gx"], wdef["gy"]))
        return cells

    def _floor_ok(self, cells):
        area = self.g.world.area
        return all(area.tile(cx, cy) == FLOOR for cx, cy in cells)

    def snap_offset(self, item, gx, gy, rot, ignore=None):
        """Centre-snap: a 1-tile seat placed beside an even-length piece slides
        half a tile so it faces the piece's CENTRE (chair at a 2-tile dining
        table, piano bench at a piano). Returns the (ox, oy) sub-tile offset."""
        if item not in F.SNAP_SEATS or F.footprint(item, rot) != (1, 1):
            return 0.0, 0.0

        def ground_at(cx, cy):
            for q in reversed(self.g.world.home_furniture):
                if (q is not ignore and q.kind not in F.SNAP_SEATS
                        and F.CAT[q.kind]["layer"] == "ground"
                        and (cx, cy) in q.cells()):
                    return q
            return None

        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            pl = ground_at(gx + dx, gy + dy)
            if pl is None:
                continue
            fw, fh = F.footprint(pl.kind, pl.rot)
            if dy != 0:                    # piece above/below -> centre along x
                d = (pl.gx + fw / 2.0) - (gx + 0.5)
                if abs(d) == 0.5:
                    return d, 0.0
            else:                          # piece left/right -> centre along y
                d = (pl.gy + fh / 2.0) - (gy + 0.5)
                if abs(d) == 0.5:
                    return 0.0, d
        return 0.0, 0.0

    # ---------- undo ----------
    def _push_undo(self):
        """Snapshot the whole editable home state BEFORE a change."""
        w = self.g.world
        self.undo.append(([pl.to_dict() for pl in w.home_furniture], self.g.gold,
                          w.home_wall_idx, w.home_floor_idx))
        if len(self.undo) > 40:
            self.undo.pop(0)

    def undo_last(self):
        if not self.undo:
            self.msg = "Nothing to undo"
            self.g.audio.play("ui_move")
            return
        items, gold, wi, fi = self.undo.pop()
        w = self.g.world
        w.home_furniture = [F.Placed(**d) for d in items]
        self.g.gold = gold
        w.home_wall_idx, w.home_floor_idx = wi, fi
        self.selected = None
        self.dragging = False
        self._refresh()
        self.msg = "Undone"
        self.g.audio.play("ui_toggle")

    # ---------- screen-accurate picking ----------
    @staticmethod
    def _pt_in_poly(px, py, poly):
        inside = False
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if (ay > py) != (by > py) and \
                    px < ax + (bx - ax) * (py - ay) / (by - ay or 1e-9):
                inside = not inside
        return inside

    def _pick_visual(self, pos):
        """Pick a GROUND piece by its VISIBLE body -- the footprint extruded up
        by the piece's height -- nearest piece first. Clicking the furniture
        itself now hits it, instead of whatever floor tile lies behind it."""
        area = self.g.world.area
        ox, oy = HI.origin(area)
        pieces = [q for q in self.g.world.home_furniture
                  if F.CAT[q.kind]["layer"] == "ground"]
        pieces.sort(key=lambda q: -(q.gx + q.ox + q.gy + q.oy
                                    + sum(F.footprint(q.kind, q.rot)) / 2.0))
        for q in pieces:
            fw, fh = F.footprint(q.kind, q.rot)
            h = max(IF.HEIGHT.get(q.kind, 22), 14)
            x0, y0 = q.gx + q.ox, q.gy + q.oy
            p = [HI.proj(ox, oy, x0, y0), HI.proj(ox, oy, x0 + fw, y0),
                 HI.proj(ox, oy, x0 + fw, y0 + fh), HI.proj(ox, oy, x0, y0 + fh)]
            hexa = [(p[0][0], p[0][1] - h), (p[1][0], p[1][1] - h), p[1],
                    p[2], p[3], (p[3][0], p[3][1] - h)]
            if self._pt_in_poly(pos[0], pos[1], hexa):
                return q
        return None

    # ---------- free-form tabletop placement (see tabletop.py) ----------
    def _free_mode(self):
        return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

    def _top_aim(self, kind, pos=None, ignore=None, point=None):
        """(surface, x, y, ok, guides) for a `kind` tabletop item aimed at the
        mouse `pos` (or a tile `point` for keyboard aiming). ok=False: no
        surface there / no room left on it."""
        world = self.g.world
        surfs = TT.surfaces(world)
        area = world.area
        if point is not None:
            px, py = point
            cand = [sf for sf in surfs if sf.contains(px, py, 0.02)]
            if not cand:
                return None, px, py, False, []
            sf = max(cand, key=lambda c: c.h)
        else:
            ox, oy = HI.origin(area)
            sf, px, py = TT.aim(area, surfs, pos[0], pos[1], HI.screen_to_point,
                                lambda a, b: HI.proj(ox, oy, a, b))
            if sf is None:
                return None, px, py, False, []
        others = TT.others_on(sf, world, surfs, ignore=ignore)
        x, y, ok, guides = TT.resolve(sf, kind, px, py, others,
                                      snap=not self._free_mode())
        return sf, x, y, ok, guides

    def _top_support(self, gx, gy, ignore=None):
        """The flat-topped piece under (gx, gy) tabletop decor would sit on
        (kept for callers that think in cells), or None."""
        for q in reversed(self.g.world.home_furniture):
            if (q is not ignore and F.CAT[q.kind]["layer"] == "ground"
                    and q.kind in F.SURFACES and (gx, gy) in q.cells()):
                return q
        return None

    def _pick_top(self, pos):
        """The tabletop item whose ON-SCREEN body is under the mouse (nearest
        the camera first) -- clicking the little item itself picks it."""
        world = self.g.world
        area = world.area
        ox, oy = HI.origin(area)
        surfs = TT.surfaces(world)
        best, bd = None, None
        for q in world.home_furniture:
            if F.CAT[q.kind]["layer"] != "top":
                continue
            sf = TT.support_of(q, surfs)
            base = sf.h if sf else 0
            x, y = TT.pos(q)
            pt = HI.proj(ox, oy, x, y)
            r = 8 + F.top_radius(q.kind) * 40
            d = (pos[0] - pt[0]) ** 2 + ((pos[1] - (pt[1] - base - 7)) * 1.3) ** 2
            if d <= r * r and (bd is None or d < bd - 1 or
                               (abs(d - bd) <= 1 and x + y > sum(TT.pos(best)))):
                best, bd = q, d
        return best

    def _items_riding(self, piece):
        """Tabletop items standing on `piece` (they travel with it)."""
        world = self.g.world
        surfs = TT.surfaces(world)
        sf = next((x for x in surfs if piece in x.pieces), None)
        if sf is None:
            return []
        return TT.items_on(sf, world, surfs)

    def can_place(self, item, gx, gy, rot, ignore=None, off=(0.0, 0.0)):
        area = self.g.world.area
        if F.CAT[item]["layer"] == "top":
            # must find room on a surface over (or around) that cell
            return self._top_aim(item, point=(gx + 0.5, gy + 0.5), ignore=ignore)[3]
        if F.CAT[item]["layer"] == "wall":
            # may hang on the back (top) wall row OR the left wall column, one per cell
            on_top = (gy == 0 and 1 <= gx <= area.w - 2)
            on_left = (gx == 0 and 1 <= gy <= area.h - 2)
            if not (on_top or on_left):
                return False
            for pl in self.g.world.home_furniture:
                if pl is ignore:
                    continue
                if F.CAT[pl.kind]["layer"] == "wall" and (gx, gy) in pl.cells():
                    return False
            return True
        fw, fh = F.footprint(item, rot)
        # cover every cell the (possibly half-tile shifted) footprint touches
        x0, x1 = int(math.floor(gx + off[0])), int(math.ceil(gx + off[0] + fw))
        y0, y1 = int(math.floor(gy + off[1])), int(math.ceil(gy + off[1] + fh))
        cells = [(cx, cy) for cx in range(x0, x1) for cy in range(y0, y1)]
        if not self._floor_ok(cells):
            return False
        if F.CAT[item]["layer"] == "floor":
            return True
        blk = self.blocked_cells()
        for p in self.g.players:                       # don't bury a player
            blk.add((int(p.x // TILE), int(p.y // TILE)))
        return not any(c in blk for c in cells)

    def _refresh(self):
        self.g.world.refresh_home_solids()

    def _origin(self):
        """Top-left screen pixel of tile (0,0), matching the game camera."""
        return -self.g.cam.x, -self.g.cam.y

    def _mouse_cell(self, pos):
        # isometric pick: which floor tile is under the cursor
        return HI.screen_to_cell(self.g.world.area, pos[0], pos[1])

    def place(self):
        if not self.brush:
            return
        gx, gy = self.cur
        if F.CAT[self.brush]["layer"] == "top":
            self._place_top()
            return
        sox, soy = self.snap_offset(self.brush, gx, gy, self.rot)
        if not self.can_place(self.brush, gx, gy, self.rot, off=(sox, soy)):
            # a blocked snap may still fit un-snapped (e.g. a row of chairs)
            if (sox or soy) and self.can_place(self.brush, gx, gy, self.rot):
                sox = soy = 0.0
            else:
                self.msg = "Can't place there"
                return
        price = F.CAT[self.brush]["price"]
        if self.g.gold < price:
            self.msg = "Not enough gold!"
            self.g.audio.play("ui_move")
            return
        self._push_undo()
        self.g.gold -= price
        pl = F.Placed(self.brush, gx, gy, self.rot, self.ci, ox=sox, oy=soy,
                      on=_arrives_on(self.brush))  # appliances arrive switched on
        # rugs go to the bottom so they render under everything
        if F.CAT[self.brush]["layer"] == "floor":
            self.g.world.home_furniture.insert(0, pl)
        else:
            self.g.world.home_furniture.append(pl)
        self._refresh()
        self.g.audio.play("sell")
        self.msg = f"Placed {F.CAT[self.brush]['label']} (-{price}g)"

    def _place_top(self):
        """Put the tabletop item in hand down where the ghost shows it."""
        tgt = self.top_target
        if tgt is None:
            tgt = self._top_aim(self.brush, point=(self.cur[0] + 0.5, self.cur[1] + 0.5))
        sf, x, y, ok, _ = tgt
        if sf is None:
            self.msg = "Tabletop decor goes on a table, counter or shelf"
            self.g.audio.play("ui_move")
            return
        if not ok:
            self.msg = "No room left on that surface"
            self.g.audio.play("ui_move")
            return
        price = F.CAT[self.brush]["price"]
        if self.g.gold < price:
            self.msg = "Not enough gold!"
            self.g.audio.play("ui_move")
            return
        self._push_undo()
        self.g.gold -= price
        pl = F.Placed(self.brush, 0, 0, self.rot, self.ci, on=_arrives_on(self.brush))
        TT.set_pos(pl, x, y, sf.h)
        self.g.world.home_furniture.append(pl)
        HI.DROP[id(pl)] = pygame.time.get_ticks()
        self._refresh()
        self.g.audio.play("sell")
        self.msg = f"Placed {F.CAT[self.brush]['label']} (-{price}g)"
        # the next one of the same kind would land on the same spot: re-aim
        self.top_target = self._top_aim(self.brush, point=(x, y))

    def _nudge_top(self, dx, dy):
        """Arrow keys fine-move a selected tabletop item (1/16 tile)."""
        sel = self.selected
        world = self.g.world
        surfs = TT.surfaces(world)
        sf = TT.support_of(sel, surfs)
        if sf is None:
            return
        x, y = TT.pos(sel)
        others = TT.others_on(sf, world, surfs, ignore=sel)
        nx, ny, ok, _ = TT.resolve(sf, sel.kind, x + dx * F.TOP_SNAP,
                                   y + dy * F.TOP_SNAP, others, snap=False)
        if ok and (abs(nx - x) > 1e-6 or abs(ny - y) > 1e-6):
            self._push_undo()
            TT.set_pos(sel, nx, ny, sf.h)
            self.g.audio.play("ui_move")

    def pick_at(self, gx, gy):
        for pl in reversed(self.g.world.home_furniture):
            if (gx, gy) in pl.cells():
                return pl
        return None

    def _wall_pick(self, pos):
        """Pick wall decor by clicking its SPRITE on the wall. The sprite hangs
        ~half a wall above its floor cell, so the floor-tile inverse projection
        never hits it -- match by screen distance to the wall anchor instead."""
        area = self.g.world.area
        ox, oy = HI.origin(area)
        best, bd = None, 26 * 26
        for pl in reversed(self.g.world.home_furniture):
            if F.CAT[pl.kind]["layer"] != "wall":
                continue
            ax, ay = HI.wall_anchor(ox, oy, area, pl.gx, pl.gy)
            d = (pos[0] - ax) ** 2 + (pos[1] - ay) ** 2
            if d < bd:
                best, bd = pl, d
        return best

    def sell_selected(self):
        # sell the selected piece, or fall back to whatever sits under the cursor
        target = self.selected
        if target is None:
            target = self.pick_at(*self.cur)
        # never sell the LAST bed -- sleeping is the only way to end the day
        if target and target.kind == "bed" and \
                sum(1 for q in self.g.world.home_furniture if q.kind == "bed") <= 1:
            self.msg = "You need at least one bed to sleep in!"
            self.g.audio.play("ui_move")
            return
        if target and target in self.g.world.home_furniture:
            self._push_undo()
            # return any stored items so selling a chest never loses contents
            stored = getattr(target, "store", None)
            moved = 0
            if stored:
                for item, qty in list(stored.items()):
                    if qty > 0:
                        self.g.players[0].inv.add(item, qty)
                        moved += qty
                stored.clear()
            refund = F.CAT[target.kind]["price"] // 2
            self.g.gold += refund
            self.g.world.home_furniture.remove(target)
            # tabletop decor left floating (its table was sold) is sold along
            surfs = TT.surfaces(self.g.world)
            orphans = [q for q in self.g.world.home_furniture
                       if F.CAT[q.kind]["layer"] == "top"
                       and TT.support_of(q, surfs) is None]
            for q in orphans:
                self.g.gold += F.CAT[q.kind]["price"] // 2
                refund += F.CAT[q.kind]["price"] // 2
                self.g.world.home_furniture.remove(q)
            self.g.audio.play("sell")
            extra = f", returned {moved} item(s)" if moved else ""
            self.msg = f"Sold {F.CAT[target.kind]['label']} (+{refund}g){extra}"
            self.selected = None
            self.brush = None
            self._refresh()
        else:
            self.msg = "Click a piece first, then Sell"
            self.g.audio.play("ui_move")

    def rotate(self):
        if self.selected and F.CAT[self.selected.kind]["layer"] == "top":
            self._push_undo()
            self.selected.rot = (self.selected.rot + 1) % 4
            HI.DROP[id(self.selected)] = pygame.time.get_ticks()   # a little hop
        elif self.selected:
            sel = self.selected
            self._push_undo()
            old_rot = sel.rot
            sel.rot = (sel.rot + 1) % 4
            sel.gx, sel.gy = self._clamp_cell(sel.gx, sel.gy, sel.kind)
            sel.ox, sel.oy = self.snap_offset(
                sel.kind, sel.gx, sel.gy, sel.rot, ignore=sel)
            if sel.kind in F.SURFACES:          # its tabletop things turn along
                TT.carry_on_rotate(self.g.world, sel, old_rot)
            self._refresh()
        else:
            self.rot = (self.rot + 1) % 4
        self.g.audio.play("ui_move")

    def set_color(self, ci):
        self.ci = ci
        if self.selected:
            self._push_undo()
            self.selected.ci = ci
        self.g.audio.play("ui_move")

    # ---------- layout ----------
    def _tab_rects(self):
        """Two rows of three tabs across the catalogue card, so every label
        ('Bedroom', 'Crafting', 'Tabletop') fits inside its own tab."""
        n = len(F.CATEGORIES)
        x0, gap, h = PANEL_X + 14, 6, 30
        w = (PANEL_W - 28 - gap * (TAB_COLS - 1)) // TAB_COLS
        return [pygame.Rect(x0 + (i % TAB_COLS) * (w + gap), 52 + (i // TAB_COLS) * (h + 6), w, h)
                for i in range(n)]

    def _item_rects(self):
        """Rects for the CURRENT window only (row 0..VIS-1).  Map a window row i
        back to the real catalogue index with `self.scroll + i`."""
        self._clamp_scroll()
        n = len(self.tab_items())
        rows = max(0, min(VIS, n - self.scroll))
        return [pygame.Rect(PANEL_X + 14, ITEM_TOP + row * ITEM_PITCH, PANEL_W - 42, 50)
                for row in range(rows)]

    def _swatch_rects(self):
        return [pygame.Rect(16 + i * 28, BAR_Y + 12, 22, 22) for i in range(len(F.PALETTE))]

    UP_COST = {2: (200, 10), 3: (500, 20)}     # furniture quality level -> (gold, wood)

    def _buttons(self):
        """Bottom-bar buttons, 8 px apart; the Wall / Floor buttons carry their
        current colour swatch INSIDE (it used to spill into the next button)."""
        y = BAR_Y + 42
        return {
            "rotate": pygame.Rect(14, y, 120, 34),
            "sell": pygame.Rect(142, y, 80, 34),
            "wall": pygame.Rect(230, y, 150, 34),
            "floor": pygame.Rect(388, y, 150, 34),
            "upgrade": pygame.Rect(546, y, 178, 34),
            "done": pygame.Rect(PANEL_X - 150, BAR_Y + 14, 132, 62),
        }

    def upgrade_selected(self):
        pl = self.selected
        if not pl:
            self.msg = "Click a piece, then Upgrade"; self.g.audio.play("ui_move"); return
        if F.CAT[pl.kind]["layer"] != "ground":
            self.msg = "Only floor furniture has quality"; self.g.audio.play("ui_move"); return
        lvl = getattr(pl, "level", 1)
        if lvl >= 3:
            self.msg = "Already max quality (3 stars)"; self.g.audio.play("ui_move"); return
        gold, wood = self.UP_COST[lvl + 1]
        p = self.g.players[0]
        if self.g.gold < gold or p.inv.count("wood") < wood:
            self.msg = f"Need {gold}g + {wood} wood"; self.g.audio.play("ui_move"); return
        self._push_undo()
        self.g.gold -= gold
        p.inv.remove("wood", wood)
        pl.level = lvl + 1
        self.g.audio.play("sell")
        self.msg = f"{F.CAT[pl.kind]['label']} -> quality {pl.level} stars!"

    # ---------- input ----------
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                HI.LIFT.clear()
                self.dragging = False
                if self.brush or self.selected:
                    self.brush = None; self.selected = None
                else:
                    self.g.state = "play"
                return
            if e.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                self.undo_last()
                return
            if e.key in (pygame.K_r,):
                self.rotate()
            elif e.key == pygame.K_TAB:
                self.tab = (self.tab + 1) % len(F.CATEGORIES); self.sel = 0; self.scroll = 0
            elif e.key in (pygame.K_DELETE, pygame.K_x):
                self.sell_selected()
            elif e.key in (pygame.K_q, pygame.K_e):
                items = self.tab_items()
                if not items:
                    return
                self.sel = (self.sel + (1 if e.key == pygame.K_e else -1)) % len(items)
                self.brush = items[self.sel]; self.selected = None
                self._scroll_to_sel()
            elif (e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)
                  and self.selected is not None and not self.brush
                  and F.CAT[self.selected.kind]["layer"] == "top"):
                self._nudge_top(*{pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
                                  pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}[e.key])
                return
            elif e.key in (pygame.K_a, pygame.K_LEFT):
                self.cur = self._clamp_cell(self.cur[0] - 1, self.cur[1], self.brush)
            elif e.key in (pygame.K_d, pygame.K_RIGHT):
                self.cur = self._clamp_cell(self.cur[0] + 1, self.cur[1], self.brush)
            elif e.key in (pygame.K_w, pygame.K_UP):
                self.cur = self._clamp_cell(self.cur[0], self.cur[1] - 1, self.brush)
            elif e.key in (pygame.K_s, pygame.K_DOWN):
                self.cur = self._clamp_cell(self.cur[0], self.cur[1] + 1, self.brush)
            elif e.key == pygame.K_SPACE:
                if self.brush:
                    self.place()
                else:
                    self.selected = self.pick_at(*self.cur)
            if e.key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT,
                         pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
                # keep the aim point in step with keyboard cursor moves
                self.cur_pt = (self.cur[0] + 0.5, self.cur[1] + 0.5)
                if self.brush and F.CAT[self.brush]["layer"] == "top":
                    self.top_target = self._top_aim(self.brush, point=self.cur_pt)
            return

        if e.type == pygame.MOUSEMOTION:
            mx, my = e.pos
            if mx < PANEL_X and my < BAR_Y:
                self.cur_pt = HI.screen_to_point(self.g.world.area, mx, my)
                cgx, cgy = self._mouse_cell(e.pos)
                if self.brush and F.CAT[self.brush]["layer"] == "top":
                    self.top_target = self._top_aim(self.brush, e.pos)
                    sf, tx, ty = self.top_target[:3]
                    cgx, cgy = int(math.floor(tx)), int(math.floor(ty))
                    self.cur_pt = (tx, ty)
                self.cur = self._clamp_cell(cgx, cgy, self.brush)
                self._hover = (self._pick_top(e.pos)
                               if not self.brush and not self.dragging else None)
                if self.dragging and self.selected:
                    sel = self.selected
                    if F.CAT[sel.kind]["layer"] == "top":
                        # carried in the hand: glides to the free spot under the
                        # mouse (sliding round its neighbours), any surface
                        sf, tx, ty, ok, guides = self._top_aim(sel.kind, e.pos, ignore=sel)
                        self.top_target = (sf, tx, ty, ok, guides)
                        if sf is not None and ok:
                            TT.set_pos(sel, tx, ty, sf.h)
                    else:
                        before = set(sel.cells())
                        riding = (self._items_riding(sel)
                                  if sel.kind in F.SURFACES else [])
                        ogx, ogy = sel.gx, sel.gy
                        sel.gx, sel.gy = self._clamp_cell(cgx, cgy, sel.kind)
                        # re-evaluate centre-snap at the new spot (seats only)
                        sel.ox, sel.oy = self.snap_offset(
                            sel.kind, sel.gx, sel.gy, sel.rot, ignore=sel)
                        ddx, ddy = sel.gx - ogx, sel.gy - ogy
                        if ddx or ddy:
                            # tabletop decor rides along with its table
                            for q in riding:
                                q.gx += ddx
                                q.gy += ddy
                    self._refresh()
            return

        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            sel = self.selected
            if self.dragging and sel is not None and F.CAT[sel.kind]["layer"] == "top":
                HI.LIFT.pop(id(sel), None)          # set it down with a bounce
                HI.DROP[id(sel)] = pygame.time.get_ticks()
                self.g.audio.play("ui_move")
                self.top_target = None
            HI.LIFT.clear()                         # nothing stays floating
            self.dragging = False
            return

        # scroll the catalogue with the mouse wheel (SDL2 MOUSEWHEEL, or legacy
        # button 4/5).  Only the catalogue scrolls, so apply it regardless of x.
        if e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            top_in_hand = ((self.brush and F.CAT[self.brush]["layer"] == "top")
                           or (self.selected is not None and not self.brush
                               and F.CAT[self.selected.kind]["layer"] == "top"))
            if mx < PANEL_X and my < BAR_Y and top_in_hand and e.y:
                self.rotate()                     # Sims-style: wheel turns it
                return
            self.scroll -= e.y
            self._clamp_scroll()
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (4, 5):
            self.scroll += (1 if e.button == 5 else -1)
            self._clamp_scroll()
            return

        # right-click = sell the piece under the cursor; middle-click (or
        # Ctrl+right) = EYEDROPPER: copy that piece as the active brush
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (2, 3):
            mx, my = e.pos
            if mx >= PANEL_X or my >= BAR_Y:
                return
            self.cur_pt = HI.screen_to_point(self.g.world.area, mx, my)
            cgx, cgy = self._mouse_cell(e.pos)
            target = (self._pick_top(e.pos) or self._pick_visual(e.pos)
                      or self.pick_at(cgx, cgy) or self._wall_pick(e.pos))
            if e.button == 2 or (pygame.key.get_mods() & pygame.KMOD_CTRL):
                if target:                       # eyedropper
                    self.brush = target.kind
                    self.ci = target.ci
                    self.rot = target.rot
                    self.selected = None
                    self.msg = f"Copied {F.CAT[target.kind]['label']}"
                    self.g.audio.play("ui_select")
            elif target:                         # quick sell
                self.selected = target
                self.sell_selected()
            else:
                self.msg = "Nothing to sell there"
                self.g.audio.play("ui_move")
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._click(e.pos)

    def _click(self, pos):
        mx, my = pos
        # catalogue panel
        if mx >= PANEL_X:
            for i, r in enumerate(self._tab_rects()):
                if r.collidepoint(pos):
                    self.tab = i; self.sel = 0; self.scroll = 0
                    self.g.audio.play("ui_move"); return
            for i, r in enumerate(self._item_rects()):
                if r.collidepoint(pos):
                    idx = self.scroll + i               # window row -> real index
                    self.brush = self.tab_items()[idx]; self.sel = idx
                    self.cur = self._clamp_cell(self.cur[0], self.cur[1], self.brush)
                    self.selected = None; self.g.audio.play("ui_select"); return
            return
        # bottom bar
        if my >= BAR_Y:
            for i, r in enumerate(self._swatch_rects()):
                if r.collidepoint(pos):
                    self.set_color(i); return
            b = self._buttons()
            if b["rotate"].collidepoint(pos):
                self.rotate()
            elif b["sell"].collidepoint(pos):
                self.sell_selected()
            elif b["wall"].collidepoint(pos):
                self._push_undo()
                self.g.world.home_wall_idx = (self.g.world.home_wall_idx + 1) % len(F.WALL_COLORS)
                self.g.audio.play("ui_toggle")
            elif b["floor"].collidepoint(pos):
                self._push_undo()
                self.g.world.home_floor_idx = (self.g.world.home_floor_idx + 1) % len(F.FLOOR_COLORS)
                self.g.audio.play("ui_toggle")
            elif b["upgrade"].collidepoint(pos):
                self.upgrade_selected()
            elif b["done"].collidepoint(pos):
                self.g.state = "play"; self.g.audio.play("ui_select")
            return
        # room
        self.cur_pt = HI.screen_to_point(self.g.world.area, *pos)
        cgx, cgy = self._mouse_cell(pos)
        if self.brush and F.CAT[self.brush]["layer"] == "top":
            # aiming at a raised surface: ray-cast onto its top
            self.top_target = self._top_aim(self.brush, pos)
            cgx, cgy = (int(math.floor(self.top_target[1])),
                        int(math.floor(self.top_target[2])))
        self.cur = self._clamp_cell(cgx, cgy, self.brush)
        # pick what the mouse VISUALLY touches: tabletop item > furniture body
        # > floor-tile fallback (rugs) > wall decor
        hit = (self._pick_top(pos) or self._pick_visual(pos)
               or self.pick_at(cgx, cgy) or self._wall_pick(pos))
        # a solid (non-rug) piece under the click is selected for editing/selling,
        # even while holding a brush — rugs still let you place furniture on top.
        # EXCEPTION: a tabletop brush places ONTO furniture, so clicking a piece
        # while holding one must place, not select (Esc first to select instead)
        solid_hit = hit if (hit and F.CAT[hit.kind]["layer"] != "floor") else None
        if self.brush and (F.CAT[self.brush]["layer"] == "top" or not solid_hit):
            self.place()
        elif solid_hit:
            self.brush = None
            self.selected = solid_hit
            self.dragging = True
            self._push_undo()                    # a drag-move is undoable
            if F.CAT[solid_hit.kind]["layer"] == "top":
                HI.LIFT[id(solid_hit)] = 7       # picked up: it floats in hand
                self._drag_from = TT.pos(solid_hit)
                self.g.audio.play("ui_select")
        else:
            self.selected = hit
            if hit:
                self.dragging = True
                self._push_undo()

    # ---------- draw ----------
    def draw(self, surf):
        # the iso room + grid are drawn by game.draw_world -> homeiso.draw_room
        self._draw_ghost(surf)
        self._draw_selection(surf)
        self._draw_panel(surf)
        self._draw_bar(surf)
        # header
        self._draw_header(surf)

    def _draw_header(self, surf):
        """Parchment header strip (matches the catalogue card and the bottom
        bar): title + gold on the first line (the last action's message on its
        right), the controls hint centred-left on the second, all in ink."""
        from . import ui_kit as K
        card = pygame.Rect(10, 8, PANEL_X - 24, 66)
        K.draw_card(surf, card, radius=14)
        y1, y2 = card.y + 22, card.y + 46
        hr = K.blit_text(surf, K.font(24, True), "Build & Buy", K.INK, (card.x + 20, y1),
                         align="left")
        gr = K.blit_text(surf, K.font(17, True), f"Gold: {self.g.gold:,}g", K.GOLD_TXT,
                         (hr.right + 24, y1), align="left")
        if self.msg:
            fm = K.font(15, True)
            room = card.right - 20 - (gr.right + 24)
            K.blit_text(surf, fm, K.ellipsize(fm, self.msg, room), K.SPROUT,
                        (card.right - 20, y1), align="right")
        top_mode = ((self.brush and F.CAT[self.brush]["layer"] == "top")
                    or (self.selected is not None
                        and F.CAT[self.selected.kind]["layer"] == "top"))
        hint = ("Drag to move  |  Wheel/R turn  |  Arrows nudge  |  Shift free place  |  "
                "Right-click sell  |  Ctrl+Z undo" if top_mode else
                "Click place  |  R rotate  |  Right-click sell  |  "
                "Mid/Ctrl+R-click copy  |  Ctrl+Z undo  |  Esc back")
        fh = K.fit_font(hint, card.w - 40, (14, 13, 12), bold=True)
        K.blit_text(surf, fh, hint, K.INK_SOFT, (card.x + 20, y2), align="left")

    def _cat_icon(self, _id):
        """Catalogue icon (tinted with the picked swatch) with a 1 px ink
        outline, so pale/white furniture still shows on the cream wells."""
        from . import ui_kit as K
        cache = self.__dict__.setdefault("_icon_cache", {})
        key = (_id, self.ci)
        s = cache.get(key)
        if s is None:
            ic = F.icon(_id, F.PALETTE[self.ci][1], 40)
            edge = pygame.mask.from_surface(ic, 40).to_surface(
                setcolor=(*K.INK_SOFT, 255), unsetcolor=(0, 0, 0, 0))
            s = pygame.Surface((ic.get_width() + 2, ic.get_height() + 2), pygame.SRCALPHA)
            for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):
                s.blit(edge, (ox, oy))
            s.blit(ic, (1, 1))
            if len(cache) > 400:
                cache.clear()
            cache[key] = s
        return s

    def _draw_ghost(self, surf):
        if not self.brush:
            return
        area = self.g.world.area
        ox, oy = HI.origin(area)
        gx, gy = self.cur
        d = F.CAT[self.brush]
        sox, soy = self.snap_offset(self.brush, gx, gy, self.rot)
        if (sox or soy) and not self.can_place(self.brush, gx, gy, self.rot,
                                               off=(sox, soy)):
            sox = soy = 0.0                      # place() falls back the same way
        ok = self.can_place(self.brush, gx, gy, self.rot, off=(sox, soy)) \
            and self.g.gold >= d["price"]
        col = (70, 210, 90) if ok else (220, 70, 70)
        spr = F.sprite(self.brush, F.PALETTE[self.ci][1], self.rot)
        if d["layer"] == "wall":
            mid = HI.wall_anchor(ox, oy, area, gx, gy)
            HI.blit_wall(surf, ox, oy, area, self.brush, F.PALETTE[self.ci][1], gx, gy,
                         on=True, alpha=170)
            pygame.draw.circle(surf, col, mid, 19, 2)
        elif d["layer"] == "top":
            if self.top_target is None:
                self.top_target = self._top_aim(self.brush, point=self.cur_pt)
            self._draw_top_ghost(surf, self.brush, self.top_target,
                                 ok_gold=self.g.gold >= d["price"])
        else:
            fw, fh = F.footprint(self.brush, self.rot)
            if ok and self.brush in F.MERGE:
                # MERGE PREVIEW: if this spot fuses with neighbours, ghost the
                # whole resulting piece in blue so you see the L/long shape
                fake = F.Placed(self.brush, gx, gy, self.rot, self.ci,
                                ox=sox, oy=soy)
                grp = next((g for g in F.merge_groups(
                    self.g.world.home_furniture + [fake])
                    if any(q is fake for q in g)), [fake])
                if len(grp) > 1:
                    rots = [q.rot % 4 for q in grp]
                    grot = max(sorted(set(rots)), key=rots.count)
                    mc = (110, 210, 255)
                    HI.outline(surf, ox, oy, gx + sox, gy + soy, fw, fh, mc, 2,
                               fill=(mc[0], mc[1], mc[2], 60))
                    HI.draw_group_piece(surf, ox, oy, self.brush,
                                        F.PALETTE[self.ci][1],
                                        F.group_cells(grp), grot, alpha=150,
                                        on=_arrives_on(self.brush))
                    return
            HI.outline(surf, ox, oy, gx + sox, gy + soy, fw, fh, col, 2,
                       fill=(col[0], col[1], col[2], 70))
            HI.draw_piece(surf, ox, oy, gx + sox, gy + soy, fw, fh, self.brush,
                          F.PALETTE[self.ci][1], alpha=170, rot=self.rot,
                          on=_arrives_on(self.brush))

    def _smooth_ghost(self, x, y, h):
        """Glide the on-screen ghost toward its target (frame-rate independent),
        so the item in hand moves like butter instead of hopping."""
        now = pygame.time.get_ticks()
        dt = 0.016 if self._ghost_t is None else min(0.1, (now - self._ghost_t) / 1000.0)
        self._ghost_t = now
        g = self._ghost
        if g is None or abs(g[0] - x) + abs(g[1] - y) > 3 or abs(g[2] - h) > 60:
            self._ghost = [x, y, float(h)]
        else:
            k = 1 - math.exp(-dt * 22)
            g[0] += (x - g[0]) * k
            g[1] += (y - g[1]) * k
            g[2] += (h - g[2]) * k
        return self._ghost

    def _foot_ellipse(self, surf, ox, oy, x, y, r, h, col, width=2, fill=None):
        pts = [HI.proj(ox, oy, x + math.cos(a) * r, y + math.sin(a) * r)
               for a in (i * math.pi / 12 for i in range(24))]
        pts = [(px, py - h) for px, py in pts]
        if fill is not None:
            lay = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
            pygame.draw.polygon(lay, fill, pts)
            surf.blit(lay, (0, 0))
        pygame.draw.polygon(surf, col, pts, width)

    def _draw_guides(self, surf, ox, oy, guides, h):
        """Dashed magnet lines on the surface top (alignment helpers)."""
        for axis, v, a, b in guides:
            if axis == "x":
                p0, p1 = HI.proj(ox, oy, v, a - 0.15), HI.proj(ox, oy, v, b + 0.15)
            else:
                p0, p1 = HI.proj(ox, oy, a - 0.15, v), HI.proj(ox, oy, b + 0.15, v)
            p0, p1 = (p0[0], p0[1] - h), (p1[0], p1[1] - h)
            n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 5))
            for i in range(0, n, 2):
                t0, t1 = i / n, min(1.0, (i + 1) / n)
                pygame.draw.line(surf, (255, 236, 150),
                                 (p0[0] + (p1[0] - p0[0]) * t0, p0[1] + (p1[1] - p0[1]) * t0),
                                 (p0[0] + (p1[0] - p0[0]) * t1, p0[1] + (p1[1] - p0[1]) * t1), 2)

    def _draw_top_ghost(self, surf, kind, tgt, ok_gold=True, held=None):
        """The tabletop item in hand: floating above the exact landing spot
        with a soft shadow + footprint ring (green / red), magnet guides, and
        a gentle bob -- smoothly following the mouse."""
        area = self.g.world.area
        ox, oy = HI.origin(area)
        sf, x, y, ok, guides = tgt
        ok = ok and ok_gold
        col = (70, 210, 90) if ok else (220, 70, 70)
        r = F.top_radius(kind)
        h = sf.h if sf is not None else 0
        gx_, gy_, gh = self._smooth_ghost(x, y, h)
        self._foot_ellipse(surf, ox, oy, x, y, r, h, col, 2,
                           fill=(col[0], col[1], col[2], 70))
        if sf is not None and guides:
            self._draw_guides(surf, ox, oy, guides, h)
        if held is None:
            bob = 7 + math.sin(pygame.time.get_ticks() / 180.0) * 1.5
            # soft contact shadow where it will land
            sh = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
            c = HI.proj(ox, oy, x, y)
            rr = 6 + r * 34
            pygame.draw.ellipse(sh, (20, 16, 30, 70), (c[0] - rr, c[1] - h - rr / 2, 2 * rr, rr))
            surf.blit(sh, (0, 0))
            HI.draw_top_piece(surf, ox, oy, gx_, gy_, kind, F.PALETTE[self.ci][1],
                              gh + bob, alpha=200 if ok else 130, rot=self.rot,
                              on=_arrives_on(kind))

    def _draw_hover(self, surf):
        """Mouse over a tabletop item (nothing in hand): a soft glow ring says
        'click to pick me up'."""
        q = self._hover
        if q is None or q not in self.g.world.home_furniture or self.dragging:
            return
        area = self.g.world.area
        ox, oy = HI.origin(area)
        sf = TT.support_of(q, TT.surfaces(self.g.world))
        h = sf.h if sf else 0
        x, y = TT.pos(q)
        t = pygame.time.get_ticks() / 250.0
        a = 150 + int(60 * math.sin(t))
        self._foot_ellipse(surf, ox, oy, x, y, F.top_radius(q.kind) + 0.03, h,
                           (255, 236, 150), 2, fill=(255, 236, 150, a // 4))

    def _draw_selection(self, surf):
        self._draw_hover(surf)
        if not self.selected:
            return
        area = self.g.world.area
        ox, oy = HI.origin(area)
        pl = self.selected
        if F.CAT[pl.kind]["layer"] == "wall":
            mid = HI.wall_anchor(ox, oy, area, pl.gx, pl.gy)
            pygame.draw.circle(surf, ACCENT, mid, 20, 3)
        elif F.CAT[pl.kind]["layer"] == "top":
            # a ring round the item's own footprint, up on its surface; while
            # carried, the landing ring + magnet guides instead
            if self.dragging and self.top_target is not None:
                self._draw_top_ghost(surf, pl.kind, self.top_target, held=pl)
                return
            sf = TT.support_of(pl, TT.surfaces(self.g.world))
            x, y = TT.pos(pl)
            self._foot_ellipse(surf, ox, oy, x, y, F.top_radius(pl.kind) + 0.02,
                               sf.h if sf else 0, ACCENT, 3)
        else:
            fw, fh = F.footprint(pl.kind, pl.rot)
            HI.outline(surf, ox, oy, pl.gx + pl.ox, pl.gy + pl.oy, fw, fh,
                       ACCENT, 3)

    def _draw_panel(self, surf):
        """The catalogue: a full-height parchment card (wooden rim, ribbon
        title), two rows of tabs, the 'shown / total' counter on its own line,
        then the item wells with the gold row cursor on the picked piece."""
        from . import ui_kit as K
        pygame.draw.rect(surf, (30, 24, 30), (PANEL_X, 0, PANEL_W, SCREEN_H))
        K.draw_card(surf, pygame.Rect(PANEL_X + 4, 10, PANEL_W - 8, SCREEN_H - 16), radius=14)
        K.ribbon(surf, K.font(20, True), "Catalogue", (PANEL_X + PANEL_W // 2, 18))
        K.tabs(surf, self._tab_rects(), F.CATEGORIES, self.tab, fnt_sizes=(14, 13, 12, 11))
        items = self.tab_items()
        window = items[self.scroll:self.scroll + VIS]
        self._t = getattr(self, "_t", 0.0) + 1 / 60
        f_lab, f_price = K.font(15, True), K.font(13, True)
        for r, _id in zip(self._item_rects(), window):
            d = F.CAT[_id]
            if self.brush == _id:
                K.row_cursor(surf, r, self._t)
            else:
                K.well(surf, r)
            # icon on its own slightly darker tile, outlined in ink, so every
            # swatch colour (white included) reads on the parchment
            tile = pygame.Rect(0, 0, 44, 44)
            tile.center = (r.x + 36, r.centery)
            pygame.draw.rect(surf, (222, 200, 166), tile, border_radius=8)
            ic = self._cat_icon(_id)
            surf.blit(ic, ic.get_rect(center=tile.center))
            tx = r.x + 64
            K.blit_text(surf, f_lab, K.ellipsize(f_lab, d["label"], r.right - 8 - tx), K.INK,
                        (tx, r.y + 17), align="left")
            K.blit_text(surf, f_price, f"{d['price']}g", K.GOLD_TXT, (tx, r.y + 35), align="left")
        self._draw_scrollbar(surf, len(items))

    def _draw_scrollbar(self, surf, n):
        """Right-edge scrollbar + up/down arrows + a 'shown/total' counter (on
        its own line between the tabs and the first card) when the catalogue is
        taller than the visible window."""
        from . import ui_kit as K
        if n <= VIS:
            return
        x = SCREEN_W - 22
        y0, h = ITEM_TOP, VIS * ITEM_PITCH - 4
        pygame.draw.rect(surf, K.WELL_LINE, (x, y0, 5, h), border_radius=2)
        th = max(20, int(h * VIS / n))
        ty = y0 + int((h - th) * (self.scroll / (n - VIS)))
        pygame.draw.rect(surf, K.WOOD, (x, ty, 5, th), border_radius=2)
        ax = PANEL_X + 14 + (PANEL_W - 42) // 2
        if self.scroll > 0:                                     # more above
            pygame.draw.polygon(surf, K.WOOD, [(ax, ITEM_TOP - 9), (ax - 6, ITEM_TOP - 3),
                                               (ax + 6, ITEM_TOP - 3)])
        if self.scroll + VIS < n:                               # more below
            by = ITEM_TOP + h + 3
            pygame.draw.polygon(surf, K.WOOD, [(ax, by + 7), (ax - 6, by), (ax + 6, by)])
        K.blit_text(surf, K.font(12, True), f"{self.scroll + 1}-{min(self.scroll + VIS, n)} of {n}",
                    K.INK_SOFT, (SCREEN_W - 22, ITEM_TOP - 12), align="right")

    def _draw_bar(self, surf):
        """Bottom tool bar on a parchment strip: colour swatches, then readable
        parchment buttons (labels centred), the Wall / Floor swatches inside
        their own buttons, and a big Done button."""
        from . import ui_kit as K
        bar = pygame.Rect(0, BAR_Y, PANEL_X, SCREEN_H - BAR_Y)
        pygame.draw.rect(surf, K.WOOD, bar)
        pygame.draw.rect(surf, K.CREAM, bar.inflate(-12, -12).move(0, 1), border_radius=10)
        pygame.draw.line(surf, K.WOOD_DK, (0, BAR_Y), (PANEL_X, BAR_Y), 2)
        for i, r in enumerate(self._swatch_rects()):
            pygame.draw.rect(surf, F.PALETTE[i][1], r, border_radius=5)
            if i == self.ci:
                pygame.draw.rect(surf, K.GOLD_RIM, r.inflate(6, 6), 3, border_radius=7)
            else:
                pygame.draw.rect(surf, K.WELL_LINE, r, 2, border_radius=5)
        b = self._buttons()
        fb = K.font(15, True)
        for key, r in b.items():
            if key == "done":
                K.button(surf, r, "Done", True, K.font(22, True))
                continue
            label = {"rotate": "Rotate (R)", "sell": "Sell", "wall": "Wall Color",
                     "floor": "Floor Color", "upgrade": "Upgrade Quality"}[key]
            if key in ("wall", "floor"):
                K.button(surf, r, "", False, fb)
                sw = pygame.Rect(r.right - 32, r.centery - 10, 20, 20)
                col = (F.WALL_COLORS[self.g.world.home_wall_idx] if key == "wall"
                       else F.FLOOR_COLORS[self.g.world.home_floor_idx])
                pygame.draw.rect(surf, col, sw, border_radius=4)
                pygame.draw.rect(surf, K.WOOD_DK, sw, 2, border_radius=4)
                K.blit_text(surf, fb, label, (110, 78, 60), ((r.x + 6 + sw.x - 4) // 2, r.centery))
            else:
                K.button(surf, r, label, False, fb)
