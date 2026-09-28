"""Villager schedules, heart events, valley restoration, festival games.

Owner: Temple, NPC & Quests (Chat 4). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

Pieces:
  * villagers  -- 4 scheduled villagers (story_data.SCHEDULES) walk between
                  town / beach / temple / meadow by the hour; contextual talk,
                  1 chat + 1 gift per day, birthdays (x4 gift points + toast).
  * heart events -- custom state "heart_event" at 2/4/6/8 hearts.
  * restoration  -- story_restore.RestorationMixin (state "restoration").
  * festival     -- story_restore.FestivalGamesMixin (Egg Hunt, Lantern Night).
  * journal tabs -- Friends (40) + Restoration (45).
"""
import math
import random
import pygame
from ..settings import (TILE, SCREEN_W, SCREEN_H, WHITE, GOLD, P1_KEYS, P2_KEYS,
                        AREA_MEADOW, AREA_TOWN)
from .. import story_data as SD
from .. import story_art as ART
from .. import festival
from .. import ui_kit as K
from ..npc import NPC, NPC_DATA, npc_frames, HEART_PTS, MAX_FRIEND
from .story_restore import RestorationMixin, FestivalGamesMixin, speaker_tag

ART.register_all()

VILLAGER_ORDER = ["Mira", "Tomas", "Elya", "Luang Por", "Fah", "Somchai", "Kai", "Luna"]


def _wrap(font, text, width):
    words, lines, cur = str(text).split(), [], ""
    for wd in words:
        cand = (cur + " " + wd) if cur else wd
        if font.size(cand)[0] <= width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


