"""Villager data for the Story domain (Chat 4): personalities, gift tastes,
birthdays, daily schedules, contextual dialogue and heart-event scripts.

Pure data + tiny pure helpers -- NO pygame / assets imports, so npc.py,
story_system.py and the tests can all import it freely.

Item ids in the taste lists may not exist yet (gems / forage land from other
domains concurrently) -- every consumer filters them against the live
registries at call time (see ``item_exists``), and ``@tokens`` expand to whole
registry categories:  @fish @crop @food @gem @ore @forage @flower @fruit @junk.
"""
from .settings import (AREA_TOWN, AREA_BEACH, AREA_FOREST, AREA_TEMPLE,
                       AREA_MEADOW)

SEASON_NAMES = ["Spring", "Summer", "Fall", "Winter"]

# ---------------------------------------------------------------------------
#  Villagers (old + new).  looks = (hair_style, hair_color_idx, skin_idx)
#  birthday = (season_idx, day)   -- never the festival day (14)
# ---------------------------------------------------------------------------
VILLAGERS = {
    "Mira": {
        "title": "Florist & Gossip",
        "birthday": (0, 5),
        "loves": ["blueberry", "melon", "fruit_salad", "crocus", "@flower",
                  "wildflower_honey"],
        "likes": ["@crop", "@forage", "milk_tea", "@artisan"],
        "dislikes": ["slime_goo", "bone", "bat_wing", "@junk"],
    },
    "Tomas": {
        "title": "Retired Sailor",
        "birthday": (1, 9),
        "loves": ["potato", "fish_dinner", "roast_meat", "steak_plate", "mead"],
        "likes": ["@fish", "@food", "meat", "@wine"],
        "dislikes": ["crocus", "slime_goo", "@flower"],
    },
    "Elya": {
        "title": "Seed Merchant",
        "birthday": (2, 3),
        "loves": ["cauliflower", "veg_stew", "pumpkin", "corn_soup", "pickles_cauliflower"],
        "likes": ["@crop", "@forage", "@artisan"],
        "dislikes": ["bat_wing", "void_essence", "tainted_crystal"],
    },
    "Luang Por": {
        "title": "Temple Abbot",
        "birthday": (3, 20),
        "loves": ["lotus", "milk_tea", "fruit_salad", "egg_custard", "@flower"],
        "likes": ["@crop", "@forage", "@fruit", "honey", "wildflower_honey", "@artisan"],
        "dislikes": ["bone", "bat_wing", "void_essence", "tainted_crystal", "@wine"],
    },
    "Fah": {
        "title": "Cafe Owner",
        "color": (246, 170, 120),
        "looks": ("ponytail", 5, 0),        # copper-red ponytail, fair skin
        "birthday": (0, 22),
        "loves": ["fruit_salad", "pumpkin_pie", "egg_custard", "melon", "blueberry",
                  "frost_melon", "milk_tea", "honey", "jam_strawberry", "cheese_wheel"],
        "likes": ["@fruit", "cheese", "goat_cheese", "@food", "cranberry", "@artisan"],
        "dislikes": ["slime_goo", "bone", "bat_wing", "stone", "@junk"],
    },
    "Somchai": {
        "title": "Old Fisherman",
        "color": (92, 130, 150),
        "looks": ("cap", 4, 4),             # white hair under a cap, tanned
        "birthday": (1, 25),
        "loves": ["tuna", "catfish", "sturgeon", "halibut", "swordfish", "fish_dinner",
                  "eel"],
        "likes": ["@fish", "milk_tea", "roast_meat", "@wine"],
        "dislikes": ["crocus", "@flower", "wire", "old_battery", "scrap_iron"],
    },
    "Kai": {
        "title": "Blacksmith Apprentice",
        "color": (196, 110, 64),
        "looks": ("spiky", 0, 2),           # black spiky hair
        "birthday": (2, 17),
        "loves": ["gold_ore", "iridium_ore", "@gem", "essence", "tainted_crystal",
                  "cursed_gear"],
        "likes": ["@ore", "copper", "iron", "roast_meat", "gear_scrap"],
        "dislikes": ["cauliflower", "eggplant", "@flower", "crocus"],
    },
    "Luna": {
        "title": "Dreamy Painter",
        "color": (150, 128, 210),
        "looks": ("long", 6, 1),            # long violet hair
        "birthday": (3, 8),
        "loves": ["crocus", "@flower", "blueberry", "@forage", "cranberry"],
        "likes": ["@crop", "@fruit", "wood", "milk_tea", "wildflower_honey"],
        "dislikes": ["meat", "bone", "slime_goo", "void_essence", "iron"],
    },
}

NEW_VILLAGERS = ("Fah", "Somchai", "Kai", "Luna")
DISPLAY = {"Somchai": "Grandpa Somchai"}        # long names for plates / journal


def display(name):
    return DISPLAY.get(name, name)


