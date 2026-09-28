"""Crop definitions and the planted-crop class.

Owner: Farming (Chat 2). Pure data + logic -- must never import ``assets``
(assets imports this module).
"""
from .settings import SEASONS

# name: dict of season, days to grow, sell price, seed cost, regrow days (0 = single harvest), color
# "premium": True -> sold in the shop's "Farm Supplies" section instead of the
# regular seed rack (pricier seeds, better crops).
CROPS = {
    "parsnip":     {"season": "Spring", "grow": 4,  "sell": 35,  "seed": 20, "regrow": 0,  "color": (210, 200, 150)},
    "potato":      {"season": "Spring", "grow": 6,  "sell": 80,  "seed": 50, "regrow": 0,  "color": (180, 150, 110)},
    "cauliflower": {"season": "Spring", "grow": 12, "sell": 175, "seed": 80, "regrow": 0,  "color": (235, 235, 215)},
    "green_bean":  {"season": "Spring", "grow": 10, "sell": 40,  "seed": 60, "regrow": 3,  "color": (90, 170, 70)},

    "melon":       {"season": "Summer", "grow": 12, "sell": 250, "seed": 80, "regrow": 0,  "color": (120, 200, 110)},
    "tomato":      {"season": "Summer", "grow": 11, "sell": 60,  "seed": 50, "regrow": 4,  "color": (220, 70, 60)},
    "blueberry":   {"season": "Summer", "grow": 13, "sell": 50,  "seed": 80, "regrow": 4,  "color": (80, 90, 200)},
    "pepper":      {"season": "Summer", "grow": 5,  "sell": 40,  "seed": 40, "regrow": 3,  "color": (230, 120, 40)},

    "pumpkin":     {"season": "Fall",   "grow": 13, "sell": 320, "seed": 100,"regrow": 0,  "color": (235, 150, 50)},
    "corn":        {"season": "Fall",   "grow": 14, "sell": 50,  "seed": 150,"regrow": 4,  "color": (235, 210, 90)},
    "cranberry":   {"season": "Fall",   "grow": 7,  "sell": 75,  "seed": 240,"regrow": 5,  "color": (190, 50, 70)},
    "eggplant":    {"season": "Fall",   "grow": 5,  "sell": 60,  "seed": 20, "regrow": 5,  "color": (110, 70, 130)},

    "winter_root": {"season": "Winter", "grow": 5,  "sell": 70,  "seed": 30, "regrow": 0,  "color": (206, 184, 146)},
    "snow_yam":    {"season": "Winter", "grow": 7,  "sell": 120, "seed": 60, "regrow": 0,  "color": (224, 214, 232)},
    "crocus":      {"season": "Winter", "grow": 6,  "sell": 90,  "seed": 40, "regrow": 0,  "color": (180, 144, 212)},
    "frost_melon": {"season": "Winter", "grow": 12, "sell": 300, "seed": 90, "regrow": 0,  "color": (150, 212, 222)},

    # premium seeds (2026-09 "Farm Supplies" shop section) -- one per season
    "strawberry":  {"season": "Spring", "grow": 8,  "sell": 120, "seed": 150, "regrow": 4, "color": (236, 84, 104),  "premium": True},
    "starfruit":   {"season": "Summer", "grow": 13, "sell": 520, "seed": 380, "regrow": 0, "color": (250, 214, 72),  "premium": True},
    "grape":       {"season": "Fall",   "grow": 10, "sell": 95,  "seed": 160, "regrow": 3, "color": (132, 84, 170),  "premium": True},
    "ice_berry":   {"season": "Winter", "grow": 9,  "sell": 150, "seed": 170, "regrow": 4, "color": (170, 214, 250), "premium": True},
}

# crops that count as FRUIT for artisan goods (jam / wine); everything else is a
# vegetable (pickles / juice)
FRUITS = {"melon", "tomato", "blueberry", "cranberry", "frost_melon",
          "strawberry", "starfruit", "grape", "ice_berry"}


def is_fruit(name):
    return name in FRUITS


def crop_label(name):
    """Display name for a crop id, title case ('green_bean' -> 'Green Bean')."""
    return name.replace("_", " ").title()


# Seeds available in the regular seed rack per season (premium ones excluded)
def shop_seeds(season):
    return [name for name, d in CROPS.items() if d["season"] == season and not d.get("premium")]


def premium_seeds(season):
    """Premium seeds for the shop's Farm Supplies section this season."""
    return [name for name, d in CROPS.items() if d["season"] == season and d.get("premium")]


# Fertilizer kinds (item ids) -> effect. The farm keeps fertilized soil in
# ArtisanMixin.fert_tiles and copies the kind onto the Crop (crop.fert) so
# growth can read it here without knowing the tile.
FERTILIZERS = {
    "fertilizer": "speed",            # extra growth stage every 3rd growing night (~30% faster)
    "quality_fertilizer": "quality",  # chance of a double harvest
}


class Crop:
    """A planted crop living on a tilled tile (keyed by (area, gx, gy))."""
    fert = None                  # fertilizer item id on this crop's soil (set by ArtisanMixin)

    def __init__(self, name):
        self.name = name
        self.data = CROPS[name]
        self.age = 0            # days watered/grown
        self.watered = False
        self.dead = False
        self.regrown_ready = False

    @property
    def grown(self):
        return self.age >= self.data["grow"]

    @property
    def ready_to_harvest(self):
        return self.grown

    def advance_day(self):
        """Called at the start of each new day."""
        if self.dead:
            return
        if self.watered and not self.grown:
            self.age += 1
            # speed fertilizer: one bonus stage on every 3rd night of growth
            if FERTILIZERS.get(self.fert) == "speed" and not self.grown and self.age % 3 == 0:
                self.age += 1
        self.watered = False

    def harvest(self):
        """Return crop name to add to inventory; reset if regrowable, else None means remove."""
        regrow = self.data["regrow"]
        if regrow > 0:
            # regrowable: reset age back so it matures again after `regrow` days
            self.age = self.data["grow"] - regrow
            return self.name, False     # (item, should_remove)
        return self.name, True

    def growth_ratio(self):
        return min(1.0, self.age / max(1, self.data["grow"]))
