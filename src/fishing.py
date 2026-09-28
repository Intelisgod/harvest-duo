"""Fishing minigame: cast -> bite -> reel (multi-press for rare fish).

Fish are grouped into tiers. Ordinary water (farm/town) yields mostly
common/uncommon fish. The quiet pond in the forest is special: it has a much
better chance at rare fish and is the ONLY place that can yield "legendary"
fish and eldritch "leviathan" fish.

Landing a fish works like this:
  * cast  -> wait for a bite (timer, shorter at higher skill)
  * bite  -> press the action key. Common/uncommon fish are landed on the
             first press. Rare and above start a short button-mash "reel":
             tap the key up to 5 times before the reel timer runs out.
  * caught -> the game grants the fish, fishing XP (+ a tier bonus), bonus
             gold, and for legendary/leviathan fish a trophy item.

The 5-tap reel is deliberately forgiving (a generous, refreshing timer) so it
reads as "exciting" rather than "hard".
"""
import random

# ---- fish catalog -------------------------------------------------------
# id: (Display Name, sell value, tier, reel taps needed to land)
# Fish split into FRESHWATER (pond/river/forest pond) and SALTWATER (beach/sea).
# Each body of water has its own legendary + leviathan apex fish.
FISH_DATA = {
    # ============ FRESHWATER (pond / river / forest pond) ============
    # common
    "carp":          ("Carp",            30, "common",    1),
    "bluegill":      ("Bluegill",        45, "common",    1),
    "sunfish":       ("Sunfish",         50, "common",    1),
    "perch":         ("Perch",           55, "common",    1),
    # uncommon  (bass = largemouth; salmon = anadromous, caught in river)
    "bass":          ("Bass",            95, "uncommon",  2),
    "salmon":        ("Salmon",         120, "uncommon",  2),
    "pike":          ("Pike",           140, "uncommon",  2),
    # rare
    "catfish":       ("Catfish",        210, "rare",      3),
    "sturgeon":      ("Sturgeon",       340, "rare",      3),
    "rainbow_trout": ("Rainbow Trout",  260, "rare",      3),
    # legendary  (forest pond only, very rare)
    "crimson_bass":  ("Crimson Bass",  1500, "legendary", 5),
    "glacier_pike":  ("Glacier Pike",  1800, "legendary", 5),
    "the_legend":    ("The Legend",    2800, "legendary", 5),
    # leviathan / eldritch  (forest pond only, ultra rare apex)
    "void_eel":      ("Void Eel",      2200, "leviathan", 5),
    "phantom_carp":  ("Phantom Carp",  2600, "leviathan", 5),
    "unseeing_maw":  ("Unseeing Maw",  3200, "leviathan", 5),

    # ================ SALTWATER (beach / open sea) ================
    # common  (schooling baitfish)
    "anchovy":       ("Anchovy",         30, "common",    1),
    "sardine":       ("Sardine",         40, "common",    1),
    "herring":       ("Herring",         40, "common",    1),
    "mackerel":      ("Mackerel",        50, "common",    1),
    # uncommon
    "tuna":          ("Tuna",           110, "uncommon",  2),
    "cod":           ("Cod",            115, "uncommon",  2),
    "red_snapper":   ("Red Snapper",    130, "uncommon",  2),
    # rare
    "pufferfish":    ("Pufferfish",     220, "rare",      3),
    "eel":           ("Eel",            280, "rare",      3),
    "halibut":       ("Halibut",        300, "rare",      3),
    "swordfish":     ("Swordfish",      360, "rare",      3),
    # legendary  (open sea only, very rare)
    "coelacanth":      ("Coelacanth",        2400, "legendary", 5),
    "golden_swordfish":("Golden Swordfish",  1700, "legendary", 5),
    "abyssal_tuna":    ("Abyssal Tuna",      1900, "legendary", 5),
    # leviathan / eldritch  (open sea only, ultra rare apex)
    "kraken_spawn":  ("Kraken Spawn",   2600, "leviathan", 5),
    "maelstrom_ray": ("Maelstrom Ray",  3000, "leviathan", 5),
    "the_leviathan": ("The Leviathan",  4200, "leviathan", 5),
}

# backwards-compatible {id: sell_value} map used by selling / NPC gifts / icons
FISH = {k: v[1] for k, v in FISH_DATA.items()}