# ---------------------------------------------------------------------------
#  Daily schedules: (from_hour, to_hour, area, (gx, gy)).  Outside every window
#  the villager is at home (not in the world).  "rain" replaces the day on wet
#  days (rain / storm / snow); "festival" is used on every festival day.
#  Tiles are *nominal* -- story_system snaps them to the nearest walkable tile.
# ---------------------------------------------------------------------------
SCHEDULES = {
    "Fah": {
        "day": [(6, 10, AREA_TOWN, (14, 11)), (10, 14, AREA_TOWN, (18, 15)),
                (14, 18, AREA_BEACH, (13, 12)), (18, 22, AREA_TOWN, (15, 11))],
        "rain": [(6, 22, AREA_TOWN, (14, 11))],
    },
    "Somchai": {
        "day": [(5, 11, AREA_BEACH, (21, 25)), (11, 13, AREA_TOWN, (29, 21)),
                (13, 18, AREA_BEACH, (20, 24)), (18, 21, AREA_TEMPLE, (14, 13))],
        "rain": [(5, 18, AREA_BEACH, (21, 25)), (18, 21, AREA_TEMPLE, (14, 13))],
    },
    "Kai": {
        "day": [(7, 12, AREA_TOWN, (6, 25)), (12, 15, AREA_TOWN, (27, 11)),
                (15, 17, AREA_FOREST, (21, 4)), (17, 19, AREA_TOWN, (7, 24)),
                (19, 22, AREA_TOWN, (21, 17))],
        "rain": [(7, 22, AREA_TOWN, (6, 25))],
    },
    "Luna": {
        "day": [(7, 11, AREA_MEADOW, (13, 18)), (11, 14, AREA_TOWN, (16, 17)),
                (14, 17, AREA_TEMPLE, (6, 12)), (17, 20, AREA_BEACH, (24, 11)),
                (20, 22, AREA_TOWN, (17, 18))],
        "rain": [(8, 20, AREA_TEMPLE, (6, 12))],
    },
}
# meadow fallback (World may not have built the meadow yet)
MEADOW_FALLBACK = (AREA_FOREST, (15, 11))
FESTIVAL_SPOTS = {"Fah": (17, 13), "Somchai": (23, 13), "Kai": (18, 16), "Luna": (22, 16)}
# Winter Lantern Night: everyone gathers at the foot of the beach pier after dusk
LANTERN_SPOTS = {"Fah": (18, 16), "Somchai": (21, 20), "Kai": (23, 16), "Luna": (17, 18)}


def schedule_slot(name, hour, wet=False, festival=False, season_idx=0):
    """(area, (gx, gy) or None) where ``name`` is at ``hour``, or None (home)."""
    sch = SCHEDULES.get(name)
    if not sch:
        return None
    if festival and season_idx == 3 and 17 <= hour < 23 and name in LANTERN_SPOTS:
        return (AREA_BEACH, LANTERN_SPOTS[name])
    if festival and 9 <= hour < 22 and name in FESTIVAL_SPOTS:
        return (AREA_TOWN, FESTIVAL_SPOTS[name])
    rows = sch["rain"] if (wet and "rain" in sch) else sch["day"]
    for h0, h1, area, tile in rows:
        if h0 <= hour < h1:
            return (area, tile)
    return None


