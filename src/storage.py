"""Storage Chest: a place to stash items you don't want to carry or sell.

Open it by interacting with a placed Storage Chest in the house. The menu has two
panes -- your bag on the left, the chest on the right. Move items between them:
  Left/Right  switch pane        Up/Down  pick an item
  Action      move 1 item        Shift+Action  move the whole stack
  Esc / B     close

Contents live on the chest's `Placed.store` dict, so they are saved with the house
furniture and survive being moved in Build mode. Tools are never stored.
"""
import pygame
from .settings import SCREEN_W, SCREEN_H, WHITE, GOLD, P1_KEYS, P2_KEYS
from . import ui_kit

ACCENT = (200, 168, 96)
DIM = (150, 120, 70)


def label(item_id):
    if item_id.startswith("seed:"):
        return item_id.split(":", 1)[1].replace("_", " ").title() + " Seed"
    return item_id.replace("_", " ").title()


class StorageMenu:
    def __init__(self, game, player, chest, linked=1, title=None):
        self.g = game
        self.p = player
        self.chest = chest
        self.linked = linked          # >1: merged double/L chest, shared inventory
        self.title = title            # e.g. "FRIDGE" / "TOY CHEST"
        self.side = 0                 # 0 = bag, 1 = chest
        self.sel = [0, 0]
        self.msg = "Stash items you want to keep. Shift+Action moves a whole stack."
        if linked > 1:
            self.msg = (f"{linked} linked chests share this inventory. "
                        "Shift+Action moves a whole stack.")

    # ---- data ----
    def bag_items(self):
        # only stackable items (tools are not in item_order), skip empties
        return [i for i in self.p.inv.item_order if self.p.inv.count(i) > 0]

    def chest_items(self):
        return sorted(k for k, q in self.chest.store.items() if q > 0)

    def cur_list(self):
        return self.bag_items() if self.side == 0 else self.chest_items()

    def _clamp(self):
        for s in (0, 1):
            n = len(self.bag_items() if s == 0 else self.chest_items())
            self.sel[s] = 0 if n == 0 else max(0, min(self.sel[s], n - 1))

    # ---- actions ----
    def move_sel(self, d):
        lst = self.cur_list()
        if lst:
            self.sel[self.side] = (self.sel[self.side] + d) % len(lst)
        self.g.audio.play("ui_move")

    def switch(self, side):
        if side != self.side:
            self.side = side
            self.g.audio.play("ui_move")

    def transfer(self, whole=False):
        lst = self.cur_list()
        if not lst:
            self.g.audio.play("ui_move")
            return
        item = lst[self.sel[self.side]]
        if self.side == 0:                       # bag -> chest
            have = self.p.inv.count(item)
            qty = have if whole else 1
            if qty <= 0:
                return
            self.p.inv.remove(item, qty)
            self.chest.store[item] = self.chest.store.get(item, 0) + qty
            self.msg = f"Stored {qty} {label(item)}"
        else:                                    # chest -> bag
            have = self.chest.store.get(item, 0)
            qty = have if whole else 1
            if qty <= 0:
                return
            self.chest.store[item] = have - qty
            if self.chest.store[item] <= 0:
                del self.chest.store[item]
            self.p.inv.add(item, qty)
            self.msg = f"Took {qty} {label(item)}"
        self.g.audio.play("sell")
        self._clamp()

    # ---- input ----
    def handle_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.g.state = "play"
            self.g.audio.play("ui_move")
            return
        if key in (P1_KEYS["up"], P2_KEYS["up"]):
            self.move_sel(-1)
        elif key in (P1_KEYS["down"], P2_KEYS["down"]):
            self.move_sel(1)
        elif key in (P1_KEYS["left"], P2_KEYS["left"]):
            self.switch(0)
        elif key in (P1_KEYS["right"], P2_KEYS["right"]):
            self.switch(1)
        elif key in (P1_KEYS["action"], P2_KEYS["action"]):
            whole = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            self.transfer(whole)

    # ---- draw ----
    def draw(self, surf):
        """Parchment modal (the ui_kit look): ribbon title, two recessed
        columns (bag | chest), gold row cursor in the active column."""
        from . import assets
        K = ui_kit
        self._clamp()
        pw, ph = 760, 504
        # a little below centre: the ribbon clears the hotbar strips up top
        px, py = (SCREEN_W - pw) // 2, (SCREEN_H - ph) // 2 + 8
        title = self.title or ("STORAGE CHEST" if self.linked <= 1
                               else f"BIG CHEST ({self.linked} LINKED)")
        K.modal(surf, (px, py, pw, ph), title.title(), K.font(26, True), dim_alpha=130)
        K.blit_text(surf, K.font(14, True), f"{self.p.name} sorting items", K.INK_SOFT,
                    (px + pw // 2, py + 44))

        colw = (pw - 60) // 2
        pane = (self.title or "Chest").title()
        cols = [("Your Bag", self.bag_items(), px + 20),
                (pane, self.chest_items(), px + 40 + colw)]
        top = py + 64
        rows_h = 368
        # header lane (32) | ▲ lane | VIS rows | ▼ lane
        ROW_TOP, PITCH, ROWH, VIS = top + 44, 38, 34, 8   # scrolling window of VIS rows
        head_f, row_f, cnt_f = K.font(18, True), K.font(15, True), K.font(12, True)
        t = pygame.time.get_ticks() / 1000.0
        for ci, (title, items, cx) in enumerate(cols):
            active = (ci == self.side)
            box = pygame.Rect(cx, top, colw, rows_h)
            K.well(surf, box, hot=active, radius=12)
            K.blit_text(surf, head_f, title, K.INK if active else K.INK_SOFT,
                        (cx + 18, top + 20), align="left")
            n = len(items)
            if not items:
                K.blit_text(surf, K.font(15), "(empty)", K.INK_FAINT,
                            (box.centerx, ROW_TOP + 2 * PITCH))
            # scroll the visible window so the selected row is always shown, even
            # past row 8 -- start is clamped to keep [start, start+VIS) inside [0, n)
            start = 0
            if n > VIS:
                start = max(0, min(self.sel[ci] - VIS // 2, n - VIS))
            bar_room = 14 if n > VIS else 0              # scrollbar lane on the right
            for vi, it in enumerate(items[start:start + VIS]):
                i = start + vi
                ry = ROW_TOP + vi * PITCH
                r = pygame.Rect(cx + 8, ry, colw - 16 - bar_room, ROWH)
                if i == self.sel[ci]:
                    if active:
                        K.row_cursor(surf, r, t)
                    else:                                # where the other cursor rests
                        pygame.draw.rect(surf, (234, 214, 180), r, border_radius=10)
                # icon, name and count all share the row's vertical centre
                try:
                    icon = assets.item_icon(it)
                    surf.blit(icon, (r.x + 16, r.centery - icon.get_height() // 2))
                except Exception:
                    pass
                qty = (self.p.inv.count(it) if ci == 0 else self.chest.store.get(it, 0))
                qtxt = f"x{qty}"
                qw = row_f.size(qtxt)[0]
                K.blit_text(surf, row_f, qtxt, K.GOLD_TXT, (r.right - 12, r.centery), align="right")
                K.blit_text(surf, row_f, K.ellipsize(row_f, label(it), r.w - 64 - qw - 20),
                            K.INK if active else K.INK_SOFT, (r.x + 52, r.centery), align="left")
            # overflow affordances when the list is longer than the window
            if n > VIS:
                # right-edge scrollbar (thumb size & position track the window)
                track = pygame.Rect(box.right - 14, ROW_TOP, 5, VIS * PITCH - 4)
                pygame.draw.rect(surf, K.WELL_LINE, track, border_radius=2)
                th = max(18, int(track.height * VIS / n))
                ty = track.y + int((track.height - th) * (start / (n - VIS)))
                pygame.draw.rect(surf, K.WOOD if active else K.INK_FAINT,
                                 (track.x, ty, 5, th), border_radius=2)
                # little up/down triangles in their own lanes above / below the rows
                ax, acol = box.centerx, (K.WOOD if active else K.INK_FAINT)
                if start > 0:
                    ay = ROW_TOP - 11
                    pygame.draw.polygon(surf, acol, [(ax, ay), (ax - 6, ay + 7), (ax + 6, ay + 7)])
                if start + VIS < n:
                    ay = ROW_TOP + VIS * PITCH + 1
                    pygame.draw.polygon(surf, acol, [(ax, ay + 7), (ax - 6, ay), (ax + 6, ay)])
                # "showing 9-16 / 23" counter so you know where you are in the list
                K.blit_text(surf, cnt_f, f"{start + 1}-{min(start + VIS, n)} / {n}",
                            K.INK_SOFT, (box.right - 16, top + 20), align="right")

        msg_f = K.fit_font(self.msg, pw - 60, (15, 14, 13, 12), bold=True)
        K.blit_text(surf, msg_f, self.msg, K.GOLD_TXT, (px + pw // 2, py + ph - 56))
        K.divider(surf, px + pw // 2, py + ph - 40, 150, heart=False)
        K.blit_text(surf, K.font(12, True),
                    "Left/Right switch  -  Up/Down select  -  Action move 1  -  "
                    "Shift+Action move all  -  Esc close",
                    K.INK_SOFT, (px + pw // 2, py + ph - 24))
