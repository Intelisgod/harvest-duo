"""Player skills, experience and the perks that levels unlock.

Five skills, each 0..MAX_LEVEL. XP is cumulative; level is derived from XP via
THRESH. Perks are pure functions of the levels so they can never desync from the
displayed level. No pygame import -> unit-testable.
"""

SKILLS = ["combat", "mining", "farming", "foraging", "fishing"]
SKILL_LABEL = {
    "combat": "Combat", "mining": "Mining", "farming": "Farming",
    "foraging": "Foraging", "fishing": "Fishing",
}
SKILL_COLOR = {
    "combat": (208, 80, 72), "mining": (150, 160, 175), "farming": (110, 190, 90),
    "foraging": (150, 110, 60), "fishing": (80, 150, 210),
}
MAX_LEVEL = 10

# cumulative XP needed to *be* at index-level (level 0..10)
THRESH = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200, 4000]


def level_for_xp(xp):
    lv = 0
    for n, need in enumerate(THRESH):
        if xp >= need:
            lv = n
        else:
            break
    return min(lv, MAX_LEVEL)


def xp_into_level(xp):
    """Return (xp_into_current_level, xp_span_to_next) for a progress bar."""
    lv = level_for_xp(xp)
    if lv >= MAX_LEVEL:
        return (1, 1)
    base = THRESH[lv]
    nxt = THRESH[lv + 1]
    return (xp - base, nxt - base)


class Skills:
    def __init__(self):
        self.xp = {s: 0 for s in SKILLS}

    # ---- xp / levels ----
    def level(self, skill):
        return level_for_xp(self.xp.get(skill, 0))

    def total_level(self):
        return sum(self.level(s) for s in SKILLS)

    def add_xp(self, skill, amount):
        """Add XP; return a list of skills that levelled up (for popups)."""
        if skill not in self.xp or amount <= 0:
            return []
        before = self.level(skill)
        self.xp[skill] += int(amount)
        after = self.level(skill)
        return [(skill, lv) for lv in range(before + 1, after + 1)]

    # ---- perks (pure functions of level) ----
    @property
    def max_hp_bonus(self):
        return self.level("combat") * 5          # up to +50 HP

    @property
    def sword_bonus(self):
        return self.level("combat")              # up to +10 damage

    @property
    def crit_bonus(self):
        return self.level("combat") * 0.01       # +1% crit chance per combat level

    @property
    def mining_luck(self):
        return self.level("mining") * 0.1        # extra-ore luck 0..1.0

    @property
    def foraging_luck(self):
        return self.level("foraging") * 0.1

    @property
    def crop_value_mult(self):
        return 1.0 + self.level("farming") * 0.04  # up to +40% crop value

    @property
    def fishing_skill(self):
        return self.level("fishing")

    def energy_discount(self, tool):
        """Fraction of tool energy saved (0..0.5) from the matching skill."""
        skill = {"pickaxe": "mining", "axe": "foraging", "hoe": "farming",
                 "watering_can": "farming", "sword": "combat",
                 "fishing_rod": "fishing"}.get(tool)
        if not skill:
            return 0.0
        return min(0.5, self.level(skill) * 0.05)

    # ---- save / load ----
    def to_dict(self):
        return dict(self.xp)

    def load(self, d):
        if isinstance(d, dict):
            for s in SKILLS:
                self.xp[s] = int(d.get(s, 0))
        return self


# XP reward constants used by the game when actions succeed
XP = {
    "till": 3, "plant": 2, "water": 1, "harvest": 8,
    "mine_rock": 4, "mine_ore": 7, "chop": 5, "fish": 12,
    # combat xp is per-monster (see monsters.py archetype "xp")
}


