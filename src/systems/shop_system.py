"""General store / shipping bin: the shop menu, buying and bulk selling.

Owner: "Farming, Animals & Cooking" chat (owns the economy/shop).
Related modules: crops.py (seeds), animals.py (livestock + produce sell),
loot.py, cooking.py, fishing.py (sell tables).

``sell_value`` is the single source of truth for what an item sells for; other
systems should route pricing through it rather than hard-coding values.
``unit_sell_value`` is what a sale actually pays (seller's crop skill + today's
market "hot item" bonus -- the ONE place that bonus is applied). Every sale
emits ``item_sold(p, item, qty, gold)``.
2026-09: "Farm Supplies" section (sprinklers, premium seeds, fertilizer, artisan
machines), section headers, daily hot item (announced each morning), Shift = x5.
"""
import random
import pygame
from ..settings import P1_KEYS, P2_KEYS, AREA_COOP
from ..crops import CROPS, shop_seeds, crop_label
from .. import crops as _crops
from .. import animals, loot, cooking
from ..animals import Animal
from ..fishing import FISH
from ..inventory import Inventory
try:                                   # Farm Supplies registry (same domain)
    from .artisan_system import MACHINES, SUPPLIES, GOODS, GOOD_SOURCE
except Exception:                      # pragma: no cover - defensive
    MACHINES, SUPPLIES, GOODS, GOOD_SOURCE = {}, {}, {}, {}

# Flat sell prices for raw materials not covered by another pricing table.
SELL = {"stone": 5, "wood": 5, "copper": 60, "iron": 120, "gold_ore": 300}

# Daily market "hot item": one crop / fish / artisan good sells +50% today.
# Picked deterministically from the date (no save key needed) by ShopMixin.
HOT = {"item": None}
HOT_MULT = 1.5
_NOSELECT = ("hot", "header")          # shop rows that are labels, not buttons

# "Sell all" (shop row + shipping bin) only bulk-sells produce and loot. Keepsakes
# (Twin Heart Locket, Golden Egg, City Key, relics), bombs / rope ladders, machines,
# fertilizer and cooked meals (buff dishes!) stay in the bag; they can still be
# sold one at a time from the "Sell items..." list.
KEEP_CATS = ("trophy", "relic", "bomb", "tool", "machine", "farming")


def bulk_sellable(item_id):
    """True if 'Sell all' may sell ``item_id`` (value aside)."""
    if item_id.startswith("seed:") or cooking.is_food(item_id):
        return False
    if loot.is_material(item_id) and loot.MATERIALS[item_id].get("cat") in KEEP_CATS:
        return False
    return True


def item_label(item_id):
    """Human name for any sellable id (crop / fish / food / registry item)."""
    try:                                      # Core display-name overrides
        from ..inventory import ITEM_LABELS   # ('sprinkler2' -> 'Premium Sprinkler')
        if item_id in ITEM_LABELS:
            return ITEM_LABELS[item_id]
    except Exception:                         # pragma: no cover - defensive
        pass
    if cooking.is_food(item_id):
        return cooking.label(item_id)
    if loot.is_material(item_id):
        return loot.label(item_id)
    return item_id.replace("_", " ").title()


def pick_hot_item(season, day, year):
    """Today's hot item -- deterministic per date so save/load keeps it."""
    rng = random.Random(f"hot|{year}|{season}|{day}")
    crops = sorted(c for c, d in CROPS.items() if d["season"] == season)
    fish = sorted(f for f, v in FISH.items() if 0 < v <= 160)
    # artisan goods made from an in-season crop, or from animals / bees
    goods = sorted(g for g in GOODS
                   if GOOD_SOURCE.get(g) is None or GOOD_SOURCE.get(g) in crops)
    roll = rng.random()
    pool = crops if roll < 0.5 else fish if roll < 0.75 else goods
    pool = pool or crops or fish
    return rng.choice(pool) if pool else None


