"""Inventory / hotbar-arrange screen (press I) -- CO-OP edition.

Owner: "UI & Rendering" chat. Both players arrange their own 10 locked hotbar
slots AT THE SAME TIME in two stacked panes:

    P1 (top pane):    WASD moves the cursor, SPACE picks / places
    P2 (bottom pane): arrows move the cursor, ENTER picks / places
    (key maps follow P1_KEYS / P2_KEYS, so rebinding carries over)
    mouse:            click slots in either pane; wheel scrolls the pane
                      under the pointer.  I or ESC drops held picks, then closes.

Each pane keeps its own cursor, held pick and backpack scroll. The screen only
RENDERS and routes intent; the actual reordering lives in inventory.py (Core):

    inv.hotbar()        -> list of <=10 entries already shown on the hotbar
    inv.backpack()      -> entries not on the hotbar
    inv.move_slot(a, b) -> reorder within the hotbar
    inv.stow(slot)      -> move hotbar[slot] into the backpack
    inv.equip(bp, slot) -> put backpack[bp] into hotbar slot

Until Core adds those methods a pane still renders and lets you browse; a
status line shows that arranging is inactive. Nothing here mutates Core state
directly (rule: read from self.* / call methods, never poke inventory data).
"""
import math
import pygame

from . import assets
from . import ui_kit as K
from .settings import (SCREEN_W, SCREEN_H, GOLD, UI_BG, UI_BORDER, WHITE,
                       P1_KEYS, P2_KEYS)

HOT = 10                      # locked hotbar slot count
CELL = 52                     # hotbar cell size (pane is half-height)
BP_CELL = 56                  # backpack grid cell
BP_X = 60
PANE_H = SCREEN_H // 2


