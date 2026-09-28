"""Headless smoke test for Harvest Duo -- the project's Definition of Done gate.

Run from the game folder (needs a Python that has pygame, e.g. ``py``):

    py tools/smoke_test.py                 # full sweep
    py tools/smoke_test.py --shots DIR     # also save PNG frames to DIR for review
    py tools/smoke_test.py --only mine,save  # run a subset of sections

SAFE BY DESIGN
  * saves go to a throw-away temp folder (APPDATA is redirected BEFORE the game is
    imported), so the player's real %APPDATA%\\HarvestDuo save is never touched;
  * the browser / anniversary page hooks are stubbed out, so nothing opens and
    memories/appearance.js is never rewritten;
  * SDL video/audio run on the dummy drivers (no window, no sound).

Every section runs even if an earlier one fails; the process exits 1 if anything
failed so it can gate a change. New content is picked up automatically: areas come
from World.areas, interaction points are discovered from area attributes, hotbar
entries/facings are swept for every player, mine depths cover every biome.
"""
import os
import sys
import json
import time
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMP = tempfile.mkdtemp(prefix="hd_smoke_")
os.environ["APPDATA"] = _TMP
os.environ["XDG_DATA_HOME"] = _TMP
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["HD_NO_EXTERNAL"] = "1"                  # never launch Spotify / send media keys
os.environ.setdefault("HD_STRICT_HOOKS", "1")      # hook errors fail the test
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import webbrowser                                   # never open a real browser
webbrowser.open = webbrowser.open_new = webbrowser.open_new_tab = lambda *a, **k: True

import pygame                                       # noqa: E402

DT = 1.0 / 60.0
RESULTS = []            # (section, name, ok, detail)
SHOTS = None
ONLY = None
_section = "?"


def section(name):
    global _section
    _section = name
    return ONLY is None or name in ONLY


def check(name, fn, *a, **k):
    """Run fn, record PASS/FAIL with a traceback; never raises."""
    try:
        r = fn(*a, **k)
        RESULTS.append((_section, name, True, "" if r is None else str(r)))
        return r
    except Exception:
        RESULTS.append((_section, name, False, traceback.format_exc()))
        return None


def shot(g, name):
    if SHOTS:
        try:
            pygame.image.save(g.screen, os.path.join(SHOTS, f"{name}.png"))
        except Exception:
            pass


class Keys:
    """Fake key-state for Player.update: only the codes in ``down`` are pressed."""
    def __init__(self, down=()):
        self.down = set(down)

    def __getitem__(self, code):
        return code in self.down


# ----------------------------------------------------------------- helpers
OVERLAYS = ("shop", "dialogue", "quest", "cook", "craft", "storage", "build",
            "inventory", "sleep", "create")


def settle(g):
    """Draw whatever overlay an action opened, then drop back to play."""
    if g.state != "play":
        g.draw()
    if g.state == "mistcity":
        g.mist_exit("leave")
    if g.state == "sleep":
        for _ in range(200):
            g.update_sleep(0.05)
            if g.state != "sleep":
                break
    if g.state in OVERLAYS or g.state not in ("play", "menu"):
        g.state = "play"
    for p in g.players:
        p.sitting = None


def frames(g, n=30, draw_every=0):
    for i in range(n):
        if g.state == "play":
            g.update(DT)
        elif g.state == "sleep":
            g.update_sleep(DT)
        elif g.state == "mistcity":
            g._mist_update(DT)
        if draw_every and i % draw_every == 0:
            g.draw()


def spawns_by_area(g):
    """Every area -> a spawn tile, derived from the warps that lead into it."""
    out = {}
    for a in g.world.areas.values():
        for w in a.warps:
            out.setdefault(w["to"], tuple(w["spawn"]))
    return out


def place(g, p, gx, gy):
    from src.settings import TILE
    p.x = gx * TILE + TILE / 2
    p.y = gy * TILE + TILE / 2