# ---------------------------------------------------------------------------
#  Dialogue.  Keys: any, Spring/Summer/Fall/Winter, rain/snow/storm/fog/sunny,
#  morning/afternoon/evening/night, h3/h6 (min hearts), at:<area>, birthday,
#  love/like/neutral/dislike (gift reactions), bday_gift.
#  {p} = the player talking, {q} = their partner.
# ---------------------------------------------------------------------------
LINES = {
    "Mira": {
        "any": ["Lovely weather for the crops!", "Did you two clear the mine yet?",
                "I adore fresh blueberries.", "You make a great team, you know.",
                "I heard Kai singing to a lump of iron yesterday. Adorable.",
                "Luna painted my shop sign. Now bees keep landing on it!"],
        "Spring": ["The tulips on the square are finally awake!"],
        "Summer": ["Summer makes everyone a little bit sillier. I love it."],
        "Fall": ["Pumpkin season! My favourite colour is orange this month."],
        "Winter": ["Snow on the petals... even winter flowers are brave."],
        "rain": ["Rain means I don't have to water the window boxes!"],
        "morning": ["Morning, {p}! Hair still messy? Mine too."],
        "evening": ["Walk {q} home tonight, the lanterns are pretty."],
        "h3": ["You two always hold the door for each other. I noticed."],
        "h6": ["I'd tell you a secret, {p}... but you'd tell {q}. Which is sweet."],
        "birthday": ["You remembered my birthday?! Oh, you two!"],
        "love": ["Oh! This is my favourite thing in the world!",
                 "You know me too well. I'm keeping this forever!"],
        "like": ["How thoughtful! Thank you.", "Ooh, that's lovely."],
        "neutral": ["Thanks for the gift!", "Oh? How nice of you."],
        "dislike": ["...Is it supposed to be sticky?", "Ah. Um. Thank you...?"],
    },
    "Tomas": {
        "any": ["The fish are biting at the pond today.", "Bring me a potato sometime, eh?",
                "Careful in the mines, slimes are about.", "Two farmers? The valley is lucky.",
                "Old Somchai and I argue about bait every single day.",
                "A sailor never forgets the smell of the sea."],
        "Summer": ["Hot enough to cook an egg on the pier!"],
        "Winter": ["In winter the sea turns grey and honest."],
        "storm": ["A proper storm! Reminds me of my ship days."],
        "fog": ["Fog like this, you steer by the gulls' voices."],
        "night": ["Stars were my map, once. Still are, some nights."],
        "h3": ["You work hard, {p}. Reminds me of my old crew."],
        "h6": ["If I'd had a partner like {q} on my ship, I'd never have come ashore."],
        "birthday": ["Heh, another year older and still handsome. Thanks for coming by."],
        "love": ["Now THAT is a real gift! You've got good taste.",
                 "Ha! You remembered! I owe you one."],
        "like": ["Good stuff. Thanks.", "That'll do nicely."],
        "neutral": ["Thanks, I suppose.", "Huh. Thank you."],
        "dislike": ["Flowers? What am I, a bee?", "Hmph. Not my thing."],
    },
    "Elya": {
        "any": ["I sell seeds at the shop, come by!", "A giant cauliflower once grew here...",
                "Friendship grows like a watered crop.", "Stay warm in winter, you two.",
                "Fah bribes me with cake to get the first strawberries.",
                "Every seed is a little promise."],
        "Spring": ["Spring seeds are in! Parsnips are an easy start."],
        "Summer": ["Blueberries keep giving all summer long!"],
        "Fall": ["Pumpkins, pumpkins, pumpkins! Plant them early."],
        "Winter": ["Winter roots are tougher than they look. Like you two."],
        "rain": ["Rain's a free watering day. Take a nap!"],
        "h3": ["Your farm is looking wonderful. I peeked over the fence!"],
        "h6": ["You two are the best customers I've ever had. And friends."],
        "birthday": ["My birthday! I planted a seed for every year. It's a forest now."],
        "love": ["Oh my, this is perfect! You grew this?",
                 "Wonderful! I'll save the seeds from it."],
        "like": ["What a lovely gift.", "Thank you, dear."],
        "neutral": ["Thank you!", "How kind."],
        "dislike": ["Oh... that's... an unusual gift.", "Hm. I'll find a place for it."],
    },
    "Luang Por": {
        "any": ["The mind is like water; let it settle and see clearly.",
                "Merit follows those with a generous heart.",
                "Come, kneel, and I shall read your fortune for the day.",
                "Fortune turns like the seasons -- accept both with calm.",
                "Two hearts walking one path make the path lighter.",
                "Luna paints the Buddha every afternoon. Her brush is a kind of prayer.",
                "Past the fog stands a clock tower whose bell forgot how to rest. "
                "If you go, go together."],
        "rain": ["Listen to the rain. It is teaching patience."],
        "Winter": ["Even the coldest season holds a warm lamp."],
        "morning": ["Morning is the best time for a quiet mind."],
        "h3": ["You carry yourselves more gently than when you first came."],
        "h6": ["Your kindness to each other is itself a form of merit."],
        "birthday": ["A birthday is a reminder to be grateful for one more turn of the wheel."],
        "love": ["Such a thoughtful offering. May merit return to you.",
                 "Ah, this brings me simple joy. Thank you."],
        "like": ["Thank you, child.", "A kind gift."],
        "neutral": ["Every gift given freely is good.", "Thank you."],
        "dislike": ["...I will accept it with a calm mind.", "Hm. Let us not speak of it."],
    },
    "Fah": {
        "any": ["Welcome, welcome! Coffee's on me... just kidding, it's 5 gold.",
                "Life's too short for bad cake!",
                "I'm trying a melon mochi recipe. Want to be my taste tester?",
                "Grandpa Somchai orders the same thing every day. Black coffee, no smile.",
                "Kai eats three pastries for breakfast. Growing boy!",
                "You two are my favourite regulars. Don't tell anyone."],
        "Spring": ["Spring strawberries are the reason I opened this cafe!"],
        "Summer": ["Iced tea weather! My ice is melting faster than I can sell it."],
        "Fall": ["Pumpkin spice everything! Yes, even the napkins."],
        "Winter": ["Hot cocoa season! I put marshmallows in everything."],
        "rain": ["Rainy days are cake days. That's the rule."],
        "storm": ["Brr! Come under the awning with me, quick!"],
        "morning": ["Morning! The first batch just came out of the oven!"],
        "afternoon": ["Afternoon slump? Nothing a little sugar can't fix."],
        "evening": ["Closing soon. Want the last slice? For you two, free!"],
        "at:beach": ["Beach break! Even a cafe owner needs sunshine."],
        "h3": ["{p}! I saved you a seat by the window."],
        "h6": ["I named a cake after you two. It's two layers, obviously."],
        "birthday": ["It's my birthday! I baked my own cake. Three of them. Oops!"],
        "love": ["EEK! This is SO good! I'm putting it on the menu!",
                 "Oh my gosh, you get me! Thank you thank you!"],
        "like": ["Ooh, yummy! Thank you!", "This will be great in a recipe!"],
        "neutral": ["Aww, thanks!", "That's sweet of you."],
        "dislike": ["Um... this doesn't go in cake, does it?", "Oh. Oh no. It's... crunchy."],
    },
    "Somchai": {
        "any": ["Hmph. The sea gives. The sea takes. Mostly it takes my bait.",
                "Seventy years on this pier. The fish still outsmart me.",
                "Patience, young one. A fish can smell hurry.",
                "My wife used to bring me lunch right here. Every day, forty years.",
                "Tomas thinks he knows fish. Tomas knows boats.",
                "Quiet. You'll scare the tuna.",
                "Misty nights, I hear a bell out past the fog. The old clock tower. "
                "Nobody goes there anymore."],
        "Spring": ["Spring tides bring the herring close."],
        "Summer": ["Hot days, the big ones hide deep. Fish at dawn."],
        "Fall": ["Fall is for eels. Slippery devils."],
        "Winter": ["Cold water, slow fish. Slow fisherman too."],
        "rain": ["Rain! Best fishing weather. Don't let anyone tell you otherwise."],
        "storm": ["Storm's coming in. The big ones get hungry now."],
        "morning": ["Dawn is when the sea is honest."],
        "evening": ["Sun's going down. Time to pray and rest my knees."],
        "at:temple": ["Even an old fisherman needs a little merit."],
        "at:beach": ["This pier and I are the same age. We both creak."],
        "h3": ["You two... you remind me of me and my Malee."],
        "h6": ["Come fish with me sometime, {p}. Bring {q}. Old men like company."],
        "birthday": ["Birthday? At my age you stop counting and start fishing."],
        "love": ["Now THIS is a fish! Hah! You've got the touch!",
                 "My, my... you remembered what an old man likes."],
        "like": ["Not bad, not bad.", "Hm. Thank you, young one."],
        "neutral": ["Eh. Thank you.", "Hm."],
        "dislike": ["Flowers? Do I look like a honeybee?", "Bah. Junk."],
    },
    "Kai": {
        "any": ["Did you know iron sings when you hit it right? Tiiing!",
                "I'm gonna forge a sword someday. A REALLY big one.",
                "Master says I talk too much. What do YOU think?",
                "The mine goes down forever! Well, maybe not forever. Maybe!",
                "Fah gives me extra pastries if I carry flour sacks!",
                "Crystals grow like plants, but super slow. Like, super super slow.",
                "They say the Mist City clock tower is full of cursed gears! "
                "...If you find one, can I see it? Just a peek!"],
        "Spring": ["Spring means new tools! Everyone breaks theirs in winter."],
        "Summer": ["It's SO hot at the forge in summer. Worth it though!"],
        "Fall": ["Fall is best for mining. Cool air, warm hammer!"],
        "Winter": ["Ice caves have the prettiest gems. I'm not allowed to go alone."],
        "rain": ["Rain makes the mine drip. Plip. Plop. Spooky!"],
        "morning": ["I've been up since four! Couldn't sleep, too excited about ore!"],
        "night": ["Shhh, I'm supposed to be in bed..."],
        "at:forest": ["Master sent me for firewood. I found a cool rock instead!"],
        "h3": ["{p}, you're the coolest miner I know! After Master. Maybe."],
        "h6": ["When I make my first real sword, you two get to hold it first!"],
        "birthday": ["It's my birthday! Did you bring me a rock?! Please say rock!"],
        "love": ["WHOA! Is this for real?! This is the BEST thing EVER!",
                 "No way! I'm gonna put this on my shelf of treasures!"],
        "like": ["Cool! Thanks!", "Ooh, shiny. Thanks!"],
        "neutral": ["Uh, thanks!", "Neat, I guess."],
        "dislike": ["Blegh! Vegetables?!", "Flowers? What do I do with flowers?"],
    },
    "Luna": {
        "any": ["The light is so soft today... hold still, I'm painting you.",
                "Colours are just feelings wearing clothes.",
                "I lost my blue paint. Have you seen a cloud? I'll use that.",
                "Somchai lets me paint him if I don't talk. I always talk.",
                "Every place has a secret colour. The mine's is violet.",
                "You two look like a painting together. Warm tones."],
        "Spring": ["Spring greens! Seventeen of them, I counted."],
        "Summer": ["Summer light is loud. I like quieter colours."],
        "Fall": ["Fall is the season that paints itself."],
        "Winter": ["Snow is a blank canvas. I love and hate it."],
        "rain": ["Rain makes the colours run. Some of my best work was an accident."],
        "fog": ["Fog is my favourite. Everything becomes a watercolour."],
        "morning": ["Morning dew catches the light like tiny lanterns."],
        "evening": ["Sunset over the sea. Nothing I paint is ever this pink."],
        "at:temple": ["The gold leaf here glows even in the dark. How?"],
        "at:meadow": ["The meadow hums. Can you hear it? Bees and colour."],
        "h3": ["I painted your farm from the hill. It looked so happy."],
        "h6": ["{p}, I want to paint you and {q}. For the town hall. If you'd let me."],
        "birthday": ["My birthday... I thought everyone forgot. Thank you."],
        "love": ["Oh... it's beautiful. I'm going to paint it tonight.",
                 "You found the exact colour I was dreaming about!"],
        "like": ["How lovely. Thank you.", "Pretty! I'll sketch it."],
        "neutral": ["Oh, for me? Thanks.", "Hm, interesting shape."],
        "dislike": ["Oh... it's a bit... grey.", "I... will not be painting this."],
    },
}


