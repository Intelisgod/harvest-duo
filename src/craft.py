"""Tool upgrade tiers + the in-house Workbench upgrade menu.

Data (tier names/colours, recipes) is pure and unit-testable. The UpgradeMenu UI
pulls fonts from game.ui and is driven by either player's keys.
"""
import pygame
from .settings import (SCREEN_W, SCREEN_H, WHITE, GOLD, UI_BORDER,
                       P1_KEYS, P2_KEYS)
from . import loot

TIER_NAMES = ["Basic", "Copper", "Iron", "Gold", "Iridium"]
TIER_COLORS = [(170, 170, 178), (205, 120, 70), (200, 205, 215),
               (240, 205, 80), (175, 130, 235)]
MAX_TIER = len(TIER_NAMES) - 1

UPGRADABLE = ["hoe", "watering_can", "pickaxe", "axe", "sword", "fishing_rod"]
TOOL_LABEL = {"hoe": "Hoe", "watering_can": "Watering Can", "pickaxe": "Pickaxe",
              "axe": "Axe", "sword": "Sword", "fishing_rod": "Fishing Rod"}

# recipe to reach tier index i (from i-1): (gold, {material: qty}); index 0 unused
RECIPES = [
    None,
    (300,  {"copper": 5}),                              # -> Copper
    (800,  {"iron": 5}),                                # -> Iron
    (2000, {"gold_ore": 5, "essence": 3}),             # -> Gold
    (5000, {"iridium_ore": 8, "void_essence": 5}),     # -> Iridium
]

# what each tier improves, for the tooltip
TIER_PERK = {
    "hoe": "till a wider patch",
    "watering_can": "water a wider patch",
    "pickaxe": "more ore, less energy",
    "axe": "more wood, less energy",
    "sword": "+4 damage per tier",
    "fishing_rod": "easier catches",
}


def next_recipe(tier):
    nt = tier + 1
    return RECIPES[nt] if 0 < nt < len(RECIPES) else None


def can_afford(game, player, recipe):
    if not recipe:
        return False
    gold, mats = recipe
    if game.gold < gold:
        return False
    return all(player.inv.count(m) >= q for m, q in mats.items())


def apply_upgrade(game, player, tool):
    """Deduct cost and bump the tool tier. Returns True on success."""
    tier = player.tool_tiers.get(tool, 0)
    rec = next_recipe(tier)
    if not can_afford(game, player, rec):
        return False
    gold, mats = rec
    game.gold -= gold
    for m, q in mats.items():
        player.inv.remove(m, q)
    player.tool_tiers[tool] = tier + 1
    emit = getattr(game, "emit", None)
    if emit:
        emit("tool_upgraded", p=player, tool=tool, tier=tier + 1)
    return True


# ---- Workbench CRAFTING (second tab of the menu): consumables made from loot.
#      id -> {label, gold, mats{item: qty}, qty (made per craft), desc}
CRAFTABLES = {
    "bomb": {"label": "Bomb", "gold": 0, "mats": {"stone": 3, "copper": 1, "slime_goo": 1},
             "qty": 1, "desc": "Use in the mine: blasts rocks & monsters"},
    "mega_bomb": {"label": "Mega Bomb", "gold": 0,
                  "mats": {"stone": 6, "iron": 1, "essence": 1, "slime_goo": 2},
                  "qty": 1, "desc": "A huge blast radius - clears half a cave"},
    "rope_ladder": {"label": "Rope Ladder", "gold": 0, "mats": {"stone": 20, "wood": 5},
                    "qty": 1, "desc": "Use in the mine: drop straight to the next level"},
}


def craft_recipe(what):
    c = CRAFTABLES.get(what)
    return (c["gold"], c["mats"]) if c else None


def craft_item(game, player, what):
    """Pay for and make one batch of a CRAFTABLES item. Returns True on success."""
    c = CRAFTABLES.get(what)
    rec = craft_recipe(what)
    if not c or not can_afford(game, player, rec):
        return False
    game.gold -= c["gold"]
    for m, q in c["mats"].items():
        player.inv.remove(m, q)
    player.inv.add(what, c["qty"])
    emit = getattr(game, "emit", None)
    if emit:
        emit("crafted", p=player, what=what)
    return True