def pois(area):
    """Interaction points: every area attribute that is an (int, int) grid tuple,
    plus lists of them (shops/ladders/new stations are found automatically)."""
    found = []
    for k, v in vars(area).items():
        if k in ("anniv_cabana",) or k.startswith("_"):
            continue
        if isinstance(v, tuple) and len(v) == 2 and all(isinstance(c, int) for c in v):
            found.append((k, v))
        elif isinstance(v, (list, tuple)) and v and all(
                isinstance(e, tuple) and len(e) == 2 and all(isinstance(c, int) for c in e)
                for e in v[:4]) and k not in ("npc_spawns", "monster_spawns", "animal_spawns",
                                                "crab_spawns", "warps"):
            found += [(k, e) for e in v[:6]]
    return found


def hotbar_index(p, kind, name):
    for i, e in enumerate(p.inv.hotbar()):
        if e == (kind, name) or (e and e[1] == name):
            return i
    return None


def stub_anniversary(Game):
    for meth in ("_write_anniv_appearance", "_open_anniversary_page"):
        if hasattr(Game, meth):
            setattr(Game, meth, lambda self, *a, **k: None)


# ----------------------------------------------------------------- sections
def s_imports():
    import pkgutil
    import importlib
    import src
    bad = []
    for m in pkgutil.walk_packages(src.__path__, "src."):
        try:
            importlib.import_module(m.name)
        except Exception:
            bad.append(m.name + "\n" + traceback.format_exc())
    if bad:
        raise RuntimeError("import failures:\n" + "\n".join(bad))
    return "all src modules import"


def s_boot():
    from src.game import Game
    from src import savegame
    stub_anniversary(Game)
    assert savegame.SAVE_PATH.startswith(_TMP), "save path not isolated!"
    g = Game()
    g.draw()
    return g


def s_menu(g):
    g.state = "menu"
    for page in ("main", "settings", "controls", "online", "help"):
        g.menu.page = page
        g.menu.sel = 0
        check(f"menu page {page}", lambda: (g.menu.update(DT), g.draw()))
        shot(g, f"menu_{page}")
    g.menu.page = "main"
    for key in (pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT, pygame.K_LEFT):
        check(f"menu key {key}", lambda: g.menu.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)))


def s_gallery(g):
    from src.gallery import GalleryScreen
    import src.gallery as G
    gal = GalleryScreen(g, on_close=lambda: None)
    cats = getattr(G, "CATEGORIES", None) or []
    for t in range(len(cats)):
        def one(t=t):
            gal.tab = t
            gal.sel = 0
            gal.update(DT)
            gal.draw(g.screen)
            n = len(gal._entries[cats[t]])
            for i in range(n):                      # every model renders in detail
                gal._open_detail(i)
                gal.update(DT)
                gal.draw(g.screen)
            gal.detail_idx = None if hasattr(gal, "detail_idx") else None
            return f"{cats[t]}: {n} entries"
        check(f"gallery tab {cats[t]}", one)
        shot(g, f"gallery_{t}")


def s_creator(g):
    g.open_creator()
    g.draw()
    shot(g, "creator")
    g.start_new(g.look)
    assert g.state == "play"


def s_areas(g):
    sp = spawns_by_area(g)
    for name in list(g.world.areas):
        def visit(name=name):
            if name not in sp:
                return f"no warp leads into {name} (skipped)"
            g.warp(name, sp[name])
            frames(g, 40)
            g.draw()
            shot(g, f"area_{name}")
            return f"{len(g.npcs)} npcs, {len(g.monsters)} monsters"
        check(f"visit {name}", visit)