# lines that unlock as the Valley Restoration progresses ("r:<bundle id>",
# "restored" = every bundle done) -- the valley notices what you two fixed
RESTORE_LINES = {
    "Mira": {"r:spring": ["The planters on the square are blooming! I'm so proud of you two."],
             "restored": ["A golden statue of you two! I cried a little. Okay, a lot."]},
    "Tomas": {"r:angler": ["Heard you fixed up the pier's old fish rack. A sailor thanks you."],
              "restored": ["The valley's shipshape again. Couldn't have sailed it better myself."]},
    "Elya": {"r:spring": ["The fields woke right up after your Spring bundle. Thank you!"],
             "r:summer": ["That fruit cart is selling out every day. Good for business!"]},
    "Luang Por": {"r:together": ["The arch you raised together... it is a quiet kind of merit."],
                  "restored": ["What was broken is whole again. So it goes, with patience."]},
    "Fah": {"r:summer": ["The fruit cart is back! Fresh fruit for my tarts every morning!"],
            "r:chef": ["That picnic table by the pond? I had lunch there. Heaven."],
            "restored": ["Two golden farmers in the square! I'm making a statue-shaped cake."]},
    "Somchai": {"r:angler": ["The old fish rack is back on the pier. Just like the old days."],
                "restored": ["Hmph. A golden statue. ...It's a good statue."]},
    "Kai": {"r:miner": ["Did you see the lamps by the mine? I can see my feet now! Ha!"],
            "restored": ["Is the statue REAL gold?! Don't worry, I won't chip it. Much."]},
    "Luna": {"r:forager": ["A little bird visits the new bird bath every morning. I named him Pip."],
             "r:together": ["That heart arch by the farm road... I've painted it four times."],
             "restored": ["The whole valley has new colours now. You two painted them."]},
}