TIER_ORDER = ["common", "uncommon", "rare", "legendary", "leviathan"]
# extra fishing XP granted on top of the base catch XP, by tier
TIER_XP_BONUS = {"common": 0, "uncommon": 4, "rare": 14, "legendary": 60, "leviathan": 90}
# bonus gold dropped on the spot, by tier
TIER_GOLD_BONUS = {"common": 0, "uncommon": 0, "rare": 25, "legendary": 200, "leviathan": 300}
# UI accent colour, by tier
TIER_COLOR = {
    "common":    (150, 200, 240),
    "uncommon":  (120, 210, 150),
    "rare":      (210, 160, 240),
    "legendary": (250, 200, 90),
    "leviathan": (180, 90, 210),
}

# tiers that pay a trophy item + the big fanfare
SPECIAL_TIERS = ("legendary", "leviathan")

# freshwater pools (pond / river / forest pond)
_FRESH_COMMON    = ["carp", "bluegill", "sunfish", "perch"]
_FRESH_UNCOMMON  = ["bass", "salmon", "pike"]
_FRESH_RARE      = ["catfish", "sturgeon", "rainbow_trout"]
_FRESH_LEGENDARY = ["crimson_bass", "glacier_pike", "the_legend"]
_FRESH_LEVIATHAN = ["void_eel", "phantom_carp", "unseeing_maw"]
# saltwater pools (beach / open sea)
_SEA_COMMON      = ["anchovy", "sardine", "herring", "mackerel"]
_SEA_UNCOMMON    = ["tuna", "cod", "red_snapper"]
_SEA_RARE        = ["pufferfish", "eel", "halibut", "swordfish"]
_SEA_LEGENDARY   = ["coelacanth", "golden_swordfish", "abyssal_tuna"]
_SEA_LEVIATHAN   = ["kraken_spawn", "maelstrom_ray", "the_leviathan"]

# water type -> (common, uncommon, rare, legendary, leviathan) pools.
# "fresh" = ordinary freshwater (no apex); "pond"/"sea" unlock legendary+leviathan.
_POOLS = {
    "fresh": (_FRESH_COMMON, _FRESH_UNCOMMON, _FRESH_RARE, None, None),
    "pond":  (_FRESH_COMMON, _FRESH_UNCOMMON, _FRESH_RARE, _FRESH_LEGENDARY, _FRESH_LEVIATHAN),
    "sea":   (_SEA_COMMON, _SEA_UNCOMMON, _SEA_RARE, _SEA_LEGENDARY, _SEA_LEVIATHAN),
}


def display_name(fish_id):
    return FISH_DATA[fish_id][0]


def tier_of(fish_id):
    return FISH_DATA[fish_id][2]


def reel_presses(fish_id):
    return FISH_DATA[fish_id][3]


def is_special(fish_id):
    return tier_of(fish_id) in SPECIAL_TIERS


# pre-computed membership sets so habitat() never drifts from the pools above
_SEA_ALL = set(_SEA_COMMON + _SEA_UNCOMMON + _SEA_RARE + _SEA_LEGENDARY + _SEA_LEVIATHAN)
_FRESH_APEX = set(_FRESH_LEGENDARY + _FRESH_LEVIATHAN)
_SEA_APEX = set(_SEA_LEGENDARY + _SEA_LEVIATHAN)


def where_short(fish_id):
    """One-word-ish 'where to look' hint for the collection page."""
    if fish_id in _FRESH_APEX:
        return "Forest"
    if fish_id in _SEA_APEX:
        return "Sea"
    if fish_id in _SEA_ALL:
        return "Beach"
    return "Ponds"


def is_saltwater(fish_id):
    """True for beach / open-sea species (collection page grouping)."""
    return fish_id in _SEA_ALL


def habitat(fish_id):
    """Authoritative 'where to catch this fish' hint, derived from the catalogue
    so it always matches the data (no hard-coding downstream).

    Public API consumed by quests._fish_where(); returns a short, player-facing
    phrase. Apex tiers are location-locked (forest pond / open sea); ordinary
    fish follow their freshwater/saltwater split:

      freshwater common/uncommon/rare -> any freshwater pond or the forest pond
      saltwater  common/uncommon/rare -> the Beach (saltwater)
      freshwater legendary/leviathan  -> the forest pond only
      saltwater  legendary/leviathan  -> the open sea only
    """
    if fish_id in _FRESH_APEX:
        return "the forest pond only (legendary catch)"
    if fish_id in _SEA_APEX:
        return "the open sea only (legendary catch)"
    if fish_id in _SEA_ALL:
        return "fish the Beach (saltwater)"
    return "fish any freshwater pond or the forest pond"