def s_walk(g):
    from src.settings import P1_KEYS, P2_KEYS
    sp = spawns_by_area(g)
    for name in list(g.world.areas):
        if name not in sp:
            continue
        def walk(name=name):
            g.warp(name, sp[name])
            area = g.world.area
            for d in ("up", "down", "left", "right"):
                for i, p in enumerate(g.players):
                    K = P1_KEYS if i == 0 else P2_KEYS
                    for _ in range(45):
                        p.update(DT, Keys([K[d]]), area)
            g.update(DT)
            g.draw()
        check(f"walk {name}", walk)


def s_actions(g):
    """Every player x every hotbar entry x every facing, in every area, plus
    standing next to every discovered interaction point and pressing action."""
    sp = spawns_by_area(g)
    total = 0
    for name in list(g.world.areas):
        if name not in sp:
            continue
        def sweep(name=name):
            n = 0
            g.warp(name, sp[name])
            g.gold = 99999
            for i, p in enumerate(g.players):
                p.energy = 270
                for slot in range(len(p.inv.hotbar())):
                    p.inv.selected = slot
                    for fx, fy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                        p.fx, p.fy = fx, fy
                        g.player_action(i)
                        settle(g)
                        frames(g, 2)
                        n += 1
                        if g.world.current != name:
                            g.warp(name, sp[name])
            return f"{n} actions"
        r = check(f"tool/item sweep {name}", sweep)
        total += 1 if r else 0

        def poi_sweep(name=name):
            g.warp(name, sp[name])
            done = []
            for key, (gx, gy) in pois(g.world.area):
                for (ox, oy, fx, fy) in ((0, 1, 0, -1), (1, 0, -1, 0), (-1, 0, 1, 0), (0, -1, 0, 1)):
                    for i, p in enumerate(g.players):
                        place(g, p, gx + ox, gy + oy)
                        p.fx, p.fy = fx, fy
                        p.inv.selected = 0
                        g.player_action(i)
                        settle(g)
                        if g.world.current != name:
                            g.warp(name, sp[name])
                done.append(key)
            return ",".join(sorted(set(done))) or "none"
        check(f"poi sweep {name}", poi_sweep)
        # interactables() drives prompts/sparkles: exercise it too
        check(f"interactables {name}", lambda: (g.warp(name, sp[name]), g._interactables(),
                                                 g.draw_prompts()))


def s_farming(g):
    from src.settings import AREA_FARM, TILE
    g.warp(AREA_FARM, (12, 12))
    p = g.players[0]
    area = g.world.area
    # find an open tile near spawn to till
    target = None
    for gy in range(8, area.h - 2):
        for gx in range(8, area.w - 2):
            if area.tile(gx, gy) in (".", ",", "d") and not area.is_solid(gx, gy) \
                    and not area.is_solid(gx, gy - 1):
                target = (gx, gy)
                break
        if target:
            break
    assert target, "no tillable tile found"
    gx, gy = target
    place(g, p, gx, gy - 1)
    p.fx, p.fy = 0, 1
    for tool in ("hoe",):
        p.inv.selected = hotbar_index(p, "tool", tool)
        g.player_action(0)
    tilled = (AREA_FARM, gx, gy) in g.world.tilled
    si = hotbar_index(p, "item", "seed:parsnip")
    if si is not None:
        p.inv.selected = si
        g.player_action(0)
    planted = (AREA_FARM, gx, gy) in g.world.crops
    before = p.inv.count("parsnip")
    for _ in range(8):
        crop = g.world.crops.get((AREA_FARM, gx, gy))
        if crop is None or crop.ready_to_harvest:
            break                       # ripe (or already auto-harvested by a facing press)
        p.inv.selected = hotbar_index(p, "tool", "watering_can")
        place(g, p, gx, gy - 1)
        p.fx, p.fy = 0, 1
        g.player_action(0)
        g.do_sleep()
        settle(g)
        g.warp(AREA_FARM, (12, 12))
    place(g, p, gx, gy - 1)
    p.fx, p.fy = 0, 1
    p.inv.selected = hotbar_index(p, "tool", "watering_can")
    g.player_action(0)
    settle(g)
    return f"tilled={tilled} planted={planted} harvested={p.inv.count('parsnip') - before}"