# said when BOTH farmers come to chat within a few seconds of each other
COUPLE_LINES = {
    "Mira": ["You two again! Inseparable. It's honestly adorable.",
             "Matching smiles today, {p} and {q}. Did something happen? Tell me everything!"],
    "Tomas": ["Ha! Where one of you goes, the other follows. Good crew.",
              "Two farmers, one heading. Steady as she goes, you two."],
    "Elya": ["Oh, both of you! Double the customers, double the joy.",
             "You know, couples who garden together grow the sweetest crops."],
    "Luang Por": ["Two hearts arriving together. The temple feels warmer already.",
                  "Walk the path together, and neither of you walks alone."],
    "Fah": ["Table for two? Coming right up! Extra sprinkles, obviously.",
            "Aww, you two! I'm naming a drink after you. The 'Better Together' latte!"],
    "Somchai": ["Hmph. Both of you. ...Malee and I used to come here together too.",
                "Sit, both of you. There's room on the pier for two."],
    "Kai": ["Whoa, the whole team! Can I be the third member? Please?",
            "You two are like hammer and anvil! ...That's a compliment!"],
    "Luna": ["Don't move! Both of you, just like that. The light is perfect.",
             "You two share a colour, did you know? A warm, sunset kind of gold."],
}


def time_band(minutes):
    h = int(minutes) // 60
    if h < 11:
        return "morning"
    if h < 17:
        return "afternoon"
    if h < 21:
        return "evening"
    return "night"


def context_lines(name, season, weather, minutes, hearts_n, area_name, done=(),
                  restored=False):
    """(contextual, general) candidate lines for a talk right now."""
    L = LINES.get(name, {})
    ctx = []
    R = RESTORE_LINES.get(name, {})
    for b in done:
        ctx += R.get("r:" + str(b), [])
    if restored:
        ctx += R.get("restored", [])
    for k in (season, weather, time_band(minutes), "at:" + str(area_name)):
        ctx += L.get(k, [])
    if hearts_n >= 3:
        ctx += L.get("h3", [])
    if hearts_n >= 6:
        ctx += L.get("h6", [])
    return ctx, list(L.get("any", []))


