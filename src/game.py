"""Main game controller: ties world, players, systems and UI together.

``Game`` is intentionally THIN. Feature logic lives in per-domain mixins under
``src/systems/`` (combat, farming, fishing, temple, social, shop, save, actions,
render) so that separate chats can edit different systems without touching this
file. This module keeps only the cross-cutting glue: construction, the main
loop, the day/area lifecycle (reset / warp / on_new_day), event dispatch and a
few shared helpers (``_grant_xp``, ``_popup``, ``add_shake``). See
``docs/ARCHITECTURE.md`` for the ownership map.
"""
import math
import random
import pygame
from .settings import (TILE, SCREEN_W, SCREEN_H, FPS, TITLE, MAX_ENERGY,
                       MAX_HEALTH, TOOL_ENERGY, P1_KEYS, P2_KEYS, BUILD_KEY,
                       AREA_FARM, AREA_TOWN, AREA_MINE, AREA_HOME, AREA_FOREST,
                       AREA_TEMPLE, AREA_COOP, AREA_BEACH)
from . import assets
from .world import (World, GRASS, GRASS2, PATH, DIRT, TILE_COLORS, WATER, FLOOR, STONE, WALL,
                    TFLOOR, TMAT)
from .timesystem import TimeSystem
from .camera import Camera
from .entities import Player, Monster
from .inventory import Inventory, TOOLS
from .crops import Crop, CROPS, shop_seeds
from . import fishing
from .fishing import FishingState, FISH
from .npc import NPC
from .ui import UI
from .particles import Particles
from .audio import Audio
from .menu import Menu
from . import furniture as F
from .build import BuildMode
from .creator import CharacterCreator
from . import savegame
from . import loot
from . import monsters as MDEF
from .progress import Skills, XP as SKILL_XP, SKILL_LABEL
from . import craft
from . import lighting
from . import quests
from . import weather
from . import cooking
from . import storage
from . import homeiso
from . import festival
from . import animals
from .animals import Animal
from .systems import (HooksMixin, SaveMixin, ActionsMixin, CombatMixin, FarmMixin,
                      FishingMixin, TempleMixin, SocialMixin, ShopMixin,
                      ShopMenu, NetMixin, RenderMixin,
                      CoopMixin, WeatherMixin, ProgressMixin, ArtisanMixin,
                      ForageMixin, StoryMixin, WorldMixin, UIMixin, AreaCtxMixin,
                      HomeMixin, PianoMixin, RecordsMixin, HomeLifeMixin)
try:
    # Mist City side-scroller mode (Chat 7 owns src/mistcity/). Optional: the
    # game must boot and run fine before that folder lands.
    from .mistcity.mist_system import MistMixin
except Exception:
    class MistMixin:
        """Inert stand-in that keeps Game's MRO stable until src/mistcity exists."""
        pass

# areas under the open sky (weather footsteps); World's meadow included by name
_OUTDOOR_AREAS = (AREA_FARM, AREA_TOWN, AREA_FOREST, AREA_BEACH, "meadow")

DEFAULT_LOOK = [
    {"name": "Player 1", "skin": 1, "hair_style": 0, "hair_color": 1, "shirt_color": 0},
    {"name": "Player 2", "skin": 3, "hair_style": 2, "hair_color": 3, "shirt_color": 1},
]