# ---------------------------------------------------------------------------
#  ACHIEVEMENTS (Chat 1 level-up) -- pure data; systems/progress_system.py
#  counts gameplay events into COUNTERS and unlocks these.
#  (key, title, description, icon, counter, target, gold reward)
#  icon: an item id (drawn with assets.item_icon) or "@heart"/"@trophy"/"@coin"/
#  "@smile" (painted by progress_system). counter "boss:<name>" = kills of that boss.
# ---------------------------------------------------------------------------
ACHIEVEMENTS = [
    ("first_harvest", "Green Thumb", "Harvest your first crop", "parsnip", "harvest", 1, 50),
    ("harvest_50", "Growing Strong", "Harvest 50 crops", "potato", "harvest", 50, 250),
    ("harvest_250", "Harvest Master", "Harvest 250 crops", "pumpkin", "harvest", 250, 1000),
    ("first_fish", "First Catch", "Catch your first fish", "carp", "fish", 1, 50),
    ("fish_25", "Angler", "Catch 25 fish", "salmon", "fish", 25, 400),
    ("legendary_fish", "Legend of the Deep", "Land a legendary fish", "the_legend", "legendary_fish", 1, 1500),
    ("depth_10", "Into the Depths", "Reach mine level 10", "iron", "depth", 10, 300),
    ("depth_20", "Abyss Walker", "Reach mine level 20", "void_essence", "depth", 20, 800),
    ("depth_30", "The Lost Kingdom", "Reach mine level 30", "ancient_relic", "depth", 30, 2000),
    ("boss_slime_king", "Slime Sovereign", "Defeat the Slime King", "slime_goo", "boss:slime_king", 1, 500),
    ("boss_rock_titan", "Titan Toppler", "Defeat the Rock Titan", "stone", "boss:rock_titan", 1, 800),
    ("boss_void_overlord", "Void Vanquisher", "Defeat the Void Overlord", "essence", "boss:void_overlord", 1, 1200),
    ("boss_abyss_wyrm", "Wyrm Slayer", "Defeat the Abyss Wyrm", "diamond", "boss:abyss_wyrm", 1, 2000),
    ("boss_ruin_colossus", "Colossus Breaker", "Defeat the Ruin Colossus", "prismatic_shard",
     "boss:ruin_colossus", 1, 3000),
    ("kills_100", "Monster Hunter", "Defeat 100 monsters", "bone", "kills", 100, 600),
    ("first_gem", "Sparkly!", "Find your first gem", "amethyst", "gems", 1, 100),
    ("all_gems", "Gem Collector", "Find every kind of gem", "emerald", "gems", 5, 2500),
    ("first_bomb", "Demolition Expert", "Craft a bomb at the Workbench", "bomb", "bombs", 1, 100),
    ("master_smith", "Master Smith", "Upgrade a tool to Iridium", "iridium_ore", "tool_tier", 4, 1000),
    ("cooked_5", "Home Chef", "Cook 5 dishes", "fried_egg", "cooked", 5, 300),
    ("friend_5", "Good Friends", "Reach 5 hearts with a villager", "@heart", "friend_hearts", 5, 400),
    ("friend_10", "Best Friends", "Reach 10 hearts with a villager", "@heart", "friend_hearts", 10, 1000),
    # partner gifts / emotes count at most once per in-game day (no ping-pong farming)
    ("partner_gifts", "Sweethearts", "Gift your partner on 10 different days", "@heart",
     "partner_gift_days", 10, 400),
    ("emotes_20", "Expressive", "Share an emote on 7 different days", "@smile", "emote_days", 7, 100),
    ("first_artisan", "Artisan", "Collect your first artisan good", "honey", "artisan", 1, 100),
    ("artisan_50", "Cottage Industry", "Collect 50 artisan goods", "cheese_wheel", "artisan", 50, 800),
    ("first_bundle", "Community Spirit", "Complete a restoration bundle", "@trophy", "bundles", 1, 500),
    ("valley_restored", "Valley Restored", "Complete every restoration bundle", "@trophy",
     "valley_restored", 1, 1500),
    ("festival_won", "Festival Champion", "Win a festival contest", "@trophy", "festivals", 1, 800),
    # the three contests arrive as festival_won; Lantern Night has no winner, so
    # releasing the lanterns together is its fourth star (progress_system)
    ("festival_all", "Festival Star", "Win the Egg Hunt, Luau & Fair, and share Lantern Night",
     "@trophy", "festival_kinds", 4, 2000),
    # a Mist City run counts once you win it or make it past Main Street
    ("mist_run", "Into the Mist", "Make it past Main Street in Mist City", "tainted_crystal",
     "mist_runs", 1, 300),
    ("mist_tower", "Clock Watcher", "Reach the Clock Tower in Mist City", "scrap_iron", "mist_zone", 2, 600),
    ("mist_zombies", "Zombie Sweeper", "Defeat 100 Mist City zombies", "bone", "mist_kills", 100, 500),
    ("boss_bell_keeper", "Bell Silencer", "Silence the Bell Keeper", "cursed_gear",
     "boss:bell_keeper", 1, 1500),
    ("gold_1k", "Pocket Money", "Earn 1,000g from selling", "@coin", "gold_earned", 1000, 100),
    ("gold_10k", "Entrepreneur", "Earn 10,000g from selling", "@coin", "gold_earned", 10000, 500),
    ("gold_100k", "Tycoon", "Earn 100,000g from selling", "@coin", "gold_earned", 100000, 5000),
]
ACH_KEYS = [a[0] for a in ACHIEVEMENTS]
ACH = {a[0]: {"title": a[1], "desc": a[2], "icon": a[3], "counter": a[4],
              "target": a[5], "gold": a[6]} for a in ACHIEVEMENTS}
# counters that keep the MAXIMUM seen value instead of a running total
MAX_COUNTERS = {"depth", "tool_tier", "friend_hearts", "gems", "festival_kinds", "mist_zone",
                "valley_restored"}


def ach_progress(key, counters):
    """(current, target) for an achievement's progress bar."""
    a = ACH[key]
    return min(a["target"], int(counters.get(a["counter"], 0))), a["target"]


def newly_unlocked(counters, unlocked):
    """Achievement keys whose targets are met but not yet in ``unlocked``."""
    return [k for k in ACH_KEYS
            if k not in unlocked and counters.get(ACH[k]["counter"], 0) >= ACH[k]["target"]]
