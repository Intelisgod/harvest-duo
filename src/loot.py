"""Materials, ores and monster loot: central metadata + drop tables.

Keeping every drop/material here means combat, mining, selling, crafting and the
HUD all agree on labels, sell prices and colours. Nothing here imports pygame, so
it is trivially unit-testable.
"""
import random

# ---------------------------------------------------------------------------
#  MATERIAL / ORE METADATA   id -> dict(label, sell, color, cat)
#  cat: "ore" | "mat" (monster material) | "resource"
# ---------------------------------------------------------------------------
MATERIALS = {
    # resources / ores
    "stone":        {"label": "Stone",        "sell": 5,   "color": (140, 140, 152), "cat": "resource"},
    "wood":         {"label": "Wood",         "sell": 5,   "color": (150, 100, 55),  "cat": "resource"},
    "copper":       {"label": "Copper Ore",   "sell": 60,  "color": (205, 120, 70),  "cat": "ore"},
    "iron":         {"label": "Iron Ore",     "sell": 120, "color": (200, 205, 215), "cat": "ore"},
    "gold_ore":     {"label": "Gold Ore",     "sell": 300, "color": (240, 205, 80),  "cat": "ore"},
    "iridium_ore":  {"label": "Iridium Ore",  "sell": 800, "color": (175, 130, 235), "cat": "ore"},
    # monster materials
    "slime_goo":    {"label": "Slime Goo",    "sell": 15,  "color": (96, 200, 120),  "cat": "mat"},
    "bat_wing":     {"label": "Bat Wing",     "sell": 25,  "color": (130, 100, 165), "cat": "mat"},
    "bone":         {"label": "Bone Shard",   "sell": 40,  "color": (236, 230, 212), "cat": "mat"},
    "essence":      {"label": "Essence",      "sell": 75,  "color": (185, 125, 225), "cat": "mat"},
    "void_essence": {"label": "Void Essence", "sell": 160, "color": (110, 70, 165),  "cat": "mat"},
    # forest hunting drops
    "meat":         {"label": "Raw Meat",     "sell": 60,  "color": (196, 96, 86),   "cat": "mat"},
    "hide":         {"label": "Hide",         "sell": 45,  "color": (158, 120, 86),  "cat": "mat"},
    "pelt":         {"label": "Fine Pelt",    "sell": 95,  "color": (134, 112, 96),  "cat": "mat"},
    # Mist City scavenge drops (side-scroller zombie town — rust/neon palette,
    # see docs/TASK_mist_city.md; icons owned by Chat 6 in assets/items.py)
    "scrap_iron":      {"label": "Scrap Iron",      "sell": 25,  "color": (146, 104, 82),  "cat": "mat"},
    "wire":            {"label": "Wire",            "sell": 30,  "color": (196, 134, 88),  "cat": "mat"},
    "old_coin":        {"label": "Old Coin",        "sell": 35,  "color": (188, 158, 92),  "cat": "mat"},
    "gear_scrap":      {"label": "Gear Scrap",      "sell": 45,  "color": (118, 122, 132), "cat": "mat"},
    "old_battery":     {"label": "Old Battery",     "sell": 60,  "color": (164, 190, 84),  "cat": "mat"},
    "mutant_herb":     {"label": "Mutant Herb",     "sell": 80,  "color": (110, 235, 120), "cat": "mat"},
    "tainted_crystal": {"label": "Tainted Crystal", "sell": 400, "color": (216, 84, 202),  "cat": "mat"},
    # gems & relics from the deep biomes (Chat 1 level-up; icons painted in
    # systems/combat_system.py -- this module must never import assets)
    "amethyst":        {"label": "Amethyst",        "sell": 100,  "color": (178, 124, 230), "cat": "gem"},
    "ruby":            {"label": "Ruby",            "sell": 160,  "color": (232, 70, 96),   "cat": "gem"},
    "emerald":         {"label": "Emerald",         "sell": 220,  "color": (70, 206, 130),  "cat": "gem"},
    "diamond":         {"label": "Diamond",         "sell": 400,  "color": (200, 240, 255), "cat": "gem"},
    "prismatic_shard": {"label": "Prismatic Shard", "sell": 1200, "color": (255, 160, 220), "cat": "gem"},
    "ancient_relic":   {"label": "Ancient Relic",   "sell": 650,  "color": (214, 180, 96),  "cat": "relic"},
    # crafted at the Workbench (craft.CRAFTABLES) -- used from the hotbar in the mine
    "bomb":            {"label": "Bomb",            "sell": 30,   "color": (70, 66, 84),    "cat": "bomb"},
    "mega_bomb":       {"label": "Mega Bomb",       "sell": 110,  "color": (206, 72, 72),   "cat": "bomb"},
    "rope_ladder":     {"label": "Rope Ladder",     "sell": 60,   "color": (186, 150, 100), "cat": "tool"},
}

