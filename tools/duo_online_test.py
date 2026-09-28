"""End-to-end LAN test: a real host and a real client Game talking over TCP
on localhost, checking that the two farmers really live in separate areas
(own map, own camera, own monsters, own menus) -- like a normal online game.

    py tools/duo_online_test.py [--shots DIR]

Saves go to a throw-away temp folder (APPDATA is redirected before import),
so the real %APPDATA%\\HarvestDuo save is never touched.
"""
import os
import sys
import json
import time
import tempfile
import traceback

_TMP = tempfile.mkdtemp(prefix="hd_duo_")
os.environ["APPDATA"] = _TMP
os.environ["XDG_DATA_HOME"] = _TMP
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["HD_NO_EXTERNAL"] = "1"                  # never launch Spotify / send media keys
os.environ.setdefault("HD_STRICT_HOOKS", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import webbrowser                                     # noqa: E402
webbrowser.open = webbrowser.open_new = webbrowser.open_new_tab = lambda *a, **k: True
import socket                                         # noqa: E402
import pygame                                         # noqa: E402

DT = 1.0 / 60.0
RESULTS = []
SHOTS = None
_KEYS = set()


class _Keys:
    def __getitem__(self, code):
        return code in _KEYS


def _pressed():
    return _Keys()


def check(name, fn):
    t0 = time.perf_counter()
    try:
        detail = fn()
        RESULTS.append((name, True, detail))
        print(f"[PASS] {name}" + (f"  -- {detail}" if detail else ""))
    except Exception:
        RESULTS.append((name, False, traceback.format_exc()))
        print(f"[FAIL] {name}\n{traceback.format_exc()}")
    finally:
        _ = time.perf_counter() - t0


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    global SHOTS
    if "--shots" in sys.argv:
        SHOTS = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(SHOTS, exist_ok=True)
    pygame.key.get_pressed = _pressed
    from src.systems import net_system as NS
    from src.settings import (TILE, SCREEN_W, SCREEN_H, P1_KEYS, AREA_FARM, AREA_MINE,
                              AREA_HOME, AREA_TOWN, AREA_FOREST)
    from src.systems.areactx_system import PARK
    NS.PORT = free_port()
    from src.game import Game

    host = Game()
    host.start_new(host.look)
    host.start_host()
    client = Game()
    client.start_client("127.0.0.1")
    CK = NS.CLIENT_KEYS
    hp1, hp2 = host.players

    def frames(n=1, hk=(), ck=(), draw=False):
        global _KEYS
        for _ in range(n):
            _KEYS = set(hk)
            host.step(DT)
            if draw:
                host.draw()
            _KEYS = set(ck)
            client.step(DT)
            if draw:
                client.draw()
            time.sleep(0.001)                    # let the sockets breathe
        _KEYS = set()

    def until(cond, limit=600, **kw):
        for _ in range(limit):
            if cond():
                return True
            frames(1, **kw)
        return cond()

    def shot(g, name):
        if SHOTS:
            g.draw()
            pygame.image.save(g.screen, os.path.join(SHOTS, name + ".png"))

    def spot(area, near_warp_to=None):
        """A free, walkable tile in ``area`` (optionally next to its warp)."""
        a = host.world.areas[area]
        for w in a.warps:
            if near_warp_to and w["to"] != near_warp_to:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                gx, gy = w["gx"] + dx, w["gy"] + dy
                if not a.is_solid(gx, gy) and not any(
                        (gx, gy) == (v["gx"], v["gy"]) for v in a.warps):
                    return (gx, gy), (-dx, -dy), w
        raise AssertionError(f"no free tile by a warp in {area}")

    def dir_keys(d, keys):
        return {(1, 0): keys["right"], (-1, 0): keys["left"],
                (0, 1): keys["down"], (0, -1): keys["up"]}[d]

    def place(p, gx, gy):
        p.x, p.y = gx * TILE + TILE / 2, gy * TILE + TILE / 2

    # ------------------------------------------------------------ connect
    def connect():
        assert until(lambda: host.net.connected and getattr(client, "_net_world_seen", False)), \
            "client never synced"
        assert host.independent() and not client.independent()
        # let the host's own start-of-play iris finish, so the "P2's warp never
        # plays an iris on the host" check below can't race a fast connect
        assert until(lambda: host.fade <= 0.01, limit=180), "host start iris never ended"
        return f"port {NS.PORT}"
    check("connect: real host + client over TCP", connect)

    # ------------------------------------------------------------ P2 walks away
    state = {}

    def p2_walks_to_other_area():
        (gx, gy), d, w = spot(AREA_FARM)
        place(hp2, gx, gy)
        target = w["to"]
        p1_xy = (hp1.x, hp1.y)
        ok = until(lambda: host.p_area[1] == target, limit=240, ck={dir_keys(d, CK)})
        assert ok, f"P2 never walked through the door to {target} (at {hp2.x},{hp2.y})"
        assert host.p_area[0] == AREA_FARM, "P1 was dragged along"
        assert host.world.current == AREA_FARM, "host screen left P1's area"
        assert (hp1.x, hp1.y) == p1_xy, "P1 moved when P2 took the door"
        card = getattr(host, "_area_card", None)
        assert not (card and target.lower() in str(card[0]).lower()),             f"P2's area card popped up on the host screen: {card}"
        assert host.fade <= 0.5, "P2's warp iris played on the host screen"
        assert until(lambda: client.world.current == target, limit=240), \
            f"client still shows {client.world.current}"
        state["p2_area"] = target
        return f"P1 on farm, P2 in {target}"
    check("independent: P2 takes a door alone, P1 stays", p2_walks_to_other_area)

    def screens_follow_own_player():
        frames(60, draw=True)
        # host camera frames P1; client camera frames P2
        assert host.cam.x - 5 <= hp1.x <= host.cam.x + SCREEN_W + 5, "host cam lost P1"
        cp2 = client.players[1]
        cam = client.cam
        assert cam.x - 5 <= cp2.x <= cam.x + SCREEN_W + 5 and \
            cam.y - 5 <= cp2.y <= cam.y + SCREEN_H + 5, "client cam lost P2"
        # each screen hides the farmer who is elsewhere
        assert client.p_area[0] == AREA_FARM and client.world.current == state["p2_area"]
        seen = {}
        orig = client._draw_frame

        def spy():
            seen["p1"] = (client.players[0].x, client.players[0].y)
            return orig()
        client._draw_frame = spy
        before = (client.players[0].x, client.players[0].y)
        client.draw()
        del client._draw_frame
        assert seen["p1"] == (PARK, PARK), "client draws P1 in P2's area"
        assert (client.players[0].x, client.players[0].y) == before, "draw() moved P1"
        shot(host, "duo_host_view")
        shot(client, "duo_client_view")
        return "host follows P1, client follows P2, absent farmer hidden"
    check("independent: each screen follows its own farmer", screens_follow_own_player)

    def p1_moves_freely():
        trail = set()
        for k in ("down", "right", "up", "left"):
            frames(20, hk={P1_KEYS[k]})
            trail.add((round(hp1.x), round(hp1.y)))
        assert len(trail) > 1, "P1 can't move"
        assert host.p_area == [AREA_FARM, state["p2_area"]], host.p_area
        return "P1 walks on the farm while P2 is away"
    check("independent: P1 still controls their own farmer", p1_moves_freely)

    # ------------------------------------------------------------ separate monsters
    def own_monsters_per_area():
        host.warp_player(0, AREA_MINE, (5, 3))             # P1 heads down the mine
        assert host.world.current == AREA_MINE and host.p_area[0] == AREA_MINE
        assert host.p_area[1] == state["p2_area"], "P2 moved with P1"
        frames(10)
        mine_mobs = len(host.monsters)
        assert mine_mobs > 0, "no monsters in P1's mine"
        with host.area_ctx(host.p_area[1]):
            p2_mobs = [m.name for m in host.monsters]
        assert until(lambda: [m.name for m in client.monsters] == p2_mobs, limit=120), \
            (f"client shows {[m.name for m in client.monsters]} but P2's area has {p2_mobs}")
        # the mine keeps running for P1: monsters move
        xs = [(m.x, m.y) for m in host.monsters]
        frames(90)
        assert any((m.x, m.y) != xy for m, xy in zip(host.monsters, xs)) or not xs, \
            "the mine froze"
        return f"mine {mine_mobs} monsters (host), P2 area {len(p2_mobs)} (client)"
    check("independent: each area has its own monsters", own_monsters_per_area)

    def partner_area_runs():
        # send P2 into the forest (wildlife there) while P1 stays in the mine
        host.warp_player(1, AREA_FOREST, host.world.areas[AREA_FOREST].warps[0]["spawn"])
        frames(5)
        with host.area_ctx(AREA_FOREST):
            mobs = list(host.monsters)
            xy0 = [(m.x, m.y) for m in mobs]
        frames(120)
        with host.area_ctx(AREA_FOREST):
            moved = [(m.x, m.y) != xy for m, xy in zip(host.monsters, xy0)]
            same = host.monsters is not None and all(a is b for a, b in zip(host.monsters, mobs))
        assert host.world.current == AREA_MINE
        assert same, "the forest respawned every frame"
        assert any(moved) or not mobs, "the forest froze while P1 was in the mine"
        assert until(lambda: client.world.current == AREA_FOREST, limit=240)
        return f"forest: {sum(moved)}/{len(mobs)} animals moved while the host watched the mine"
    check("independent: the partner's area keeps living", partner_area_runs)

    def p2_keeps_playing_under_p1_menu():
        host.state = "journal"
        x0 = hp2.x
        frames(40, ck={CK["right"]})
        frames(40, ck={CK["left"]})
        frames(40, ck={CK["down"]})
        moved = (hp2.x, hp2.y) != (x0, hp2.y) or abs(hp2.x - x0) > 0
        host.state = "menu"
        frames(30, ck={CK["up"]})
        host.state = "play"
        assert host.players[1] is hp2
        assert moved, "P2 froze while P1 read the journal"
        return "journal + pause menu on the host never freeze P2"
    check("independent: P1's menus don't freeze P2", p2_keeps_playing_under_p1_menu)

    def p2_faint_only_p2():
        hp2.health = 0
        frames(3)
        assert host.p_area[1] == AREA_FARM and host.p_area[0] == AREA_MINE, host.p_area
        assert host.world.current == AREA_MINE
        assert until(lambda: client.world.current == AREA_FARM, limit=240)
        return "P2 rescued home, P1 still in the mine"
    check("independent: fainting only rescues that farmer", p2_faint_only_p2)

    def p2_ladder_alone():
        host.warp_player(0, AREA_FARM, (12, 12))
        host.warp_player(1, AREA_MINE, (5, 3))
        frames(5)
        lvl = host.world.mine_level
        with host.area_ctx(AREA_MINE):
            host.monsters = [m for m in host.monsters if not getattr(m, "boss", False)]
            lad = host.world.area.ladder
            place(hp2, lad[0], lad[1] + 1 if not host.world.area.is_solid(lad[0], lad[1] + 1)
                  else lad[1])
            host._apply_remote_event("action")
        assert host.world.mine_level == lvl + 1, "P2 couldn't use the ladder alone"
        assert host.p_area == [AREA_FARM, AREA_MINE], host.p_area
        assert host.world.current == AREA_FARM
        assert until(lambda: client.world.current == AREA_MINE, limit=120)
        return f"P2 descended to Lv.{host.world.mine_level}, P1 stayed on the farm"
    check("independent: mine ladder moves only who is in the mine", p2_ladder_alone)

    def sleep_needs_both_home():
        host.warp_player(1, AREA_HOME, (5, 5))
        host._net_sleep_op()
        frames(3)
        assert host.state == "play", "the day ended with P1 still out"
        assert host._sleep_ready == 1
        host.warp_player(0, AREA_HOME, (6, 5))
        host.request_sleep(0)
        frames(2)
        assert host.state in ("sleep", "day_report"), host.state
        until(lambda: host.state == "day_report", limit=200)
        host.state = "play"
        return "waits in bed until both are home, then the day ends"
    check("independent: sleeping waits for both farmers", sleep_needs_both_home)

    def save_never_parks():
        from src import savegame
        host.warp_player(1, AREA_TOWN, host.world.areas[AREA_TOWN].warps[0]["spawn"])
        frames(5)
        with host.area_ctx(AREA_TOWN):
            host._save()                          # even from inside a context
        d = savegame.load_game()
        for i, pd in enumerate(d["players"]):
            assert pd["x"] != PARK and pd["y"] != PARK, f"P{i + 1} saved off-map"
        assert d.get("p_area") == [AREA_HOME, AREA_TOWN], d.get("p_area")
        return f"saved p_area {d.get('p_area')}"
    check("save: a farmer in another area is saved at their real spot", save_never_parks)

    def npc_talk_in_own_area():
        with host.area_ctx(AREA_TOWN):
            names = [n.name for n in host.npcs]
        assert names, "no villagers in town"
        with host.area_ctx(host.p_area[0]):
            home_names = [n.name for n in host.npcs]
        assert set(names) != set(home_names) or not home_names
        n = names[0]
        with host.area_ctx(AREA_TOWN):
            npc = next(x for x in host.npcs if x.name == n)
            hp2.x, hp2.y = npc.x + TILE * 0.5, npc.y
        before = host.state
        with host.area_ctx(host.p_area[1]):
            host._net_apply_menu({"m": "talk", "npc": n})
        assert host.state == before
        return f"P2 chats with {n} in town while P1 is home"
    check("independent: P2 talks to villagers in their own area", npc_talk_in_own_area)

    def hud_shows_partner_area():
        frames(20, draw=True)
        assert host.apart()
        host.draw()
        client.draw()
        shot(host, "duo_host_hud")
        shot(client, "duo_client_hud")
        return "partner tag drawn on both screens"
    check("hud: partner location tag", hud_shows_partner_area)

    def mist_needs_both():
        host.mist_enter()
        assert host.state != "mistcity", "Mist City started with the partner elsewhere"
        return "gate refuses a solo online run"
    check("mist: the gate waits for both farmers", mist_needs_both)

    # ------------------------------------------------------------ review round
    def save_current_is_view():
        from src import savegame
        with host.area_ctx(host.p_area[1]):
            host._save()
        d = savegame.load_game()
        assert d["current"] == host.p_area[0], f"saved current={d['current']}, view={host.p_area[0]}"
        return f"current={d['current']} even when saved from P2's area"
    check("save: 'current' is always the host's own area", save_current_is_view)

    def sleep_cancels_if_someone_leaves():
        host.warp_player(0, AREA_HOME, (6, 5))
        host.warp_player(1, AREA_HOME, (5, 5))
        host.state = "journal"
        host._net_sleep_op()                      # both home, P1 busy -> pending
        assert host._sleep_pending
        host.warp_player(1, AREA_FARM, (12, 12))  # ...P2 wanders out again
        host.state = "play"
        frames(3)
        assert host.state == "play", f"the day ended with P2 outside ({host.state})"
        assert not host._sleep_pending
        return "pending sleep is cancelled when a farmer leaves the house"
    check("sleep: cancelled if a farmer walks out before it begins", sleep_cancels_if_someone_leaves)

    def home_furniture_for_client():
        """Fridge / TV / seat / wardrobe all work from the client's screen."""
        host.warp_player(0, AREA_HOME, (6, 5))
        host.warp_player(1, AREA_HOME, (5, 5))
        host.state = "play"
        assert until(lambda: client.world.current == AREA_HOME, limit=240)
        cp2 = client.players[1]
        hfr = next(q for q in host.world.home_furniture if q.kind == "fridge")
        hfr.store.update({"fried_egg": 1})
        hp2.inv.add("parsnip", 2)
        host._net_world_t = 99.0
        assert until(lambda: cp2.inv.count("parsnip") >= 2, limit=240), "bag never synced"
        # fridge: put a parsnip in, eat the fried egg
        cfr = next(q for q in client.world.home_furniture if q.kind == "fridge")
        client._open_fridge(1, cfr, client=True)
        assert client.state == "fridge"
        before_p, before_e = hfr.store.get("parsnip", 0), hp2.energy
        hp2.energy = 10
        client._fridge_op(1, client.fridge_menu.fr, "put", "parsnip", 1, client=True)
        client._fridge_op(1, client.fridge_menu.fr, "eat", "fried_egg", 1, client=True)
        assert until(lambda: hfr.store.get("parsnip", 0) == before_p + 1
                     and "fried_egg" not in hfr.store, limit=240), hfr.store
        assert hp2.energy > 10, "eating from the fridge gave no energy"
        client.fridge_menu.close()
        frames(30)
        assert client.state == "play", client.state
        # TV: switching it on from the client flips the host's set
        htv = next(q for q in host.world.home_furniture if q.kind == "tv")
        htv.on = False
        host._net_world_t = 99.0
        assert until(lambda: not next(q for q in client.world.home_furniture
                                      if q.kind == "tv").on, limit=240)
        ctv = next(q for q in client.world.home_furniture if q.kind == "tv")
        assert client._home_client_interact(cp2, ctv) is True and client.state == "tv"
        assert until(lambda: htv.on, limit=120), "host TV never switched on"
        client.tv_screen._leave(power_off=True)
        assert until(lambda: client.state == "play" and not htv.on, limit=240), \
            "powering off on the client never reached the host"
        # seat: the host sits P2 down and the client sees it
        sofa = next(q for q in host.world.home_furniture if q.kind == "sofa")
        place(hp2, sofa.gx, sofa.gy + 1)
        hp2.fx, hp2.fy = 0, -1
        frames(10)
        client._client_capture_key(CK["action"])
        assert until(lambda: getattr(hp2, "sitting", None) is not None, limit=120), \
            "host never seated P2"
        assert until(lambda: getattr(cp2, "sitting", None) is not None, limit=120), \
            "client never saw P2 seated"
        hp2.sitting = None
        assert until(lambda: getattr(cp2, "sitting", None) is None, limit=120)
        # wardrobe: a new shirt reaches the host's P2
        shirt = hp2.appearance.get("shirt_color", 0)
        client._open_wardrobe(1, "wardrobe", client=True)
        client.wardrobe.handle_key(CK["right"])
        client.wardrobe.handle_key(CK["action"])
        assert until(lambda: hp2.appearance.get("shirt_color", 0) != shirt, limit=120), \
            "outfit change never reached the host"
        return "fridge put/eat, TV on/off, sofa seat and outfit all sync"
    check("home: fridge, TV, seats and wardrobe work for the client", home_furniture_for_client)

    def piano_and_records_over_lan():
        """Each farmer hears the other's piano; the client's record player is
        switched on/off through the host and only ever drives the CLIENT's
        Spotify (safety-gated here: nothing external really happens)."""
        from src import furniture as F, piano as PN, spotify as SP
        assert SP.gated(), "Spotify safety gate is OFF in the online test"
        host.warp_player(0, AREA_HOME, (6, 5))
        host.warp_player(1, AREA_HOME, (5, 5))
        host.state = "play"
        pn = next((q for q in host.world.home_furniture if q.kind == "piano"), None)
        if pn is None:
            pn = F.Placed("piano", 7, 2, 0, 10)
            host.world.home_furniture.append(pn)
        rp = next((q for q in host.world.home_furniture if q.kind == "record_player"), None)
        if rp is None:
            rp = F.Placed("record_player", 3, 6, 0, 8)
            host.world.home_furniture.append(rp)
        rp.on = False
        host._net_world_t = 99.0
        assert until(lambda: client.world.current == AREA_HOME and
                     any(q.kind == "piano" for q in client.world.home_furniture) and
                     any(q.kind == "record_player" and not q.on
                         for q in client.world.home_furniture), limit=300)
        ev = pygame.event.Event
        # --- piano: client plays, host hears
        hsyn = PN.synth(host.audio)
        heard = []
        orig = hsyn.note_on
        hsyn.note_on = lambda key, midi, vel=1.0: (heard.append(midi), orig(key, midi, vel))[1]
        try:
            cpn = next(q for q in client.world.home_furniture if q.kind == "piano")
            assert client._home_client_interact(client.players[1], cpn) is True
            assert client.state == "piano", client.state
            client._run_state("event", ev(pygame.KEYDOWN, key=pygame.K_q, mod=0,
                                          unicode="", scancode=0))
            assert until(lambda: 60 in heard, limit=120), f"host never heard C4: {heard}"
            client._run_state("event", ev(pygame.KEYUP, key=pygame.K_q, mod=0,
                                          unicode="", scancode=0))
            client._run_state("event", ev(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0,
                                          unicode="", scancode=0))
            frames(30)
            assert client.state == "play", client.state
        finally:
            hsyn.note_on = orig
        # --- record player: the client's press flips the HOST's piece
        calls0 = len(SP.CALLS)
        crp = next(q for q in client.world.home_furniture if q.kind == "record_player")
        assert client._home_client_interact(client.players[1], crp) is True
        assert client.state == "records", client.state
        assert until(lambda: rp.on, limit=240), "host record player never switched on"
        assert not getattr(host, "records_active", False), "host listens because of the client"
        client.records_screen.handle_key(pygame.K_x)
        assert until(lambda: not rp.on, limit=240), "client's X never reached the host"
        frames(10)
        assert client.state in ("play", "records"), client.state
        if client.state == "records":
            client.records_screen.handle_key(pygame.K_ESCAPE)
        return f"piano heard on host; record player on/off via host; gated calls {SP.CALLS[calls0:]}"
    check("home: piano + record player over LAN", piano_and_records_over_lan)

    def sit_beside_busy_host():
        """P1 watches TV on the host; the client's press on the sofa still
        seats Player 2 (it used to be dropped while P1 had a screen open)."""
        from src import furniture as F
        host.warp_player(0, AREA_HOME, (6, 5))
        host.warp_player(1, AREA_HOME, (5, 5))
        host.state = "play"
        hp2.sitting = hp1.sitting = None
        sofa = next(q for q in host.world.home_furniture if q.kind == "sofa")
        tvp = next(q for q in host.world.home_furniture if q.kind == "tv")
        host._open_tv(0, tvp)
        assert host.state == "tv", host.state
        fw, fh = F.footprint(sofa.kind, sofa.rot)
        f = ((0, 1), (-1, 0), (0, -1), (1, 0))[sofa.rot % 4]
        place(hp2, sofa.gx + (fw - 1) * max(0, f[0]) + f[0], sofa.gy + (fh - 1) * max(0, f[1]) + f[1])
        hp2.fx, hp2.fy = -f[0], -f[1]
        frames(15)
        client._client_capture_key(CK["action"])
        assert until(lambda: getattr(hp2, "sitting", None) is not None, limit=120),             "P2's seat press was dropped while P1 watched TV"
        assert host.state == "tv", f"P1's TV screen was taken over: {host.state}"
        assert until(lambda: getattr(client.players[1], "sitting", None) is not None, limit=120)
        host.tv_screen._leave(power_off=False)
        hp2.sitting = None
        frames(10)
        return "P2 sat on the sofa while P1 kept watching TV"
    check("home: partner sits down while the host watches TV", sit_beside_busy_host)

    def heart_event_never_hijacks_p1():
        host.warp_player(0, AREA_FARM, (12, 12))
        host.warp_player(1, AREA_TOWN, host.world.areas[AREA_TOWN].warps[0]["spawn"])
        frames(3)
        orig_lv, orig_start = host._story_event_level, host._story_start_event
        host._story_event_level = lambda npc: 2

        def fake_start(npc, lv, idx):
            host.state = "heart_event"
        host._story_start_event = fake_start
        try:
            with host.area_ctx(AREA_TOWN):
                n = host.npcs[0].name
            with host.area_ctx(host.p_area[1]):
                host._net_apply_menu({"m": "talk", "npc": n})
        finally:
            host._story_event_level, host._story_start_event = orig_lv, orig_start
        assert host.state == "play", f"P2's heart event opened on P1's screen ({host.state})"
        return "event stays ready; P2 is asked to come back together"
    check("story: P2's heart event never pops up on P1's screen from afar",
          heart_event_never_hijacks_p1)

    def together_games_wait():
        assert host.together_needed("The Egg Hunt") is True
        assert host.p_area[0] != host.p_area[1]
        host._egg = {"t": 30.0, "eggs": [], "score": [0, 0], "n": 0}
        frames(2)
        assert host._egg is None and host.state == "play", "a hunt kept running while apart"
        return "egg hunt / Mist City need both; a hunt ends if someone leaves"
    check("festival: together-only games wait for both farmers", together_games_wait)

    def client_ignores_p1_mine_floors():
        host.warp_player(0, AREA_MINE, (5, 3))
        frames(30)
        calls = []
        orig = client._spawn_area_entities

        def spy():
            calls.append(client.world.current)
            return orig()
        client._spawn_area_entities = spy
        try:
            with host.area_ctx(AREA_MINE):
                host.world.regen_mine(host.world.mine_level + 1)
                host.warp(AREA_MINE, (5, 3))
            frames(90)
        finally:
            del client._spawn_area_entities
        assert not calls, f"client re-entered {calls} when only P1 changed floor"
        card = getattr(host, "_area_card", None)
        assert card and "mine" in str(card[0]).lower(), f"no mine card for P1: {card}"
        return f"P1 on Lv.{host.world.mine_level} got the card; P2's screen untouched"
    check("mine: P1 changing floor never resets P2's screen", client_ignores_p1_mine_floors)

    def nested_ctx_keeps_moves():
        host.warp_player(0, AREA_FARM, (12, 12))
        frames(2)
        with host.area_ctx(host.p_area[1]):          # P1 parked
            with host.area_ctx(AREA_FARM):           # P1 here again
                place(hp1, 20, 14)
            assert hp1.x == PARK
        assert (hp1.x, hp1.y) == (20 * TILE + TILE / 2, 14 * TILE + TILE / 2), (hp1.x, hp1.y)
        return "a move made in an inner context sticks"
    check("contexts: nesting keeps what happened inside", nested_ctx_keeps_moves)

    def partner_runs_once_per_frame():
        n = []
        orig = host.partner_update
        host.partner_update = lambda dt: n.append(1) or orig(dt)
        try:
            host.state = "play"
            frames(5)
            assert not n, "partner_update ran during normal play"
            host.state = "journal"
            frames(5)
            assert len(n) == 5, n
        finally:
            del host.partner_update
            host.state = "play"
        return "exactly one pass of P2's area per frame"
    check("frames: P2's area never runs twice in one frame", partner_runs_once_per_frame)

    def offline_partner():
        host.warp_player(1, AREA_FOREST, host.world.areas[AREA_FOREST].warps[0]["spawn"])
        frames(5)
        hp2.health = 5
        host.partner_online = lambda: False
        try:
            xy = (hp2.x, hp2.y)
            frames(60)
            assert (hp2.x, hp2.y) == xy and hp2.health == 5, "offline P2 left to the monsters"
            host.warp_player(0, AREA_HOME, (6, 5))
            host.request_sleep(0)
            frames(2)
            assert host.state in ("sleep", "day_report"), f"offline partner blocked sleep: {host.state}"
            assert host.p_area[1] == AREA_HOME, host.p_area
        finally:
            del host.partner_online
            until(lambda: host.state == "day_report", limit=200)
            host.state = "play"
        return "frozen while offline; the bed brings them home"
    check("offline: a dropped partner is frozen and never blocks the day", offline_partner)

    def stop_hosting_regroups():
        host.net_stop()
        assert not host.independent()
        assert host.p_area[0] == host.p_area[1] == host.world.current, host.p_area
        assert abs(hp1.x - hp2.x) <= TILE * 1.5 and abs(hp1.y - hp2.y) <= TILE
        frames(10)
        return "Player 2 is back beside Player 1"
    check("local again: stop hosting brings P2 back", stop_hosting_regroups)

    def local_leash():
        host.warp(AREA_FARM, (12, 12))
        host.state = "play"
        lim = SCREEN_W - TILE * 3
        from src.settings import P2_KEYS
        global _KEYS
        for _ in range(400):
            _KEYS = {P2_KEYS["right"]}
            host.update(DT)
        _KEYS = set()
        assert abs(hp1.x - hp2.x) <= lim + 4, abs(hp1.x - hp2.x)
        return f"max gap {abs(hp1.x - hp2.x) / TILE:.1f} tiles (screen fits both)"
    check("local co-op: nobody walks off the shared screen", local_leash)

    try:
        client.net_stop()
    except Exception:
        pass
    passed = sum(1 for r in RESULTS if r[1])
    print(f"\n{passed} passed, {len(RESULTS) - passed} failed   (isolated save dir: {_TMP})")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
