"""Cooking: turn crops / fish / animal produce into food that restores energy & HP.

Open the menu at a Stove. Cooked food is an inventory item; selecting it and using
it (Action) eats it. Pure data + a pygame menu (driven by either player's keys).
"""
import pygame
from .settings import SCREEN_W, SCREEN_H, WHITE, GOLD, P1_KEYS, P2_KEYS

ACCENT = (235, 170, 110)

# food id -> stats
FOODS = {
    "fried_egg":    {"label": "Fried Egg",    "energy": 50,  "health": 15, "sell": 70},
    "milk_tea":     {"label": "Milk Tea",     "energy": 40,  "health": 10, "sell": 60, "drink": True},
    "veg_stew":     {"label": "Veggie Stew",  "energy": 75,  "health": 25, "sell": 130},
    "fish_dinner":  {"label": "Fish Dinner",  "energy": 90,  "health": 30, "sell": 190},
    "pumpkin_soup": {"label": "Pumpkin Soup", "energy": 110, "health": 45, "sell": 260},
    "fruit_salad":  {"label": "Fruit Salad",  "energy": 70,  "health": 20, "sell": 150},
    "roast_meat":   {"label": "Roast Meat",   "energy": 95,  "health": 35, "sell": 180},
    # expansion pack (2026-06-04)
    "cheese":         {"label": "Cheese",         "energy": 45,  "health": 18, "sell": 120},
    "veggie_omelette":{"label": "Veggie Omelette","energy": 70,  "health": 22, "sell": 140},
    "corn_soup":      {"label": "Corn Soup",      "energy": 95,  "health": 30, "sell": 175},
    "steak_plate":    {"label": "Steak Plate",    "energy": 115, "health": 45, "sell": 240},
    "pumpkin_pie":    {"label": "Pumpkin Pie",    "energy": 130, "health": 55, "sell": 320},
    "egg_custard":    {"label": "Egg Custard",    "energy": 85,  "health": 30, "sell": 175},
    "goat_cheese":    {"label": "Goat Cheese",    "energy": 60,  "health": 26, "sell": 200},
    # buff dishes (2026-09 level-up) -- see BUFFS below
    "spicy_curry":    {"label": "Spicy Curry",     "energy": 60,  "health": 20, "sell": 185},
    "lucky_dumplings":{"label": "Lucky Dumplings", "energy": 55,  "health": 20, "sell": 230},
    "miners_pie":     {"label": "Miner's Pie",     "energy": 90,  "health": 30, "sell": 250},
    "sushi_roll":     {"label": "Sushi Roll",      "energy": 50,  "health": 18, "sell": 110},
    "farmers_lunch":  {"label": "Farmer's Lunch",  "energy": 80,  "health": 22, "sell": 120},
    "hero_stew":      {"label": "Hero Stew",       "energy": 85,  "health": 50, "sell": 300},
    "yam_porridge":   {"label": "Snow Yam Porridge","energy": 70, "health": 40, "sell": 220},
    "honey_tea":      {"label": "Honey Tea",       "energy": 30,  "health": 10, "sell": 240, "drink": True},
    # forage dishes (2026-09 fix round): wild finds from the forest & meadow
    "wild_salad":     {"label": "Wild Salad",       "energy": 55,  "health": 22, "sell": 150},
    "berry_tart":     {"label": "Blackberry Tart",  "energy": 75,  "health": 24, "sell": 210},
    "hazelnut_cookies": {"label": "Hazelnut Cookies", "energy": 60, "health": 16, "sell": 260},
    "mushroom_soup":  {"label": "Mushroom Soup",    "energy": 100, "health": 40, "sell": 300},
}
# dishes cooked from forageables (src/forage.py); icons painted in artisan_system
FORAGE_DISHES = ("wild_salad", "berry_tart", "hazelnut_cookies", "mushroom_soup")

# food id -> (buff kind, amount, seconds) granted when eaten (Player.add_buff).
# Kinds: speed (+move), luck, mining, fishing, farming, combat (+dmg),
# defense (dmg reduced), regen (energy/sec). Applied by ArtisanMixin.
BUFFS = {
    "spicy_curry":     ("speed",   0.25, 180),
    "lucky_dumplings": ("luck",    0.30, 240),
    "miners_pie":      ("mining",  0.30, 240),
    "sushi_roll":      ("fishing", 0.30, 240),
    "farmers_lunch":   ("farming", 0.30, 240),
    "hero_stew":       ("combat",  0.25, 180),
    "yam_porridge":    ("defense", 0.20, 180),
    "honey_tea":       ("regen",   0.60, 150),
    "hazelnut_cookies": ("speed",  0.15, 240),
    "mushroom_soup":   ("regen",   0.40, 210),
}
BUFF_LABEL = {"speed": "Speed", "luck": "Luck", "mining": "Mining", "fishing": "Fishing",
              "farming": "Farming", "combat": "Attack", "defense": "Defense", "regen": "Regen"}
