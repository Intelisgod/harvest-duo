"""Seasonal festivals: one festival day per season with a town reward stall."""

FEST_DAY = 14   # mid-season

NAMES = {"Spring": "Flower Festival", "Summer": "Summer Luau",
         "Fall": "Harvest Fair", "Winter": "Star Festival"}

# one-time reward per festival: gold + a seasonal gift item
REWARD = {
    "Spring": (300, "cauliflower", 2),
    "Summer": (300, "blueberry", 3),
    "Fall":   (300, "pumpkin", 2),
    "Winter": (300, "snow_yam", 2),
}


# the mini-game each festival hosts (run by systems/story_restore.py)
ACTIVITY = {"Spring": "Egg Hunt", "Summer": "Luau Potluck",
            "Fall": "Best in Show", "Winter": "Lantern Night"}
# where / how to join, for banners and hints
ACTIVITY_HINT = {
    "Spring": "Talk to the festival stall in town to start a 60 s egg hunt!",
    "Summer": "Each farmer holds an ingredient at the stall to add it to the pot.",
    "Fall": "Hold your best produce at the stall to enter Best in Show.",
    "Winter": "After 5 PM, both farmers press Action together at the beach pier.",
}


def is_festival_day(time):
    return time.day == FEST_DAY


def activity(season):
    return ACTIVITY.get(season, "")


def name(season):
    return NAMES.get(season, "Festival")


def key(time):
    return f"{time.year}-{time.season_idx}"
