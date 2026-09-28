"""Town fetch-quests: bring requested goods to the quest board for gold.

Quest generation is pure/data-driven; the QuestMenu UI pulls fonts from game.ui
and reads/writes game.gold, game.active_quests and the players' inventories.
"""
import random
import pygame
from .settings import SCREEN_W, SCREEN_H, WHITE, GOLD, UI_BORDER
from .crops import CROPS
from .fishing import FISH
from . import loot

ACCENT = (120, 190, 235)


def value(item):
    if item in CROPS:
        return CROPS[item]["sell"]
    if item in FISH:
        return FISH[item]
    return loot.sell_value(item)


def label(item):
    if loot.is_material(item):
        return loot.label(item)
    return item.replace("_", " ").title()


# item id -> short hint telling the player where to find/produce it.
# Pure function of the item, so it never has to be stored in the save.
_ORE = {"copper", "iron", "gold_ore", "iridium_ore"}
_MONSTER_MAT = {"slime_goo", "bat_wing", "bone", "essence", "void_essence"}
_HUNT_MAT = {"meat", "hide", "pelt"}


def _fish_where(item):
    """Location hint for a fish, read from fishing's own data so it always
    matches the catalogue (freshwater vs saltwater, forest-pond-only apex).

    Prefers a public ``fishing.habitat(id)`` helper if Chat 3 adds one; until
    then it derives the answer from the tier + pool tables already in
    fishing.py. Falls back safely to the generic freshwater line if the data
    isn't shaped as expected.
    """
    from . import fishing as fsh
    hb = getattr(fsh, "habitat", None)
    if callable(hb):
        try:
            return hb(item)
        except Exception:
            pass
    g = lambda n: getattr(fsh, n, [])
    fresh_apex = set(g("_FRESH_LEGENDARY")) | set(g("_FRESH_LEVIATHAN"))
    sea_apex = set(g("_SEA_LEGENDARY")) | set(g("_SEA_LEVIATHAN"))
    sea_all = (set(g("_SEA_COMMON")) | set(g("_SEA_UNCOMMON"))
               | set(g("_SEA_RARE")) | sea_apex)
    if item in fresh_apex:
        return "the forest pond only (legendary catch)"
    if item in sea_apex:
        return "the open sea only (legendary catch)"
    if item in sea_all:
        return "fish the Beach (saltwater)"
    return "fish any freshwater pond or the forest pond"


def where(item):
    if item in CROPS:
        return "grow it on the Farm"
    if item in FISH:
        return _fish_where(item)
    if item == "wood":
        return "chop trees (Farm / Forest)"
    if item == "stone":
        return "break rocks in the Mine"
    if item in _ORE:
        return "mine ore in the Mine"
    if item in _MONSTER_MAT:
        return "fight monsters in the Mine"
    if item in _HUNT_MAT:
        return "hunt animals in the Forest"
    # new registry materials we don't know by name yet: hint from their cat
    if loot.is_material(item):
        cat = loot.MATERIALS[item].get("cat")
        if cat == "ore":
            return "mine ore in the Mine"
        if cat == "resource":
            return "gather it (Farm / Forest / Mine)"
        if cat == "mat":
            return "monster drops / hunting"
        if cat in ("gem", "gems", "crystal"):
            return "break rocks deep in the Mine"
        if cat in ("forage", "flower"):
            return "forage in the Forest / Meadow"
        if cat == "artisan":
            return "make it in an artisan machine on the Farm"
        if cat in ("relic", "trophy"):
            return "a rare find -- festivals, bosses & treasure"
    try:
        from .cooking import FOODS
        if item in FOODS:
            return "cook it at the Stove at home"
    except Exception:
        pass
    return "ask around town"


_POOL = None
# never board errands: once-a-year trophies, keepsakes, key items and crafted
# consumables/tools (a quest must ask for something you can go and gather)
QUEST_EXCLUDE = {"golden_egg", "twin_locket", "city_key", "cursed_gear"}
QUEST_EXCLUDE_CATS = {"trophy", "relic", "bomb", "tool", "machine", "farming", "key"}


def _questable(item):
    if item in QUEST_EXCLUDE:
        return False
    if loot.is_material(item) and item not in CROPS and item not in FISH:
        if loot.MATERIALS[item].get("cat") in QUEST_EXCLUDE_CATS:
            return False
    return 0 < value(item) <= 400