BUFF_COLOR = {"speed": (140, 220, 250), "luck": (120, 230, 140), "mining": (210, 180, 130),
              "fishing": (120, 180, 250), "farming": (170, 230, 110), "combat": (250, 130, 110),
              "defense": (190, 190, 230), "regen": (250, 210, 120)}


def buff_of(food_id):
    """(kind, amount, seconds) for a buff dish, else None."""
    return BUFFS.get(food_id)


def buff_text(food_id):
    """Short menu/popup text, e.g. '+Speed 3:00'."""
    b = BUFFS.get(food_id)
    if not b:
        return ""
    kind, _amt, secs = b
    return f"+{BUFF_LABEL.get(kind, kind.title())} {int(secs) // 60}:{int(secs) % 60:02d}"

# food id -> {ingredient item id: qty}
RECIPES = {
    "fried_egg":    {"egg": 1},
    "milk_tea":     {"milk": 1},
    "veg_stew":     {"potato": 1, "parsnip": 1},
    "fish_dinner":  {"sardine": 1, "potato": 1},
    "pumpkin_soup": {"pumpkin": 1, "milk": 1},
    "fruit_salad":  {"blueberry": 1, "melon": 1},
    "roast_meat":   {"meat": 1},
    "cheese":          {"milk": 2},
    "veggie_omelette": {"egg": 1, "tomato": 1, "pepper": 1},
    "corn_soup":       {"corn": 1, "milk": 1},
    "steak_plate":     {"meat": 1, "potato": 1, "pepper": 1},
    "pumpkin_pie":     {"pumpkin": 1, "egg": 1, "milk": 1},
    "egg_custard":     {"duck_egg": 1, "milk": 1},
    "goat_cheese":     {"goat_milk": 2},
    "spicy_curry":     {"pepper": 2, "meat": 1},
    "lucky_dumplings": {"cauliflower": 1, "egg": 1},
    "miners_pie":      {"potato": 1, "meat": 1, "egg": 1},
    "sushi_roll":      {"sardine": 1, "anchovy": 1},
    "farmers_lunch":   {"parsnip": 1, "egg": 1},
    "hero_stew":       {"meat": 1, "pumpkin": 1},
    "yam_porridge":    {"snow_yam": 1, "milk": 1},
    "honey_tea":       {"honey": 1, "milk": 1},
    "wild_salad":      {"wild_leek": 1, "dandelion": 1},
    "berry_tart":      {"blackberry": 3, "egg": 1},
    "hazelnut_cookies": {"hazelnut": 2, "egg": 1},
    "mushroom_soup":   {"chanterelle": 1, "milk": 1},
}


def is_food(item_id):
    return item_id in FOODS


def label(item_id):
    if item_id in FOODS:
        return FOODS[item_id]["label"]
    return item_id.replace("_", " ").title()


def sell_value(item_id):
    return FOODS[item_id]["sell"] if item_id in FOODS else 0


