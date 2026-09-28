"""Player interaction & tool dispatch -- the "what happens when you press
SPACE / ENTER" wiring.

Owner: "Core & Save/Load" chat (this is cross-cutting glue).

This is the one intentionally-shared seam: ``player_action`` runs an ordered
list of interaction checks (NPC, quest board, alms box, collector, animals,
festival, shop, bed, furniture, mine ladder, harvest) and otherwise falls
through to ``use_tool``. Each branch *calls into* a domain method (owned by that
domain's chat) rather than embedding the logic here, e.g. ``self._monk_fortune``
(temple), ``self._friendship_reward`` (social), ``self._land_fish`` (fishing),
``self.sword_attack`` (combat). To add a NEW kind of interaction, add a branch
here (preserving order = priority) and put the behaviour in your own system file.
PREFERRED since 2026-09: don't edit this file at all -- define an
``_interact_early_*`` / ``_interact_late_*`` / ``_on_tool_*`` hook in your own
mixin (see systems/hooks.py); it is picked up automatically.
"""
from ..settings import (TILE, MAX_ENERGY, TOOL_ENERGY, AREA_FARM, AREA_TOWN,
                        AREA_MINE, AREA_HOME, AREA_FOREST, AREA_TEMPLE, AREA_COOP,
                        AREA_BEACH)
from ..world import GRASS, GRASS2, PATH, DIRT
from ..crops import Crop, CROPS
from ..progress import XP as SKILL_XP
from .. import loot, cooking, craft, storage, festival, quests, furniture

# Sims-style furniture interactions: kind -> (verb, energy restored)
FURN_ACTION = {
    "sofa": ("relax on the sofa", 14), "armchair": ("lounge in the armchair", 12),
    "bench": ("rest on the bench", 8), "chair": ("sit down", 6), "stool": ("perch on the stool", 5),
    "tv": ("watch some TV", 16), "bookshelf": ("read a book", 10),
    "fridge": ("grab a snack", 18), "stove": ("cook a hot meal", 30),
    "counter": ("tidy the counter", 5), "dining_table": ("eat at the table", 22),
    "bed": ("take a cozy nap", 26), "dresser": ("freshen up", 8),
    "wardrobe": ("pick an outfit", 8), "nightstand": ("check the nightstand", 4),
    "vanity": ("groom at the vanity", 10), "fireplace": ("warm up by the fire", 14),
    "plant": ("water the plant", 4), "painting": ("admire the painting", 4),
    "clock": ("check the time", 3), "lamp": ("switch the lamp", 3),
    "rug": ("straighten the rug", 3), "bin_decor": ("empty the bin", 2),
    # expansion-pack furniture (2026-06-04)
    "coffee_table": ("put your feet up", 6), "piano": ("play a tune on the piano", 18),
    "piano_bench": ("sit at the piano bench", 6),
    "desk_mirror": ("check the mirror", 4), "paper_stack": ("scribble a note", 3),
    "pen_holder": ("click a pen", 2), "photo_frame": ("smile at the photo", 6),
    "candle_small": ("watch the candle flicker", 5), "book_stack": ("flip through a book", 6),
    "vase_flowers": ("smell the flowers", 5), "fruit_bowl": ("grab a fruit", 8),
    "coffee_mug": ("sip some coffee", 10), "desk_lamp": ("switch the lamp on", 3),
    "cactus_small": ("admire the cactus", 4), "music_sheet": ("hum the melody", 5),
    "aquarium": ("watch the fish drift by", 12), "record_player": ("spin a record", 12),
    "crib": ("rock the crib gently", 6), "toy_chest": ("dig through the toys", 6),
    "sink": ("wash up at the sink", 8), "microwave": ("heat a quick snack", 14),
    "kitchen_island": ("prep food at the island", 10), "easel": ("paint at the easel", 12),
    "globe": ("spin the globe and dream", 8), "cat_tower": ("pet the napping cat", 14),
    "standing_fan": ("cool off by the fan", 10), "wall_mirror": ("check the mirror", 6),
    "neon_sign": ("bask in the neon glow", 5),
    "window": ("gaze out the window", 5), "wall_shelf": ("rearrange the shelf", 4),
    "wall_lamp": ("switch the wall lamp", 3),
}

# anniversary cabana timing (real seconds): how long a player's "ready" press stays
# valid for the other to match, and the minimum gap between anniversary-page opens.
# WINDOW is generous so the two presses don't have to be frame-perfect.
ANNIV_WINDOW = 1.5
ANNIV_COOLDOWN = 4.0