def sell_value(item_id):
    if item_id in CROPS:
        return CROPS[item_id]["sell"]
    if item_id in FISH:
        return FISH[item_id]
    if loot.is_material(item_id):       # ores + monster materials
        return loot.sell_value(item_id)
    if cooking.is_food(item_id):        # cooked dishes
        return cooking.sell_value(item_id)
    if item_id in animals.PRODUCE_SELL:  # egg / milk
        return animals.PRODUCE_SELL[item_id]
    if item_id in SELL:
        return SELL[item_id]
    return 0


def unit_sell_value(player, item_id):
    """What ONE of ``item_id`` sells for when ``player`` is the seller
    (applies their crop-value skill bonus, like sell_all does)."""
    val = sell_value(item_id)
    if val > 0 and item_id in CROPS:
        val = int(val * player.skills.crop_value_mult)
    if val > 0 and item_id == HOT.get("item"):      # the ONE place the hot bonus applies
        val = int(val * HOT_MULT)
    return val


class ShopMenu:
    def __init__(self):
        self.sel = 0
        self.options = []
        self.title = "General Store"
        self.mode = "main"             # "main" | "sell" (per-item sell list)
        self._args = ("Spring", True, "General Store")   # last build() args (for Back)

    def build(self, season, allow_buy=True, title="General Store"):
        self.title = title
        self.mode = "main"
        self._args = (season, allow_buy, title)
        opts = []
        hot = HOT.get("item")
        if hot:
            opts.append((f"* HOT TODAY: {item_label(hot)} +50% *", None, "hot"))
        if allow_buy:
            opts.append(("~ Seeds ~   (Shift: buy 5)", None, "header"))
            for s in shop_seeds(season):
                opts.append((f"Buy {crop_label(s)} Seeds", CROPS[s]["seed"], "buy:" + s))
            opts.append(("~ Livestock ~", None, "header"))
            for akind, a in animals.ANIMALS.items():   # registry-driven livestock list
                opts.append((f"Buy {a['label']} (to coop)", a["cost"], "animal:" + akind))
            opts.append(("~ Farm Supplies ~", None, "header"))
            opts.append(("Buy Sprinkler", 600, "buyitem:sprinkler"))
            opts.append(("Buy Premium Sprinkler (3x3)", 1500, "buyitem:sprinkler2"))
            for s in _crops.premium_seeds(season):     # premium seeds by season
                opts.append((f"Buy {crop_label(s)} Seeds (premium)",
                             CROPS[s]["seed"], "buy:" + s))
            for sid, (lab, price) in SUPPLIES.items():
                opts.append((f"Buy {lab}", price, "buyitem:" + sid))
            for mid, m in MACHINES.items():            # artisan machines
                opts.append((f"Buy {m['label']}", m["price"], "buyitem:" + mid))
        opts.append(("Sell items...  (pick what to sell)", None, "sellmenu"))
        opts.append(("Sell all crops / fish / goods", None, "sell"))
        opts.append(("Leave", None, "leave"))
        self.options = opts
        self.sel %= len(self.options)
        self.skip_labels(1)

    def build_sell(self, player, keep_sel=False):
        """Per-item sell list for ``player`` (whoever opened the shop). Each row
        shows the held quantity and the UNIT price; rows vanish when sold out."""
        self.mode = "sell"
        self.title = f"Sell - {player.name}"
        sel = self.sel if keep_sel else 0
        opts = []
        for item_id in list(player.inv.item_order):
            if item_id.startswith("seed:"):          # seeds never sell (same as sell_all)
                continue
            val = unit_sell_value(player, item_id)
            qty = player.inv.count(item_id)
            if val <= 0 or qty <= 0:
                continue
            label = Inventory.label(("item", item_id))
            hot = "  HOT!" if item_id == HOT.get("item") else ""
            opts.append((f"Sell {label}  x{qty}{hot}", val, "sellitem:" + item_id))
        if not opts:
            opts.append(("(nothing to sell)", None, "sellback"))
        opts.append(("Back", None, "sellback"))
        self.options = opts
        self.sel = min(sel, len(opts) - 1)

    def skip_labels(self, d=1):
        """Move the cursor off label rows (hot-item banner / section headers)."""
        n = len(self.options)
        for _ in range(n):
            if self.options[self.sel % n][2] not in _NOSELECT:
                break
            self.sel = (self.sel + d) % n