# ---- sizes (cm) --------------------------------------------------------
# Every catch rolls a length inside its species range; rarer tiers run bigger.
# Records (count + biggest) live in FishingMixin.fish_records (saved).
FISH_SIZE = {
    # freshwater
    "carp": (30, 90), "bluegill": (10, 26), "sunfish": (10, 24), "perch": (15, 40),
    "bass": (30, 70), "salmon": (50, 110), "pike": (45, 120),
    "catfish": (40, 150), "sturgeon": (90, 260), "rainbow_trout": (30, 80),
    "crimson_bass": (80, 160), "glacier_pike": (120, 220), "the_legend": (180, 320),
    "void_eel": (200, 400), "phantom_carp": (150, 300), "unseeing_maw": (250, 500),
    # saltwater
    "anchovy": (8, 20), "sardine": (12, 26), "herring": (18, 40), "mackerel": (25, 55),
    "tuna": (60, 180), "cod": (40, 120), "red_snapper": (35, 90),
    "pufferfish": (15, 45), "eel": (50, 160), "halibut": (60, 220), "swordfish": (120, 300),
    "coelacanth": (120, 200), "golden_swordfish": (180, 340), "abyssal_tuna": (160, 320),
    "kraken_spawn": (220, 450), "maelstrom_ray": (250, 520), "the_leviathan": (400, 900),
}
# fallback for fish added later without an explicit range
_TIER_SIZE = {"common": (10, 45), "uncommon": (35, 110), "rare": (50, 180),
              "legendary": (120, 300), "leviathan": (200, 500)}


def size_range(fish_id):
    """(min_cm, max_cm) for a species."""
    r = FISH_SIZE.get(fish_id)
    if r:
        return r
    return _TIER_SIZE.get(tier_of(fish_id) if fish_id in FISH_DATA else "common", (10, 45))


def roll_size(fish_id, skill=0, bonus=0.0, rng=random):
    """Length in whole cm. Middle-heavy (average of two rolls); fishing skill and
    the fishing/luck buffs nudge it toward the top of the range."""
    lo, hi = size_range(fish_id)
    u = (rng.random() + rng.random()) / 2.0
    nudge = min(0.35, skill * 0.015 + max(0.0, bonus) * 0.25)
    u += (1.0 - u) * nudge * rng.random()
    return int(round(lo + (hi - lo) * max(0.0, min(1.0, u))))


def size_frac(fish_id, size):
    lo, hi = size_range(fish_id)
    return max(0.0, min(1.0, (size - lo) / float(max(1, hi - lo))))


def size_label(fish_id, size):
    """Short adjective for the catch popup ('' for an ordinary size)."""
    f = size_frac(fish_id, size)
    if f >= 0.9:
        return "Whopper!"
    if f >= 0.72:
        return "Big one!"
    if f <= 0.1:
        return "Tiddler"
    return ""


def treasure_chance(skill=0, luck=0.0, buff=0.0):
    """Chance a landed fish drags up a treasure chest (~5% base)."""
    return min(0.18, 0.05 + skill * 0.003 + max(0.0, luck) * 0.08 + max(0.0, buff) * 0.08)


def random_fish(skill=0, water="fresh"):
    """Pick a fish id for the given body of water. Higher skill biases toward
    rarer fish. "pond" (forest) and "sea" (beach) use rare-heavy odds and are
    the only waters that unlock legendary + leviathan apex fish; ordinary
    "fresh" water tops out at rare.

    water in {"fresh", "pond", "sea"}.
    """
    common, uncommon, rare, legendary, leviathan = _POOLS.get(water, _POOLS["fresh"])
    r = random.random()
    s = min(0.30, skill * 0.03)
    if legendary is not None:             # forest pond / open sea: apex unlocked
        if r < 0.020 + s * 0.05:          # eldritch leviathan
            return random.choice(leviathan)
        if r < 0.060 + s * 0.08:          # legendary
            return random.choice(legendary)
        if r < 0.34:                      # rare
            return random.choice(rare)
        if r < 0.64:                      # uncommon
            return random.choice(uncommon)
        return random.choice(common)
    # ordinary freshwater
    if r < 0.42 - s:
        return random.choice(common)
    if r < 0.82 - s * 0.5:
        return random.choice(uncommon)
    return random.choice(rare)