class UpgradeMenu:
    def __init__(self, game, player):
        self.g = game
        self.p = player
        self.sel = 0
        self.tab = 0                       # 0 = tool upgrades, 1 = crafting
        self.items = list(UPGRADABLE)
        self.crafts = list(CRAFTABLES)
        self.msg = "Spend ore, monster loot & gold to upgrade."
        self.flash = 0.0                   # green pulse on the row just crafted

    # ---- input ----
    def move(self, d):
        n = len(self.crafts) if self.tab == 1 else len(self.items)
        self.sel = (self.sel + d) % max(1, n)
        self.g.audio.play("ui_move")

    def switch_tab(self):
        self.tab = 1 - self.tab
        self.sel = 0
        self.msg = ("Craft handy consumables from your loot." if self.tab == 1
                    else "Spend ore, monster loot & gold to upgrade.")
        self.g.audio.play("ui_move")

    def confirm_craft(self):
        what = self.crafts[self.sel]
        c = CRAFTABLES[what]
        if getattr(self.g, "net_mode", None) == "client" and getattr(self.g, "net", None):
            self.g.net.send({"t": "menu", "m": "craft", "tool": what})
            self.g.audio.play("ui_select")
            self.msg = "Crafting... (sent to host)"
            return
        if not craft_item(self.g, self.p, what):
            need = ", ".join(f"{q} {loot.label(m)}" for m, q in c["mats"].items())
            self.msg = f"Need {need}" + (f" + {c['gold']}g." if c["gold"] else ".")
            self.g.audio.play("ui_move")
            return
        self.g.audio.play("craft" if "craft" in getattr(self.g.audio, "sfx", {}) else "sell")
        self.flash = 0.5
        have = self.p.inv.count(what)
        self.msg = f"Crafted {c['qty']} {c['label']}! (you have {have})"
        self.g.ui.log(self.msg)

    def confirm(self):
        if self.tab == 1:
            self.confirm_craft()
            return
        tool = self.items[self.sel]
        if getattr(self.g, "net_mode", None) == "client" and getattr(self.g, "net", None):
            self.g.net.send({"t": "menu", "m": "craft", "tool": tool})
            self.g.audio.play("ui_select")
            self.msg = "Upgrading... (sent to host)"
            return
        tier = self.p.tool_tiers.get(tool, 0)
        rec = next_recipe(tier)
        if rec is None:
            self.msg = f"{TOOL_LABEL[tool]} is already Iridium (max)."
            self.g.audio.play("ui_move")
            return
        if not can_afford(self.g, self.p, rec):
            gold, mats = rec
            need = ", ".join(f"{q} {loot.label(m)}" for m, q in mats.items())
            self.msg = f"Need {gold}g + {need}."
            self.g.audio.play("ui_move")
            return
        apply_upgrade(self.g, self.p, tool)
        self.g.audio.play("sell")
        self.msg = f"{TOOL_LABEL[tool]} upgraded to {TIER_NAMES[tier + 1]}!"
        self.g.ui.log(self.msg)

    def handle_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.g.state = "play"
            self.g.audio.play("ui_move")
            return
        if key in (P1_KEYS["left"], P2_KEYS["left"], P1_KEYS["right"], P2_KEYS["right"],
                   pygame.K_TAB):
            self.switch_tab()
        elif key in (P1_KEYS["up"], P2_KEYS["up"]):
            self.move(-1)
        elif key in (P1_KEYS["down"], P2_KEYS["down"]):
            self.move(1)
        elif key in (P1_KEYS["action"], P2_KEYS["action"]):
            self.confirm()

    # ---- draw ----
    # row pitch per tab; the parchment card is sized to the open tab's rows
    TOOL_ROW, CRAFT_ROW = 62, 84
    _TOP, _FOOT = 112, 72

    def _panel_rect(self):
        """Card rect for the open tab, sized to its own rows (nothing left
        empty) and centred in the band under both HUD hotbar rows, so the
        ribbon title never lands on the hotbars (its top stays below y=108)."""
        pw = 760
        n, pitch = ((len(self.crafts), self.CRAFT_ROW) if self.tab == 1
                    else (len(self.items), self.TOOL_ROW))
        ph = self._TOP + max(1, n) * pitch + self._FOOT
        py = 130 + max(0, (SCREEN_H - 10 - 130 - ph) // 2)
        return pygame.Rect((SCREEN_W - pw) // 2, py, pw, ph)

    def draw(self, surf):
        from . import ui_kit as K
        self._t = getattr(self, "_t", 0.0) + 1 / 60
        K.dim(surf, 150)
        P = K.modal(surf, self._panel_rect(), "Workbench", K.font(28, True))
        pw = P.w
        K.blit_text(surf, K.font(15, True), f"{self.p.name}'s tools   -   Gold: {self.g.gold:,}g",
                    K.GOLD_TXT, (P.centerx, P.y + 48))
        # tabs (Left/Right switch), centred under the title
        tw, th, gap = 190, 32, 12
        tx0 = P.centerx - tw - gap // 2
        K.tabs(surf, [pygame.Rect(tx0, P.y + 64, tw, th), pygame.Rect(tx0 + tw + gap, P.y + 64, tw, th)],
               ["Tool Upgrades", "Crafting"], self.tab)

        row_y = P.y + self._TOP
        if self.tab == 1:
            self._draw_crafts(surf, P.x, pw, row_y)
            self._draw_footer(surf, P.x, P.y, P.h)
            return
        f_name, f_sub, f_small = K.font(18, True), K.font(14), K.font(14, True)
        for i, tool in enumerate(self.items):
            tier = self.p.tool_tiers.get(tool, 0)
            r = pygame.Rect(P.x + 24, row_y + i * self.TOOL_ROW, pw - 48, self.TOOL_ROW - 8)
            if i == self.sel:
                K.row_cursor(surf, r, self._t)
            else:
                K.well(surf, r, radius=10)
            # tier swatch, centred on the row
            sw = pygame.Rect(0, 0, 26, 26)
            sw.center = (r.x + 32, r.centery)
            pygame.draw.rect(surf, TIER_COLORS[tier], sw, border_radius=6)
            pygame.draw.rect(surf, K.WOOD_DK, sw, 2, border_radius=6)
            K.blit_text(surf, f_name, TOOL_LABEL[tool], K.INK, (r.x + 58, r.y + 17), align="left")
            K.blit_text(surf, f_sub, f"{TIER_NAMES[tier]}  -  {TIER_PERK[tool]}", K.INK_SOFT,
                        (r.x + 58, r.y + 37), align="left")
            # recipe / status on the right
            rec = next_recipe(tier)
            if rec is None:
                K.blit_text(surf, f_small, "MAX (Iridium)", _ink(TIER_COLORS[MAX_TIER]),
                            (r.right - 16, r.centery), align="right")
            else:
                gold, mats = rec
                afford = can_afford(self.g, self.p, rec)
                parts = [f"{gold}g"] + [f"{q} {loot.label(m)}" for m, q in mats.items()]
                col = (64, 128, 52) if afford else K.WARN
                K.blit_text(surf, f_small, "  +  ".join(parts), col,
                            (r.right - 16, r.y + 17), align="right")
                K.blit_text(surf, K.font(13, True), f"-> {TIER_NAMES[tier + 1]}",
                            _ink(TIER_COLORS[tier + 1]), (r.right - 16, r.y + 37), align="right")

        self._draw_footer(surf, P.x, P.y, P.h)

    def _draw_footer(self, surf, px, py, ph):
        from . import ui_kit as K
        pw = 760
        cx = px + pw // 2
        if self.msg:
            f = K.font(15, True)
            K.blit_text(surf, f, K.ellipsize(f, self.msg, pw - 60), K.INK, (cx, py + ph - 52))
        K.divider(surf, cx, py + ph - 35, pw // 2 - 60, heart=False)
        verb = "craft" if self.tab == 1 else "upgrade"
        K.blit_text(surf, K.font(13), f"Up/Down select   -   Left/Right switch tab   -   Action {verb}"
                    "   -   Esc / B close", K.INK_SOFT, (cx, py + ph - 20))

    def _draw_crafts(self, surf, px, pw, row_y):
        from . import assets
        from . import ui_kit as K
        self.flash = max(0.0, self.flash - 1 / 60)
        f_name, f_sub, f_small = K.font(18, True), K.font(14), K.font(14, True)
        for i, what in enumerate(self.crafts):
            c = CRAFTABLES[what]
            r = pygame.Rect(px + 24, row_y + i * self.CRAFT_ROW, pw - 48, self.CRAFT_ROW - 8)
            on = (i == self.sel)
            if on:
                K.row_cursor(surf, r, getattr(self, "_t", 0.0))
                if self.flash > 0:                    # green pulse on the row just crafted
                    fl = pygame.Surface(r.size, pygame.SRCALPHA)
                    pygame.draw.rect(fl, (*K.LEAF, int(150 * self.flash)), fl.get_rect(),
                                     border_radius=10)
                    surf.blit(fl, r.topleft)
            else:
                K.well(surf, r, radius=10)
            try:
                ic = pygame.transform.scale(assets.item_icon(what), (48, 48))
                surf.blit(ic, ic.get_rect(center=(r.x + 42, r.centery)))
            except Exception:
                pass
            have = self.p.inv.count(what)
            tx = r.x + 78
            K.blit_text(surf, f_name, f"{c['label']}  x{c['qty']}", K.INK, (tx, r.y + 17),
                        align="left")
            K.blit_text(surf, f_small, f"you have {have}", K.GOLD_TXT, (r.right - 16, r.y + 17),
                        align="right")
            K.blit_text(surf, f_sub, c["desc"], K.INK_SOFT, (tx, r.y + 38), align="left")
            rec = craft_recipe(what)
            afford = can_afford(self.g, self.p, rec)
            parts = ([f"{c['gold']}g"] if c["gold"] else []) + \
                [f"{q} {loot.label(m)} ({self.p.inv.count(m)})" for m, q in c["mats"].items()]
            col = (64, 128, 52) if afford else K.WARN
            K.blit_text(surf, f_small, K.ellipsize(f_small, "Needs: " + " + ".join(parts),
                                                   r.right - 16 - tx),
                        col, (tx, r.y + 59), align="left")


def _ink(c, k=0.62):
    """A tier colour darkened enough to read as text on the parchment card."""
    return tuple(int(v * k) for v in c)