def _pool():
    global _POOL
    if _POOL is None:
        # Single source of truth (docs/TASK_no_hardcode.md): the quest pool is
        # derived from the item registries — crops.CROPS, fishing.FISH and
        # loot.MATERIALS — so anything added to a registry becomes questable
        # automatically. value(i) > 0 keeps unsellable placeholders out.
        items = list(CROPS.keys()) + list(FISH.keys()) + list(loot.MATERIALS)
        # cap at 400g so legendary/leviathan fish and iridium-tier loot never
        # become "fetch 3x" board quests (those are trophies, not errands)
        _POOL = [i for i in dict.fromkeys(items) if _questable(i)]
    return _POOL


def generate(rng=random):
    pool = _pool()
    item = rng.choice(pool)
    # artisan goods are ~half the registry (every crop has a jam/juice/pickle);
    # thin them out so the board still mostly asks for things you can gather
    if (loot.is_material(item) and loot.MATERIALS[item].get("cat") == "artisan"
            and rng.random() < 0.6):
        item = rng.choice(pool)
    v = value(item)
    if v <= 10:
        qty = rng.randint(8, 16)
    elif v <= 80:
        qty = rng.randint(4, 8)
    else:
        qty = rng.randint(2, 4)
    reward = int(v * qty * 1.6 + 40)
    q = {"item": item, "qty": qty, "reward": reward}
    who = _requester(item, rng)
    if who:
        q["npc"] = who
    return q


# friendship points a villager gains when you finish THEIR request (half a heart)
QUEST_FRIEND_PTS = 25


def _requester(item, rng=random):
    """A villager who'd ask for this item (someone who loves/likes it when
    possible) -- quests become little favours for your neighbours."""
    try:
        from . import story_data as SD
        names = sorted(SD.VILLAGERS)
        fans = [n for n in names if SD.taste(n, item) in ("love", "like")]
        return rng.choice(fans or names)
    except Exception:
        return None


def requester_name(q):
    who = q.get("npc") if isinstance(q, dict) else None
    if not who:
        return None
    try:
        from . import story_data as SD
        return SD.display(who)
    except Exception:
        return who


def to_dict(q):
    d = {"item": q["item"], "qty": q["qty"], "reward": q["reward"]}
    if q.get("npc"):
        d["npc"] = str(q["npc"])
    return d