class _Pane:
    """One player's arrange pane: own cursor, pick, scroll and click rects."""

    def __init__(self, game, pi, y0, keys, tag):
        self.g = game
        self.pi = pi
        self.y0 = y0
        self.keys = keys              # that player's (rebindable) key map
        self.tag = tag                # "P1" / "P2"
        self.cursor = ("hot", 0)      # ("hot", i) or ("bp", i)
        self.held = None              # picked-up source, same shape as cursor
        self.bp_top = 0               # backpack scroll (row index)
        self.vis_rows = 2             # refreshed each draw (for cursor-follow)
        self._hot_rects = []
        self._bp_rects = []
        self.cols = max(1, (SCREEN_W - BP_X * 2 - 20) // BP_CELL)

    # ---- player / inventory access ----
    @property
    def player(self):
        players = getattr(self.g, "players", None)
        if players and self.pi < len(players):
            return players[self.pi]
        return None

    @property
    def inv(self):
        p = self.player
        return p.inv if p is not None else None

    def _hotbar(self):
        inv = self.inv
        return list(inv.hotbar())[:HOT] if inv else []

    def _backpack(self):
        inv = self.inv
        if not inv:
            return []
        fn = getattr(inv, "backpack", None)
        if callable(fn):
            try:
                return list(fn())
            except Exception:
                pass
        return list(inv.hotbar())[HOT:]      # fallback: overflow beyond 10

    def _api(self, name):
        fn = getattr(self.inv, name, None)
        return fn if callable(fn) else None

    @property
    def can_arrange(self):
        return self._api("move_slot") is not None

    # ---- intent ----
    def _activate(self, target):
        if target is None:
            return
        if self.held is None:
            self.held = target
            return
        if self.held == target:
            self.held = None
            return
        hk, hi = self.held
        tk, ti = target
        if hk == "hot" and tk == "hot":
            f = self._api("move_slot")
            if f:
                f(hi, ti)
        elif hk == "bp" and tk == "hot":
            f = self._api("equip")
            if f:
                f(hi, ti)
        elif hk == "hot" and tk == "bp":
            f = self._api("stow")
            if f:
                f(hi)
        elif hk == "bp" and tk == "bp":
            self.held = target           # reselect a different backpack item
            return
        self.held = None

    # ---- input (returns True when the event was this pane's) ----
    def handle_key(self, k):
        K = self.keys
        if k == K["action"]:
            self._activate(self.cursor)
            return True
        if k in (K["left"], K["right"], K["up"], K["down"]):
            self._move_cursor(k)
            return True
        return False

    def click(self, pos):
        for rect, i in self._hot_rects:
            if rect.collidepoint(pos):
                self.cursor = ("hot", i)
                self._activate(("hot", i))
                return True
        for rect, i in self._bp_rects:
            if rect.collidepoint(pos):
                self.cursor = ("bp", i)
                self._activate(("bp", i))
                return True
        return False

    def wheel(self, pos, dy):
        if self.y0 <= pos[1] < self.y0 + PANE_H:
            self.bp_top = max(0, self.bp_top - dy)
            return True
        return False

    def _move_cursor(self, k):
        K = self.keys
        region, i = self.cursor
        n = len(self._backpack())
        cols = self.cols
        if region == "hot":
            if k == K["left"]:
                self.cursor = ("hot", (i - 1) % HOT)
            elif k == K["right"]:
                self.cursor = ("hot", (i + 1) % HOT)
            elif k == K["down"] and n:
                self.cursor = ("bp", min(n - 1, self.bp_top * cols))
        else:
            if k == K["left"]:
                self.cursor = ("bp", max(0, i - 1))
            elif k == K["right"]:
                self.cursor = ("bp", min(n - 1, i + 1)) if n else ("hot", 0)
            elif k == K["down"]:
                self.cursor = ("bp", min(n - 1, i + cols)) if n else self.cursor
            elif k == K["up"]:
                if i - cols < 0:
                    self.cursor = ("hot", 0)
                else:
                    self.cursor = ("bp", i - cols)
            # keep the keyboard cursor on a visible backpack row
            if self.cursor[0] == "bp" and cols:
                row = self.cursor[1] // cols
                if row < self.bp_top:
                    self.bp_top = row
                elif row >= self.bp_top + self.vis_rows:
                    self.bp_top = row - self.vis_rows + 1

    # ---- item names ----
    def _cursor_entry(self):
        region, i = self.cursor
        lst = self._hotbar() if region == "hot" else self._backpack()
        return lst[i] if 0 <= i < len(lst) else None

    def _entry_info(self, entry):
        """(full name, detail) for a slot: 'Blueberry', 'x4  -  sells 50g'."""
        kind, name = entry[0], entry[1]
        if kind == "tool":
            try:
                from .inventory import Inventory
                lab = Inventory.label(entry)
            except Exception:
                lab = str(name).replace("_", " ").title()
            tier = (getattr(self.player, "tool_tiers", None) or {}).get(name, 0)
            return lab, (f"tier {tier}" if tier else "tool")
        name = str(name)
        try:
            from .systems import shop_system as SS
        except Exception:                       # pragma: no cover
            SS = None
        if name.startswith("seed:"):
            lab = name.split(":", 1)[1].replace("_", " ").title() + " Seeds"
        else:
            lab = None
            try:
                from . import fishing
                if name in fishing.FISH_DATA:
                    lab = fishing.display_name(name)
            except Exception:
                lab = None
            if lab is None:
                try:
                    lab = SS.item_label(name) if SS else name.replace("_", " ").title()
                except Exception:
                    lab = name.replace("_", " ").title()
        qty = self.inv.count(name) if self.inv is not None else 0
        price = 0
        try:
            price = SS.sell_value(name) if SS else 0
        except Exception:
            price = 0
        detail = f"x{qty}" + (f"  -  sells {price}g each" if price else "")
        return lab, detail

    def _draw_cursor_name(self, surf, y, right=SCREEN_W - 40):
        entry = self._cursor_entry()
        if entry is None:
            return
        cache = self.__dict__.setdefault("_name_cache", {})
        key = (tuple(entry), self.inv.count(entry[1]) if entry[0] == "item" and self.inv else 0)
        s = cache.get(key)
        if s is None:
            ui_ = self.g.ui
            lab, detail = self._entry_info(entry)
            t1 = K.font(18, True).render(lab, True, K.INK)
            t2 = K.font(14).render(detail, True, K.INK_SOFT)
            s = pygame.Surface((t1.get_width() + t2.get_width() + 14, t1.get_height()),
                               pygame.SRCALPHA)
            s.blit(t1, (0, 0))
            # share the name's baseline
            s.blit(t2, (t1.get_width() + 14, K.font(18, True).get_ascent() - K.font(14).get_ascent()))
            if len(cache) > 64:
                cache.clear()
            cache[key] = s
        # ``y`` is the header row's centre line; right edge = the grid's right edge
        f = K.font(18, True)
        top = y - f.get_ascent() + (f.metrics("H")[0][3] + 1) // 2
        surf.blit(s, (right - s.get_width(), top))

    # ---- draw ----
    def _slot(self, surf, x, y, size, entry, selected, held):
        """A recessed parchment slot (ui_kit.well look); gold rim = cursor,
        warm wood rim = the picked-up item."""
        r = pygame.Rect(x, y, size, size)
        if held:
            pygame.draw.rect(surf, (255, 222, 150), r, border_radius=8)
            pygame.draw.rect(surf, K.WOOD, r, 3, border_radius=8)
        elif selected:
            pygame.draw.rect(surf, K.HILITE, r, border_radius=8)
            pygame.draw.rect(surf, K.GOLD_RIM, r, 3, border_radius=8)
        else:
            # a shade deeper than ui_kit.WELL so pale icons (bone, diamond,
            # quartz) still stand out against the slot
            pygame.draw.rect(surf, (232, 211, 176), r, border_radius=8)
            pygame.draw.rect(surf, (204, 176, 140), r, 2, border_radius=8)
        if entry is None:
            return
        ico = assets.hotbar_icon(entry)
        ico = pygame.transform.scale(ico, (size - 14, size - 14))
        surf.blit(ico, (x + 7, y + 5))
        if entry[0] == "item" and self.inv is not None:
            cnt = K.outlined(K.font(11, True), str(self.inv.count(entry[1])), K.INK, K.CREAM_HI, 1)
            surf.blit(cnt, (x + size - cnt.get_width() - 2, y + size - cnt.get_height() - 1))

    def draw(self, surf):
        ui_ = self.g.ui
        y0 = self.y0
        p = self.player
        name = getattr(p, "name", "?") if p is not None else "?"
        accent = K.P_COL[self.pi % 2]
        cols = self.cols
        grid_w = cols * BP_CELL - 6
        gx0 = (SCREEN_W - grid_w) // 2                 # backpack grid, centred
        # the top pane sits under the ribbon title; the bottom one under the
        # divider -- both then share the same inner rhythm
        top = y0 + (46 if self.pi == 0 else 18)
        hc = top + 16                                  # header row centre line
        # header: face medallion + "P1 - name" (player colour) ... cursor item name
        mx = gx0 + 14
        try:
            pygame.draw.circle(surf, K.WELL, (mx, hc), 14)
            fr = (getattr(p, "frames", None) or {}).get("down", [None])[0]
            if fr is not None:
                face = assets.hud.face_icon(fr, 24)
                clip = surf.get_clip()
                surf.set_clip(pygame.Rect(mx - 13, hc - 13, 26, 26))
                surf.blit(face, (mx - face.get_width() // 2, hc - 12))
                surf.set_clip(clip)
            pygame.draw.circle(surf, accent, (mx, hc), 14, 2)
        except Exception:
            pass
        K.blit_text(surf, K.font(18, True), f"{self.tag} - {name}", accent,
                    (mx + 24, hc), align="left")
        # the full name of whatever the cursor is on (the grid is icons only)
        self._draw_cursor_name(surf, hc, gx0 + grid_w)

        # hotbar row (10 locked slots, centred)
        hot = self._hotbar()
        hy = top + 38
        total_w = HOT * (CELL + 6) - 6
        hx0 = SCREEN_W // 2 - total_w // 2
        self._hot_rects = []
        numf = K.font(11, True)
        for i in range(HOT):
            x = hx0 + i * (CELL + 6)
            entry = hot[i] if i < len(hot) else None
            self._slot(surf, x, hy, CELL, entry,
                       self.cursor == ("hot", i), self.held == ("hot", i))
            surf.blit(numf.render(str((i + 1) % 10), True, K.INK_FAINT), (x + 5, hy + 3))
            self._hot_rects.append((pygame.Rect(x, hy, CELL, CELL), i))

        # backpack grid (everything not on the hotbar)
        bp = self._backpack()
        by = hy + CELL + 32
        K.blit_text(surf, K.font(14, True), f"BACKPACK  ({len(bp)})", K.SPROUT,
                    (gx0, by - 14), align="left")
        rows_total = max(1, math.ceil(len(bp) / cols)) if bp else 0
        limit = min(y0 + PANE_H - 14, SCREEN_H - 24)
        grid_h = limit - by
        self.vis_rows = max(1, (grid_h + 6) // BP_CELL)
        self.bp_top = max(0, min(self.bp_top, max(0, rows_total - self.vis_rows)))
        start = self.bp_top
        end = min(rows_total, start + self.vis_rows)
        if not bp:
            area = pygame.Rect(gx0, by, grid_w, self.vis_rows * BP_CELL - 6)
            pygame.draw.rect(surf, (244, 230, 204), area, border_radius=10)
            pygame.draw.rect(surf, K.WELL_LINE, area, 2, border_radius=10)
            K.blit_text(surf, K.font(15), "Backpack is empty - forage, fish and mine to fill it!",
                        K.INK_SOFT, area.center)
        else:
            # faint empty cells fill the visible rows, so the grid reads as a bag
            for r_ in range(self.vis_rows):
                for c in range(cols):
                    pygame.draw.rect(surf, (244, 232, 208),
                                     (gx0 + c * BP_CELL, by + r_ * BP_CELL, BP_CELL - 6, BP_CELL - 6),
                                     border_radius=8)
        self._bp_rects = []
        for idx in range(start * cols, min(len(bp), end * cols)):
            r = idx // cols - start
            c = idx % cols
            x = gx0 + c * BP_CELL
            y = by + r * BP_CELL
            self._slot(surf, x, y, BP_CELL - 6, bp[idx],
                       self.cursor == ("bp", idx), self.held == ("bp", idx))
            self._bp_rects.append((pygame.Rect(x, y, BP_CELL - 6, BP_CELL - 6), idx))
        if rows_total > self.vis_rows:
            ui_.draw_scrollbar(surf, gx0 + grid_w + 8, by,
                               self.vis_rows * BP_CELL - 6, rows_total, self.vis_rows, start,
                               track=K.WELL_LINE, thumb_col=K.WOOD)
        if not self.can_arrange:
            K.blit_text(surf, K.font(11, True),
                        "(arranging activates once the inventory API is wired in Core)",
                        K.WARN, (gx0, limit + 4), align="left")


class InventoryScreen:
    """Both players' panes, live at the same time. Constructor signature is kept
    compatible with Core's lazy `_open_inventory` (player/player_index unused
    now -- the screen always shows everyone)."""

    def __init__(self, game, player=None, player_index=0, on_close=None):
        self.g = game
        self.on_close = on_close
        self.pi = player_index        # kept for Core back-compat; panes are fixed
        self.panes = [_Pane(game, 0, 0, P1_KEYS, "P1"),
                      _Pane(game, 1, PANE_H, P2_KEYS, "P2")]

    # ---- input ----
    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for pane in self.panes:
                if pane.click(e.pos):
                    return
            return
        if e.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            for pane in self.panes:
                if pane.wheel(pos, e.y):
                    return
            return
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k in (pygame.K_ESCAPE, pygame.K_i):
            holding = [p for p in self.panes if p.held is not None]
            if holding:
                for p in holding:
                    p.held = None     # first press just drops the picks
            else:
                self._close()
            return
        for pane in self.panes:       # disjoint key maps; first taker wins
            if pane.handle_key(k):
                return

    def _close(self):
        if self.on_close:
            self.on_close()
        else:
            self.g.state = "play"

    def update(self, dt):
        pass

    # ---- draw ----
    def draw(self, surf):
        bg = getattr(self, "_bg", None)
        if bg is None:                       # soft warm dusk gradient (built once)
            bg = self._bg = pygame.Surface((SCREEN_W, SCREEN_H))
            for y in range(0, SCREEN_H, 4):
                f = y / SCREEN_H
                pygame.draw.rect(bg, (int(70 - 18 * f), int(52 - 14 * f), int(52 - 10 * f)),
                                 (0, y, SCREEN_W, 4))
        surf.blit(bg, (0, 0))
        # ONE parchment card for both players, ribbon title on its top edge
        card = pygame.Rect(16, 24, SCREEN_W - 32, SCREEN_H - 32)
        K.draw_card(surf, card)
        for pane in self.panes:
            pane.draw(surf)
        K.ribbon(surf, K.font(24, True), "Inventory", (card.centerx, card.y + 2))
        from .ui import key_label as _kl
        def mv(keys):
            labs = [_kl(keys[a]) for a in ("up", "left", "down", "right")]
            return "".join(labs) if all(len(x) == 1 for x in labs) else "/".join(labs)
        hint = (f"P1: {mv(P1_KEYS)} + {_kl(P1_KEYS['action'])}      "
                f"P2: {mv(P2_KEYS)} + {_kl(P2_KEYS['action'])}      "
                "click / wheel: mouse      I or ESC: close")
        # the controls line sits ON the divider between the two players
        hf = K.font(12, True)
        hw = hf.size(hint)[0]
        cx, cy = SCREEN_W // 2, PANE_H
        pygame.draw.line(surf, K.WELL_LINE, (card.x + 24, cy), (cx - hw // 2 - 14, cy), 2)
        pygame.draw.line(surf, K.WELL_LINE, (cx + hw // 2 + 14, cy), (card.right - 24, cy), 2)
        K.blit_text(surf, hf, hint, K.INK_SOFT, (cx, cy))