# the gems in collection order (achievements "all gems", journal)
GEMS = ["amethyst", "ruby", "emerald", "diamond", "prismatic_shard"]
RELICS = ["ancient_relic"]

# bonus gem chances per broken rock, by mine biome: [(item, chance), ...]
ROCK_GEMS = {
    "rock":    [("amethyst", 0.006)],
    "ice":     [("amethyst", 0.04)],
    "lava":    [("ruby", 0.04), ("amethyst", 0.01)],
    "crystal": [("emerald", 0.05), ("ruby", 0.01)],
    "abyss":   [("diamond", 0.03), ("emerald", 0.02)],
    "ruins":   [("diamond", 0.025), ("ancient_relic", 0.01), ("prismatic_shard", 0.004)],
}


def roll_rock_gem(biome, luck=0.0, rng=random):
    """Maybe a bonus gem from a broken mine rock (None most of the time).
    ``luck`` 0..~1.5 (mining skill + luck buff) scales the chances by up to 1.6x."""
    mult = 1.0 + min(0.6, max(0.0, luck) * 0.4)
    for item, chance in ROCK_GEMS.get(biome, ()):
        if rng.random() < chance * mult:
            return item
    return None

# ore drop id from a mined rock's ore-tag (rock stores "copper"/"iron"/"gold"/"iridium")
ROCK_ORE_ITEM = {"copper": "copper", "iron": "iron", "gold": "gold_ore", "iridium": "iridium_ore"}


def register_item(item_id, label, sell, color=(170, 170, 170), cat="mat"):
    """Extension point for ANY domain: add a new sellable/giftable item id.

    It then gets a label, a sell price (shop_system.sell_value reads MATERIALS),
    and shows up in the gallery / quest pools that derive from MATERIALS. Call it
    at import time of your own module. ``cat`` examples: "ore", "mat",
    "resource", "gem", "forage", "artisan", "relic". Pair it with
    ``assets.register_item_icon(item_id, painter)`` for a real icon (from a module
    the assets package does not import -- NOT crops/fishing/loot/cooking)."""
    MATERIALS[item_id] = {"label": label, "sell": int(sell), "color": tuple(color), "cat": cat}
    return item_id


def label(item_id):
    if item_id in MATERIALS:
        return MATERIALS[item_id]["label"]
    return item_id.replace("_", " ").title()


def color(item_id):
    if item_id in MATERIALS:
        return MATERIALS[item_id]["color"]
    return (180, 180, 188)


def sell_value(item_id):
    if item_id in MATERIALS:
        return MATERIALS[item_id]["sell"]
    return 0


def is_material(item_id):
    return item_id in MATERIALS


# ---------------------------------------------------------------------------
#  DROP ROLLING
#  A drop table is a list of (item_id, chance 0..1, (min_qty, max_qty)).
#  roll_drops returns a {item_id: qty} dict.
# ---------------------------------------------------------------------------
def roll_drops(table, luck=0.0, rng=random):
    """luck (0..) nudges chances & quantities up a little (mining/combat skill)."""
    out = {}
    for item_id, chance, (lo, hi) in table:
        if rng.random() < min(0.98, chance + luck * 0.04):
            qty = rng.randint(lo, hi)
            if luck >= 0.5 and rng.random() < luck * 0.10:
                qty += 1
            if qty > 0:
                out[item_id] = out.get(item_id, 0) + qty
    return out