class FishingState:
    """States: idle -> casting -> bite -> reeling -> idle.

    Fishing skill makes bites come faster and widens the bite/reel windows, so
    a high-level angler lands tricky fish more reliably.
    """
    def __init__(self):
        self.state = "idle"
        self.timer = 0.0
        self.fish = None
        self.message = ""
        self.skill = 0
        self.water = "fresh"          # "fresh" | "pond" | "sea"
        self.reel_done = 0
        self.reel_needed = 0
        # fishing buff (fraction, e.g. 0.3 = +30%) -- refreshed every frame from
        # the angler's p.buff("fishing") by FishingMixin: faster bites, wider
        # bite/reel windows.
        self.bonus = 0.0
        # True while the angler's line is in today's bubbling hot spot (also set
        # per frame by FishingMixin): quicker bites + better odds for rare fish.
        self.hotspot = False

    def _speed(self):
        f = 1.0 - min(0.5, max(0.0, self.bonus) * 0.8)
        return f * (0.7 if self.hotspot else 1.0)

    def _widen(self):
        return 1.0 + min(0.6, max(0.0, self.bonus))

    # ---- helpers for the UI ----
    @property
    def tier(self):
        return tier_of(self.fish) if self.fish else None

    def cast(self, skill=0, water="fresh", forest=None):
        self.skill = skill
        # back-compat: older callers (Core) may still pass forest=<bool> until
        # actions_system is updated to pass water=. Map it: True -> forest pond.
        if forest is not None:
            water = "pond" if forest else "fresh"
        self.water = water
        self.state = "casting"
        self.timer = max(0.6, random.uniform(1.2, 3.5) - skill * 0.16) * self._speed()
        self.fish = None
        self.reel_done = 0
        self.reel_needed = 0
        self.message = "Casting... wait for a bite!"

    def update(self, dt):
        if self.state == "casting":
            self.timer -= dt
            if self.timer <= 0:
                self.fish = random_fish(self.skill + (3 if self.hotspot else 0), self.water)
                self.state = "bite"
                self.timer = min(2.2, 0.7 + self.skill * 0.14) * self._widen()
                t = self.tier
                if t in SPECIAL_TIERS:
                    self.message = f"!!! Something huge bites! Reel hard!"
                else:
                    self.message = "! A bite! Press your action key!"
        elif self.state == "bite":
            self.timer -= dt
            if self.timer <= 0:
                self._escape()
        elif self.state == "reeling":
            self.timer -= dt
            if self.timer <= 0:
                self._escape()

    def _escape(self):
        lost = self.fish
        self.state = "idle"
        self.fish = None
        self.reel_done = self.reel_needed = 0
        if lost and tier_of(lost) in SPECIAL_TIERS:
            self.message = f"The line snaps -- {display_name(lost)} escapes into the deep..."
        else:
            self.message = "The fish got away..."

    def try_hook(self):
        """Called on each action press.

        Returns a fish id only on the press that fully lands the fish; returns
        None while still casting/reeling (check self.state/self.message for UI).
        """
        if self.state == "bite":
            self.reel_needed = reel_presses(self.fish)
            self.reel_done = 1
            if self.reel_done >= self.reel_needed:        # common fish: 1 tap
                return self._land()
            # rare+: begin the button-mash reel
            self.state = "reeling"
            self.timer = max(1.4, 2.4 + self.skill * 0.12) * (1.0 + (self._widen() - 1.0) * 0.5)
            self.message = f"Reel! {self.reel_done}/{self.reel_needed}"
            return None
        if self.state == "reeling":
            self.reel_done += 1
            cap = (2.6 + self.skill * 0.12) * (1.0 + (self._widen() - 1.0) * 0.5)
            self.timer = min(self.timer + 0.5, cap)                     # each tap buys time
            if self.reel_done >= self.reel_needed:
                return self._land()
            self.message = f"Reel! {self.reel_done}/{self.reel_needed}"
            return None
        if self.state == "casting":
            self.state = "idle"
            self.fish = None
            self.message = "Too early -- nothing there."
        return None

    def _land(self):
        caught = self.fish
        self.state = "idle"
        self.fish = None
        self.reel_done = self.reel_needed = 0
        self.message = f"Landed {display_name(caught)}!"
        return caught