class Game(HooksMixin, SaveMixin, ActionsMixin, CombatMixin, FarmMixin, FishingMixin,
           TempleMixin, SocialMixin, ShopMixin, NetMixin, MistMixin,
           CoopMixin, WeatherMixin, ProgressMixin, ArtisanMixin, ForageMixin,
           StoryMixin, WorldMixin, UIMixin, AreaCtxMixin, HomeMixin, PianoMixin,
           RecordsMixin, HomeLifeMixin, RenderMixin):
    """The game controller. Behaviour is supplied by the system mixins above;
    only lifecycle/loop/glue lives directly on this class."""

    def __init__(self):
        pygame.init()
        try:
            pygame.display.set_caption(TITLE)
        except Exception:
            pass
        self.fullscreen = False
        self.screen = None
        self._apply_display()
        self.clock = pygame.time.Clock()
        self.running = True
        self.started = False
        self.load_failed = False   # set if a save couldn't load -> never overwrite it
        self.state = "menu"        # menu, play, shop, dialogue, sleep
        self._net_init_fields()    # net=None until a LAN host/join is started
        self.audio = Audio()
        self.look = [dict(DEFAULT_LOOK[0]), dict(DEFAULT_LOOK[1])]
        self.reset()
        self.menu = Menu(self)
        self.build = BuildMode(self)
        self.creator = CharacterCreator(self)
        # load persisted settings + game
        st = savegame.load_settings()
        if st:
            self._apply_settings(st)
        self.has_save = savegame.has_save()
        if self.has_save:
            data = savegame.load_game()
            if data:
                try:
                    self._apply_save(data)
                except Exception:
                    # A load hiccup must NEVER cost the player their progress.
                    # Keep a copy of the offending save, record why it failed, and
                    # lock saving for this session so we can't overwrite the file
                    # with a blank reset state on exit. It stays on disk to recover.
                    import traceback
                    savegame.preserve_corrupt()
                    savegame.log_error(traceback.format_exc())
                    self.load_failed = True
                    self.reset()
        notes = getattr(self, "_settings_notes", None)
        if notes:                   # reserved hotkeys cleaned out of old settings
            self._settings_notes = []
            for n in notes:
                self.ui.log(n)
            try:
                self.save_settings()
            except Exception:
                pass
        self.audio.start_music()

    def _apply_display(self):
        flags = pygame.SCALED
        if self.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        except Exception:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._apply_display()
        if getattr(self, "audio", None):
            self.save_settings()

    def begin_play(self):
        self.started = True
        self.state = "play"
        self.fade = 1.0            # the warp iris also plays when entering from the menu
        if getattr(self, "audio", None):
            self.audio.play_area(self.world.current)

    def new_game(self):
        if getattr(self, "_net_client_session", False):
            self.net_stop()        # leave the LAN session before a fresh farm
        savegame.delete_game()
        self.has_save = False
        self.load_failed = False
        self.reset()
        self.begin_play()

    def open_creator(self):
        self.creator.load(self.look)
        self.state = "create"

    def start_new(self, looks):
        if getattr(self, "_net_client_session", False):
            self.net_stop()        # leave the LAN session before a fresh farm
        savegame.delete_game()
        self.has_save = False
        self.load_failed = False
        self.look = [dict(l) for l in looks]
        self.reset()
        self.begin_play()

    # ---------- shared helpers (used across systems) ----------
    def _max_hp(self, p):
        return MAX_HEALTH + (p.skills.max_hp_bonus if getattr(p, "skills", None) else 0)

    def _popup(self, x, y, text, color=(255, 235, 150)):
        self.popups.append([x, y, text, color, 1.1])

    def _grant_xp(self, p, skill, amount):
        for sk, lv in p.skills.add_xp(skill, amount):
            self.audio.play("levelup")
            self.add_shake(4)
            self.parts.sparkle(p.x, p.y - 8, n=16, color=(180, 240, 170))
            self.ui.log(f"{p.name}: {SKILL_LABEL[sk]} Lv {lv}!")
            self._popup(p.x, p.y - 10, f"{SKILL_LABEL[sk]} Lv{lv}!", (150, 235, 150))

    def _count_all(self, item):
        """Total of an item held across BOTH players' inventories."""
        return sum(pl.inv.count(item) for pl in self.players)

    def _remove_all(self, item, qty):
        """Remove up to ``qty`` of an item, drawing from both players. Returns
        how many were actually removed. Used by quests (turn-in) and cooking."""
        left = qty
        for pl in self.players:
            if left <= 0:
                break
            take = min(left, pl.inv.count(item))
            if take > 0:
                pl.inv.remove(item, take)
                left -= take
        return qty - left

    def reset(self):
        self.world = World()
        self.time = TimeSystem()
        self.cam = Camera()
        self.ui = UI()
        self.gold = 500
        self.slept_in_bed = False
        p1 = Player(self.look[0].get("name", "Player 1"), P1_KEYS, self.look[0], 12, 12)
        p2 = Player(self.look[1].get("name", "Player 2"), P2_KEYS, self.look[1], 14, 12)
        p1.inv = Inventory()
        p2.inv = Inventory()
        self.players = [p1, p2]
        for p in self.players:                 # progression state per player
            p.skills = Skills()
            p.tool_tiers = {t: 0 for t in TOOLS}
        self.monsters = []
        self.fishing = {0: FishingState(), 1: FishingState()}
        self.fishing_banner = None      # (text, color, seconds_left) for big catches
        # daily fortune from the temple monk: per player -> "lucky" / "unlucky" / None
        self.fortune = {0: None, 1: None}
        self.fortune_read = set()        # player indices who already asked today
        self.merit = {0: 0, 1: 0}        # alms-box donations today -> better luck odds
        self.npcs = []
        self.shop = ShopMenu()
        self.shop_buyer = 0        # index of the player who opened the shop
        self.craft = None          # active workbench UpgradeMenu (state == "craft")
        self.quest = None          # active QuestMenu (state == "quest")
        self.active_quests = []    # accepted fetch quests
        self.quest_offers = [quests.generate() for _ in range(3)]
        self.npc_gifted_today = set()   # NPC names that already gave a talk-reward today
        self.cook = None           # active CookingMenu (state == "cook")
        self.storage = None        # active StorageMenu (state == "storage")
        self.inv_screen = None     # lazy InventoryScreen (state == "inventory")
        self.weather = weather.pick(self.time.season)
        self.tilled_idle = {}      # (area,gx,gy) -> mornings a tilled tile sat empty
                                   #   (farm_system._revert_idle_tilled reverts to grass)
        self.animals = []          # farm livestock (Animal)
        self.claimed_festivals = set()   # festival keys already rewarded
        self.popups = []           # floating world-space text [x, y, text, color, life]
        self.shake = 0.0           # screen-shake magnitude (px), decays each frame
        self.hurt_flash = 0.0      # red edge flash when a player is hit
        self.night = 0.0           # current night intensity (0..1) from lighting
        self.leaf_t = 0.0          # ambient leaf/mote spawn timer
        self.dialogue_text = ""
        self.sleep_timer = 0.0
        self.parts = Particles()
        self.anim_t = 0.0          # global animation clock (water/trees/crops)
        self.fade = 0.0            # warp fade overlay alpha 0..1
        self.ambient_t = 0.0       # throttles interaction sparkles
        # co-op "In-Sync": both farmers working side by side build a gentle bond
        # -> hearts drift up between them + a slow shared energy trickle (ephemeral)
        self.sync_t = 0.0          # seconds the two players have stayed close
        self.in_sync = False       # True once the bond warms up (>= 0.8s)
        self._sync_heart_t = 0.0   # throttles the drifting hearts between them
        # --- anniversary cabana: a hidden two-player gift on the beach. Opens the
        # local anniversary.html only when BOTH players "ready up" (stand beside the
        # right cabana and press their action key) within a short window. ---
        self._anniv_ready = [0.0, 0.0]  # monotonic s of each player's last ready press
        self._anniv_cd = 0.0            # monotonic s until re-open allowed (anti web-spam)
        self._anniv_solo_t = 0.0        # throttles the "needs two players" nudge
        self._anniv_hint = None         # [wx, wy, life] transient Thai on-screen prompt
        self._load_failed_hooks = []    # _on_load_* hooks that raised (save_system)
        self._load_raw = None
        self._run_hooks("_on_reset_")   # domain state (see systems/hooks.py)
        self._spawn_area_entities()

    # ---------- area entry ----------
    def _spawn_area_entities(self):
        area = self.world.area
        self.npcs = []
        self.monsters = []
        if area.name in (AREA_TOWN, AREA_TEMPLE):
            for (name, gx, gy) in area.npc_spawns:
                self.npcs.append(NPC(name, gx, gy, friend=self.world.friend))
        if area.name == AREA_MINE:
            depth = self.world.mine_level
            spawns = list(getattr(area, "monster_spawns", []))
            if depth % 5 == 0 and spawns:               # boss floor!
                bx, by = spawns[0]
                self.monsters.append(Monster(bx, by, MDEF.boss_for_depth(depth), depth))
                spawns = spawns[3:]                     # fewer minions alongside the boss
            for (gx, gy) in spawns:
                self.monsters.append(Monster(gx, gy, MDEF.spawn_name(depth), depth))
        if area.name == AREA_FOREST:
            import random as _r
            for (gx, gy) in getattr(area, "animal_spawns", []):
                self.monsters.append(Monster(gx, gy, MDEF.forest_spawn_name(_r)))
        if area.name == AREA_COOP:
            self._rehome_animals()      # tidy the livestock into the barn
        # beach crabs: decorative critters that scuttle along the tideline. Re-rolled
        # on every area entry (this runs at init + each warp), so they reset when you
        # enter the beach and clear out everywhere else. Purely cosmetic -- they don't
        # collide or deal damage, and are intentionally NOT part of the save schema.
        self.beach_critters = []
        for (gx, gy) in getattr(area, "crab_spawns", []):
            cx = gx * TILE + TILE / 2
            self.beach_critters.append({
                "x": cx, "y": gy * TILE + TILE * 0.7,
                "dir": random.choice((-1, 1)), "spd": random.uniform(14.0, 26.0),
                "flip_t": random.uniform(1.5, 3.5), "pause_t": 0.0,
                "home_x": cx, "rng": TILE * 3.0, "bob": random.uniform(0, 6.28),
            })
        # the home is an ISO room: map particle spawn points onto it (see particles)
        setp = getattr(self.parts, "set_projection", None)
        if setp:
            setp(self._iso_spawn if area.name == AREA_HOME else None)
        self._run_hooks("_on_area_enter_")

    def _iso_spawn(self, wx, wy):
        """World point -> where the iso home room draws it (screen + cam)."""
        area = self.world.area
        ox, oy = homeiso.origin(area)
        sx, sy = homeiso.proj(ox, oy, wx / TILE, wy / TILE)
        return sx + self.cam.x, sy + self.cam.y

    HOME_CAM_Y = -148              # vertical offset that drops the room below the HUD

    def _update_camera(self, area, focus=None):
        """Home is fixed & centred in the clear zone; other areas follow the players.
        ``focus`` pins the camera to one player (a partner's own area)."""
        if area.name == AREA_HOME:
            self.cam.x = -((SCREEN_W - area.w * TILE) // 2)
            self.cam.y = self.HOME_CAM_Y
        elif area.name == AREA_COOP:
            # small barn room: centre it on screen, just below the HUD
            self.cam.x = -((SCREEN_W - area.w * TILE) // 2)
            self.cam.y = -((SCREEN_H - area.h * TILE) // 2)
        else:
            # online: each machine's camera follows its own player; local co-op
            # keeps both on screen by following their midpoint.
            foc = focus if focus is not None else getattr(self, "cam_focus", None)
            who = [self.players[foc]] if foc is not None else self.players
            self.cam.update(who, area)

    def warp(self, target, spawn):
        if self.independent():
            # online: only the farmers standing in THIS area travel (a door,
            # the mine ladder); the partner elsewhere is untouched
            cur = self.world.current
            here = [i for i in range(len(self.players))
                    if self.p_area[i] == cur and self.player_here(i)] or [0]
            for k, i in enumerate(here):
                self.warp_player(i, target, spawn, beside=k > 0)
            if target == cur and self.world.current == target:
                self._spawn_area_entities()        # same area rebuilt (next mine floor)
                if 0 in here and self._ctx_depth > 0:
                    self._view_arrived()           # (at rest warp_player already did)
            return
        self.p_area = [target, target]
        if getattr(self, "audio", None):
            self.audio.stop_song()                  # end the anniversary song on leaving
        self.world.current = target
        sx, sy = spawn
        self.players[0].x = sx * TILE + TILE / 2
        self.players[0].y = sy * TILE + TILE / 2
        self.players[1].x = (sx + 1) * TILE + TILE / 2
        self.players[1].y = sy * TILE + TILE / 2
        self._spawn_area_entities()
        self.parts.items.clear()
        self.popups.clear()        # floating text belongs to the map it was made on
        self._anniv_hint = None
        self.fade = 1.0            # fade in after warp
        self.audio.play("warp")
        self.audio.play_area(target)
        self._update_camera(self.world.area)
        self.emit("warp", area=target)

    def _iris_tick(self, dt):
        """The warp iris keeps opening under dialogue / shop / journal / heart
        events too (update() -- which decays it in play -- only runs in "play";
        the LAN client decays it in _net_client_step)."""
        if self.state != "play" and self.fade > 0 and self.net_mode != "client":
            self.fade = max(0.0, self.fade - dt * 2.2)

    # ---------- main loop ----------
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            self.handle_events()
            self.step(dt)
            self.draw()
        self.net_stop()
        self._save()
        pygame.quit()

    def step(self, dt):
        """One frame of simulation (everything but input events and drawing)."""
        st_start = self.state
        if self.net_mode == "host" and self.net:
            self._net_host_ingest()          # apply P2's input before simulating
        self._iris_tick(dt)
        if self.net_mode == "client":
            self._net_client_step(dt)        # render-only: send input, apply state
        elif self.state == "play":
            self.update(dt)
        elif self.state == "menu":
            self.menu.update(dt)
            amb = getattr(self.audio, "set_ambience", None)
            if amb:
                amb(None)                    # no rain bed over the title menu
        elif self.state == "inventory" and self.inv_screen:
            self.inv_screen.update(dt)
        elif self.state == "mistcity":
            f = getattr(self, "_mist_update", None)         # MistMixin (guarded)
            if f:
                f(dt)
            amb = getattr(self.audio, "set_ambience", None)
            if amb:
                amb(None)
        else:
            self._run_state("update", dt)                   # domain custom states
        if self.net_mode == "host" and self.net:
            if self.state != "play" and st_start != "play":
                self._net_host_overlay_step(dt)   # P2's area keeps running under P1's screen
            self._net_host_broadcast(dt)     # ship snapshot to the client
        if self.independent():
            self._ctx_rest_tasks()           # sleep etc. (nobody parked here)

    # ---------- events ----------
    def handle_events(self):
        # Key-repeat: enable hold-to-scroll only in menu/overlay states (they consume
        # KEYDOWN via on_keydown / handle_event). Off during play, so actions and F11
        # fire once per physical press; player movement uses key.get_pressed() polling
        # and is unaffected either way. Only call set_repeat on a mode CHANGE -- calling
        # it every frame would keep resetting the repeat timer and repeats would never fire.
        overlay = (self.state in ("menu", "create", "shop", "dialogue", "quest",
                                  "cook", "craft", "storage", "build", "inventory")
                   or self._custom_state("event") is not None)
        want = (260, 60) if overlay else None       # (delay ms, interval ms)
        if getattr(self, "_kr", 0) != want:
            self._kr = want
            pygame.key.set_repeat(*want) if want else pygame.key.set_repeat()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif self.state == "menu":
                self.menu.handle_event(e)
            elif self.state == "create":
                self.creator.handle_event(e)
            elif self.state == "build":
                self.build.handle_event(e)
            elif self.state == "inventory" and self.inv_screen:
                # co-op screen: both players' panes live at once; the screen
                # routes P1/P2 key maps itself, so just forward everything.
                self.inv_screen.handle_event(e)
            elif self.state == "mistcity":
                f = getattr(self, "_mist_handle_event", None)   # MistMixin (guarded)
                if f:
                    f(e)
            elif self._run_state("event", e):                  # domain custom states
                pass
            elif e.type == pygame.KEYDOWN:
                if self.net_mode == "client" and self.state == "play":
                    if e.key == pygame.K_ESCAPE:
                        self.state = "menu"        # local pause; sim stays on host
                        self.audio.play("ui_move")
                    else:
                        self._client_capture_key(e.key)   # relay action/cycle to host
                else:
                    self.on_keydown(e.key)

    def on_keydown(self, key):
        # menu states route keys to their overlay object. If the object is
        # ever missing (state desync, e.g. after a LAN hiccup or load), drop
        # back to play instead of hard-crashing mid-session.
        if self.state in ("craft", "quest", "cook", "storage"):
            menu = getattr(self, self.state, None)
            if menu:
                menu.handle_key(key)
            else:
                self.state = "play"
            return
        if self.state == "sleep":
            # the "Sleeping..." banner: ESC skips ahead to the End-of-Day report
            # (it must never jump to the menu and lose the report)
            if key == pygame.K_ESCAPE:
                self.sleep_timer = 0.0
            return
        if key == pygame.K_ESCAPE:
            if self.state in ("shop", "dialogue"):
                self.state = "play"
            else:
                self._save()
                self.state = "menu"
            return
        if self.state == "dialogue":
            if key in (P1_KEYS["action"], P2_KEYS["action"]):
                self.state = "play"
            return
        if self.state == "shop":
            self.shop_input(key)
            return
        if self.state == "play":
            with self.area_ctx(self.p_area[0]):                # online: P2 elsewhere is parked
                if self._first_hook("_on_keydown_", key):    # domain hotkeys
                    return
            # a player action bound to B / I (old settings) wins over the hotkey
            bound = any(key == c for K in (P1_KEYS, P2_KEYS) for c in K.values())
            if key == BUILD_KEY and self.world.current == AREA_HOME and not bound:
                for p in self.players:          # pieces may move: everyone stands up
                    p.sitting = None
                self.state = "build"
                self.audio.play("ui_select")
                return
            if key == pygame.K_i and not bound:
                self._open_inventory()
                return
            # tool cycling (online, Player 2 is driven by the client, not this keyboard)
            for idx, K in ((0, P1_KEYS), (1, P2_KEYS)):
                if idx == 1 and self.independent():
                    continue
                if key == K["prev"]:
                    self.players[idx].inv.cycle(-1)
                elif key == K["next"]:
                    self.players[idx].inv.cycle(1)
                elif key == K["action"]:
                    with self.area_ctx(self.p_area[idx]):
                        self.player_action(idx)

    def _open_inventory(self, pi=0):
        """Open the hotbar-arrange screen (press I; I/ESC inside it closes back
        to play). The screen is UI-domain code, so it is imported lazily and
        guarded -- a broken/missing inventory_screen never crashes the game."""
        if self.inv_screen is None:
            try:
                from .inventory_screen import InventoryScreen
                self.inv_screen = InventoryScreen(self, player_index=pi)
            except Exception:
                self.ui.log("Inventory screen unavailable.")
                return
        self.inv_screen.pi = pi
        self.state = "inventory"
        self.audio.play("ui_select")

    # ---------- sleep / day transition ----------
    def do_sleep(self):
        for p in self.players:          # nobody sleeps sitting on the sofa
            p.sitting = None
        self.slept_in_bed = True
        self.audio.play("sleep")
        self.time.sleep()
        self.state = "sleep"
        self.sleep_timer = 1.4
        self.on_new_day()
        self.has_save = True
        self._save()

    def on_new_day(self):
        # advance crops
        for key, crop in list(self.world.crops.items()):
            crop.advance_day()
        self.world.watered.clear()
        # today's weather = yesterday's forecast (WeatherMixin pre-rolls it so the
        # TV / day report can show it); rain & storms water every tilled tile
        roll = getattr(self, "_roll_weather", None)
        self.weather = roll() if roll else weather.pick(self.time.season)
        if weather.waters(self.weather):
            for k in list(self.world.tilled):
                self.world.watered.add(k)
                if k in self.world.crops:
                    self.world.crops[k].watered = True
        # sprinklers water the farm each morning: basic = 4 neighbours,
        # premium ("sprinkler2") = the full 3x3 block around it
        _SPRINKLER_AREA = {
            "sprinkler": ((1, 0), (-1, 0), (0, 1), (0, -1)),
            "sprinkler2": tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                if (dx, dy) != (0, 0)),
        }
        for (sx, sy), kind in self.world.farm_objects.items():
            for dx, dy in _SPRINKLER_AREA.get(kind, ()):
                k = (AREA_FARM, sx + dx, sy + dy)
                if k in self.world.tilled:
                    self.world.watered.add(k)
                    if k in self.world.crops:
                        self.world.crops[k].watered = True
        # tilled-but-empty soil slowly reverts to grass (logic owned by farm_system).
        # Guarded so Core stays green until that chat lands _revert_idle_tilled.
        if hasattr(self, "_revert_idle_tilled"):
            self._revert_idle_tilled()
        # livestock produce fresh goods each morning
        for an in self.animals:
            an.has_produce = True
        # the forest slowly regrows: a few new trees sprout each morning (capped),
        # keeping the central hunting clearing, pond and warp tiles clear
        self._regrow_forest()
        # refresh the town quest board and let NPCs hand out gifts again
        self.quest_offers = [quests.generate() for _ in range(3)]
        self.npc_gifted_today = set()
        # yesterday's fortune fades at dawn -- visit the monk again for a new one
        self.fortune = {0: None, 1: None}
        self.fortune_read = set()
        self.merit = {0: 0, 1: 0}
        for p in self.players:
            p.energy = MAX_ENERGY if self.slept_in_bed else int(MAX_ENERGY * 0.55)
            if self.slept_in_bed:
                p.health = min(self._max_hp(p), p.health + 40)
        self._run_hooks("_on_new_day_")   # domain morning work (may read slept_in_bed)
        self._ctx_drop_others()           # online: the partner's area wakes up fresh too
        self.slept_in_bed = False
        self.emit("day_started", day=self.time.day, season=self.time.season_idx,
                  year=self.time.year)

    # ---------- update ----------
    def update(self, dt):
        prev_day = (self.time.day, self.time.season_idx)
        self.time.update(dt)
        if self.time.new_day_flag and (self.time.day, self.time.season_idx) != prev_day:
            # passed out at 2am (not via bed)
            names = " & ".join(p.name for p in self.players)
            self.on_new_day()
            self.ui.log(f"{names} stayed up too late and passed out... "
                        f"(only 55% energy - sleep in bed before 2 AM)")
            self.state = "sleep"
            self.sleep_timer = 1.4
            return
        if not self.independent():
            self.p_area = [self.world.current, self.world.current]   # local: always together
            self._update_area(dt, (0, 1), globals_=True)
            return
        # online: every area a farmer stands in runs, the host's view first
        order = [self.p_area[0]]
        if self.p_area[1] != self.p_area[0] and self.partner_online():
            order.append(self.p_area[1])          # (an offline partner waits, frozen)
        done, st0 = set(), self.state
        for k, name in enumerate(order):
            idxs = [i for i in range(len(self.players))
                    if self.p_area[i] == name and i not in done
                    and (i == 0 or self.partner_online() or not self.apart())]
            if not idxs:
                continue
            done.update(idxs)
            with self.area_ctx(name, idxs):
                self._update_area(dt, idxs, globals_=(k == 0))
            if self.state != st0:
                break                                 # a menu / sleep took over

    def partner_update(self, dt):
        """Online host: Player 1 has a screen open (journal, shop, pause menu...)
        -- Player 2's world keeps running around them."""
        with self.area_ctx(self.p_area[1], [1]):
            self._update_area(dt, [1], globals_=False)

    def _update_area(self, dt, idxs, globals_=True):
        """One frame of the CURRENT area for the farmers ``idxs``. ``globals_``:
        also tick the once-per-frame view/global bits (the first pass only)."""
        self._ctx_warped = False
        st0 = self.state
        if globals_:
            self.anim_t += dt
            if self.fade > 0:
                self.fade = max(0.0, self.fade - dt * 2.2)
            self.parts.update(dt)
            self.update_coop_bond(dt)   # co-op In-Sync closeness (hearts + energy)

            self.ambient_t += dt
            if self.ambient_t >= 0.55:
                self.ambient_t = 0.0
                acol = {"shop": (255, 220, 120), "bed": (150, 200, 235),
                        "ladder": (240, 160, 80), "talk": (235, 180, 210),
                        "quest": (140, 200, 235)}
                for gx, gy, kind in self._interactables():
                    wx = gx * TILE + TILE / 2
                    wy = gy * TILE + TILE / 2
                    if any(abs(p.x - wx) + abs(p.y - wy) < TILE * 1.7 for p in self.players):
                        self.parts.sparkle(wx, wy - TILE * 0.4, n=3, color=acol[kind])
                # the anniversary cabana always wears a gentle float of hearts so it
                # reads as 'special' next to the other cabanas (discoverability; A3).
                anniv = getattr(self.world.area, "anniv_cabana", None)
                if anniv:
                    hx = anniv[0] * TILE + TILE / 2
                    hy = anniv[1] * TILE
                    self.parts.heart_float(hx + random.uniform(-7, 7), hy - TILE * 0.15)

        pressed = pygame.key.get_pressed()
        area = self.world.area
        inputs = self._player_inputs(pressed)   # online host drives P2 from the client
        from .settings import P1_KEYS, P2_KEYS, AREA_HOME as _HOME
        prev = [(p.x, p.y) for p in self.players]
        for i in idxs:
            p = self.players[i]
            sit = getattr(p, "sitting", None)
            if sit:
                # seat sold/moved or we left the house -> quietly stand up
                fw_, fh_ = F.footprint(sit[0].kind, sit[0].rot)
                sx0, sy0 = sit[0].gx + sit[0].ox, sit[0].gy + sit[0].oy
                if (self.world.current != _HOME
                        or not any(q is sit[0] for q in self.world.home_furniture)
                        or not (sx0 <= sit[1] <= sx0 + fw_ and sy0 <= sit[2] <= sy0 + fh_)):
                    p.sitting = None
                else:
                    keys = P1_KEYS if i == 0 else P2_KEYS
                    if any(inputs[i][keys[d]] for d in ("up", "down", "left", "right")):
                        p.sitting = None        # stand up and walk away
                    else:
                        continue                # stay comfy on the seat
            p.update(dt, inputs[i], area)
            if p.emit_step:
                out = area.name in _OUTDOOR_AREAS
                wet = out and self.weather in (weather.RAIN, getattr(weather, "STORM", "storm"))
                splash = getattr(self.parts, "rain_splash", None) if wet else None
                if splash:
                    splash(p.x, p.y + 8)             # puddle-y steps in the rain
                elif out and self.weather == weather.SNOW:
                    self.parts.footstep(p.x, p.y + 6, color=(240, 244, 252))
                else:
                    self.parts.footstep(p.x, p.y + 6)
                self.audio.play("step")
        if not self.independent():
            self._leash(area, prev)             # one shared screen: nobody walks off it

        # warps: online each farmer takes their own door; local co-op moves together
        for warp in area.warps:
            for i in idxs:
                p = self.players[i]
                if int(p.x // TILE) == warp["gx"] and int(p.y // TILE) == warp["gy"]:
                    if self.independent():
                        self.warp_player(i, warp["to"], warp["spawn"])
                    else:
                        self.warp(warp["to"], warp["spawn"])
                    return

        for i in idxs:
            self.fishing[i].update(dt)

        if globals_ and self.fishing_banner:
            txt, col, t = self.fishing_banner
            t -= dt
            self.fishing_banner = (txt, col, t) if t > 0 else None

        for npc in self.npcs:
            npc.update(dt, area)

        if area.name == AREA_COOP:
            for an in self.animals:
                an.update(dt, area)

        here = [self.players[i] for i in idxs]
        for m in self.monsters:
            m.update(dt, here, area)
        self.monsters = [m for m in self.monsters if m.hp > 0]

        self._run_hooks("_on_area_update_", dt)  # per-area domain logic (every occupied area)
        if globals_:
            self._run_hooks("_on_update_", dt)   # once-per-frame domain logic (view)
        if self.state != st0 or self.world.area is not area or self._ctx_warped:
            return                               # a hook warped / opened a menu

        # beach crabs: cosmetic critters that scuttle the tideline (empty list off
        # the beach, so this is a no-op elsewhere). No collision / no damage.
        for c in getattr(self, "beach_critters", ()):
            c["bob"] += dt * 6.0
            if c["pause_t"] > 0:
                c["pause_t"] -= dt
                continue
            c["x"] += c["dir"] * c["spd"] * dt
            c["flip_t"] -= dt
            out = abs(c["x"] - c["home_x"]) > c["rng"]
            if c["flip_t"] <= 0 or out:          # turn back / randomly pause like a real crab
                c["dir"] *= -1
                c["flip_t"] = random.uniform(1.5, 3.5)
                if random.random() < 0.3:
                    c["pause_t"] = random.uniform(0.4, 1.2)
                c["x"] = max(c["home_x"] - c["rng"], min(c["home_x"] + c["rng"], c["x"]))

        # red flash + shake when a player was just hit
        for p in here:
            if p.hurt_cd > 0.92:
                self.hurt_flash = max(self.hurt_flash, 0.7)
                self.add_shake(5)

        if globals_:
            # the cabana's "needs two players" hint drifts up and fades out
            if self._anniv_hint is not None:
                self._anniv_hint[1] -= dt * 16    # drift up
                self._anniv_hint[2] -= dt         # life
                if self._anniv_hint[2] <= 0:
                    self._anniv_hint = None

            # floating popups (xp / gold / level-up)
            for pu in self.popups:
                pu[1] -= dt * 26          # drift up
                pu[4] -= dt               # life
            self.popups = [pu for pu in self.popups if pu[4] > 0]

            # juice decay
            self.shake = max(0.0, self.shake - dt * 38)
            self.hurt_flash = max(0.0, self.hurt_flash - dt * 1.6)

            # ambient drifting motes / falling leaves (outdoors)
            self.leaf_t += dt
            if self.leaf_t > 0.5 and area.name in (AREA_FARM, AREA_TOWN, AREA_FOREST):
                self.leaf_t = 0.0
                mx = self.cam.x + random.uniform(0, SCREEN_W)
                my = self.cam.y + random.uniform(0, SCREEN_H)
                self.parts.mote(mx, my, night=self.night)

        # player death -> respawn at farm, lose a little gold
        for i in idxs:
            p = self.players[i]
            if p.health <= 0:
                p.health = self._max_hp(p)
                p.energy = int(MAX_ENERGY * 0.5)
                self.gold = max(0, self.gold - 50)
                if self.independent():
                    self.warp_player(i, AREA_FARM, (12, 12))
                else:
                    self.warp(AREA_FARM, (12, 12))
                self.ui.log(f"{p.name} fainted! Rescued home (-50g).")
                return

        if globals_:
            self._update_camera(area)
            self.ui.update(dt)
        elif self.world.current != self.view_area():
            self._update_camera(area, focus=idxs[0])   # the partner's own camera

    def _leash(self, area, prev):
        """Local co-op shares ONE screen: a farmer can't walk so far from the
        other that either would leave it (the camera frames their midpoint)."""
        a, b = self.players[0], self.players[1]
        for axis, lim, size in (("x", SCREEN_W - TILE * 3, area.w * TILE),
                                ("y", SCREEN_H - TILE * 4, area.h * TILE)):
            if size <= lim:
                continue
            k = 0 if axis == "x" else 1
            d_new = abs(getattr(a, axis) - getattr(b, axis))
            d_old = abs(prev[0][k] - prev[1][k])
            if d_new > lim and d_new > d_old:
                setattr(a, axis, prev[0][k])
                setattr(b, axis, prev[1][k])

    # ---------- sleep state ----------
    def update_sleep(self, dt):
        self.sleep_timer -= dt
        if self.sleep_timer <= 0:
            self.state = "play"
            # the cosy "End of Day" card (CoopMixin) -- host/local only; it sets
            # state "day_report" itself and returns to play when dismissed
            opener = getattr(self, "_open_day_report", None)
            if opener:
                opener()

    # ---------- screen-shake juice (shared by combat + render) ----------
    def add_shake(self, mag):
        self.shake = min(16.0, self.shake + mag)

    def _shake_offset(self):
        if self.shake <= 0.2:
            return 0.0, 0.0
        return (random.uniform(-self.shake, self.shake),
                random.uniform(-self.shake, self.shake))
# ----------------------------------------------------------------------------
# Module notes:
#   This controller is now a thin composition of the system mixins in
#   src/systems/. Construction, the main loop, the day/area lifecycle, event
#   dispatch and shared juice helpers live here; everything else is owned by a
#   domain mixin (see docs/ARCHITECTURE.md for who owns what).
# ----------------------------------------------------------------------------