class CookingMenu:
    def __init__(self, game, player):
        self.g = game
        self.p = player
        self.sel = 0
        self.items = list(RECIPES.keys())
        self.msg = "Cooks with both bags AND the fridge."

    def move(self, d):
        self.sel = (self.sel + d) % len(self.items)
        self.g.audio.play("ui_move")

    def confirm(self):
        fid = self.items[self.sel]
        if getattr(self.g, "net_mode", None) == "client" and getattr(self.g, "net", None):
            self.g.net.send({"t": "menu", "m": "cook", "food": fid})
            self.g.audio.play("ui_select")
            self.msg = "Cooking... (sent to host)"
            return
        need = RECIPES[fid]
        count = getattr(self.g, "_kitchen_count", None) or self.g._count_all
        remove = getattr(self.g, "_kitchen_remove", None) or self.g._remove_all
        if all(count(i) >= q for i, q in need.items()):
            for i, q in need.items():
                remove(i, q)
            self.p.inv.add(fid, 1)
            self.g.audio.play("harvest")
            self.msg = f"Cooked {FOODS[fid]['label']}!"
            self.g.ui.log(self.msg)
            parts = getattr(self.g, "parts", None)
            if parts is not None:
                parts.sparkle(self.p.x, self.p.y - 10, n=10, color=(255, 214, 150))
            emit = getattr(self.g, "emit", None)
            if emit:
                emit("cooked", p=self.p, food=fid)
        else:
            miss = ", ".join(f"{q} {label(i)}" for i, q in need.items())
            self.msg = f"Need: {miss}"
            self.g.audio.play("ui_move")

    def handle_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.g.state = "play"
            self.g.audio.play("ui_move")
            return
        if key in (P1_KEYS["up"], P2_KEYS["up"]):
            self.move(-1)
        elif key in (P1_KEYS["down"], P2_KEYS["down"]):
            self.move(1)
        elif key in (P1_KEYS["action"], P2_KEYS["action"]):
            self.confirm()

    # how many recipe rows fit at once (scrolling kicks in past this)
    VIS = 7
    PITCH = 54
    ROW_H = 48

    def draw(self, surf):
        """Parchment modal matching the Quest Board / Workbench: ribbon title,
        a well per recipe, the gold row cursor on the pick, ingredients
        right-aligned, footer hint centred."""
        from .ui import scroll_window
        from . import assets
        from . import ui_kit as K
        self._t = getattr(self, "_t", 0.0) + 1 / 60
        K.dim(surf, 150)
        total = len(self.items)
        vis = max(1, min(self.VIS, total))
        pw = 760
        ph = 84 + vis * self.PITCH + 74
        # centred in the band under both HUD hotbar rows (the ribbon clears y=108)
        px, py = (SCREEN_W - pw) // 2, 130 + max(0, (SCREEN_H - 10 - 130 - ph) // 2)
        P = K.modal(surf, (px, py, pw, ph), "Kitchen", K.font(28, True))
        K.blit_text(surf, K.font(15, True), f"{self.p.name} at the stove", K.GOLD_TXT,
                    (P.centerx, P.y + 48))

        if total:
            self.sel %= total
        start, end = scroll_window(total, self.VIS, self.sel)
        y0 = P.y + 84                       # room above for the 'more above' arrow
        f_name, f_sub, f_ing = K.font(17, True), K.font(14, True), K.font(14, True)
        for j, fid in enumerate(self.items[start:end]):
            i = start + j
            r = pygame.Rect(P.x + 24, y0 + j * self.PITCH, pw - 48 - 12, self.ROW_H)
            if i == self.sel:
                K.row_cursor(surf, r, self._t)
            else:
                K.well(surf, r, radius=10)
            try:
                ic = assets.item_icon(fid)
                surf.blit(ic, ic.get_rect(center=(r.x + 34, r.centery)))
            except Exception:
                pass
            f = FOODS[fid]
            tx = r.x + 60
            K.blit_text(surf, f_name, f["label"], K.INK, (tx, r.y + 15), align="left")
            sr = K.blit_text(surf, f_sub, f"+{f['energy']} energy, +{f['health']} HP",
                             (64, 128, 52), (tx, r.y + 34), align="left")
            bt = buff_text(fid)
            if bt:                                   # buff dishes: coloured buff tag
                kind = BUFFS[fid][0]
                col = tuple(int(v * 0.6) for v in BUFF_COLOR.get(kind, GOLD))
                K.blit_text(surf, f_sub, bt, col, (sr.right + 10, r.y + 34), align="left")
            need = RECIPES[fid]
            count = getattr(self.g, "_kitchen_count", None) or self.g._count_all
            afford = all(count(it) >= q for it, q in need.items())
            txt = "   ".join(f"{q} {label(it)}" for it, q in need.items())
            K.blit_text(surf, f_ing, txt, K.INK_SOFT if afford else K.WARN,
                        (r.right - 16, r.centery), align="right")
        # scroll affordances when the list runs past the window
        region_h = self.VIS * self.PITCH - (self.PITCH - self.ROW_H)
        self.g.ui.draw_scrollbar(surf, P.right - 30, y0, region_h, total, self.VIS, start,
                                 track=K.WELL_LINE, thumb_col=K.WOOD)
        self.g.ui.draw_scroll_arrows(surf, start, end, total, P.x + 24, y0, pw - 60, region_h,
                                     vertical=True, color=K.WOOD)
        if self.msg:
            fm = K.font(15, True)
            K.blit_text(surf, fm, K.ellipsize(fm, self.msg, pw - 60), K.INK, (P.centerx, P.bottom - 52))
        K.divider(surf, P.centerx, P.bottom - 35, pw // 2 - 60, heart=False)
        K.blit_text(surf, K.font(13), "Up/Down select  -  Action cook  -  Esc close", K.INK_SOFT,
                    (P.centerx, P.bottom - 20))
