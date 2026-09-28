"""Functional home furniture -- the house pieces actually DO things.

Owner: Home (2026-09-28 "make the furniture real" pass). Plugs in through the
hook bus (systems/hooks.py); the only seam edits are one call at the top of
``ActionsMixin.interact_furniture`` / the sitting branch of ``player_action``,
the stove's ingredient counts, and the LAN client's furniture branch.

* Fridge   -> ``fridge.FridgeMenu`` (state "fridge"): door swings open (the piece
             in the room too), food-only shelves, eat straight from it. The
             Stove cooks with everything in every fridge (``_kitchen_count``).
* TV       -> ``tv.TVScreen`` (state "tv"): four channels (weather, almanac,
             cooking show, the two of you). Sitting on a seat while a TV is on,
             Action opens it without standing up. The room's TV shows the channel.
* Wardrobe / Dresser / Vanity / mirrors -> ``wardrobe.WardrobeMenu`` (state
             "wardrobe"): change hair & shirt mid-game.
* Chairs & piano benches are real seats now (furniture.SEATS); two farmers
  sitting close together get a daily "cosy together" moment.
* Clock tells the time, the window reports the weather, bookshelves / book
  stacks hold tip books, the piano plays a tune, and lamps / TV / fireplace /
  neon really light the room at night (``_lights_home``).
* LAN: the client opens these screens locally; fridge ops and outfit changes
  are sent to the host (``_net_menu_home``); seated farmers ride along in the
  snapshot (``_net_snap_out_home`` / ``_net_snap_in_home``).
"""
import random

from ..settings import TILE, MAX_ENERGY, AREA_HOME
from .. import furniture as F

_MIRRORS = {"vanity", "wall_mirror", "desk_mirror", "floor_mirror"}
_CLOTHES = {"wardrobe", "dresser"}
_BOOKS = {"bookshelf", "book_stack"}
# lights that glow at night when switched on: kind -> (lift px, radius, colour)
_GLOW = {
    "lamp": (44, 130, (255, 214, 140)), "wall_lamp": (40, 110, (255, 214, 150)),
    "desk_lamp": (30, 80, (255, 220, 160)), "neon_sign": (40, 100, (255, 120, 200)),
    "fireplace": (20, 150, (255, 150, 70)), "tv": (26, 90, (140, 180, 255)),
    "candle_small": (26, 56, (255, 200, 120)), "aquarium": (20, 70, (120, 200, 240)),
    # catalogue expansion (2026-09-28)
    "lantern": (16, 74, (255, 196, 110)), "christmas_tree": (34, 96, (255, 214, 140)),
    "string_lights": (42, 80, (255, 214, 150)), "lava_lamp": (34, 54, (255, 150, 196)),
    "laptop": (32, 44, (150, 196, 255)),
}
TIPS = [
    ("The Rain Almanac", "Rain and storms water every tilled tile for you. Check "
     "the TV's weather channel before you haul the watering can around."),
    ("Kitchen Secrets", "The Stove cooks with ingredients from BOTH bags and every "
     "fridge in the house. Stock the fridge and cook from there!"),
    ("Two Hearts, One Farm", "Send a heart emote at the same moment while standing "
     "close together for a Love Boost: energy for both and a warm regen buff."),
    ("Buff Cookery", "Some dishes grant buffs: Spicy Curry for speed, Sushi Roll for "
     "fishing, Miner's Pie for mining. Eat before a big day out."),
    ("Sprinkler Basics", "A sprinkler waters the soil around it every morning. "
     "Premium sprinklers cover the whole 3x3."),
    ("The Fisher's Log", "Legendary fish only bite in the forest pond and out at "
     "sea. Foggy mornings are lovely for a quiet cast."),
    ("Festival Calendar", "Every season holds a festival on day 14. The TV's "
     "almanac channel counts down the days."),
    ("Artisan Goods", "A Keg turns fruit into wine and honey into mead; a Preserves "
     "Jar makes jam and pickles. Artisan goods sell for far more."),
    ("Busy Bees", "Bee Houses make honey every two days. Flowers nearby turn it "
     "into pricier wildflower honey."),
    ("Home Sweet Home", "Press B inside the house to decorate. Same-colour pieces "
     "placed side by side merge into one big sofa, counter or chest."),
    ("A Good Night's Sleep", "Head to bed before 2 AM, or you'll pass out and "
     "wake up tired. Both farmers need to be home to sleep."),
    ("Quality Soil", "Quality fertilizer gives crops a chance at a double harvest; "
     "plain fertilizer makes them grow faster."),
    ("Dress Up", "Wardrobes, dressers, vanities and mirrors let you try a new "
     "hairstyle or shirt whenever you like."),
    ("Cosy Evenings", "Sit together on the sofa or at the table for a cosy "
     "moment once a day - it restores energy for both of you."),
]
# pampering pieces: kind -> (verb, energy once a day, buff kind, seconds,
# amount, buff label, toast title, toast body, toast colour)
_PAMPER = {
    "coffee_machine": ("brews a fresh espresso", 16, "speed", 240, 0.15,
                       "Caffeinated", "Espresso time!",
                       "{name} feels zippy - walking faster for a while.",
                       (214, 170, 120)),
    "bathtub": ("sinks into a bubble bath", 30, "regen", 300, 0.25,
                "Fresh & Cosy", "Bubble bath",
                "{name} comes out warm, pink and very relaxed.",
                (190, 220, 246)),
}
# a few little piano tunes (note names from audio.NOTE)
_TUNES = [("C4", "E4", "G4", "C5", "G4", "E4", "C4"),
          ("E4", "D4", "C4", "D4", "E4", "E4", "E4"),
          ("G4", "A4", "G4", "E4", "C4", "D4", "E4")]