def s_mine(g):
    from src.settings import AREA_MINE
    shots_at = {1, 5, 10, 15, 20, 25, 30}
    for lvl in (1, 2, 4, 5, 9, 10, 14, 15, 19, 20, 24, 25, 30, 35, 40, 50, 75, 100):
        def dive(lvl=lvl):
            g.world.mine_level = lvl
            g.world.regen_mine(lvl)
            g.warp(AREA_MINE, (5, 3))
            frames(g, 30)
            g.draw()
            if lvl in shots_at:
                shot(g, f"mine_{lvl:03d}")
            p = g.players[0]
            p.health = 999
            kinds = sorted({getattr(m, "kind", getattr(m, "name", "?")) for m in g.monsters})
            si = hotbar_index(p, "tool", "sword")
            for m in list(g.monsters):
                p.x, p.y = m.x, m.y - 30
                p.fx, p.fy = 0, 1
                if si is not None:
                    p.inv.selected = si
                for _ in range(3):
                    g.sword_attack(p)
                    frames(g, 3)
            for m in list(g.monsters):              # finish them off via the reward path
                m.hp = 0
                g._reward_kill(p, m)
            frames(g, 10)
            g.draw()
            return f"monsters={kinds}"
        check(f"mine depth {lvl}", dive)


def s_time(g):
    from src.settings import AREA_FARM, AREA_TOWN
    for s_idx in range(4):
        for w in ("sunny", "rain", "snow", "storm", "fog"):
            def one(s_idx=s_idx, w=w):
                g.time.season_idx = s_idx
                g.weather = w
                for area in (AREA_FARM, AREA_TOWN):
                    g.warp(area, spawns_by_area(g)[area])
                    for mins in (8 * 60, 19 * 60, 23 * 60):
                        g.time.minutes = mins
                        frames(g, 5)
                        g.draw()
                if s_idx in (0, 3) and w in ("sunny", "snow", "rain"):
                    shot(g, f"season{s_idx}_{w}")
            check(f"season {s_idx} weather {w}", one)
    def days():
        for _ in range(30):
            g.do_sleep()
            settle(g)
        return g.time.date_str()
    check("sleep 30 days", days)
    def pass_out():
        from src.settings import DAY_END_MIN
        g.state = "play"
        g.time.minutes = DAY_END_MIN - 1
        frames(g, 240)
        settle(g)
    check("pass out at 2am", pass_out)