class StoryMixin(RestorationMixin, FestivalGamesMixin):
    """Villager schedules, heart events, valley restoration, festival games."""

    # ================================================================ state
    def _on_reset_story(self):
        self.story_talked_today = set()     # villager names chatted with today
        self.story_gifted_today = set()     # "Name|player_idx" gifts given today
        self.story_seen_events = set()      # "Name|level" heart events watched
        self.story_known_loves = set()      # "Name|item" discovered loved gifts
        self.story_bday_gifts = set()       # "Name|year" birthday gifts given
        self._story_hour = None
        self._story_talker = 0
        self._he = None                     # running heart event
        self._he_hearts = []                # screen-space floating hearts
        self._story_spot_cache = {}
        self.story_intro = False            # "meet the neighbours" onboarding shown
        self.story_board_intro = False      # "Restoration Board is up" hint shown
        self.story_newcomers = False        # pre-story save: Fah/Somchai/Kai/Luna "moved in"
        self._story_board_hint_t = None     # seconds until that hint (in town only)

    def _story_day_key(self):
        """'year|season|day' stamp for per-day state that must survive a relaunch."""
        t = self.time
        return f"{t.year}|{t.season_idx}|{t.day}"

    def _on_save_story(self):
        return {"story_intro": bool(self.story_intro),
                "story_board_intro": bool(self.story_board_intro),
                "story_newcomers": bool(self.story_newcomers),
                "story_seen_events": sorted(self.story_seen_events),
                "story_known_loves": sorted(self.story_known_loves),
                "story_bday_gifts": sorted(self.story_bday_gifts),
                # today's first-chat / gift limits (quit + relaunch must not reset them)
                "story_today": {"day": self._story_day_key(),
                                "talked": sorted(self.story_talked_today),
                                "gifted": sorted(self.story_gifted_today)}}

    def _on_load_story(self, d):
        self.story_seen_events = set(d.get("story_seen_events", []) or [])
        self.story_known_loves = set(d.get("story_known_loves", []) or [])
        self.story_bday_gifts = set(d.get("story_bday_gifts", []) or [])
        self.story_intro = bool(d.get("story_intro", False))
        # saves from before the board hint had it shown together with the intro
        self.story_board_intro = bool(d.get("story_board_intro", self.story_intro))
        # a save that predates the story domain already had a town: the four
        # new villagers really did "move in" (a fresh farm meets everyone at once)
        self.story_newcomers = bool(d.get("story_newcomers", "story_intro" not in d))
        self._story_board_hint_t = None
        self._story_hour = None
        today = d.get("story_today") or {}
        if isinstance(today, dict) and today.get("day") == self._story_day_key():
            self.story_talked_today = set(str(x) for x in (today.get("talked") or []))
            self.story_gifted_today = set(str(x) for x in (today.get("gifted") or []))
        else:                                # old save, or saved on another day
            self.story_talked_today = set()
            self.story_gifted_today = set()

    def _on_new_day_story(self):
        self.story_talked_today = set()
        self.story_gifted_today = set()
        self._story_hour = None
        if festival.is_festival_day(self.time):
            s = self.time.season_idx
            if s == 0 and str(self.time.year) not in getattr(self, "story_egg_hunts", ()):
                self.toast("Flower Festival today!",
                           "Visit the festival stall in town for the Egg Hunt",
                           icon="golden_egg", color=(255, 190, 210), seconds=6.0)
            elif s == 1:
                self.toast("Summer Luau today!",
                           "Each of you: hold an ingredient at the stall to add it to the pot",
                           color=(250, 196, 110), seconds=6.0)
            elif s == 2:
                self.toast("Harvest Fair today!",
                           "Hold your best produce at the stall -- Best in Show wins a prize",
                           color=(236, 170, 90), seconds=6.0)
            elif s == 3:
                self.toast("Star Festival: Lantern Night",
                           "After 5 PM, meet at the beach pier and release lanterns together",
                           color=(255, 196, 120), seconds=6.0)
        for name in VILLAGER_ORDER:
            if self._story_is_birthday(name):
                self.toast(f"{SD.display(name)}'s birthday!",
                           "A gift today means a lot (x4 friendship)",
                           icon=None, color=(255, 170, 200), seconds=5.0)
                self.ui.log(f"Today is {SD.display(name)}'s birthday!")

    # ================================================================ helpers
    def _story_is_birthday(self, name):
        b = SD.VILLAGERS.get(name, {}).get("birthday")
        t = getattr(self, "time", None)
        return bool(b and t and t.season_idx == b[0] and t.day == b[1])

    def _story_wet(self):
        return str(getattr(self, "weather", "")) in ("rain", "storm", "snow")

    def _story_where(self, name):
        """(area_name, (gx, gy)) of a scheduled villager right now, or None."""
        hour = int(self.time.minutes) // 60
        slot = SD.schedule_slot(name, hour, wet=self._story_wet(),
                                festival=festival.is_festival_day(self.time),
                                season_idx=self.time.season_idx)
        if not slot:
            return None
        area, tile = slot
        if area == AREA_MEADOW and AREA_MEADOW not in self.world.areas:
            area, tile = SD.MEADOW_FALLBACK
        if area not in self.world.areas:
            return None
        return area, tile

    def _story_free(self, a, gx, gy):
        if not (1 <= gx < a.w - 1 and 1 <= gy < a.h - 1):
            return False
        if a.is_solid(gx, gy):
            return False
        for w in a.warps:
            if abs(w["gx"] - gx) + abs(w["gy"] - gy) <= 1:
                return False
        return True

    def _story_spot(self, a, tile):
        """Nearest walkable tile to ``tile`` in area ``a`` (spiral search).
        ``tile`` None = the area's centre. Cached per area object."""
        key = (id(a), tile)
        c = self._story_spot_cache.get(key)
        if c is not None:
            return c
        if tile is None:
            tile = (a.w // 2, a.h // 2)
        tx, ty = tile
        best = None
        for r in range(0, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    if self._story_free(a, tx + dx, ty + dy):
                        best = (tx + dx, ty + dy)
                        break
                if best:
                    break
            if best:
                break
        best = best or (tx, ty)
        self._story_spot_cache[key] = best
        return best

    def _story_now_where(self, name):
        """Human label of where a villager is right now (journal hint)."""
        if name in SD.SCHEDULES:
            w = self._story_where(name)
            return w[0].replace("_", " ").title() if w else "Home (resting)"
        for a in self.world.areas.values():
            if any(n == name for n, *_ in getattr(a, "npc_spawns", ())):
                return a.name.title()
        return "?"

    def _story_event_level(self, npc):
        """Lowest unseen heart-event level this villager is ready for, or None."""
        evs = SD.events_for(npc.name)
        hc = npc.heart_count
        for lv in SD.EVENT_LEVELS:
            if lv in evs and hc >= lv and f"{npc.name}|{lv}" not in self.story_seen_events:
                return lv
        return None

    def _story_refresh_flags(self):
        for n in self.npcs:
            n.game = self
            n.event_ready = self._story_event_level(n) is not None

    # ================================================================ villagers
    def _on_area_enter_story_villagers(self):
        area = self.world.area
        self._story_spot_cache = {}
        present = {n.name for n in self.npcs}
        for name in SD.NEW_VILLAGERS:
            if name in present:
                continue
            where = self._story_where(name)
            if where and where[0] == area.name:
                gx, gy = self._story_spot(area, where[1])
                self.npcs.append(NPC(name, gx, gy, friend=self.world.friend))
        self._story_hour = int(self.time.minutes) // 60
        self._story_refresh_flags()
        self._story_board_hint_t = None
        if area.name == AREA_TOWN and getattr(self, "started", True):
            if not self.story_intro:
                self.story_intro = True
                self._story_intro_toast()
                # one card at a time: the board hint follows once this one fades
                if not self.story_board_intro:
                    self._story_board_hint_t = 7.0
            elif not self.story_board_intro:
                self._story_board_hint_t = 3.0       # after the area title card

    def _story_intro_toast(self):
        """First town visit. A fresh farm meets the whole town at once (every
        Friends card still reads 'Not met yet'); only a save from before the new
        villagers existed gets the 'moved in' news."""
        from ..settings import JOURNAL_KEY
        from ..ui import key_label
        jk = key_label(JOURNAL_KEY)
        if self.story_newcomers:
            self.toast("New faces in the valley!",
                       f"Fah, Grandpa Somchai, Kai and Luna have moved in. "
                       f"See Journal ({jk}) > Friends", color=(255, 180, 200), seconds=6.0)
        else:
            self.toast("Meet the neighbours!",
                       f"Say hi to everyone in town. New friends appear in "
                       f"Journal ({jk}) > Friends", color=(255, 180, 200), seconds=6.0)

    def _story_board_hint(self):
        self.story_board_intro = True
        self._story_board_hint_t = None
        self.toast("The Restoration Board is up!",
                   "Bring goods to the board in the town square to restore the valley",
                   icon="twin_locket", color=(255, 214, 140), seconds=6.0)

    def _story_replan(self):
        """Hourly: villagers stroll to their next spot, arrive from / leave via
        the nearest warp when their schedule changes area."""
        area = self.world.area
        by_name = {n.name: n for n in self.npcs}
        for name in SD.NEW_VILLAGERS:
            where = self._story_where(name)
            npc = by_name.get(name)
            here = bool(where and where[0] == area.name)
            if here:
                gx, gy = self._story_spot(area, where[1])
                tx, ty = gx * TILE + TILE / 2, gy * TILE + TILE / 2
                if npc is None:
                    sx, sy = self._story_entry(area, gx, gy)
                    npc = NPC(name, int(sx // TILE), int(sy // TILE), friend=self.world.friend)
                    npc.x, npc.y = sx, sy
                    npc.game = self
                    npc.walk_to(tx, ty)
                    self.npcs.append(npc)
                elif abs(npc.home[0] - tx) + abs(npc.home[1] - ty) > TILE:
                    npc.walk_to(tx, ty)
            elif npc is not None and not npc.leaving:
                ex, ey = self._story_entry(area, int(npc.x // TILE), int(npc.y // TILE),
                                           dest=where[0] if where else None)
                npc.walk_to(ex, ey, leaving=True)
        self._story_refresh_flags()

    def _story_entry(self, area, gx, gy, dest=None):
        """World px of the warp tile nearest (gx, gy) -- where villagers come
        and go (preferring a warp that leads to ``dest``, else towards the farm
        hub). Falls back to the tile itself when the area has no warps."""
        best, bd = None, 1e9
        ws = [w for w in area.warps if dest and w.get("to") == dest]
        if not ws and dest:
            ws = [w for w in area.warps if w.get("to") == "farm"]
        ws = ws or area.warps
        for w in ws:
            d = abs(w["gx"] - gx) + abs(w["gy"] - gy)
            if d < bd:
                bd, best = d, w
        if best is None:
            return gx * TILE + TILE / 2, gy * TILE + TILE / 2
        # one tile inside the map from the warp edge
        wx, wy = best["gx"], best["gy"]
        wx = min(max(wx, 1), area.w - 2)
        wy = min(max(wy, 1), area.h - 2)
        return wx * TILE + TILE / 2, wy * TILE + TILE / 2

    def _on_update_story_villagers(self, dt):
        hour = int(self.time.minutes) // 60
        if hour != self._story_hour:
            self._story_hour = hour
            self._story_replan()
        bt = self._story_board_hint_t
        if bt is not None:
            if self.story_board_intro or self.world.current != AREA_TOWN:
                self._story_board_hint_t = None
            elif bt - dt <= 0:
                self._story_board_hint()
            else:
                self._story_board_hint_t = bt - dt
        self._story_flag_t = getattr(self, "_story_flag_t", 0.0) + dt
        if self._story_flag_t > 1.0:                 # cheap: <= ~8 villagers
            self._story_flag_t = 0.0
            for n in self.npcs:                      # birthday sparkle aura
                if self._story_is_birthday(n.name):
                    self.parts.confetti(n.x + random.uniform(-10, 10), n.y - 44, n=3)
            for n in self.npcs:
                was = getattr(n, "event_ready", False)
                n.game = self
                n.event_ready = self._story_event_level(n) is not None
                if n.event_ready and not was:
                    self.parts.heart_burst(n.x, n.y - 24, n=8)
                    self.ui.log(f"{SD.display(n.name)} seems to want to tell you something...")
        if any(getattr(n, "gone", False) for n in self.npcs):
            for n in self.npcs:
                if getattr(n, "gone", False):
                    self.parts.sparkle(n.x, n.y - 8, n=4, color=(230, 230, 240))
            self.npcs = [n for n in self.npcs if not getattr(n, "gone", False)]

    # ---- name tags over villagers the players are close to ----
    def _draw_world_story_names(self):
        if not self.npcs:
            return
        cam = self.cam
        for n in self.npcs:
            near = any(abs(p.x - n.x) + abs(p.y - n.y) < TILE * 2.6 for p in self.players)
            if not near:
                continue
            tag = ART.name_tag(self.ui.tiny, SD.display(n.name))
            y = n.y - cam.y - 62
            if n.event_ready or n.heart_count > 0:
                y -= 6
            self.screen.blit(tag, (int(n.x - cam.x - tag.get_width() / 2), int(y)))
            if self._story_is_birthday(n.name):
                bx = int(n.x - cam.x + tag.get_width() / 2 + 2)
                by = int(y)
                pygame.draw.rect(self.screen, (236, 110, 140), (bx, by + 4, 10, 8))
                pygame.draw.rect(self.screen, (255, 230, 120), (bx + 4, by + 4, 2, 8))
                pygame.draw.rect(self.screen, (255, 230, 120), (bx, by + 7, 10, 2))

    # ---- rainy days: villagers outdoors carry a little umbrella ----
    _INDOOR = ("home", "temple", "coop", "mine")

    def _draw_world_story_umbrellas(self):
        if not self.npcs or str(getattr(self, "weather", "")) not in ("rain", "storm"):
            return
        if self.world.current in self._INDOOR:
            return
        cam = self.cam
        for n in self.npcs:
            if n.name == "Somchai":          # he loves the rain. No umbrella. Ever.
                continue
            spr = ART.umbrella(NPC_DATA.get(n.name, {}).get("color", (200, 170, 220)))
            sway = int(math.sin(self.anim_t * 2 + n.x * 0.01) * 1.5)
            self.screen.blit(spr, (int(n.x - cam.x - 18 + sway), int(n.y - cam.y - 62)))

    # ---- villagers' work props (Luna's easel, Kai's anvil...) at their spot ----
    _PROP_AREAS = {"Kai": ("town", "forest"), "Fah": ("town",), "Somchai": ("beach",)}

    def _world_sprites_story_props(self):
        out = []
        if not self.npcs or festival.is_festival_day(self.time):
            return out                       # festival: everyone's off work
        cam = self.cam
        cur = self.world.current
        for n in self.npcs:
            fn = ART.VILLAGER_PROPS.get(n.name)
            if fn is None or n.target is not None or n.leaving:
                continue
            ok_areas = self._PROP_AREAS.get(n.name)
            if ok_areas and cur not in ok_areas:
                continue
            spr = fn()
            hx, hy = n.home
            x = hx + TILE * 0.55
            base = hy + TILE * 0.35
            out.append((base, spr, (x - cam.x, base - spr.get_height() - cam.y)))
        return out

    # ---- a portrait card beside the dialogue box when a villager speaks ----
    def _draw_hud_story_portrait(self):
        """Hands the speaking villager's portrait + heart row to UI.draw_dialogue,
        which draws the card beside the parchment box at the box's own height
        (so card and box always match).  Cleared when nobody we know speaks."""
        ui = self.ui
        if self.state != "dialogue":
            ui.dialogue_portrait = None
            return
        txt = str(getattr(self, "dialogue_text", ""))
        name = next((n for n in VILLAGER_ORDER
                     if txt.startswith(SD.display(n) + ":") or txt.startswith(n + " ")
                     or txt.startswith(n + ":")), None)
        if name is None:
            ui.dialogue_portrait = None
            return
        por = self._story_bust(name)
        hc = min(10, int(self.world.friend.get(name, 0) or 0) // HEART_PTS)
        cache = self.__dict__.setdefault("_story_heart_rows", {})
        row = cache.get(hc)
        if row is None:
            row = cache[hc] = pygame.Surface((10 * 10 - 1, 9), pygame.SRCALPHA)
            for i in range(10):
                row.blit(ART.heart_icon(9, i < hc), (i * 10, 0))
        ui.dialogue_portrait = {"text": txt, "portrait": por, "hearts": row}

    _BUST_ROWS, _BUST_COLS, _BUST_SCALE = 32, 31, 2.5

    def _story_bust(self, name):
        """Fixed-size head-and-shoulders portrait for the dialogue card: the
        sprite's front frame cropped from its own top (hair / bun / bald head
        alike) so every villager is framed the same way.  Cached."""
        cache = self.__dict__.setdefault("_story_busts", {})
        s = cache.get(name)
        if s is None:
            fr = npc_frames(name)["down"][0]
            r = fr.get_bounding_rect()
            rows, cols, k = self._BUST_ROWS, self._BUST_COLS, self._BUST_SCALE
            crop = pygame.Surface((cols, rows), pygame.SRCALPHA)
            crop.blit(fr, (0, 0), pygame.Rect(r.centerx - cols // 2, r.y, cols, rows))
            s = cache[name] = pygame.transform.scale(crop, (int(cols * k), int(rows * k)))
        return s

    # ================================================================ interaction
    def _story_npc_near(self, p):
        for npc in self.npcs:
            if abs(npc.x - p.x) < TILE * 1.1 and abs(npc.y - p.y) < TILE * 1.1:
                return npc
        return None

    def _interact_early_40_story_npc(self, idx, p):
        npc = self._story_npc_near(p)
        if npc is None:
            return False
        npc.game = self
        self._story_talker = idx
        if hasattr(npc, "face"):
            npc.face(p.x, p.y)
        entry = p.inv.selected_entry() if p.inv else None
        gifting = bool(entry and entry[0] == "item" and not str(entry[1]).startswith("seed:"))
        if gifting:
            if f"{npc.name}|{idx}" in self.story_gifted_today:
                self.dialogue_text = (f"{SD.display(npc.name)}: You already gave me something "
                                      f"today, {p.name}. Come see me tomorrow!")
                self.state = "dialogue"
                self.audio.play("ui_move")
                return True
            return False                      # Core gives the gift -> npc.give_gift
        lv = self._story_event_level(npc)
        if lv is not None:
            self._story_start_event(npc, lv, idx)
            return True
        # both farmers chatting with the same villager within a few seconds ->
        # a special "you two" line (+ a little heart pop)
        last = self.__dict__.setdefault("_story_last_talk", {})
        now = self.anim_t
        other = last.get((npc.name, 1 - idx))
        last[(npc.name, idx)] = now
        if other is not None and now - other <= 6.0 and len(self.players) > 1:
            npc.couple_line = True
            last.pop((npc.name, 1 - idx), None)
            self.parts.heart_burst(npc.x, npc.y - 30, n=10)
        if npc.name == "Luang Por" and npc.name not in self.story_talked_today:
            # the monk answers with a fortune (not npc.talk), so grant the daily
            # first-chat friendship here
            self.story_talked_today.add(npc.name)
            npc.hearts = npc.hearts + 5
        return False                           # Core talks (npc.talk) / monk fortune

    def _story_after_gift(self, npc, item, taste, bday):
        """Called from NPC.give_gift: bookkeeping + juice. Returns extra text."""
        idx = self._story_talker
        self.story_gifted_today.add(f"{npc.name}|{idx}")
        npc.react = [taste, 2.2]
        extra = ""
        if taste == "love":
            new = f"{npc.name}|{item}" not in self.story_known_loves
            self.story_known_loves.add(f"{npc.name}|{item}")
            self.parts.heart_burst(npc.x, npc.y - 20, n=14)
            self.audio.play("gift")
            if new:
                self.toast(f"{SD.display(npc.name)} loves {self._story_label(item)}!",
                           "Noted in the Friends journal", icon=item, color=(255, 160, 190))
        elif taste == "like":
            self.parts.heart_float(npc.x, npc.y - 24)
            self.audio.play("gift")
        elif taste == "dislike":
            self.parts.sparkle(npc.x, npc.y - 20, n=6, color=(150, 140, 160))
        if bday:
            key = f"{npc.name}|{self.time.year}"
            if key not in self.story_bday_gifts:
                self.story_bday_gifts.add(key)
                self.toast(f"Happy birthday, {SD.display(npc.name)}!",
                           "Birthday gift: friendship x4", icon=item, color=(255, 200, 120),
                           seconds=4.5)
                for _ in range(3):
                    self.parts.confetti(npc.x + random.uniform(-20, 20), npc.y - 40, n=8)
                extra = " -- a birthday gift! They're overjoyed!"
        if self._story_event_level(npc) is not None and not npc.event_ready:
            npc.event_ready = True
            self.ui.log(f"{SD.display(npc.name)} seems to want to tell you something...")
        return extra

    def _story_label(self, item):
        from .. import quests
        try:
            if item.startswith("seed:"):
                return item[5:].replace("_", " ").title() + " Seeds"
            from ..cooking import FOODS
            if item in FOODS:
                return FOODS[item]["label"]
            from ..fishing import FISH_DATA
            if item in FISH_DATA:
                return FISH_DATA[item][0]
            return quests.label(item)
        except Exception:
            return item.replace("_", " ").title()

    # ================================================================ heart events
    def _story_start_event(self, npc, lv, idx):
        ev = SD.events_for(npc.name).get(lv)
        if not ev:
            return
        p = self.players[idx]
        q = self.players[1 - idx] if len(self.players) > 1 else p
        pages = [(sp, txt.replace("{p}", p.name).replace("{q}", q.name))
                 for sp, txt in ev["pages"]]
        self._he = {"name": npc.name, "level": lv, "title": ev.get("title", "Memory"),
                    "bg": tuple(ev.get("bg", (220, 190, 220))), "pages": pages, "i": 0,
                    "chars": 0.0, "reward": ev.get("reward", {}), "idx": idx, "t": 0.0,
                    "frames": npc.frames}
        self._he_hearts = []
        self.state = "heart_event"
        self.audio.play("page")
        self.audio.play("ui_select")

    def _story_replay(self, name):
        """Journal > Friends: re-watch a heart event already seen ("Memories").
        No rewards; cycles through that villager's memories on each press and
        returns to the journal afterwards."""
        seen = [lv for lv in SD.EVENT_LEVELS if f"{name}|{lv}" in self.story_seen_events
                and lv in SD.events_for(name)]
        if not seen:
            self.audio.play("ui_move")
            return False
        cyc = self.__dict__.setdefault("_story_replay_i", {})
        i = cyc.get(name, -1) + 1
        cyc[name] = i
        lv = seen[i % len(seen)]
        ev = SD.events_for(name)[lv]
        p, q = self.players[0], self.players[-1]
        pages = [(sp, txt.replace("{p}", p.name).replace("{q}", q.name))
                 for sp, txt in ev["pages"]]
        self._he = {"name": name, "level": lv, "title": ev.get("title", "Memory"),
                    "bg": tuple(ev.get("bg", (220, 190, 220))), "pages": pages, "i": 0,
                    "chars": 0.0, "reward": {}, "idx": 0, "t": 0.0,
                    "frames": npc_frames(name), "replay": True,
                    "back": self.state if self.state == "journal" else "play"}
        self._he_hearts = []
        self.state = "heart_event"
        self.audio.play("page")
        return True

    def _story_finish_event(self):
        he = self._he
        self._he = None
        self.state = "play"
        if not he:
            return
        if he.get("replay"):
            self.state = he.get("back", "play")
            self.audio.play("page")
            return
        self.story_seen_events.add(f"{he['name']}|{he['level']}")
        idx = he.get("idx", 0)
        p = self.players[idx] if idx < len(self.players) else self.players[0]
        rw = he.get("reward") or {}
        gold = int(rw.get("gold", 0))
        got = []
        for item, qty in rw.get("items", []):
            if SD.item_exists(item):
                p.inv.add(item, qty)
                got.append(f"{self._story_label(item)} x{qty}")
            else:
                gold += 60 * qty                      # graceful fallback
        self.gold += gold
        bits = ([f"+{gold}g"] if gold else []) + got
        first = next((it for it, _ in rw.get("items", []) if SD.item_exists(it)), None)
        self.toast(f"{SD.display(he['name'])}: {he['title']}",
                   ", ".join(bits) or "A cherished memory", icon=first,
                   color=(255, 170, 200), seconds=4.5)
        self.ui.log(f"Heart event with {SD.display(he['name'])} -- {', '.join(bits)}")
        self.audio.play("achievement")
        for n in self.npcs:
            if n.name == he["name"]:
                self.parts.heart_burst(n.x, n.y - 20, n=20)
                self._popup(n.x, n.y - 30, f"{he['level']} hearts!", (255, 170, 200))
        self._popup(p.x, p.y - 20, f"+{gold}g" if gold else "Memory!", (255, 220, 120))
        self._story_refresh_flags()

    def _story_is_action(self, key):
        return key in (P1_KEYS["action"], P2_KEYS["action"], pygame.K_SPACE, pygame.K_RETURN)

    def _state_event_heart_event(self, e):
        he = self._he
        if he is None:
            if e.type == pygame.KEYDOWN:
                self.state = "play"
            return
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self._story_finish_event()
            return
        if self._story_is_action(e.key):
            txt = he["pages"][he["i"]][1]
            if he["chars"] < len(txt):
                he["chars"] = float(len(txt))
            elif he["i"] + 1 < len(he["pages"]):
                he["i"] += 1
                he["chars"] = 0.0
                self.audio.play("page")
            else:
                self._story_finish_event()

    def _state_update_heart_event(self, dt):
        he = self._he
        if he is None:
            self.state = "play"
            return
        he["t"] += dt
        he["chars"] += dt * 48
        hs = self._he_hearts
        if random.random() < dt * 2.2:
            hs.append([random.uniform(80, SCREEN_W - 80), SCREEN_H + 10,
                       random.uniform(-10, 10), random.uniform(28, 55), random.uniform(0, 6)])
        for h in hs:
            h[1] -= h[3] * dt
            h[0] += math.sin(h[4] + he["t"] * 2) * 10 * dt + h[2] * dt
        self._he_hearts = [h for h in hs if h[1] > -20][-40:]

    def _state_draw_heart_event(self):
        he = self._he
        scr = self.screen
        scr.blit(ART.dim(160), (0, 0))
        if he is None:
            return
        bg = he["bg"]
        # sized like the day report: the ribbon stays below both hotbar rows,
        # the card above the bottom player panels and right of the minimap
        pw, ph = 820, 446
        px, py = (SCREEN_W - pw) // 2, 134
        # parchment card with the event's title on the ribbon
        K.modal(scr, (px, py, pw, ph), he["title"],
                K.fit_font(he["title"], 420, (26, 24, 22, 20), bold=True))
        # the villager's favourite place as a soft backdrop + a ground shadow
        kind = ART.SCENE_OF.get(he["name"], "meadow")
        scene = ART.scene(kind, bg, 320, 236)
        scene_rect = scene.get_rect(topleft=(px + 30, py + 42))
        pygame.draw.rect(scr, K.WOOD, scene_rect.inflate(10, 10), border_radius=22)
        pygame.draw.rect(scr, K.WOOD_DK, scene_rect.inflate(10, 10), 2, border_radius=22)
        scr.blit(scene, scene_rect)
        # shadow + portrait stay inside the rounded scene frame
        old_clip = scr.get_clip()
        scr.set_clip(scene_rect.inflate(-6, -6).clip(old_clip))
        pygame.draw.ellipse(scr, _mix(bg, (60, 50, 70), 0.55),
                            (scene_rect.centerx - 90, scene_rect.bottom - 40, 180, 26))
        scr.set_clip(old_clip)
        # floating hearts drifting up over the scene (behind the portrait)
        hi = ART.heart_icon(12)
        for hx, hy, _, _, ph_ in self._he_hearts:
            if py + 8 < hy < py + ph - 20 and px + 8 < hx < px + pw - 20:
                scr.blit(hi, (int(hx), int(hy)))
        # big portrait with a gentle breathing bob
        scr.set_clip(scene_rect.inflate(-6, -6).clip(old_clip))
        por = ART.portrait(he["frames"], he["name"], 4)
        bob = int(math.sin(he["t"] * 2.2) * 4)
        scr.blit(por, (scene_rect.centerx - por.get_width() // 2,
                       scene_rect.bottom - 16 - por.get_height() + bob))
        scr.set_clip(old_clip)
        # ---- right column: who, hearts, and the memories so far ----
        f, f_s = self.ui.font, self.ui.small
        cx0 = scene_rect.right + 30
        cw = px + pw - 34 - cx0
        ccx = cx0 + cw // 2
        who = SD.display(he["name"])
        ttl = SD.VILLAGERS.get(he["name"], {}).get("title", "")
        K.blit_text(scr, K.fit_font(who, cw, (26, 24, 22, 20), bold=True), who, K.INK,
                    (ccx, py + 62))
        if ttl:
            K.blit_text(scr, K.font(16), ttl, K.INK_SOFT, (ccx, py + 90))
        lv = he["level"]
        lab = f"{lv}-heart event"
        lf = K.font(15, True)
        rw = lv * 20 - 4 + 10 + lf.size(lab)[0]
        hx = ccx - rw // 2
        for i in range(lv):
            scr.blit(ART.heart_icon(16), (hx + i * 20, py + 108))
        K.blit_text(scr, lf, lab, (54, 116, 44), (hx + lv * 20 + 6, py + 116), align="left")
        K.divider(scr, ccx, py + 140, cw // 2 - 10)
        # a little scrapbook of memories: the pages so far as quotes -- the most
        # recent ones that fit (older ones scroll off the top)
        top_y, limit = py + 154, scene_rect.bottom
        if he["i"] == 0:
            K.blit_text(scr, K.font(15), "~ a new memory begins ~", K.INK_SOFT, (ccx, top_y + 12))
        blocks = []
        for j in range(he["i"]):
            sp0, t0 = he["pages"][j]
            q = ("~ " + t0) if sp0 is None else (f"{SD.display(sp0)}: \"{t0}\"")
            blocks.append(K.wrap(f_s, q, cw - 8)[:3])
        room, keep = limit - top_y, []
        for bl in reversed(blocks):
            need = len(bl) * 19 + 8
            if need > room:
                break
            keep.insert(0, bl)
            room -= need
        yy = top_y
        for bl in keep:
            for ln in bl:
                K.blit_text(scr, f_s, ln, K.INK_SOFT, (cx0 + 4, yy + 9), align="left")
                yy += 19
            yy += 8
        # ---- the text box: a parchment well with the speaker's wooden tag ----
        sp, txt = he["pages"][he["i"]]
        box = pygame.Rect(px + 30, py + ph - 136, pw - 60, 108)
        K.well(scr, box, radius=12)
        if sp:
            speaker_tag(scr, SD.display(sp), (box.x + 22, box.y - 15))
        # typewriter text (narration in soft ink)
        shown = txt[:int(he["chars"])]
        col = K.INK if sp else K.INK_SOFT
        for i, ln in enumerate(K.wrap(f, shown, box.w - 56)[:3]):
            K.blit_text(scr, f, ln, col, (box.x + 28, box.y + 32 + i * 24), align="left")
        # page dots + the standard continue line
        n = len(he["pages"])
        for i in range(n):
            c = K.GOLD_RIM if i == he["i"] else K.WELL_LINE
            pygame.draw.circle(scr, c, (box.x + 30 + i * 14, box.bottom - 17), 4)
        if he["chars"] >= len(txt):
            from ..ui import key_label
            hint = f"{key_label(P1_KEYS['action'])} / {key_label(P2_KEYS['action'])}  -  continue"
            K.continue_hint(scr, (box.right - 26 - K.font(15, True).size(hint)[0] // 2,
                                  box.bottom - 17), he["t"], text=hint)

    # ================================================================ journal: friends
    def _journal_tab_40_story_friends(self):
        return {"title": "Friends", "draw": self._story_draw_friends,
                "key": self._story_friends_key}

    def _story_friends_key(self, key):
        n = len(VILLAGER_ORDER)
        if key in (P1_KEYS["action"], P2_KEYS["action"], pygame.K_RETURN, pygame.K_SPACE):
            name = VILLAGER_ORDER[getattr(self, "_story_fr_sel", 0) % n]
            return self._story_replay(name)
        if key in (P1_KEYS["down"], P2_KEYS["down"]):
            self._story_fr_sel = (getattr(self, "_story_fr_sel", 0) + 1) % n
            return True
        if key in (P1_KEYS["up"], P2_KEYS["up"]):
            self._story_fr_sel = (getattr(self, "_story_fr_sel", 0) - 1) % n
            return True
        return False

    def _story_draw_friends(self, surf, rect):
        rect = pygame.Rect(rect)
        f, f_s, f_t = self.ui.font, self.ui.small, self.ui.tiny
        friend = self.world.friend
        cols = 2
        cw = (rect.w - 12) // cols
        chh = min(128, (rect.h - 8) // 4)
        sel = getattr(self, "_story_fr_sel", 0) % len(VILLAGER_ORDER)
        rose = (190, 78, 112)                 # heart accents, dark enough for cream
        for i, name in enumerate(VILLAGER_ORDER):
            c, r = i % cols, i // cols
            box = pygame.Rect(rect.x + c * (cw + 12), rect.y + r * chh, cw, chh - 8)
            K.well(surf, box, hot=(i == sel), radius=10)
            pts = int(friend.get(name, 0))
            met = name in friend
            por = ART.portrait(npc_frames(name), name, 1) if met else None
            pbox = pygame.Rect(box.x + 10, box.y + 10, 56, 56)
            pygame.draw.rect(surf, (228, 206, 170), pbox, border_radius=8)
            pygame.draw.rect(surf, K.WELL_LINE, pbox, 2, border_radius=8)
            if por is not None:
                surf.blit(por, (pbox.centerx - por.get_width() // 2, pbox.y + 2),
                          area=pygame.Rect(0, 0, por.get_width(), pbox.h - 4))
            else:
                K.blit_text(surf, f, "?", K.INK_FAINT, pbox.center)
            title = SD.VILLAGERS.get(name, {}).get("title", "")
            tx = box.x + 78
            K.blit_text(surf, f, SD.display(name) if met else "???", K.INK,
                        (tx, box.y + 17), align="left")
            K.blit_text(surf, f_t, title if met else "Not met yet", K.INK_SOFT,
                        (tx, box.y + 36), align="left")
            hc = min(10, pts // HEART_PTS)
            for h in range(10):
                surf.blit(ART.heart_icon(11, h < hc), (tx + h * 13, box.y + 46))
            bd = f"Birthday: {SD.birthday_str(name)}"
            if self._story_is_birthday(name):
                bd += "  (TODAY!)"
            K.blit_text(surf, f_t, bd, K.GOLD_TXT, (tx, box.y + 68), align="left")
            now = self._story_now_where(name)
            if met:
                gifted = any(f"{name}|{i}" in self.story_gifted_today for i in range(2))
                txt = f"Now: {now}" + ("   gift given today" if gifted else "")
                K.blit_text(surf, f_t, txt, K.SPROUT, (box.right - 12, box.y + 68), align="right")
            elif now != "?":               # help a new farm find who to say hi to
                K.blit_text(surf, f_t, f"Seen near: {now}", K.INK_SOFT,
                            (box.right - 12, box.y + 68), align="right")
            loves = sorted(k.split("|", 1)[1] for k in self.story_known_loves
                           if k.split("|", 1)[0] == name)
            ly = box.y + 80
            if ly + 22 <= box.bottom:
                pygame.draw.line(surf, K.WELL_LINE, (box.x + 10, ly - 2), (box.right - 10, ly - 2), 1)
                K.blit_text(surf, f_t, "Loves:", rose, (box.x + 12, ly + 12), align="left")
                if loves:
                    from .. import assets
                    for j, it in enumerate(loves[:8]):
                        try:
                            ic = assets.item_icon(it)
                            surf.blit(pygame.transform.smoothscale(ic, (20, 20)),
                                      (box.x + 60 + j * 23, ly + 2))
                        except Exception:
                            pass
                else:
                    K.blit_text(surf, f_t, "? gift them to find out", K.INK_SOFT,
                                (box.x + 60, ly + 12), align="left")
            mem = sum(1 for lv in SD.EVENT_LEVELS if f"{name}|{lv}" in self.story_seen_events)
            if mem and box.h > 100:
                K.blit_text(surf, f_t, f"{mem} memor{'y' if mem == 1 else 'ies'}"
                            + ("  - Action: replay" if i == sel else ""), rose,
                            (box.right - 12, box.y + 36), align="right")
            nxt = next((lv for lv in SD.EVENT_LEVELS if lv in SD.events_for(name)
                        and f"{name}|{lv}" not in self.story_seen_events), None)
            if nxt is not None and box.h > 100:
                msg = (f"Heart event ready!" if hc >= nxt else f"Next event at {nxt} hearts")
                K.blit_text(surf, f_t, msg, rose if hc >= nxt else K.INK_SOFT,
                            (box.right - 12, box.y + 17), align="right")


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