class ActionsMixin:
    """Interaction dispatch (player_action) and tool use (use_tool)."""

    def interact_furniture(self, p, fr):
        if fr.kind == "workbench":                       # functional: opens upgrades
            self.craft = craft.UpgradeMenu(self, p)
            self.state = "craft"
            self.audio.play("ui_select")
            return
        if fr.kind == "stove":                           # functional: cooking
            self.cook = cooking.CookingMenu(self, p)
            self.state = "cook"
            self.audio.play("ui_select")
            return
        if fr.kind == "fridge" and fr.on:                # open fridge: shut the door
            fr.on = False
            self.ui.log(f"{p.name}: closes the fridge")
            self.audio.play("ui_toggle")
            return
        if fr.kind in ("chest", "fridge", "toy_chest"):  # functional: item storage
            # connected same-colour chests act as ONE big chest (Minecraft
            # double chest): consolidate the group's contents into a single
            # holder piece so every member opens the same shared inventory
            grp = next((g for g in furniture.merge_groups(self.world.home_furniture)
                        if any(q is fr for q in g)), [fr])
            if len(grp) > 1:
                hold = min(grp, key=lambda q: (q.gy, q.gx))
                for q in grp:
                    if q is not hold:
                        for it, qty in list(q.store.items()):
                            hold.store[it] = hold.store.get(it, 0) + qty
                        q.store.clear()
                fr = hold
            title = {"fridge": "FRIDGE", "toy_chest": "TOY CHEST"}.get(fr.kind)
            if fr.kind == "fridge":                      # door swings open and the
                fr.on = True                             # shelves show their contents
            self.storage = storage.StorageMenu(self, p, fr, linked=len(grp),
                                               title=title)
            self.state = "storage"
            self.audio.play("ui_select")
            return
        if fr.kind in furniture.SEATS:                   # actually SIT on it
            verb, gain = FURN_ACTION.get(fr.kind, ("sit down", 6))
            gain = int(gain * getattr(fr, "level", 1))
            p.energy = min(MAX_ENERGY, p.energy + gain)
            # nearest seat spot on the piece's VISUAL footprint (includes the
            # half-tile centre-snap offset, so a snapped piano bench seats you
            # dead centre, not on a grid cell beside it)
            fw, fh = furniture.footprint(fr.kind, fr.rot)
            spots = [(fr.gx + fr.ox + i + 0.5, fr.gy + fr.oy + j + 0.5)
                     for i in range(fw) for j in range(fh)]
            sx, sy = min(spots, key=lambda s: (s[0] - p.x / TILE) ** 2
                         + (s[1] - p.y / TILE) ** 2)
            # seats with a backrest always face the way the seat points;
            # BACKLESS seats swivel toward a piano/table right beside them
            f = ((0, 1), (-1, 0), (0, -1), (1, 0))[fr.rot % 4]
            if fr.kind in furniture.SWIVEL_SEATS:
                scx, scy = int(sx), int(sy)
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    if any(q.kind in furniture.SIT_FACE
                           and (scx + dx, scy + dy) in q.cells()
                           for q in self.world.home_furniture):
                        f = (dx, dy)
                        break
            p.fx, p.fy = f                               # turn the sprite too
            # Stardew-style micro-offset: camera-facing sitters slide a touch
            # forward on the cushion; everyone else sits dead centre (nudging
            # sideways made sitters perch on edges or melt into backrests)
            nud = 0.06 if f == (0, 1) else 0.0
            p.sitting = (fr, sx, sy + nud)
            self.audio.play("ui_select")
            self.ui.log(f"{p.name}: {verb} (+{gain} energy) — move or press "
                        "action to stand up")
            return
        if fr.kind in furniture.TOGGLE:                  # power on/off
            grp = [fr]
            if fr.kind in furniture.MERGE:               # merged TVs switch as one
                grp = next((g for g in furniture.merge_groups(self.world.home_furniture)
                            if any(q is fr for q in g)), [fr])
            new = not fr.on
            for q in grp:
                q.on = new
            label = furniture.CAT[fr.kind]["label"]
            if new:
                verb, gain = FURN_ACTION.get(fr.kind, ("enjoy it", 4))
                gain = int(gain * getattr(fr, "level", 1))
                p.energy = min(MAX_ENERGY, p.energy + gain)
                self.parts.sparkle(fr.gx * TILE + TILE / 2, fr.gy * TILE + TILE / 2,
                                   n=4, color=(255, 230, 150))
                self.ui.log(f"{p.name}: turns the {label} ON — {verb} (+{gain} energy)")
                if fr.kind == "tv":                      # the weather channel
                    fc = getattr(self, "forecast_text", None)
                    if fc:
                        self.ui.log(f"Weather report: tomorrow looks {fc().lower()}.")
                        toast = getattr(self, "toast", None)
                        if toast:
                            try:
                                from .weather_system import weather_icon
                                icon = weather_icon(self.weather_tomorrow, 28)
                            except Exception:
                                icon = None
                            toast("Weather Report", f"Tomorrow: {fc()}", icon=icon,
                                  color=(170, 205, 245))
            else:
                self.ui.log(f"{p.name}: turns the {label} off")
            self.audio.play("ui_toggle")
            return
        verb, gain = FURN_ACTION.get(fr.kind, ("admire it", 3))
        gain = int(gain * getattr(fr, "level", 1))       # quality level boosts the buff
        p.energy = min(MAX_ENERGY, p.energy + gain)
        self.parts.sparkle(fr.gx * TILE + TILE / 2, fr.gy * TILE + TILE / 2,
                           n=4, color=(255, 230, 150))
        self.audio.play("ui_select")
        self.ui.log(f"{p.name}: {verb} (+{gain} energy)")

    def _aoe_cells(self, p, tool, tgx, tgy):
        """Tiles affected by a hoe/watering swing, widening with the tool tier."""
        tier = p.tool_tiers.get(tool, 0)
        w, d = {0: (1, 1), 1: (3, 1), 2: (5, 1), 3: (3, 3), 4: (5, 3)}[tier]
        fx, fy = p.fx, p.fy
        perp = (-fy, fx)
        cells = []
        for di in range(d):
            for wi in range(-(w // 2), w // 2 + 1):
                cells.append((tgx + fx * di + perp[0] * wi, tgy + fy * di + perp[1] * wi))
        return cells

    def _tool_energy(self, p, tool):
        disc = p.skills.energy_discount(tool)
        if tool == "pickaxe" and hasattr(p, "buff"):
            disc += p.buff("mining") * 0.5      # Miner's Pie: lighter swings too
        return max(1, round(TOOL_ENERGY * (1 - min(0.8, disc))))

    # ---------- anniversary cabana (hidden two-player gift) ----------
    def _near_anniv_cabana(self, p, anniv):
        # within ~2 tiles counts as "by the cabana" -- roomy enough that BOTH
        # co-op characters can stand near it at once without fighting for one tile.
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)
        return abs(pgx - anniv[0]) <= 2 and abs(pgy - anniv[1]) <= 2

    def _anniv_press(self, idx, anniv):
        """One player pressed action beside the right cabana. Record their 'ready'
        stamp; if BOTH players are ready within ANNIV_WINDOW and both are still
        standing beside the cabana, open the anniversary page once (rate-limited by
        ANNIV_COOLDOWN). A lone press instead shows the 'needs two players' nudge."""
        import time as _time
        now = _time.monotonic()
        self._anniv_ready[idx] = now
        other = 1 - idx
        cx = anniv[0] * TILE + TILE / 2
        cy = anniv[1] * TILE + TILE / 2
        both_ready = (now - self._anniv_ready[other]) <= ANNIV_WINDOW
        both_near = all(self._near_anniv_cabana(p, anniv) for p in self.players)
        if both_ready and both_near:
            if now >= self._anniv_cd:                 # not cooling down -> fire once
                self._anniv_cd = now + ANNIV_COOLDOWN
                self._anniv_ready = [0.0, 0.0]        # consume so it triggers once
                self._anniv_hint = None               # clear any lingering nudge
                self.parts.heart_burst(cx, cy - TILE * 0.5, n=20)
                self.audio.play("levelup")
                self.add_shake(3)
                self._popup(cx, cy - TILE, "Happy 4 Years!", (255, 150, 185))
                self.ui.log("Together, you open the cabana... happy anniversary! <3")
                self._open_anniversary_page()
                self._play_anniv_song()
            else:                                     # both pressed, still cooling down
                self.audio.play("ui_move")            # acknowledge quietly (no spam)
            return
        # only one player is ready -> nudge that it takes two (throttled)
        if now - self._anniv_solo_t >= 0.9:
            self._anniv_solo_t = now
            self.parts.heart_float(cx, cy - TILE * 0.35)
            self.audio.play("ui_move")
            self._anniv_hint = [cx, cy - TILE * 0.55, 1.7]   # [wx, wy, life]
            if self._near_anniv_cabana(self.players[other], anniv):
                self.ui.log("Almost! Both of you are by the cabana -- now press Space AND Enter together.")
            else:
                self.ui.log("This gift opens together -- bring your partner to the cabana too, then press together.")

    def _anniv_url(self):
        """URL for the anniversary page. Prefer a tiny localhost web server (started
        once, rooted at the game folder) so the page can reliably load photos, videos,
        music and any JavaScript -- things a bare file:// page blocks in many browsers.
        Falls back to a file:// path if the server can't start. Localhost only, so it is
        never exposed to the network."""
        import os
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "..", ".."))                  # game folder
        if getattr(self, "_anniv_httpd", None) is None:
            try:
                import functools, threading
                from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
                handler = functools.partial(SimpleHTTPRequestHandler, directory=root)
                httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)     # 0 = free port
                threading.Thread(target=httpd.serve_forever, daemon=True).start()
                self._anniv_httpd = httpd
            except Exception:
                self._anniv_httpd = None
        httpd = getattr(self, "_anniv_httpd", None)
        if httpd is not None:
            return f"http://127.0.0.1:{httpd.server_address[1]}/anniversary.html?from=game"
        path = os.path.join(root, "anniversary.html")                      # file:// fallback
        try:
            from pathlib import Path
            return Path(path).as_uri() + "?from=game"
        except Exception:
            return "file://" + path + "?from=game"

    def _write_anniv_appearance(self):
        """Export both players' CURRENT appearance to memories/appearance.js so the
        characters on the anniversary page always match the in-game outfits, whatever
        save is being played. (The page can't read savegame.json itself -- browsers
        block local file reads -- so the game hands it over via this tiny script.)"""
        import os, json
        try:
            root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "..", ".."))               # game folder
            looks = {f"p{i + 1}": dict(p.appearance)
                     for i, p in enumerate(self.players[:2])}
            path = os.path.join(root, "memories", "appearance.js")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("window.GAME_APPEARANCE = " + json.dumps(looks) + ";\n")
        except Exception:
            pass            # cosmetic only -- the page falls back to built-in outfits

    def _open_anniversary_page(self):
        """Open the anniversary page in the default browser. Resilient: a test/sandbox
        can set self._anniv_web_opener to capture the URL instead of launching a browser."""
        import webbrowser
        self._write_anniv_appearance()   # sync web characters with current outfits
        url = self._anniv_url()
        opener = getattr(self, "_anniv_web_opener", None) or webbrowser.open
        try:
            opener(url)
        except Exception:
            self.ui.log("(Could not open the anniversary page.)")

    def _play_anniv_song(self):
        """Play the anniversary song from the GAME (pygame) so it sounds the moment
        the gift opens -- browsers block audio autoplay, the game doesn't. Picks the
        first .ogg/.mp3 in memories/music/ so it keeps working if the song changes."""
        import os, glob
        here = os.path.dirname(os.path.abspath(__file__))
        mdir = os.path.abspath(os.path.join(here, "..", "..", "memories", "music"))
        for ext in ("*.ogg", "*.mp3"):
            files = sorted(glob.glob(os.path.join(mdir, ext)))
            if files:
                try:
                    self.audio.play_song(files[0])
                except Exception:
                    pass
                return

    # ---------- player action dispatch ----------
    def _bed_confirmed(self, idx, p, facing=True):
        """Two-press guard for the bed: sleeping ends the day and saves, so a
        stray press never costs a couple their day. Facing the bed in the
        evening (18:00+) sleeps at once; otherwise the first press asks and a
        second press within ~2.5 s confirms."""
        import time as _time
        tm = self.time
        if facing and getattr(tm, "minutes", 0) >= 18 * 60:
            return True
        now = _time.monotonic()
        # one pending ask PER PLAYER, so interleaved P1/P2 presses can't cancel
        # each other's confirmation
        pend = getattr(self, "_bed_ask", None)
        if not isinstance(pend, dict):
            pend = {}
        self._bed_ask = pend
        t0 = pend.get(idx)
        if t0 is not None and now - t0 <= 2.5:
            pend.clear()           # no stale ask from the partner carries over
            return True
        pend[idx] = now
        self.audio.play("ui_move")
        self.ui.log(f"{p.name}: sleep and end the day? Press again to sleep.")
        return False

    def player_action(self, idx):
        p = self.players[idx]
        area = self.world.area
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)

        # sitting? any action press just stands you back up
        if getattr(p, "sitting", None):
            p.sitting = None
            self.audio.play("ui_move")
            self.ui.log(f"{p.name} stands up.")
            return

        # 0a) fishing wins over every interaction: casting toward water, or any
        #     press while a line is out (bite / reel), must never be hijacked by
        #     a villager standing on the pier next to you
        entry = p.inv.selected_entry() if p.inv else None
        if entry == ("tool", "fishing_rod"):
            st = self.fishing.get(idx) if isinstance(self.fishing, dict) else None
            tgt = p.target_tile()
            if (st is not None and st.state != "idle") or area.is_water(*tgt):
                self.use_tool(idx, tgt)
                return

        # 0) domain hooks that must win over everything else (systems/hooks.py)
        if self._first_hook("_interact_early_", idx, p):
            return

        # 1) NPC interaction (talk / gift) — now with rewards
        for npc in self.npcs:
            if abs(npc.x - p.x) < TILE * 1.1 and abs(npc.y - p.y) < TILE * 1.1:
                entry = p.inv.selected_entry()
                if entry and entry[0] == "item" and not entry[1].startswith("seed:"):
                    before = npc.heart_count
                    msg = npc.give_gift(entry[1])
                    p.inv.remove(entry[1], 1)
                    self.parts.sparkle(npc.x, npc.y - 6, n=6, color=(235, 130, 150))
                    self.ui.log(msg)
                    self.parts.heart_float(npc.x, npc.y - 30)
                    self.audio.play("gift")
                    self.emit("gift_given", p=p, npc=npc.name, item=entry[1])
                    if npc.heart_count > before:          # crossed a heart milestone
                        self._friendship_reward(p, npc)
                elif npc.name == "Luang Por":
                    self.dialogue_text = self._monk_fortune(idx, p)
                    self.state = "dialogue"
                else:
                    self.dialogue_text = npc.talk()
                    self._talk_reward(p, npc)
                    self.state = "dialogue"
                return

        # 1b) town quest board -> accept / turn in fetch quests
        if area.name == AREA_TOWN and getattr(area, "quest_board", None):
            qb = area.quest_board
            if abs(pgx - qb[0]) <= 1 and abs(pgy - qb[1]) <= 1:
                self.quest = quests.QuestMenu(self, p)
                self.state = "quest"
                self.audio.play("ui_select")
                return

        # 1b2) temple alms box -> donate gold for merit (better fortune odds)
        if area.name == AREA_TEMPLE and getattr(area, "donation_box", None):
            db = area.donation_box
            if abs(pgx - db[0]) <= 1 and abs(pgy - db[1]) <= 1:
                self.dialogue_text = self._donate(idx, p)
                self.state = "dialogue"
                return

        # 1c0) coop auto-collector -> gather produce from ALL animals in one press
        if area.name == AREA_COOP and getattr(area, "collector", None):
            cl = area.collector
            if abs(pgx - cl[0]) <= 1 and abs(pgy - cl[1]) <= 1:
                self._collect_all_produce(idx, p)
                return

        # 1c) coop animals -> collect produce / pet
        if area.name == AREA_COOP and self.animals:
            for an in self.animals:
                if abs(an.x - p.x) < TILE * 1.1 and abs(an.y - p.y) < TILE * 1.1:
                    if an.has_produce:
                        p.inv.add(an.produce, 1)
                        an.has_produce = False
                        an.friend = min(250, an.friend + 8)
                        self.parts.sparkle(an.x, an.y - 8, n=8, color=(255, 230, 160))
                        self.audio.play("harvest")
                        self.ui.log(f"Collected {an.produce} from the {an.label}!")
                        self.emit("animal_product", p=p, item=an.produce)
                    else:
                        an.friend = min(250, an.friend + 4)
                        self.parts.sparkle(an.x, an.y - 6, n=4, color=(235, 150, 170))
                        self.parts.heart_float(an.x, an.y - 14)
                        self.ui.log(f"You pet the {an.label}.")
                        self.emit("animal_petted", p=p, animal=an.kind)
                    return

        # 1d) town festival stall (on the festival day) -> one-time seasonal reward
        if area.name == AREA_TOWN and festival.is_festival_day(self.time):
            # stall position comes from the world registry (TASK_no_hardcode);
            # `or (20, 12)` keeps old worlds working where the attr is None/absent
            fb = getattr(area, "festival_stall", None) or (20, 12)
            if abs(pgx - fb[0]) <= 1 and abs(pgy - fb[1]) <= 1:
                fk = festival.key(self.time)
                if fk in self.claimed_festivals:
                    self.dialogue_text = f"Enjoy the {festival.name(self.time.season)}!"
                    self.state = "dialogue"
                else:
                    self.claimed_festivals.add(fk)
                    gold, item, qty = festival.REWARD[self.time.season]
                    self.gold += gold
                    p.inv.add(item, qty)
                    self.parts.sparkle(fb[0] * TILE + TILE / 2, fb[1] * TILE + TILE / 2,
                                       n=16, color=(255, 220, 140))
                    self.audio.play("levelup")
                    self._popup(fb[0] * TILE + TILE / 2, fb[1] * TILE, f"+{gold}g", (255, 220, 120))
                    self.ui.log(f"{festival.name(self.time.season)}! +{gold}g and {qty} {item.title()}")
                return

        # 1e) ruined mist gate -> enter the Mist City run (both players warp; the
        # behaviour lives in MistMixin._mist_enter, called guarded so this is a
        # safe no-op flavour line until Chat 7 lands src/mistcity.
        if getattr(area, "mist_gate", None):
            mg = area.mist_gate
            if abs(pgx - mg[0]) <= 1 and abs(pgy - mg[1]) <= 1:
                f = getattr(self, "_mist_enter", None)
                if f:
                    f()
                else:
                    self.dialogue_text = ("The ruined gate hums faintly... "
                                          "but nothing happens. (yet)")
                    self.state = "dialogue"
                return

        # 1f) anniversary cabana (beach, RIGHT cabana only): a hidden two-player gift.
        # Opens the local anniversary.html, but only when BOTH players are near it and
        # press their action key together (see _anniv_press). Placed before the shop/
        # tool fall-through so it never disturbs other interactions.
        anniv = getattr(area, "anniv_cabana", None)
        if area.name == AREA_BEACH and anniv and \
                abs(pgx - anniv[0]) <= 2 and abs(pgy - anniv[1]) <= 2:
            self._anniv_press(idx, anniv)
            return

        # 2) shop tile
        if area.shop and abs(pgx - area.shop[0]) <= 1 and abs(pgy - area.shop[1]) <= 1:
            self.shop_buyer = idx                    # purchases go to whoever opened the shop
            town = area.name == AREA_TOWN
            self.shop.build(self.time.season, allow_buy=town,
                            title="General Store" if town else "Shipping Bin")
            self.audio.play("ui_select")
            self.state = "shop"
            return

        # 3) furniture inside the house (Sims-style) -- checked BEFORE the bed
        #    so wall decor / pieces hanging near the bed corner stay clickable;
        #    the bed itself falls through to the sleep branch below.
        if area.name == AREA_HOME:
            facing = self.world.furniture_at(*p.target_tile())
            fr = facing or self.world.furniture_at(pgx, pgy)
            if fr:
                if fr.kind == "bed":             # facing any bed cell (any rotation)
                    if self._bed_confirmed(idx, p, facing=facing is fr):
                        self.request_sleep(idx)
                else:
                    self.interact_furniture(p, fr)
                return

        # 3b) bed -> sleep (standing beside the bed without facing it). Sleeping
        #     ends the day AND saves, so it always asks first here, and a press
        #     with a tool in hand while looking away is a tool swing, not a nap.
        if area.bed and abs(pgx - area.bed[0]) <= 1 and abs(pgy - area.bed[1]) <= 1:
            if not (entry and entry[0] == "tool"):
                if self._bed_confirmed(idx, p, facing=False):
                    self.request_sleep(idx)
                return

        # 4) mine ladder -> go deeper
        if area.name == AREA_MINE and area.ladder and \
                abs(pgx - area.ladder[0]) <= 1 and abs(pgy - area.ladder[1]) <= 1:
            if any(getattr(m, "boss", False) for m in self.monsters):
                self.ui.log("A boss guards the way down — defeat it first!")
                self.audio.play("ui_move")
                return
            self.world.regen_mine(self.world.mine_level + 1)
            self.warp(AREA_MINE, (5, 3))
            self.ui.log(f"Descended to mine level {self.world.mine_level}!")
            self.emit("mine_depth", level=self.world.mine_level)
            return

        # 5) harvest a ready crop in front -- BUT if the pickaxe is selected, fall
        # through to use_tool so it CLEARS the tile (remove crop / un-till) instead.
        tgt = p.target_tile()
        key = (area.name, tgt[0], tgt[1])
        crop = self.world.crops.get(key)
        _sel = p.inv.selected_entry()
        _holding_pick = bool(_sel) and _sel[1] == "pickaxe"
        if crop and crop.ready_to_harvest and not _holding_pick:
            import random as _r
            name, remove = crop.harvest()
            # today's fortune can bless or spoil the harvest
            fort = self.fortune.get(idx)
            qty, note = 1, ""
            if fort == "lucky" and _r.random() < 0.5:
                qty, note = 2, " Bumper crop! (x2)"
                self._popup(tgt[0] * TILE + TILE / 2, tgt[1] * TILE, "LUCKY x2!", (255, 224, 120))
                sb = getattr(self.parts, "star_burst", None)
                if sb:
                    sb(tgt[0] * TILE + TILE / 2, tgt[1] * TILE + TILE / 3, (255, 224, 120), n=8)
            elif fort == "unlucky" and _r.random() < 0.25:
                qty, note = 0, " ...but bad luck spoiled it!"
                self._popup(tgt[0] * TILE + TILE / 2, tgt[1] * TILE, "Spoiled!", (180, 130, 210))
            if qty:
                p.inv.add(name, qty)
                self.emit("harvest", p=p, item=name, qty=qty)
            if remove:
                del self.world.crops[key]
                self.world.tilled.discard(key)
            self.parts.sparkle(tgt[0] * TILE + TILE / 2, tgt[1] * TILE + TILE / 2,
                               color=crop.data["color"])
            self.audio.play("harvest")
            self._grant_xp(p, "farming", SKILL_XP["harvest"])
            self.ui.log(f"Harvested {name}!{note}" if qty else f"The {name}{note}")
            return

        # 5b) domain hooks that sit just above the tool fallthrough
        if self._first_hook("_interact_late_", idx, p):
            return

        # 6) use selected tool / plant seed
        self.use_tool(idx, tgt)

    def use_tool(self, idx, tgt):
        p = self.players[idx]
        area = self.world.area
        entry = p.inv.selected_entry()
        if not entry:
            return
        kind, name = entry
        tgx, tgy = tgt
        key = (area.name, tgx, tgy)
        if self._first_hook("_on_tool_", idx, p, name, tgx, tgy):   # domain tool/item uses
            return

        if kind == "item":
            if cooking.is_food(name):                    # eat cooked food
                f = cooking.FOODS[name]
                p.energy = min(MAX_ENERGY, p.energy + f["energy"])
                p.health = min(self._max_hp(p), p.health + f["health"])
                p.inv.remove(name, 1)
                drink = bool(f.get("drink", name in ("milk_tea",)))
                p.trigger_item_use(name, "drink" if drink else "eat", 0.75)
                self.parts.sparkle(p.x, p.y - 8, n=8, color=(255, 210, 150))
                self.audio.play("harvest")
                verb = "drank" if drink else "ate"
                self.ui.log(f"{p.name} {verb} {f['label']} (+{f['energy']} energy)")
                return
            if name in ("sprinkler", "sprinkler2"):      # place a sprinkler on the farm
                if area.name == AREA_FARM and area.tile(tgx, tgy) in (GRASS, GRASS2, DIRT, PATH) \
                        and not area.is_solid(tgx, tgy) and (tgx, tgy) not in self.world.farm_objects:
                    self.world.farm_objects[(tgx, tgy)] = name
                    p.inv.remove(name, 1)
                    p.trigger_item_use(name, "place", 0.5)
                    self.parts.sparkle(tgx * TILE + TILE / 2, tgy * TILE + TILE / 2,
                                       n=6, color=(150, 200, 235))
                    self.audio.play("ui_select")
                    self.ui.log("Placed a premium sprinkler (waters the 3x3 around it)."
                                if name == "sprinkler2" else
                                "Placed a sprinkler (waters nearby soil each morning).")
                else:
                    self.ui.log("Place a sprinkler on open farm ground.")
                return
            if name.startswith("seed:"):
                crop_name = name.split(":", 1)[1]
                if key in self.world.tilled and key not in self.world.crops:
                    if CROPS[crop_name]["season"] == self.time.season:
                        self.world.crops[key] = Crop(crop_name)
                        p.inv.remove(name, 1)
                        p.trigger_item_use(name, "sow", 0.5)
                        self.parts.dust(tgx * TILE + TILE / 2, tgy * TILE + TILE / 2, n=4)
                        self.audio.play("plant")
                        self.emit("crop_planted", p=p, crop=crop_name)
                    else:
                        self.ui.log(f"{crop_name} can't grow in {self.time.season}.")
                else:
                    self.ui.log("Need tilled, empty soil here.")
                return
            p.trigger_item_use(name, "generic", 0.4)   # plain materials: little raise
            return
        p.energy = max(0, p.energy - self._tool_energy(p, name))
        p.trigger_swing()
        cx, cy = tgx * TILE + TILE / 2, tgy * TILE + TILE / 2

        if name == "hoe":
            tilled_any = False
            for (gx, gy) in self._aoe_cells(p, "hoe", tgx, tgy):
                k = (area.name, gx, gy)
                if area.name == AREA_FARM and area.tile(gx, gy) in (GRASS, GRASS2, DIRT, PATH) \
                        and not area.is_solid(gx, gy) and k not in self.world.tilled:
                    self.world.tilled.add(k)
                    self.parts.dust(gx * TILE + TILE / 2, gy * TILE + TILE / 2, n=4)
                    tilled_any = True
            if tilled_any:
                self.audio.play("till")         # sound + dust confirm it: no log
                self._grant_xp(p, "farming", SKILL_XP["till"])   # line (keeps tips readable)
        elif name == "watering_can":
            watered_any = False
            for (gx, gy) in self._aoe_cells(p, "watering_can", tgx, tgy):
                k = (area.name, gx, gy)
                if k in self.world.tilled:
                    self.world.watered.add(k)
                    if k in self.world.crops:
                        self.world.crops[k].watered = True
                    self.parts.splash(gx * TILE + TILE / 2, gy * TILE + TILE / 2, n=5)
                    watered_any = True
            if watered_any:
                self.audio.play("water")
                self._grant_xp(p, "farming", SKILL_XP["water"])
        elif name == "pickaxe":
            if tgt in area.rocks:
                import random as _r
                ore = area.rocks.pop(tgt)
                tier = p.tool_tiers.get("pickaxe", 0)
                p.inv.add("stone", 1 + tier // 2)
                if ore:
                    item = loot.ROCK_ORE_ITEM.get(ore)
                    # Miner's Pie ("mining" buff, e.g. +0.30) = that much more
                    # chance of a double ore drop
                    mb = p.buff("mining") if hasattr(p, "buff") else 0.0
                    qty = 1 + (1 if _r.random() < (0.18 * tier + p.skills.mining_luck + mb)
                               else 0)
                    if item:
                        p.inv.add(item, qty)
                    self._grant_xp(p, "mining", SKILL_XP["mine_ore"])
                else:
                    self._grant_xp(p, "mining", SKILL_XP["mine_rock"])
                self.parts.chips(cx, cy)
                pf = getattr(self.parts, "poof", None)
                if pf:
                    pf(cx, cy + 6, (206, 204, 214), n=5)      # a little dust cloud
                self.audio.play("mine")
                self.add_shake(2)
                self.emit("rock_broken", p=p, area=area.name)
            elif key in self.world.crops or key in self.world.tilled:
                # clear worked ground: pull up a planted crop (incl. ones that linger
                # after harvest) and/or fill hoed soil back to plain ground, so the farm
                # can be tidied or replanted.
                had_crop = self.world.crops.pop(key, None) is not None
                self.world.tilled.discard(key)
                self.world.watered.discard(key)
                if hasattr(self, "tilled_idle"):
                    self.tilled_idle.pop(key, None)
                self.parts.dust(cx, cy, n=6)
                self.audio.play("till")
                self.add_shake(1)
                self.ui.log("Pulled up the crop." if had_crop else "Filled the soil back in.")
        elif name == "axe":
            if tgt in area.trees:
                area.trees.discard(tgt)
                tier = p.tool_tiers.get("axe", 0)
                amount = 3 + tier + int(p.skills.foraging_luck * 3)
                p.inv.add("wood", amount)
                self.parts.chips(cx, cy, color=(110, 80, 50))
                pt = getattr(self.parts, "petal", None)
                if pt:                                     # leaves shake loose and drift
                    import random as _r
                    leaves = {"Spring": ((255, 196, 214), (160, 212, 128), (134, 196, 110)),
                              "Fall": ((236, 146, 76), (220, 110, 70), (246, 196, 96)),
                              "Winter": ((236, 242, 250), (214, 226, 240))}.get(
                        self.time.season, ((134, 196, 110), (160, 212, 128), (112, 176, 96)))
                    for _ in range(7):
                        pt(cx + _r.uniform(-16, 16), cy - TILE * 0.9 + _r.uniform(-10, 10),
                           _r.choice(leaves), vx=_r.uniform(-40, 40), vy=_r.uniform(-30, 10))
                self.audio.play("chop")
                self.add_shake(2)
                self._grant_xp(p, "foraging", SKILL_XP["chop"])
                self.ui.log(f"Chopped wood (+{amount}).")
                self.emit("tree_chopped", p=p, area=area.name)
        elif name == "sword":
            self.sword_attack(p)
        elif name == "fishing_rod":
            if area.is_water(tgx, tgy):
                st = self.fishing[idx]
                if st.state == "idle":
                    # today's fortune nudges the bite speed, window and rarity odds
                    eff = p.skills.fishing_skill
                    fort = self.fortune.get(idx)
                    if fort == "lucky":
                        eff += 3
                    elif fort == "unlucky":
                        eff = max(0, eff - 2)
                    water = ("pond" if area.name == AREA_FOREST
                             else "sea" if area.name == AREA_BEACH
                             else "fresh")
                    st.cast(eff, water=water)
                    # splash exactly where the bobber lands (see render_system: the
                    # bobber is drawn at p.x+fx*TILE, p.y+fy*TILE -- NOT the tile centre)
                    self.parts.splash(p.x + p.fx * TILE, p.y + p.fy * TILE)
                    self.audio.play("cast")
                else:
                    caught = st.try_hook()
                    if caught:
                        self._land_fish(p, caught, cx, cy)
                self.ui.log(st.message)
            else:
                self.ui.log("Face the water to fish.")