def s_build(g):
    from src.settings import AREA_HOME
    g.warp(AREA_HOME, spawns_by_area(g)[AREA_HOME])
    g.gold = 99999
    g.state = "build"
    g.draw()
    shot(g, "build")
    ev = pygame.event.Event
    for key in (pygame.K_e, pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_SPACE,
                pygame.K_d, pygame.K_s, pygame.K_SPACE, pygame.K_TAB, pygame.K_DELETE):
        g.build.handle_event(ev(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
        g.draw()
    for pos in ((300, 300), (640, 360), (1100, 200), (1150, 500)):
        g.build.handle_event(ev(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        g.build.handle_event(ev(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        g.build.handle_event(ev(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        g.draw()
    g.build.handle_event(ev(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
    settle(g)
    return f"{len(g.world.home_furniture)} furniture placed"


def s_home(g):
    """Functional furniture (HomeMixin): fridge, TV, wardrobe, seats, books."""
    from src.settings import AREA_HOME, P1_KEYS
    from src import furniture as F
    g.warp(AREA_HOME, spawns_by_area(g)[AREA_HOME])
    g.state = "play"
    p = g.players[0]
    ev = pygame.event.Event

    def poke(keys, name):
        for k in keys:
            g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
            for _ in range(3):
                g._run_state("update", DT)
            g.draw()
        shot(g, name)

    def piece(kind):
        q = next((q for q in g.world.home_furniture if q.kind == kind), None)
        if q is None:
            q = F.Placed(kind, 6, 5, 0, 0)
            g.world.home_furniture.append(q)
        return q

    def fridge():
        fr = piece("fridge")
        p.inv.add("parsnip", 3)
        p.inv.add("sardine", 1)
        g.interact_furniture(p, fr)
        assert g.state == "fridge", g.state
        poke([P1_KEYS["left"], P1_KEYS["action"], P1_KEYS["down"], P1_KEYS["action"],
              P1_KEYS["right"], P1_KEYS["down"], P1_KEYS["up"], pygame.K_e], "home_fridge")
        have = fr.store.get("parsnip", 0)
        ok, _ = g._fridge_op(0, fr, "put", "parsnip", 1)
        assert ok and fr.store.get("parsnip", 0) == have + 1, fr.store
        p.inv.add("wood", 1)
        ok, msg = g._fridge_op(0, fr, "put", "wood", 1)
        assert not ok and "wood" not in fr.store, "wood went in the fridge"
        assert g._kitchen_count("parsnip") >= 3
        poke([pygame.K_ESCAPE], "home_fridge_close")
        for _ in range(40):
            g._run_state("update", DT)
        assert g.state == "play" and not fr.on, (g.state, fr.on)
    check("home fridge: stock, eat, shut", fridge)

    def tv():
        t = piece("tv")
        t.on = False
        g.interact_furniture(p, t)
        assert g.state == "tv" and t.on
        for _ in range(30):
            g._run_state("update", DT)
        poke([P1_KEYS["right"], P1_KEYS["right"], P1_KEYS["right"], P1_KEYS["right"],
              pygame.K_3], "home_tv")
        poke([P1_KEYS["action"]], "home_tv_off")
        for _ in range(40):
            g._run_state("update", DT)
        assert g.state == "play" and not t.on, (g.state, t.on)
    check("home tv: channels + power", tv)

    def wardrobe():
        before = dict(p.appearance)
        g.interact_furniture(p, piece("wardrobe"))
        assert g.state == "wardrobe"
        poke([P1_KEYS["right"], P1_KEYS["up"], P1_KEYS["left"]], "home_wardrobe")
        poke([pygame.K_ESCAPE], "home_wardrobe_cancel")
        assert g.state == "play" and p.appearance == before, "Esc must put the look back"
    check("home wardrobe: try on, put back", wardrobe)

    def seats():
        for kind in sorted(F.SEATS):
            q = piece(kind)
            for rot in range(4):
                q.rot = rot
                g.interact_furniture(p, q)
                assert p.sitting and p.sitting[0] is q, kind
                g.draw()
                p.sitting = None
            q.rot = 0
        return f"{len(F.SEATS)} seat kinds x 4 rotations"
    check("home seats: every seat, every rotation", seats)

    def small_things():
        for kind in ("clock", "window", "bookshelf", "piano"):
            g.interact_furniture(p, piece(kind))
            g.draw()
            settle(g)
        g.time.minutes = 22 * 60
        piece("lamp").on = True
        assert g._lights_home(), "no night glow from the lamps"
        g.draw()
        shot(g, "home_night")
    check("home clock/window/books/piano/lights", small_things)
    settle(g)


def s_inventory(g):
    g._open_inventory(0)
    g.draw()
    shot(g, "inventory")
    ev = pygame.event.Event
    for key in (pygame.K_d, pygame.K_s, pygame.K_SPACE, pygame.K_RIGHT, pygame.K_DOWN,
                pygame.K_RETURN, pygame.K_i):
        if g.state != "inventory":
            break
        g.inv_screen.handle_event(ev(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
        g.inv_screen.update(DT)
        g.draw()
    settle(g)


def s_overlays(g):
    """Open each menu object directly and poke it with keys."""
    from src.settings import P1_KEYS
    from src import quests
    keys = [P1_KEYS["down"], P1_KEYS["up"], P1_KEYS["right"], P1_KEYS["left"],
            P1_KEYS["action"], P1_KEYS["down"], P1_KEYS["action"], pygame.K_ESCAPE]
    p = g.players[0]
    g.gold = 99999

    def shop():
        g.shop.build(g.time.season)
        g.state = "shop"
        g.draw()
        shot(g, "shop")
        for k in keys[:-1]:
            if g.state == "shop":
                g.shop_input(k)
                g.draw()
        g.state = "play"
    check("shop menu", shop)

    def quest():
        g.quest = quests.QuestMenu(g, p)
        g.state = "quest"
        g.draw()
        shot(g, "quest")
        for k in keys:
            if g.state == "quest" and g.quest:
                g.quest.handle_key(k)
                g.draw()
        settle(g)
    check("quest menu", quest)


def s_mist(g):
    if not hasattr(g, "mist_enter"):
        return "MistMixin missing (skipped)"
    from src.settings import P1_KEYS, P2_KEYS
    g.state = "play"
    g.mist_enter()
    assert g.state == "mistcity"
    ev = pygame.event.Event
    for i in range(600):
        g._mist_update(DT)
        if i % 20 == 0:
            for K in (P1_KEYS, P2_KEYS):
                g._mist_handle_event(ev(pygame.KEYDOWN, key=K["action"], mod=0,
                                        unicode="", scancode=0))
                g._mist_handle_event(ev(pygame.KEYDOWN, key=K["up"], mod=0,
                                        unicode="", scancode=0))
        if i % 60 == 0:
            g.draw()
        if i == 300:
            shot(g, "mistcity")
        if g.state != "mistcity":
            break
    if g.state == "mistcity":
        g.mist_exit("leave")
    assert g.state == "play"


def s_save(g):
    from src import savegame
    d1 = g._collect_save()
    s1 = json.dumps(d1, sort_keys=True)
    g.reset()
    g._apply_save(json.loads(s1))
    d2 = g._collect_save()
    s2 = json.dumps(d2, sort_keys=True)
    if s1 != s2:
        diff = [k for k in set(d1) | set(d2)
                if json.dumps(d1.get(k), sort_keys=True) != json.dumps(d2.get(k), sort_keys=True)]
        raise AssertionError(f"save roundtrip changed keys: {sorted(diff)}")
    g.started = True
    g._save()
    assert os.path.exists(savegame.SAVE_PATH) and savegame.SAVE_PATH.startswith(_TMP)
    back = savegame.load_game()
    assert json.dumps(back, sort_keys=True) == s1, "disk roundtrip mismatch"
    return f"{len(d1)} top-level keys roundtrip OK"


def s_old_saves(g):
    cands = [os.path.join(ROOT, "savegame.json"),
             os.path.join(os.path.dirname(ROOT), "game_backup_20260926_1230", "savedata",
                          "savegame.json")]
    cands += [c for c in os.environ.get("HD_OLD_SAVES", "").split(os.pathsep) if c]
    n = 0
    for c in cands:
        if not os.path.exists(c):
            continue
        def one(c=c):
            with open(c, encoding="utf-8") as f:
                data = json.load(f)
            g.reset()
            g._apply_save(data)
            g.state = "play"
            frames(g, 20)
            g.draw()
            json.dumps(g._collect_save())
        check(f"old save {os.path.basename(os.path.dirname(c))}/{os.path.basename(c)}", one)
        n += 1
    def minimal():                                # a bare-minimum ancient save
        g.reset()
        g._apply_save({"gold": 10})
        frames(g, 5)
        g.draw()
    check("minimal save dict", minimal)
    return f"{n} old saves"


def s_hotkeys(g):
    """Press every letter/digit/F-key in play (domain hotkeys via _on_keydown_*)."""
    from src.settings import AREA_FARM, AREA_TOWN, AREA_HOME
    sp = spawns_by_area(g)
    codes = [getattr(pygame, f"K_{c}") for c in "abcdefghijklmnopqrstuvwxyz0123456789"]
    codes += [pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4, pygame.K_F5, pygame.K_TAB,
              pygame.K_SLASH, pygame.K_RSHIFT, pygame.K_LSHIFT, pygame.K_BACKQUOTE]
    ev = pygame.event.Event
    n = 0
    for area in (AREA_FARM, AREA_TOWN, AREA_HOME):
        g.warp(area, sp[area])
        for c in codes:
            g.state = "play"
            g.on_keydown(c)
            g.draw()
            if g.state not in ("play", "menu"):
                # a hotkey opened a screen: drive it a little, then leave
                for k in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE,
                          pygame.K_ESCAPE):
                    if g._custom_state("event") is not None:
                        g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="",
                                                 scancode=0))
                        g._run_state("update", DT)
                    g.draw()
                n += 1
            settle(g)
            frames(g, 2)
    return f"{n} hotkeys opened a screen"


def s_custom_states(g):
    """Every _state_draw_<name> screen a domain registered: open, poke, draw."""
    names = sorted({n.split("_state_draw_", 1)[1] for n in dir(type(g))
                    if n.startswith("_state_draw_")})
    ev = pygame.event.Event
    for name in names:
        def one(name=name):
            g.state = name
            for k in (pygame.K_DOWN, pygame.K_UP, pygame.K_RIGHT, pygame.K_LEFT,
                      pygame.K_SPACE, pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                if g.state != name:
                    break
                g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
                g._run_state("update", DT)
                g.draw()
                if k == pygame.K_SPACE:
                    shot(g, f"state_{name}")
            for pos in ((640, 360), (200, 200)):
                if g.state != name:
                    break
                g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
                g._run_state("event", ev(pygame.MOUSEBUTTONUP, pos=pos, button=1))
                g.draw()
            settle(g)
        check(f"custom state {name}", one)
    return f"{len(names)} custom states: {names}"


def s_events(g):
    """Fire every documented event at the subscribers with plausible data."""
    p = g.players[0]
    samples = [("harvest", dict(p=p, item="parsnip", qty=1)),
               ("fish_caught", dict(p=p, fish=next(iter(__import__("src.fishing",
                                     fromlist=["FISH"]).FISH)), size=12)),
               ("monster_killed", dict(p=p, kind="green_slime", boss=False)),
               ("item_sold", dict(p=p, item="parsnip", qty=3, gold=105)),
               ("gift_given", dict(p=p, npc="Mira", item="parsnip")),
               ("cooked", dict(p=p, food="fried_egg")),
               ("crafted", dict(p=p, what="sprinkler")),
               ("mine_depth", dict(level=12)),
               ("day_started", dict(day=2, season=0, year=1)),
               ("foraged", dict(p=p, item="wood")),
               ("quest_done", dict(p=p, quest=None)),
               ("warp", dict(area="farm")),
               ("tool_upgraded", dict(p=p, tool="hoe", tier=1)),
               ("animal_product", dict(p=p, item="egg")),
               ("emote", dict(p=p, kind="heart"))]
    for ev_name, data in samples:
        for _ in range(3):
            g.emit(ev_name, **data)
    frames(g, 5)
    g.draw()
    return f"{len(g._hook_names('_on_event_'))} subscribers"


def s_domain_tests(g):
    """Run every tools/tests/test_*.py: each defines run(g, check, H) where H is
    this smoke-test module (helpers: frames, settle, place, spawns_by_area,
    hotbar_index, shot, Keys, DT). Domain chats add their own file there instead
    of editing this one."""
    import importlib.util
    tdir = os.path.join(ROOT, "tools", "tests")
    if not os.path.isdir(tdir):
        return "no domain tests"
    H = sys.modules[__name__]
    ran = []
    for fn in sorted(os.listdir(tdir)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        def one(fn=fn):
            spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(tdir, fn))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            g.state = "play"
            r = mod.run(g, check, H)
            settle(g)
            return r
        check(f"domain test {fn}", one)
        ran.append(fn)
    return f"{len(ran)} domain test files"


def s_net(g):
    if not hasattr(g, "_collect_snapshot"):
        return "no net"
    snap = g._collect_snapshot()
    js = json.dumps(snap)
    g._apply_snapshot(json.loads(js))
    if hasattr(g, "_collect_world"):
        w = g._collect_world()
        g._apply_world(json.loads(json.dumps(w)))
    g.draw()
    return f"snapshot {len(js)} bytes"


def s_reboot():
    """A second Game() must boot from the save the earlier sections wrote."""
    from src.game import Game
    g2 = Game()
    assert not g2.load_failed, "save written by this build failed to load"
    g2.begin_play()
    frames(g2, 10)
    g2.draw()
    return f"has_save={g2.has_save}"


def s_perf(g):
    from src.settings import AREA_FARM, AREA_TOWN, AREA_FOREST
    out = []
    sp = spawns_by_area(g)
    for a in (AREA_FARM, AREA_TOWN, AREA_FOREST):
        g.warp(a, sp[a])
        g.state = "play"
        t0 = time.perf_counter()
        for _ in range(60):
            g.update(DT)
            g.draw()
        ms = (time.perf_counter() - t0) * 1000 / 60
        out.append(f"{a} {ms:.1f}ms/frame")
    return ", ".join(out)


# ----------------------------------------------------------------- main
def main():
    global SHOTS, ONLY
    args = sys.argv[1:]
    if "--shots" in args:
        SHOTS = os.path.abspath(args[args.index("--shots") + 1])
        os.makedirs(SHOTS, exist_ok=True)
    if "--only" in args:
        ONLY = set(args[args.index("--only") + 1].split(","))
    t0 = time.perf_counter()

    if section("imports"):
        check("import every src module", s_imports)
    section("boot")
    g = check("boot Game()", s_boot)
    if g is None:
        return report(t0)
    order = [("menu", s_menu), ("gallery", s_gallery), ("creator", s_creator),
             ("areas", s_areas), ("walk", s_walk), ("actions", s_actions),
             ("farming", s_farming), ("mine", s_mine), ("time", s_time),
             ("build", s_build), ("home", s_home), ("inventory", s_inventory), ("overlays", s_overlays),
             ("mist", s_mist), ("hotkeys", s_hotkeys), ("custom_states", s_custom_states),
             ("events", s_events), ("domain", s_domain_tests), ("net", s_net), ("save", s_save), ("old_saves", s_old_saves),
             ("perf", s_perf)]
    for name, fn in order:
        if section(name):
            check(f"<{name}>", fn, g)         # sub-steps record their own results
            if g.state not in ("play", "menu"):
                g.state = "play"
    if section("reboot"):
        check("reboot from written save", s_reboot)
    return report(t0)


def report(t0):
    fails = [r for r in RESULTS if not r[2]]
    for sec, name, ok, detail in RESULTS:
        tag = "PASS" if ok else "FAIL"
        line = f"[{tag}] {sec:10s} {name}"
        if ok and detail:
            line += f"  -- {detail[:160]}"
        print(line)
    for sec, name, ok, detail in fails:
        print(f"\n===== FAIL {sec} / {name} =====\n{detail}")
    print(f"\n{len(RESULTS) - len(fails)} passed, {len(fails)} failed "
          f"in {time.perf_counter() - t0:.1f}s   (isolated save dir: {_TMP})")
    if SHOTS:
        print(f"screenshots: {SHOTS}")
    return 1 if fails else 0


if __name__ == "__main__":
    code = main()
    try:
        pygame.quit()
    except Exception:
        pass
    sys.exit(code)