class HomeMixin:
    """Fridge / TV / wardrobe screens, real seats and cosy house details."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_home(self):
        self.tv_channel = 0
        self.fridge_menu = None
        self.tv_screen = None
        self.wardrobe = None
        self._cosy_day = None
        try:
            from .. import isofurn
            isofurn.TV_ART = self._tv_world_art
        except Exception:
            pass

    def _on_area_enter_home(self):
        if self.world.current == AREA_HOME:       # first visit: make the home sounds
            self._home_build_sfx()

    def _on_load_home(self, d):
        resync = getattr(self, "_net_applying_world", False)
        for q in self.world.home_furniture:     # nobody left the fridge hanging open
            if q.kind == "fridge" and not resync:
                q.on = False
        fm = getattr(self, "fridge_menu", None) if resync else None
        if fm is not None:                      # the client's own open door stays open
            for q in self._fridges():
                if (q.gx, q.gy) == (fm.gx, fm.gy):
                    q.on = True
        cd = d.get("home_cosy_day")
        self._cosy_day = tuple(cd) if isinstance(cd, (list, tuple)) else None
        try:
            self.tv_channel = int(d.get("home_tv_channel", 0)) % 4
        except (TypeError, ValueError):
            self.tv_channel = 0

    def _on_save_home(self):
        cd = self._cosy_day
        return {"home_cosy_day": list(cd) if cd else None,
                "home_tv_channel": self.tv_channel}

    def _home_build_sfx(self):
        """Synthesise the home sounds OFF the startup path (like audio's soft
        tracks); until they exist every caller falls back to a stock sound."""
        a = getattr(self, "audio", None)
        a = getattr(a, "_real", None) or a      # inside an area context: the REAL audio
        if (not a or not getattr(a, "enabled", False)
                or a.sfx.get("fridge_open") is not None
                or getattr(a, "_home_sfx_busy", False)):
            return
        a._home_sfx_busy = True
        import threading
        threading.Thread(target=self._home_synth_sfx, args=(a,), daemon=True).start()

    @staticmethod
    def _home_synth_sfx(a):
        try:
            from ..audio import NOTE
        except Exception:
            NOTE = {}
        try:
            R, S = a._render, a._to_sound
            a.sfx["fridge_open"] = S(a._seq(R(0.05, [180], "square", 0.12, noise=0.5),
                                            R(0.28, [110, 220], "sine", 0.14, noise=0.25,
                                              release=0.5)))
            a.sfx["fridge_close"] = S(R(0.12, [90], "sine", 0.4, noise=0.35, sweep=-0.5,
                                        release=0.6))
            a.sfx["tv_on"] = S(a._seq(R(0.04, [60], "saw", 0.2, noise=0.7),
                                      R(0.16, [1800], "sine", 0.05, sweep=-0.2, release=0.7)))
            a.sfx["tv_off"] = S(R(0.18, [900], "sine", 0.18, sweep=-0.9, release=0.6))
            a.sfx["tv_zap"] = S(R(0.12, [400], "square", 0.08, noise=0.85, release=0.4))
            for i, tune in enumerate(_TUNES):
                if all(n in NOTE for n in tune):
                    a.sfx[f"piano_{i}"] = S(a._seq(*[R(0.16, [NOTE[n], NOTE[n] * 2], "tri",
                                                       0.26, release=0.7) for n in tune]))
        except Exception:
            pass
        finally:
            a._home_sfx_busy = False

    # ------------------------------------------------------------ helpers
    def _pidx_of(self, p):
        for i, q in enumerate(self.players):
            if q is p:
                return i
        return 0

    def _fridges(self):
        return [q for q in self.world.home_furniture if q.kind == "fridge"]

    def _kitchen_count(self, item):
        """Held by either farmer OR sitting in any fridge in the house."""
        return self._count_all(item) + sum(q.store.get(item, 0) for q in self._fridges())

    def _kitchen_remove(self, item, qty):
        """Use bag items first, then the fridge. Returns how many were taken."""
        took = self._remove_all(item, qty)
        left = qty - took
        for q in self._fridges():
            if left <= 0:
                break
            have = q.store.get(item, 0)
            t = min(have, left)
            if t > 0:
                q.store[item] = have - t
                if q.store[item] <= 0:
                    del q.store[item]
                left -= t
        return qty - left

    def _home_piece_group(self, fr):
        grp = [fr]
        if fr.kind in F.MERGE:
            grp = next((g for g in F.merge_groups(self.world.home_furniture)
                        if any(q is fr for q in g)), [fr])
        return grp

    def _home_tv_on(self):
        return next((q for q in self.world.home_furniture if q.kind == "tv" and q.on), None)

    def _home_sfx(self, name, fallback):
        a = getattr(self.audio, "_real", None) or self.audio
        ready = getattr(a, "sfx", {}).get(name) is not None
        self.audio.play(name if ready else fallback)

    def _home_toast(self, title, body, icon=None, color=(250, 226, 170)):
        t = getattr(self, "toast", None)
        if t:
            try:
                t(title, body, icon=icon, color=color)
            except Exception:
                pass

    # ------------------------------------------------------------ pampering
    def _home_pamper(self, p, fr):
        """Coffee station / bubble bath: the piece runs for a moment (steam,
        bubbles), the farmer gets a real buff, and the energy boost counts
        once per farmer per day (the buff can be topped up any time)."""
        kind = fr.kind
        verb, energy, buff, secs, amt, label, title, body, col = _PAMPER[kind]
        fr.on = True
        self._home_pamper_t = getattr(self, "_home_pamper_t", {})
        self._home_pamper_t[id(fr)] = 6.0                   # switches itself off
        t = self.time
        today = f"{t.year}-{t.season}-{t.day}"
        done = fr.data.setdefault("used", {})
        who = str(self._pidx_of(p))
        fresh = done.get(who) != today
        done[who] = today
        if fresh:
            p.energy = min(MAX_ENERGY, p.energy + energy)
        if hasattr(p, "add_buff"):
            p.add_buff(buff, secs, amt, label)
        self._home_sfx("ui_toggle", "ui_toggle")
        gain = f" (+{energy} energy)" if fresh else ""
        self._home_seat_say(p, f"{p.name} {verb}{gain} - {label}!")
        self._home_toast(title, body.format(name=p.name), color=col)

    def _on_update_home_pamper(self, dt):
        tm = getattr(self, "_home_pamper_t", None)
        if not tm:
            return
        for q in self.world.home_furniture:
            k = id(q)
            if k in tm:
                tm[k] -= dt
                if tm[k] <= 0:
                    q.on = False
                    del tm[k]

    # ------------------------------------------------------------ interact
    def _home_interact(self, p, fr):
        """Called first by interact_furniture. True = handled here."""
        kind = fr.kind
        idx = self._pidx_of(p)
        # the LAN host never pops a screen up for the remote farmer (the client
        # opens its own); fall back to the plain interaction instead
        remote = getattr(self, "net_mode", None) == "host" and idx == 1
        show = getattr(self, "_show_interact", None)      # ShowpieceMixin: easel, paintings,
        if show and show(idx, p, fr, remote):             # telescope, arcade cabinet
            return True
        if kind in _PAMPER:
            self._home_pamper(p, fr)
            return True
        if kind == "fridge" and not remote:
            self._open_fridge(idx, fr)
            return True
        if kind == "tv" and not remote:
            self._open_tv(idx, fr)
            return True
        if (kind in _CLOTHES or kind in _MIRRORS) and not remote:
            self._open_wardrobe(idx, "wardrobe" if kind in _CLOTHES else "mirror")
            return True
        if kind in _BOOKS and not remote:
            self._home_read(p, fr)
            return True
        if kind == "clock":
            self._home_clock(p)
            return True
        if kind == "window":
            self._home_window(p)
            return True
        if kind == "piano":
            if remote:
                self._home_piano(p, fr)
            else:
                self._home_play_piano(idx, p, fr)
            return True
        if kind == "record_player" and not remote:
            return bool(self._records_open(idx, fr))     # False -> plain on/off toggle
        return False

    # ------------------------------------------------------------ piano seating
    def _home_piano_by(self, sx, sy):
        """(piano, (dx, dy)) for a piano orthogonally next to seat point (sx, sy)."""
        cx, cy = int(sx), int(sy)
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            for q in self.world.home_furniture:
                if q.kind == "piano" and (cx + dx, cy + dy) in q.cells():
                    return q, (dx, dy)
        return None, None

    def _home_piano_seat(self, p):
        """The piano a SEATED farmer is sitting at: orthogonally next to the
        seat point and facing it (a sofa with its back to the keys doesn't
        count). Backless seats already swivel to face it."""
        sit = getattr(p, "sitting", None)
        if not sit:
            return None
        piano, d = self._home_piano_by(sit[1], sit[2])
        if piano is None:
            return None
        if sit[0].kind in F.SWIVEL_SEATS or (p.fx, p.fy) == d:
            return piano
        return None

    def _home_seat_hint(self, p):
        """What Action does from this seat (the sit-down log line)."""
        if self._home_piano_seat(p) is not None:
            return "action to play the piano, move to stand up"
        if self._home_tv_on() is not None:
            return "action to watch TV, move to stand up"
        return "move or press action to stand up"

    def _home_bench_for(self, piano, p=None):
        """A free seat right next to ``piano`` that faces it (piano bench
        first). With ``p``: only one within reach of where they stand, so
        using the piano from behind never hops them round it."""
        cells = set(piano.cells())
        front = ((0, 1), (-1, 0), (0, -1), (1, 0))
        best = None
        for q in self.world.home_furniture:
            if q.kind not in F.SEATS:
                continue
            fw, fh = F.footprint(q.kind, q.rot)
            spots = [(q.gx + q.ox + i + 0.5, q.gy + q.oy + j + 0.5)
                     for i in range(fw) for j in range(fh)]
            if any(getattr(pl, "sitting", None) and pl.sitting[0] is q for pl in self.players):
                continue
            for sx, sy in spots:
                cx, cy = int(sx), int(sy)
                if p is not None and ((p.x / TILE - sx) ** 2 + (p.y / TILE - sy) ** 2) > 1.7 ** 2:
                    continue
                if q.kind not in F.SWIVEL_SEATS:       # backed seats face their rot
                    f = front[q.rot % 4]
                    if (cx + f[0], cy + f[1]) not in cells:
                        continue
                if any((cx + dx, cy + dy) in cells
                       for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))):
                    rank = 0 if q.kind == "piano_bench" else 1
                    if best is None or rank < best[0]:
                        best = (rank, q)
        return best[1] if best else None

    def _home_play_piano(self, idx, p, piano, client=False):
        """Use the piano: sit down on the bench in front of it (facing the
        keys) when there is one, then open the playable piano."""
        seated = False
        if self._home_piano_seat(p) is piano:
            seated = True
        elif not client:
            bench = self._home_bench_for(piano, p)
            if bench is not None:
                self.interact_furniture(p, bench)       # sits + turns to the keys
                seated = bool(getattr(p, "sitting", None))
        self._piano_open(idx, piano, seated=seated, client=client)

    def _open_fridge(self, idx, fr, client=False):
        from .. import fridge
        fr.on = True                                  # the room's fridge opens too
        self.fridge_menu = fridge.FridgeMenu(self, idx, fr, client=client)
        self.state = "fridge"
        self._home_sfx("fridge_open", "ui_select")

    def _fridge_closed(self, menu):
        menu.fr.on = False
        self.fridge_menu = None
        if self.state == "fridge":
            self.state = "play"

    def _open_tv(self, idx, fr, client=False, from_seat=False):
        from .. import tv
        p = self.players[idx]
        if not fr.on:
            if client:                                # the host owns the real switch
                self._net_send_menu({"m": "furn", "kind": "tv", "gx": fr.gx, "gy": fr.gy,
                                     "on": True})
            else:
                from .actions_system import FURN_ACTION
                verb, gain = FURN_ACTION.get("tv", ("watch some TV", 16))
                gain = int(gain * getattr(fr, "level", 1))
                p.energy = min(MAX_ENERGY, p.energy + gain)
                self.ui.log(f"{p.name}: turns the TV ON - {verb} (+{gain} energy)")
            for q in self._home_piece_group(fr):
                q.on = True
            self._home_sfx("tv_on", "ui_toggle")
        else:
            self.audio.play("ui_select")
        self.tv_screen = tv.TVScreen(self, idx, fr, channel=self.tv_channel, client=client,
                                     from_seat=from_seat)
        self.state = "tv"

    def _tv_channel_changed(self, screen):
        self.tv_channel = screen.ch
        if screen.client:                             # the host owns the saved channel
            self._net_send_menu({"m": "tv", "ch": screen.ch})

    def _tv_closed(self, screen, power_off):
        self.tv_channel = screen.ch
        if power_off:
            fr = screen.tv
            live = next((q for q in self.world.home_furniture
                         if q.kind == "tv" and q.gx == fr.gx and q.gy == fr.gy), fr)
            if screen.client:                         # idempotent SET on the host
                self._net_send_menu({"m": "furn", "kind": "tv", "gx": live.gx, "gy": live.gy,
                                     "on": False})
            for q in self._home_piece_group(live):
                q.on = False
            if not screen.client:                     # (the host mirrors its own line)
                self.ui.log(f"{self.players[screen.pidx].name}: switches the TV off")
        self.tv_screen = None
        if self.state == "tv":
            self.state = "play"

    def _open_wardrobe(self, idx, kind, client=False):
        from .. import wardrobe
        self.wardrobe = wardrobe.WardrobeMenu(self, idx, kind, client=client)
        self.state = "wardrobe"
        self.audio.play("ui_select")

    def _wardrobe_done(self, menu, keep):
        p = self.players[menu.pidx]
        if keep and menu.look != menu.before:
            look = dict(menu.look)
            look["name"] = p.name
            p.set_appearance(look, p.name)
            try:
                self.look[menu.pidx] = dict(look)
            except Exception:
                pass
            if menu.client:
                self._net_send_menu({"m": "look", "look": look})
            self.parts.sparkle(p.x, p.y - 10, n=12, color=(255, 214, 236))
            self._home_sfx("emote_happy", "ui_select")
            self.ui.log(f"{p.name} tries on a new look. Very stylish!")
        else:
            self.audio.play("ui_move")
        self.wardrobe = None
        if self.state == "wardrobe":
            self.state = "play"

    def _home_clock(self, p):
        t = self.time
        h = int(t.minutes) // 60
        part = ("Early morning" if h < 9 else "Morning" if h < 12 else "Afternoon" if h < 17
                else "Evening" if h < 21 else "Late night" if h < 24 else "Way past bedtime")
        self.audio.play("ui_toggle")
        self.ui.log(f"{p.name} checks the clock: {t.clock_str()}  -  {part}.")
        self._home_toast(t.clock_str(), f"{t.season} {t.day}, year {t.year}  -  {part}",
                         color=(240, 226, 190))
        if h >= 23:
            self.ui.log("It's getting really late - time for bed!")

    def _home_window(self, p, energy=True):
        from .. import weather as W
        w = getattr(self, "weather", W.SUNNY)
        night = int(self.time.minutes) >= 19 * 60
        lines = {
            W.SUNNY: "Stars twinkle over the farm." if night else "Sunshine over the fields.",
            W.RAIN: "Raindrops streak down the glass.",
            W.STORM: "Lightning flickers over the hills!",
            W.FOG: "Soft fog hides the fields.",
            W.WINDY: "Petals and leaves dance past on the wind.",
            W.SNOW: "Snowflakes drift past the glass.",
        }
        self.audio.play("ui_toggle")
        if energy:
            p.energy = min(MAX_ENERGY, p.energy + 3)
        fc = getattr(self, "forecast_text", None)
        tail = f" Tomorrow looks {fc().lower()}." if fc else ""
        self.ui.log(f"{p.name} gazes out the window. {lines.get(w, '')}{tail}")

    def _home_read(self, p, fr):
        from .actions_system import FURN_ACTION
        title, body = random.choice(TIPS)
        verb, gain = FURN_ACTION.get(fr.kind, ("read a book", 10))
        gain = int(gain * getattr(fr, "level", 1))
        p.energy = min(MAX_ENERGY, p.energy + gain)
        self._home_sfx("page", "ui_select")
        self.dialogue_text = f'{p.name} pulls out "{title}" (+{gain} energy)\n\n{body}'
        self.state = "dialogue"

    def _home_piano(self, p, fr):
        from .actions_system import FURN_ACTION
        verb, gain = FURN_ACTION.get("piano", ("play a tune on the piano", 18))
        gain = int(gain * getattr(fr, "level", 1))
        p.energy = min(MAX_ENERGY, p.energy + gain)
        tunes = [k for k in list(getattr(self.audio, "sfx", {})) if k.startswith("piano_")]
        self.audio.play(random.choice(tunes) if tunes else "emote_note")
        for _ in range(5):
            self.parts.sparkle(fr.gx * TILE + TILE / 2 + random.uniform(-14, 14),
                               fr.gy * TILE + random.uniform(-10, 6), n=1,
                               color=random.choice([(255, 200, 230), (200, 220, 255),
                                                    (255, 236, 160)]))
        self.ui.log(f"{p.name}: {verb} (+{gain} energy) - la la la~")

    def _home_wall_near(self, tx, ty):
        """Facing a bare wall cell: the wall decor right beside it, so a lamp
        or window hung above a sofa / bed (floor tile blocked) is still usable.
        Pieces whose own floor tile is blocked win."""
        if ty != 0 and tx != 0:
            return None
        home = self.world.area
        cand = []
        for n in ((tx - 1, ty), (tx + 1, ty)) if ty == 0 else ((tx, ty - 1), (tx, ty + 1)):
            q = self.world.furniture_at(*n)
            if q is not None and F.CAT[q.kind]["layer"] == "wall":
                below = (n[0], n[1] + 1) if ty == 0 else (n[0] + 1, n[1])
                cand.append((0 if home.is_solid(*below) else 1, q))
        cand.sort(key=lambda c: c[0])
        return cand[0][1] if cand else None

    def _home_overlay_seat(self, p):
        """LAN host, P1 busy on a screen (TV, piano...): Player 2's Action on a
        seat still sits her down / stands her up (never opens a host screen)."""
        if self.world.current != AREA_HOME:
            return False
        st = self.state
        try:
            if getattr(p, "sitting", None):
                p.sitting = None
                self._home_seat_say(p, f"{p.name} stands up.")
                return True
            fr = self.world.furniture_at(*p.target_tile())
            if fr is None or fr.kind not in F.SEATS:
                return False
            self.interact_furniture(p, fr)
            return True
        finally:
            if self.state != st:
                self.state = st

    def _home_seat_say(self, p, text):
        """A seat line for the farmer who pressed: on the LAN host, Player 2's
        lines also go to her screen (inside her own area context the UI relay
        already forwards them)."""
        self.ui.log(text)
        if (getattr(self, "net_mode", None) == "host" and p is self.players[1]
                and getattr(self, "_ctx_view_saved", None) is None):
            self._net_toast(text)

    # ------------------------------------------------------------ seated extras
    def _home_seat_action(self, idx, p):
        """Action while seated: with a TV on in the room, watch it from the seat
        instead of standing up. True = handled (the farmer stays seated)."""
        if self.world.current != AREA_HOME:
            return False
        if getattr(self, "net_mode", None) == "host" and idx == 1:
            return False
        piano = self._home_piano_seat(p)
        if piano is not None:                         # at the piano: play it
            self._piano_open(idx, piano, seated=True)
            return True
        tvp = self._home_tv_on()
        if tvp is None:
            return False
        self._open_tv(idx, tvp, from_seat=True)
        return True

    def _on_update_home(self, dt):
        if self.world.current != AREA_HOME:
            return
        self._home_music_notes(dt)
        ps = self.players
        if len(ps) < 2 or not all(getattr(p, "sitting", None) for p in ps):
            return
        if getattr(self, "net_mode", None) == "host" and not self.partner_online():
            return                                    # a frozen, offline partner
        today = (self.time.year, self.time.season_idx, self.time.day)
        if self._cosy_day == today:
            return
        a, b = ps[0].sitting, ps[1].sitting
        if (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 > 2.3 ** 2:
            return
        self._cosy_day = today
        for p in ps:
            p.energy = min(MAX_ENERGY, p.energy + 25)
            if hasattr(p, "add_buff"):
                p.add_buff("regen", 60, 0.3, "Cosy")
        # seated farmers are drawn at their SEAT point, not where they stood
        mx = (a[1] + b[1]) / 2 * TILE
        my = (a[2] + b[2]) / 2 * TILE
        what = "TV" if self._home_tv_on() else "the room glow"
        self._home_cosy_fx(mx, my, what)
        if getattr(self, "net_mode", None) == "host":
            self._net_send_fx("cosy", x=mx, y=my, what=what)
        self.emit("love_boost", players=list(ps))

    def _home_cosy_fx(self, mx, my, what):
        hb = getattr(self.parts, "heart_burst", None)
        if hb:
            hb(mx, my, n=16)
        self._home_sfx("bell", "levelup")
        self.ui.log("Snuggled up together... cosy! +25 energy for you both <3")
        icon = None
        try:
            from .coop_system import _misc_icon
            icon = _misc_icon("heart")
        except Exception:
            pass
        self._home_toast("Cosy together", f"Sitting close, watching {what}. +25 energy each",
                         icon=icon, color=(255, 170, 200))

    def _net_fx_home(self, m):
        """LAN client: the host's cosy-together moment, shown here too."""
        if m.get("kind") != "cosy":
            return False
        try:
            x, y = float(m.get("x", 0)), float(m.get("y", 0))
        except (TypeError, ValueError):
            return True
        what = m.get("what") if m.get("what") in ("TV", "the room glow") else "the room glow"
        if self.world.current == AREA_HOME:
            self._home_cosy_fx(x, y, what)
        return True

    def _home_music_notes(self, dt):
        """A playing record player puffs out a music note now and then."""
        self._note_t = getattr(self, "_note_t", 0.0) - dt
        if self._note_t > 0:
            return
        self._note_t = random.uniform(0.7, 1.2)
        nf = getattr(self.parts, "note_float", None)
        if nf is None:
            return
        cols = ((150, 110, 220), (230, 120, 160), (90, 160, 220), (240, 170, 70))
        for q in self.world.home_furniture:
            if q.kind == "record_player" and q.on:
                # spawn on the record itself: in the iso room a particle's
                # world point is projected once, then it rises straight up
                nf(q.gx * TILE + TILE / 2, q.gy * TILE + TILE / 2,
                   color=random.choice(cols))

    def _on_client_update_home_notes(self, dt):
        if self.world.current == AREA_HOME and self.state == "play":
            self._home_music_notes(dt)

    # ------------------------------------------------------------ fridge ops
    def _fridge_op(self, pidx, fr, op, item, n=1, client=False):
        """put / take / eat for the fridge menu (and the LAN host for a client).
        Returns (ok, message)."""
        from .. import fridge as FR
        p = self.players[pidx]
        if p.inv is None:
            return False, ""
        try:
            n = max(1, int(n))
        except (TypeError, ValueError):
            n = 1
        name = FR.label(item)
        if op == "put":
            if not FR.is_fridge_food(item):
                self.audio.play("ui_move")
                return False, f"{name} doesn't belong in the fridge!"
            n = min(n, p.inv.count(item))
            if n <= 0:
                return False, ""
            p.inv.remove(item, n)
            fr.store[item] = fr.store.get(item, 0) + n
            msg = f"Put {n} {name} in the " + ("freezer" if FR.is_frozen(item) else "fridge")
            self.audio.play("ui_select")
        elif op == "take":
            n = min(n, fr.store.get(item, 0))
            if n <= 0:
                return False, ""
            fr.store[item] -= n
            if fr.store[item] <= 0:
                del fr.store[item]
            p.inv.add(item, n)
            msg = f"Took {n} {name}"
            self.audio.play("sell")
        elif op == "eat":
            info = FR.eat_info(item)
            if info is None or fr.store.get(item, 0) <= 0:
                return False, f"{name} needs cooking first."
            energy, health, verb = info
            fr.store[item] -= 1
            if fr.store[item] <= 0:
                del fr.store[item]
            if not client:
                self._home_eat(p, item, energy, health, verb)
            msg = (f"{p.name} {'drank' if verb == 'drink' else 'ate'} {name} "
                   f"(+{energy} energy" + (f", +{health} HP)" if health else ")"))
            self.audio.play("harvest")
        else:
            return False, ""
        if client:
            self._net_send_menu({"m": "fridge", "op": op, "item": item, "n": n,
                                 "gx": fr.gx, "gy": fr.gy})
        return True, msg

    def _home_eat(self, p, item, energy, health, verb):
        from .. import cooking
        p.energy = min(MAX_ENERGY, p.energy + energy)
        if health:
            p.health = min(self._max_hp(p), p.health + health)
        b = cooking.buff_of(item)
        if b and hasattr(p, "add_buff"):
            kind, amt, secs = b
            lab = cooking.BUFF_LABEL.get(kind, kind.title())
            p.add_buff(kind, secs, amt, lab)
            self.ui.log(f"{p.name}: +{lab} buff ({int(secs) // 60}:{int(secs) % 60:02d})")
        try:
            p.trigger_item_use(item, verb, 0.75)
        except Exception:
            pass
        self.parts.sparkle(p.x, p.y - 8, n=8, color=(255, 210, 150))
        from .. import fridge as FR
        self.ui.log(f"{p.name} {'drank' if verb == 'drink' else 'ate'} {FR.label(item)} "
                    f"from the fridge (+{energy} energy" + (f", +{health} HP)" if health else ")"))

    # ------------------------------------------------------------ custom states
    def _home_menu_for_state(self):
        return {"fridge": getattr(self, "fridge_menu", None),
                "tv": getattr(self, "tv_screen", None),
                "wardrobe": getattr(self, "wardrobe", None)}.get(self.state)

    def _home_state_event(self, e):
        import pygame
        m = self._home_menu_for_state()
        if m is None:
            self.state = "play"
            return
        if e.type == pygame.KEYDOWN:
            m.handle_key(e.key)

    def _home_state_update(self, dt):
        m = self._home_menu_for_state()
        if m is None:
            self.state = "play"
            return
        m.update(dt)
        if self.state == "tv" and m.phase == "live" and m.clock > 2.5:
            live = next((q for q in self.world.home_furniture
                         if q.kind == "tv" and (q.gx, q.gy) == (m.tv.gx, m.tv.gy)), None)
            if live is not None and not live.on:      # switched off on the other PC
                self.ui.log("The TV was switched off.")
                self._tv_closed(m, power_off=False)

    def _home_state_draw(self):
        m = self._home_menu_for_state()
        if m is not None:
            m.draw(self.screen)

    _state_event_fridge = _state_event_tv = _state_event_wardrobe = _home_state_event
    _state_update_fridge = _state_update_tv = _state_update_wardrobe = _home_state_update
    _state_draw_fridge = _state_draw_tv = _state_draw_wardrobe = _home_state_draw

    # ------------------------------------------------------------ world art & light
    def _tv_world_art(self, surf, quad):
        """Paint the current channel onto the room's little TV screen."""
        import pygame
        from .. import tv
        xs = [q[0] for q in quad]
        ys = [q[1] for q in quad]
        cx, cy = sum(xs) / 4, sum(ys) / 4
        w = max(xs) - min(xs)
        name = tv.CHANNELS[self.tv_channel % len(tv.CHANNELS)][0]
        base = {"weather": (96, 160, 220), "almanac": (86, 150, 96), "cooking": (220, 130, 96),
                "us": (214, 120, 160)}.get(name, (88, 148, 198))
        fl = 0.92 + 0.04 * ((pygame.time.get_ticks() // 90) % 3)
        pygame.draw.polygon(surf, tuple(min(255, int(c * fl)) for c in base), quad)
        size = int(max(8, min(18, w * 0.42)))
        ic = None
        try:
            if name == "weather":
                from .weather_system import weather_icon
                ic = weather_icon(getattr(self, "weather_tomorrow", "sunny"), size)
            elif name == "cooking":
                from .. import assets
                ic = pygame.transform.smoothscale(assets.item_icon(tv.recipe_of_day(self.time)),
                                                  (size, size))
        except Exception:
            ic = None
        if ic is not None:
            surf.blit(ic, ic.get_rect(center=(int(cx), int(cy))))
        elif name == "us":
            r = max(2, size // 5)
            pygame.draw.circle(surf, (255, 236, 244), (int(cx - r), int(cy - 1)), r)
            pygame.draw.circle(surf, (255, 236, 244), (int(cx + r), int(cy - 1)), r)
            pygame.draw.polygon(surf, (255, 236, 244), [(cx - 2 * r, cy), (cx + 2 * r, cy),
                                                        (cx, cy + 2 * r + 1)])
        else:
            pygame.draw.line(surf, (230, 244, 220), (cx - w * 0.25, cy - 2),
                             (cx + w * 0.25, cy - 2), 2)
            pygame.draw.line(surf, (230, 244, 220), (cx - w * 0.25, cy + 3),
                             (cx + w * 0.1, cy + 3), 2)

    def _lights_home(self):
        if self.world.current != AREA_HOME:
            return ()
        try:
            from .. import homeiso
            ox, oy = homeiso.origin(self.world.area)
        except Exception:
            return ()
        out = []
        cam = self.cam
        for q in self.world.home_furniture:
            g = _GLOW.get(q.kind)
            if g is None or not (q.on or q.kind == "aquarium"):
                continue
            lift, r, col = g
            fw, fh = F.footprint(q.kind, q.rot)
            sx, sy = homeiso.proj(ox, oy, q.gx + q.ox + fw / 2, q.gy + q.oy + fh / 2)
            out.append((sx + cam.x, sy - lift + cam.y, r, col))
        for q in self._fridges():                     # an open fridge spills cold light
            if q.on:
                sx, sy = homeiso.proj(ox, oy, q.gx + 0.5, q.gy + 0.5)
                out.append((sx + cam.x, sy - 30 + cam.y, 80, (200, 230, 255)))
        return out

    # ------------------------------------------------------------ LAN
    def _net_menu_home(self, mm, m):
        """Host: a client's fridge op / outfit change for Player 2."""
        if mm == "fridge":
            gx, gy = m.get("gx"), m.get("gy")
            fr = next((q for q in self._fridges() if q.gx == gx and q.gy == gy), None)
            if fr is not None:
                ok, msg = self._fridge_op(1, fr, m.get("op", ""), str(m.get("item", "")),
                                          m.get("n", 1))
                if ok and m.get("op") == "eat":
                    self._net_toast(msg)
            self._net_world_t = 99.0                  # resync the client right away
            return True
        if mm == "tv":
            try:
                self.tv_channel = int(m.get("ch", 0)) % 4
            except (TypeError, ValueError):
                pass
            self._net_world_t = 99.0
            return True
        if mm == "look":
            look = m.get("look")
            if isinstance(look, dict):
                p = self.players[1]
                new = dict(p.appearance)
                new.update({k: int(look[k]) for k in ("hair_style", "hair_color", "shirt_color")
                            if isinstance(look.get(k), int)})
                p.set_appearance(new, p.name)
                try:
                    self.look[1] = dict(new)
                except Exception:
                    pass
                self.ui.log(f"{p.name} tries on a new look!")
                self._net_world_t = 99.0
            return True
        return False

    def _home_client_interact(self, p, fr):
        """LAN client: open the home screens locally. True = handled here,
        None = let the host run the press (seats), False = not ours."""
        show = getattr(self, "_show_client_interact", None)     # ShowpieceMixin
        if show and show(p, fr):
            return True
        life = getattr(self, "_life_client_interact", None)    # HomeLifeMixin: cat,
        r = life(p, fr) if life else False                      # aquarium, plants
        if r is not False:
            return r
        if fr.kind == "fridge":
            self._open_fridge(1, fr, client=True)
            return True
        if fr.kind == "tv":
            self._open_tv(1, fr, client=True)
            return True
        if fr.kind in _CLOTHES or fr.kind in _MIRRORS:
            self._open_wardrobe(1, "wardrobe" if fr.kind in _CLOTHES else "mirror",
                                client=True)
            return True
        if fr.kind in _BOOKS:
            title, body = random.choice(TIPS)
            self._net_send_menu({"m": "furn", "kind": fr.kind, "gx": fr.gx, "gy": fr.gy})
            self.dialogue_text = f'{p.name} pulls out "{title}"\n\n{body}'
            self.state = "dialogue"
            self.audio.play("ui_select")
            return True
        if fr.kind == "clock":
            self._home_clock(p)
            return True
        if fr.kind == "window":
            self._home_window(p, energy=False)
            return True
        if fr.kind == "piano":
            self._home_play_piano(1, p, fr, client=True)
            return True
        if fr.kind == "record_player":
            return True if self._records_open(1, fr, client=True) else False
        if fr.kind in F.SEATS:
            return None
        return False

    def _home_client_seated(self):
        """LAN client pressing Action while seated. True = handled locally
        (watch the TV); False = send the press on so the host stands P2 up."""
        if self.world.current != AREA_HOME:
            return False
        piano = self._home_piano_seat(self.players[1])
        if piano is not None:
            self._piano_open(1, piano, seated=True, client=True)
            return True
        tvp = self._home_tv_on()
        if tvp is not None:
            self._open_tv(1, tvp, client=True, from_seat=True)
            return True
        return False

    def _net_snap_out_home(self):
        rows = []
        for i, p in enumerate(self.players):
            s = getattr(p, "sitting", None)
            if s:
                rows.append([i, s[0].gx, s[0].gy, round(s[1], 3), round(s[2], 3)])
        return {"SIT": rows}

    def _net_snap_in_home(self, d):
        rows = d.get("SIT")
        if rows is None:
            return
        seen = set()
        for row in rows:
            try:
                i, gx, gy, sx, sy = row
                p = self.players[int(i)]
            except Exception:
                continue
            fr = next((q for q in self.world.home_furniture
                       if q.gx == gx and q.gy == gy and q.kind in F.SEATS), None)
            if fr is not None and self.world.current == AREA_HOME:
                p.sitting = (fr, float(sx), float(sy))
                seen.add(int(i))
        for i, p in enumerate(self.players):
            if i not in seen and getattr(p, "sitting", None):
                p.sitting = None