class QuestMenu:
    def __init__(self, game, player):
        self.g = game
        self.p = player
        self.sel = 0
        self.msg = "Bring the goods, collect the reward!"

    # rows: ("turnin", quest) for each active, ("accept", quest) for each offer
    def _rows(self):
        rows = [("turnin", q) for q in self.g.active_quests]
        rows += [("accept", q) for q in self.g.quest_offers]
        return rows

    def move(self, d):
        rows = self._rows()
        if rows:
            self.sel = (self.sel + d) % len(rows)
        self.g.audio.play("ui_move")

    def confirm(self):
        rows = self._rows()
        if not rows:
            return
        self.sel %= len(rows)
        kind, q = rows[self.sel]
        if getattr(self.g, "net_mode", None) == "client" and getattr(self.g, "net", None):
            # client: the host owns gold/inventory/quests — relay the choice
            self.g.net.send({"t": "menu", "m": "quest", "op": kind, "q": to_dict(q)})
            self.g.audio.play("ui_select")
            self.msg = ("Accepting..." if kind == "accept" else "Turning in...") + " (sent to host)"
            return
        if kind == "accept":
            if len(self.g.active_quests) >= 4:
                self.msg = "You already have 4 active quests."
                self.g.audio.play("ui_move")
                return
            self.g.quest_offers.remove(q)
            self.g.active_quests.append(q)
            self.g.audio.play("ui_select")
            self.msg = f"Accepted: bring {q['qty']} {label(q['item'])} - {where(q['item'])}."
        else:  # turn in
            have = self.g._count_all(q["item"])
            if have < q["qty"]:
                self.msg = f"Need {q['qty']} {label(q['item'])} (have {have})."
                self.g.audio.play("ui_move")
                return
            self.g._remove_all(q["item"], q["qty"])
            self.g.gold += q["reward"]
            self.g.active_quests.remove(q)
            self.g.audio.play("sell")
            self.g._popup(self.p.x, self.p.y - 12, f"+{q['reward']}g", (255, 220, 120))
            self.g.ui.log(f"Quest complete! +{q['reward']}g")
            self.msg = f"Reward paid: {q['reward']}g. Thank you!"
            who = q.get("npc")
            friend = getattr(getattr(self.g, "world", None), "friend", None)
            if who and isinstance(friend, dict):
                cap = 500
                friend[who] = min(cap, int(friend.get(who, 0)) + QUEST_FRIEND_PTS)
                nm = requester_name(q)
                self.msg = f"{nm} is delighted! +{q['reward']}g, +friendship"
                self.g.ui.log(f"{nm} thanks you for the {label(q['item'])}! (+friendship)")
            # juice + shared event bus (Story domain emits quest_done)
            parts = getattr(self.g, "parts", None)
            if parts is not None:
                parts.sparkle(self.p.x, self.p.y - 10, n=14, color=(255, 222, 130))
                cb = getattr(parts, "coin_burst", None)
                if cb:
                    try:
                        cb(self.p.x, self.p.y - 10)
                    except Exception:
                        pass
            emit = getattr(self.g, "emit", None)
            if emit:
                emit("quest_done", p=self.p, quest=to_dict(q))
        self.sel = min(self.sel, max(0, len(self._rows()) - 1))

    def cancel(self):
        """Abandon the selected accepted quest, returning it to the offer list."""
        rows = self._rows()
        if not rows:
            return
        self.sel %= len(rows)
        kind, q = rows[self.sel]
        if kind != "turnin":
            self.msg = "Select an accepted quest to cancel."
            self.g.audio.play("ui_move")
            return
        if getattr(self.g, "net_mode", None) == "client" and getattr(self.g, "net", None):
            self.g.net.send({"t": "menu", "m": "quest", "op": "cancel", "q": to_dict(q)})
            self.g.audio.play("ui_move")
            self.msg = "Cancelling... (sent to host)"
            return
        self.g.active_quests.remove(q)
        if q not in self.g.quest_offers:
            self.g.quest_offers.append(q)
        self.g.audio.play("ui_move")
        self.msg = f"Cancelled: {q['qty']} {label(q['item'])}. Back on the board."
        self.sel = min(self.sel, max(0, len(self._rows()) - 1))

    def handle_key(self, key):
        from .settings import P1_KEYS, P2_KEYS
        if key in (pygame.K_ESCAPE,):
            self.g.state = "play"
            self.g.audio.play("ui_move")
            return
        if key in (P1_KEYS["up"], P2_KEYS["up"]):
            self.move(-1)
        elif key in (P1_KEYS["down"], P2_KEYS["down"]):
            self.move(1)
        elif key in (P1_KEYS["action"], P2_KEYS["action"]):
            self.confirm()
        elif key in (pygame.K_x, pygame.K_DELETE, pygame.K_BACKSPACE):
            self.cancel()

    # how many rows fit in the panel at once (scrolling kicks in beyond this)
    VIS = 6
    ROW_H = 64

    def draw(self, surf):
        """Parchment modal (the title menu's look): ribbon title, one well per
        quest, the keyboard row under the gold row cursor, rewards right-aligned
        in a gold column, and the footer hint centred. The card is sized to
        the rows it shows, so a short board has no empty half."""
        from .ui import scroll_window
        from . import ui_kit as K
        self._t = getattr(self, "_t", 0.0) + 1 / 60
        K.dim(surf, 150)
        rows = self._rows()
        total = len(rows)
        vis = max(1, min(self.VIS, total))
        pw = 760
        ph = 80 + vis * self.ROW_H + 80
        # centred in the band under both HUD hotbar rows (the ribbon clears y=108)
        px, py = (SCREEN_W - pw) // 2, 130 + max(0, (SCREEN_H - 10 - 130 - ph) // 2)
        P = K.modal(surf, (px, py, pw, ph), "Quest Board", K.font(28, True))
        K.blit_text(surf, K.font(15, True), f"Gold: {self.g.gold:,}g", K.GOLD_TXT,
                    (P.centerx, P.y + 50))
        y0 = P.y + 80                       # room above for the 'more above' arrow
        if not rows:
            K.well(surf, pygame.Rect(P.x + 24, y0, pw - 48, self.ROW_H - 8))
            K.blit_text(surf, K.font(16), "No quests right now. Come back tomorrow!",
                        K.INK_SOFT, (P.centerx, y0 + (self.ROW_H - 8) // 2))

        # only render the visible window; self.sel (driven by move()) stays centred
        if total:
            self.sel %= total
        start, end = scroll_window(total, self.VIS, self.sel)
        f_head, f_sub, f_loc = K.font(17, True), K.font(14), K.font(12)
        f_rew = K.font(18, True)
        rew_w = 96                                  # the right-aligned reward column
        for j, (kind, q) in enumerate(rows[start:end]):
            i = start + j
            r = pygame.Rect(P.x + 24, y0 + j * self.ROW_H, pw - 48 - 10, self.ROW_H - 8)
            if i == self.sel:
                K.row_cursor(surf, r, self._t)
            else:
                K.well(surf, r, radius=10)
            ic = assets_icon(q["item"])
            icx = r.x + 36
            if ic:
                surf.blit(ic, ic.get_rect(center=(icx, r.centery)))
            tx = r.x + 64
            textw = r.right - rew_w - 12 - tx
            tag = "TURN IN" if kind == "turnin" else "QUEST"
            head = K.ellipsize(f_head, f"{tag}: {q['qty']} x {label(q['item'])}", textw)
            hr = K.blit_text(surf, f_head, head, K.INK, (tx, r.y + 13), align="left")
            nm = requester_name(q)
            if nm and hr.right + 10 + K.font(12, True).size(f"for {nm}")[0] <= tx + textw:
                K.blit_text(surf, K.font(12, True), f"for {nm}", (176, 76, 112),
                            (hr.right + 10, r.y + 13), align="left")
            if kind == "turnin":
                have = self.g._count_all(q["item"])
                done = have >= q["qty"]
                sub, scol = (f"have {have}/{q['qty']}  -  Action to turn in  -  X to cancel",
                             K.SPROUT if done else (170, 104, 48))
            else:
                sub, scol = "press Action to accept", K.INK_SOFT
            K.blit_text(surf, f_sub, K.ellipsize(f_sub, sub, textw), scol,
                        (tx, r.y + 30), align="left")
            K.blit_text(surf, f_loc, K.ellipsize(f_loc, f"Find at: {where(q['item'])}", textw),
                        (96, 120, 72), (tx, r.y + 45), align="left")
            # reward column: a thin rule, then the amount right-aligned, centred on the row
            cx0 = r.right - rew_w
            pygame.draw.line(surf, K.WELL_LINE, (cx0, r.y + 10), (cx0, r.bottom - 10), 2)
            K.blit_text(surf, f_rew, f"+{q['reward']}g", K.GOLD_TXT,
                        (r.right - 14, r.centery - 7), align="right")
            K.blit_text(surf, K.font(13, True), "reward", K.INK_SOFT,
                        (r.right - 14, r.centery + 12), align="right")

        # scroll affordances when the list runs past the window
        region_h = self.VIS * self.ROW_H - 8
        self.g.ui.draw_scrollbar(surf, P.right - 30, y0, region_h, total, self.VIS, start,
                                 track=K.WELL_LINE, thumb_col=K.WOOD)
        self.g.ui.draw_scroll_arrows(surf, start, end, total, P.x + 24, y0, pw - 58, region_h,
                                     vertical=True, color=K.WOOD)

        if self.msg:
            K.blit_text(surf, K.font(15, True), K.ellipsize(K.font(15, True), self.msg, pw - 60),
                        K.INK, (P.centerx, P.bottom - 50))
        K.divider(surf, P.centerx, P.bottom - 34, pw // 2 - 60, heart=False)
        K.blit_text(surf, K.font(13),
                    "Up/Down select  -  Action accept / turn in  -  X cancel  -  Esc close",
                    K.INK_SOFT, (P.centerx, P.bottom - 20))


def assets_icon(item):
    from . import assets
    try:
        return assets.item_icon(item)
    except Exception:
        return None