# ---------------------------------------------------------------------------
#  Heart events.  pages: list of (speaker or None for narration, text).
#  reward: {"gold": n, "items": [(item_id, qty), ...]}  (missing ids -> gold)
# ---------------------------------------------------------------------------
HEART_EVENTS = {
    "Mira": {
        2: {"title": "Pressed Petals", "bg": (236, 186, 206), "pages": [
            (None, "Mira is kneeling by a flower box, carefully tucking petals into a book."),
            ("Mira", "Oh! {p}! You caught me. I press one flower from every season."),
            ("Mira", "This one's from the day you two arrived. I didn't want to forget it."),
            ("Mira", "Here -- take a few seeds. Plant something to remember today by.")],
            "reward": {"gold": 0, "items": [("seed:cauliflower", 4), ("fruit_salad", 1)]}},
        4: {"title": "The Secret Garden", "bg": (214, 196, 236), "pages": [
            (None, "Mira leads you behind the shop to a tiny, hidden garden."),
            ("Mira", "Nobody knows about this place. Well... now you do."),
            ("Mira", "My grandmother planted it. I come here when I miss her."),
            ("Mira", "Thank you for listening, {p}. Friends like you are rare.")],
            "reward": {"gold": 250, "items": [("seed:melon", 4)]}},
        6: {"title": "Flower Crowns", "bg": (246, 206, 226), "pages": [
            (None, "Mira is weaving two crowns out of daisies, humming to herself."),
            ("Mira", "One for you, {p}, and one for {q}. Don't argue, I measured your heads!"),
            (None, "She plops the crowns on. Somewhere, Luna gasps and grabs her sketchbook."),
            ("Mira", "Perfect. Now you're officially the valley's royal couple of farming.")],
            "reward": {"gold": 400, "items": [("fruit_salad", 2), ("seed:blueberry", 5)]}},
        8: {"title": "Grandmother's Seeds", "bg": (226, 214, 250), "pages": [
            (None, "In the hidden garden, Mira holds out a tiny tin box."),
            ("Mira", "These are the very last seeds my grandmother saved."),
            ("Mira", "I want them to grow somewhere full of love. So... your farm."),
            ("Mira", "Promise you'll plant them together? Okay. Now I'm crying. Go!")],
            "reward": {"gold": 800, "items": [("seed:cauliflower", 8), ("seed:melon", 8)]}},
    },
    "Tomas": {
        2: {"title": "Knots and Stories", "bg": (170, 196, 226), "pages": [
            (None, "Tomas is tying rope knots on a crate, humming a sea shanty."),
            ("Tomas", "Bowline, clove hitch, sheet bend... you never forget them."),
            ("Tomas", "Here, {p}. My lucky lure. Caught a tuna the size of a door with it."),
            ("Tomas", "Well. A small door. Don't tell Somchai.")],
            "reward": {"gold": 150, "items": [("tuna", 1)]}},
        4: {"title": "The Last Voyage", "bg": (120, 150, 196), "pages": [
            (None, "Tomas stares out towards the sea, quieter than usual."),
            ("Tomas", "My last voyage, a storm took our mast. We drifted nine days."),
            ("Tomas", "What kept us alive was the crew. Looking out for each other."),
            ("Tomas", "You two have that. Hold on to it. Here -- for your kitchen.")],
            "reward": {"gold": 200, "items": [("fish_dinner", 2)]}},
        6: {"title": "The Bottle Letter", "bg": (150, 186, 220), "pages": [
            (None, "Tomas turns a green glass bottle over and over in his hands."),
            ("Tomas", "Found it on the beach. A letter inside, forty years old."),
            ("Tomas", "It's from my first mate. 'If you find this, Tomas -- go home.'"),
            ("Tomas", "Took me a long time. But I think this valley is home now. Thanks to you two.")],
            "reward": {"gold": 450, "items": [("tuna", 2)]}},
        8: {"title": "Ship in a Bottle", "bg": (190, 214, 240), "pages": [
            (None, "Tomas presents a tiny ship in a bottle. Its sails say 'DUO'."),
            ("Tomas", "Built her myself. Took all winter. My hands aren't what they were."),
            ("Tomas", "A ship needs a crew that trusts each other. That's you two."),
            ("Tomas", "Fair winds, farmers. You'll always have a sailor on your side.")],
            "reward": {"gold": 900, "items": [("fish_dinner", 3)]}},
    },
    "Elya": {
        2: {"title": "Seed Library", "bg": (196, 226, 170), "pages": [
            (None, "Elya is sorting tiny paper envelopes by colour."),
            ("Elya", "It's a seed library! Borrow seeds, grow them, return twice as many."),
            ("Elya", "You two are my first members. Take these, on the house!")],
            "reward": {"gold": 0, "items": [("seed:potato", 5), ("seed:parsnip", 8)]}},
        4: {"title": "The Giant Cauliflower", "bg": (226, 232, 196), "pages": [
            (None, "Elya pulls out an old photo of an enormous cauliflower."),
            ("Elya", "My father grew this. The whole valley came to see it!"),
            ("Elya", "He said the secret was growing things WITH someone. Not alone."),
            ("Elya", "I think you two could grow one. Take these -- his last seeds.")],
            "reward": {"gold": 150, "items": [("seed:cauliflower", 6), ("cauliflower", 2)]}},
        6: {"title": "Rainy Day Ledger", "bg": (206, 222, 190), "pages": [
            (None, "Rain drums on the shop roof. Elya is frowning at a thick ledger."),
            ("Elya", "Numbers, numbers... I'm better with seeds than sums."),
            (None, "{p} and {q} help her tally the columns. It balances on the first try."),
            ("Elya", "You two could run this shop! ...Don't, though. I'd miss it. Take a discount!")],
            "reward": {"gold": 500, "items": [("seed:pumpkin", 5)]}},
        8: {"title": "The Valley Harvest", "bg": (240, 226, 170), "pages": [
            (None, "Elya stands at the edge of your farm, looking over the rows."),
            ("Elya", "When you arrived, this was all weeds and rocks."),
            ("Elya", "Now it feeds half the valley. My father would have loved to see it."),
            ("Elya", "Here -- his golden watering can charm. It belongs with you now.")],
            "reward": {"gold": 900, "items": [("sprinkler2", 2)]}},
    },
    "Luang Por": {
        2: {"title": "Morning Alms", "bg": (238, 200, 140), "pages": [
            (None, "At dawn, Luang Por walks slowly with his alms bowl."),
            ("Luang Por", "Giving is not about the size of the gift, {p}."),
            ("Luang Por", "It is about the heart that offers it. Yours is warm."),
            ("Luang Por", "Take this blessing. May your harvest be gentle and full.")],
            "reward": {"gold": 200, "items": [("milk_tea", 2)]}},
        4: {"title": "Two Candles", "bg": (250, 214, 150), "pages": [
            (None, "Luang Por lights two candles from a single flame."),
            ("Luang Por", "See? The first candle loses nothing by lighting the second."),
            ("Luang Por", "So it is with you and {q}. Share your light freely."),
            ("Luang Por", "Carry this merit home. Return whenever your minds are heavy.")],
            "reward": {"gold": 400, "items": []}},
        6: {"title": "Walking Meditation", "bg": (236, 214, 170), "pages": [
            (None, "Luang Por walks slowly around the temple hall. He waves you to follow."),
            ("Luang Por", "Step. Breathe. Step. There is nowhere to hurry to."),
            (None, "You walk three slow circles together. The world feels quieter."),
            ("Luang Por", "Bring this calm to your fields. Crops grow better near a peaceful heart.")],
            "reward": {"gold": 500, "items": [("egg_custard", 2)]}},
        8: {"title": "Blessing String", "bg": (255, 226, 170), "pages": [
            (None, "Luang Por ties a white cotton string around {p}'s wrist, then {q}'s."),
            ("Luang Por", "Sai sin. A thread of blessing. It joins your fortunes together."),
            ("Luang Por", "When one of you stumbles, the other will feel the pull. Help each other up."),
            ("Luang Por", "Go in peace, my children. This temple will always be your home too.")],
            "reward": {"gold": 1000, "items": [("milk_tea", 3)]}},
    },
    "Fah": {
        2: {"title": "Taste Test", "bg": (250, 206, 176), "pages": [
            (None, "Fah waves you over, holding a plate of wobbly pastries."),
            ("Fah", "Okay okay okay. New recipe. Be honest. Brutally honest."),
            (None, "You take a bite. It is... surprisingly amazing."),
            ("Fah", "REALLY?! Eee! Take some home! Share with {q}!")],
            "reward": {"gold": 0, "items": [("egg_custard", 2), ("milk_tea", 2)]}},
        4: {"title": "The Burnt Cake", "bg": (236, 176, 150), "pages": [
            (None, "Smoke drifts from the cafe window. Fah is fanning a charred cake."),
            ("Fah", "It was for my mum's recipe contest! It's ruined!"),
            (None, "Together you scrape off the burnt top and cover it in fruit."),
            ("Fah", "...It actually looks better now. You two are geniuses!"),
            ("Fah", "Here, the prize money. You earned half. No -- all of it!")],
            "reward": {"gold": 350, "items": [("fruit_salad", 2)]}},
        6: {"title": "Cafe After Dark", "bg": (190, 150, 190), "pages": [
            (None, "The cafe is closed, chairs up on the tables. Fah pours two teas."),
            ("Fah", "I almost sold this place last year. Nobody came in."),
            ("Fah", "Then you two started showing up. Every day. Muddy boots and all."),
            ("Fah", "So... thank you. Here's my secret recipe book page. Don't lose it!")],
            "reward": {"gold": 300, "items": [("pumpkin_pie", 2)]}},
        8: {"title": "Named on the Menu", "bg": (255, 222, 170), "pages": [
            (None, "A new chalkboard hangs outside: 'THE DUO -- two layers, one heart.'"),
            ("Fah", "Ta-daa! It's our bestseller already!"),
            ("Fah", "You two taught me that the best recipes need two cooks."),
            ("Fah", "Best friends forever, okay? Pinky swear. Both of you!")],
            "reward": {"gold": 800, "items": [("pumpkin_pie", 3), ("egg_custard", 3)]}},
    },
    "Somchai": {
        2: {"title": "The Quiet Rule", "bg": (150, 186, 206), "pages": [
            (None, "Grandpa Somchai doesn't look up from his line."),
            ("Somchai", "Sit. Don't talk. Watch the float."),
            (None, "You sit in silence. A gull lands nearby. The float bobs."),
            ("Somchai", "...Hm. You can sit still. Rare, for young people. Take this.")],
            "reward": {"gold": 120, "items": [("sardine", 3)]}},
        4: {"title": "Malee's Hat", "bg": (206, 186, 150), "pages": [
            (None, "Somchai is holding an old woven hat, frayed at the brim."),
            ("Somchai", "My wife Malee wore this. She could out-fish me any day."),
            ("Somchai", "She'd have liked you two. Always laughing together."),
            ("Somchai", "Here. Her old tackle box. It should catch fish, not dust.")],
            "reward": {"gold": 300, "items": [("halibut", 1)]}},
        6: {"title": "The One That Got Away", "bg": (110, 140, 176), "pages": [
            (None, "At the end of the pier, Somchai points at the dark water."),
            ("Somchai", "Forty years I've chased one fish. A giant. Silver as the moon."),
            ("Somchai", "Maybe I'm not meant to catch it. Maybe you are."),
            ("Somchai", "If you ever do... let it see the sky. Then tell me about it.")],
            "reward": {"gold": 400, "items": [("swordfish", 1)]}},
        8: {"title": "Grandpa", "bg": (236, 196, 150), "pages": [
            (None, "Somchai hands you a small carved wooden fish."),
            ("Somchai", "I carved two. One for each of you."),
            ("Somchai", "I never had grandchildren. But these days... I feel like I do."),
            ("Somchai", "Now go on. Don't make an old man cry on his own pier.")],
            "reward": {"gold": 900, "items": [("fish_dinner", 3)]}},
    },
    "Kai": {
        2: {"title": "First Spark", "bg": (240, 176, 120), "pages": [
            (None, "Kai is hammering a nail. Very, very hard. It is very bent."),
            ("Kai", "It's supposed to be a horseshoe! ...For a very small horse."),
            ("Kai", "Hey {p}, can you hold this? No wait, it's hot! Sorry!"),
            ("Kai", "Here, have some ore! I found extra. Don't tell Master!")],
            "reward": {"gold": 0, "items": [("copper", 8), ("iron", 3)]}},
        4: {"title": "Lost in the Mine", "bg": (150, 130, 176), "pages": [
            (None, "Kai looks pale, clutching a lantern."),
            ("Kai", "I went down to floor five alone. The lantern went out."),
            ("Kai", "I thought about you two. How you always go down together."),
            ("Kai", "So I sang until I found the ladder. Haha... Please don't tell Master.")],
            "reward": {"gold": 250, "items": [("gold_ore", 2)]}},
        6: {"title": "The First Blade", "bg": (200, 200, 216), "pages": [
            (None, "Kai proudly holds up a small, slightly wobbly knife."),
            ("Kai", "My first REAL blade! Master said it's 'not terrible'!"),
            ("Kai", "That's the nicest thing he's ever said! Ever!"),
            ("Kai", "I made it with the ore you two gave me. So it's half yours!")],
            "reward": {"gold": 400, "items": [("iron", 6), ("gold_ore", 2)]}},
        8: {"title": "Apprentice No More", "bg": (255, 206, 120), "pages": [
            (None, "The whole town gathers as Kai is handed his own hammer."),
            ("Kai", "I'm a real smith now! Can you believe it?!"),
            ("Kai", "You two believed in me before anyone. Even before me!"),
            ("Kai", "This is my best work. It's for your farm. Forever and ever!")],
            "reward": {"gold": 800, "items": [("iridium_ore", 2)]}},
    },
    "Luna": {
        2: {"title": "Colour Study", "bg": (200, 186, 236), "pages": [
            (None, "Luna's easel shows a blur of soft greens and a small golden dot."),
            ("Luna", "That's you, {p}. The golden dot. You were laughing."),
            ("Luna", "People are easier to paint when they're happy."),
            ("Luna", "Here, some blueberries. For... inspiration. Mine, not yours.")],
            "reward": {"gold": 100, "items": [("blueberry", 3)]}},
        4: {"title": "Lost Paintings", "bg": (176, 170, 220), "pages": [
            (None, "Luna sits among torn canvases, looking lost."),
            ("Luna", "The wind took my whole sketchbook into the pond."),
            ("Luna", "...But look. The water made the colours bleed. It's beautiful."),
            ("Luna", "Maybe losing things just makes room for new colours. Thank you for staying.")],
            "reward": {"gold": 300, "items": [("seed:crocus", 5)]}},
        6: {"title": "The Portrait", "bg": (236, 200, 220), "pages": [
            (None, "Luna turns her easel around. It's a portrait of you and {q}."),
            ("Luna", "I've been painting it in secret all season."),
            ("Luna", "I wanted to capture how you look at each other. It's the hardest colour."),
            ("Luna", "It's going in the town hall. Everyone will see it. Okay?")],
            "reward": {"gold": 500, "items": [("fruit_salad", 2)]}},
        8: {"title": "The Mural", "bg": (255, 214, 190), "pages": [
            (None, "At sunrise, Luna unveils a mural of the whole valley."),
            (None, "Every villager is in it. And in the middle, two farmers holding hands."),
            ("Luna", "You two are the heart of the valley now. I just painted what's true."),
            ("Luna", "Thank you for being my friends. My brightest colours.")],
            "reward": {"gold": 900, "items": [("crocus", 3)]}},
    },
}