class ShopMixin:
    """Shop navigation, purchases and the 'sell all' action."""

    def shop_input(self, key):
        # never crash on a missing/empty shop (state desync or an empty
        # stock list) -- just drop back to play
        if not getattr(self, "shop", None) or not self.shop.options:
            self.state = "play"
            return
        if key in (P1_KEYS["up"], P2_KEYS["up"]):
            self.shop.sel = (self.shop.sel - 1) % len(self.shop.options)
            if hasattr(self.shop, "skip_labels"):
                self.shop.skip_labels(-1)
        elif key in (P1_KEYS["down"], P2_KEYS["down"]):
            self.shop.sel = (self.shop.sel + 1) % len(self.shop.options)
            if hasattr(self.shop, "skip_labels"):
                self.shop.skip_labels(1)
        elif key in (P1_KEYS["action"], P2_KEYS["action"]):
            if getattr(self, "net_mode", None) == "client":
                self._client_shop_confirm()      # relay the purchase to the host
            else:
                self.do_shop_select()
        elif key in (P1_KEYS["prev"], P2_KEYS["prev"]):
            if self.shop.mode == "sell":         # back out of the sell list first
                self.shop.build(*self.shop._args)
                self.shop.sel = 0
                self.audio.play("ui_move")
            else:
                self.state = "play"

    def do_shop_select(self):
        label, price, kind = self.shop.options[self.shop.sel]
        if kind == "sellmenu":                       # open the per-item sell list
            self.shop.build_sell(self.players[self.shop_buyer])
            self.audio.play("ui_select")
            return
        if kind == "sellback":                       # back to the main shop page
            self.shop.build(*self.shop._args)
            self.shop.sel = 0
            self.audio.play("ui_move")
            return
        if kind.startswith("sellitem:"):
            item_id = kind.split(":", 1)[1]          # maxsplit: ids may contain ':'
            p = self.players[self.shop_buyer]
            whole = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
            self._sell_items(p, item_id, p.inv.count(item_id) if whole else 1)
            self.shop.build_sell(p, keep_sel=True)   # refresh quantities / drop empties
            return
        if kind in _NOSELECT:                        # banner / header rows do nothing
            self.audio.play("ui_move")
            return
        if kind == "leave" or kind == "none":
            self.state = "play"
        elif kind.startswith("buy:"):
            crop = kind.split(":", 1)[1]
            n = self._shop_bulk_qty()
            cost = CROPS[crop]["seed"]
            n = max(1, min(n, self.gold // max(1, cost))) if self.gold >= cost else 1
            if self.gold >= cost * n:
                self.gold -= cost * n
                self.players[self.shop_buyer].inv.add("seed:" + crop, n)
                self.ui.log(f"Bought {n} {crop_label(crop)} Seed{'s' if n > 1 else ''}"
                            f" (-{cost * n}g)")
                self.audio.play("sell")
            else:
                self.ui.log("Not enough gold!")
                self.audio.play("error")
        elif kind.startswith("animal:"):
            akind = kind.split(":", 1)[1]
            cost = animals.ANIMALS[akind]["cost"]
            if self.gold >= cost:
                self.gold -= cost
                n = len(self.animals)
                self.animals.append(Animal(akind, 3 + n % 5, 3 + (n // 5)))   # placed in the coop barn
                if self.world.current == AREA_COOP:
                    self._rehome_animals()                                    # tidy them in immediately
                self.ui.log(f"Bought a {animals.ANIMALS[akind]['label']}! It's in the coop (-{cost}g)")
                self.audio.play("sell")
            else:
                self.ui.log("Not enough gold!")
        elif kind.startswith("buyitem:"):
            it = kind.split(":", 1)[1]
            n = self._shop_bulk_qty() if it in SUPPLIES else 1   # bulk only for consumables
            n = max(1, min(n, self.gold // max(1, price))) if self.gold >= price else 1
            if self.gold >= price * n:
                self.gold -= price * n
                self.players[self.shop_buyer].inv.add(it, n)
                self.ui.log(f"Bought {n} x {item_label(it)} (-{price * n}g)" if n > 1
                            else f"Bought {item_label(it)} (-{price}g)")
                self.audio.play("sell")
                if it in MACHINES and hasattr(self, "toast"):
                    self.toast(f"{MACHINES[it]['label']} bought!",
                               "Use it on farm grass to place it", icon=it,
                               color=(255, 214, 140))
            else:
                self.ui.log("Not enough gold!")
                self.audio.play("error")
        elif kind == "sell":
            self.sell_all()

    def _shop_bulk_qty(self):
        """Shift held while buying seeds / fertilizer -> buy 5 at once."""
        try:
            return 5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
        except Exception:
            return 1

    def _sell_items(self, p, item_id, qty):
        """Sell up to ``qty`` of one item from ``p``'s bag (used by the per-item
        sell list, locally and via the LAN relay). Returns the gold earned."""
        qty = max(0, min(int(qty), p.inv.count(item_id)))
        val = unit_sell_value(p, item_id)
        if qty <= 0 or val <= 0:
            return 0
        earned = val * qty
        p.inv.remove(item_id, qty)
        self.gold += earned
        self.audio.play("sell")
        self.audio.play("coin")
        hot = " (HOT +50%!)" if item_id == HOT.get("item") else ""
        self.ui.log(f"{p.name} sold {qty} x {item_label(item_id)} (+{earned}g){hot}")
        self.emit("item_sold", p=p, item=item_id, qty=qty, gold=earned)
        return earned

    def sell_all(self):
        earned = 0
        hot_gold = 0
        sold = []                                  # (p, item, qty, gold) -> item_sold events
        kept = 0                                   # sellable keepsakes / meals left alone
        for p in self.players:
            for item_id in list(p.inv.items.keys()):
                if not bulk_sellable(item_id):
                    if not item_id.startswith("seed:") and sell_value(item_id) > 0:
                        kept += 1
                    continue
                val = unit_sell_value(p, item_id)  # crop skill + hot bonus, one place
                if val > 0:
                    qty = p.inv.count(item_id)
                    earned += val * qty
                    if item_id == HOT.get("item"):
                        hot_gold += val * qty
                    sold.append((p, item_id, qty, val * qty))
                    p.inv.items[item_id] = 0
                    del p.inv.items[item_id]
                    p.inv.item_order.remove(item_id)
        self.gold += earned
        if earned:
            self.audio.play("sell")
            self.audio.play("coin")
        hot = f" (hot item bonus included: {hot_gold}g)" if hot_gold else ""
        self.ui.log(f"Sold goods for {earned}g!{hot}" if earned else "Nothing to sell.")
        if kept:
            self.ui.log("Keepsakes, tools & meals kept (sell them one by one).")
        for p, item_id, qty, gold in sold:
            self.emit("item_sold", p=p, item=item_id, qty=qty, gold=gold)

    # ---------- daily market (hot item) ----------
    def _shop_refresh_hot(self):
        t = self.time
        HOT["item"] = pick_hot_item(t.season, t.day, t.year)
        return HOT["item"]

    def _on_reset_shop_market(self):
        self._shop_refresh_hot()

    def _on_load_shop_market(self, d):
        self._shop_refresh_hot()

    def _on_new_day_shop_market(self):
        hot = self._shop_refresh_hot()
        if hot:
            self.ui.log(f"Market news: {item_label(hot)} sells +50% at the shop today!")