EVENT_LEVELS = (2, 4, 6, 8)


def events_for(name):
    return HEART_EVENTS.get(name, {})


# ---------------------------------------------------------------------------
#  Gift tastes -- resolved against the live registries at call time.
# ---------------------------------------------------------------------------
_FLOWER_WORDS = ("flower", "bloom", "daisy", "tulip", "poppy", "rose", "lily", "lotus",
                 "orchid", "crocus", "sunflower", "lavender", "jasmine", "petal")
_FRUIT = {"blueberry", "melon", "tomato", "cranberry", "frost_melon", "strawberry",
          "grape", "apple", "mango", "peach", "cherry", "orange", "banana", "berry"}
_JUNK = {"wire", "old_battery", "scrap_iron", "gear_scrap", "slime_goo", "trash", "junk"}


def _registries():
    from . import loot
    from .crops import CROPS
    from .fishing import FISH
    try:
        from .cooking import FOODS
    except Exception:
        FOODS = {}
    return loot.MATERIALS, CROPS, FISH, FOODS


def item_exists(item):
    if not isinstance(item, str) or not item:
        return False
    M, C, F, FD = _registries()
    if item.startswith("seed:"):
        return item[5:] in C
    return item in M or item in C or item in F or item in FD or item in (
        "egg", "milk", "duck_egg", "goat_milk", "wool", "truffle", "sprinkler", "sprinkler2")


def _cat(item):
    M, C, F, FD = _registries()
    if item in F:
        return "fish"
    if item in C:
        return "crop"
    if item in FD:
        return "food"
    return (M.get(item) or {}).get("cat", "")


def token_match(tok, item):
    """Does item match a taste entry (an id or an @category token)?"""
    if not tok.startswith("@"):
        return tok == item
    t = tok[1:]
    c = _cat(item)
    low = item.lower()
    if t in ("fish", "crop", "food"):
        return c == t
    if t == "gem":
        return c in ("gem", "gems", "crystal")
    if t == "ore":
        return c == "ore"
    if t == "forage":
        return c in ("forage", "flower")
    if t == "flower":
        return c == "flower" or (c in ("forage", "crop") and
                                 any(w in low for w in _FLOWER_WORDS))
    if t == "fruit":
        return low in _FRUIT or any(w in low for w in ("berry", "melon", "fruit"))
    if t == "junk":
        return low in _JUNK or c == "junk"
    if t == "artisan":                    # jams, pickles, juice, cheese, honey (Farming)
        return c == "artisan"
    if t == "wine":                       # the keg's wines + mead
        return c == "artisan" and (low.startswith("wine_") or low == "mead")
    return False


def taste(name, item):
    """'love' | 'like' | 'dislike' | 'neutral' for giving ``item`` to ``name``.
    Concrete ids win over @categories; love beats like beats dislike."""
    v = VILLAGERS.get(name)
    if not v:
        return "neutral"
    for kind in ("loves", "likes", "dislikes"):          # exact ids first
        if item in v.get(kind, ()):
            return {"loves": "love", "likes": "like", "dislikes": "dislike"}[kind]
    for kind in ("loves", "dislikes", "likes"):
        for tok in v.get(kind, ()):
            if tok.startswith("@") and token_match(tok, item):
                return {"loves": "love", "likes": "like", "dislikes": "dislike"}[kind]
    return "neutral"


def loved_items(name):
    """Concrete loved ids that exist right now (registry-filtered), for hints."""
    v = VILLAGERS.get(name, {})
    out = [i for i in v.get("loves", ()) if not i.startswith("@") and item_exists(i)]
    return out


def birthday_str(name):
    b = VILLAGERS.get(name, {}).get("birthday")
    if not b:
        return "?"
    return f"{SEASON_NAMES[b[0] % 4]} {b[1]}"
