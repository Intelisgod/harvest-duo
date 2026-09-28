"""World, Areas & Build (Chat 5) end-to-end checks -- run by tools/smoke_test.py
(section "domain").  Exercises: mine biomes + hazards + BIOME_STYLE, the farm
beautification (open land, paths, warps), the Flower Meadow + Promise Tree couple
moment (+ save round-trip), outdoor decor mode, and the town restoration board."""
import json
import pygame


def run(g, check, H):
    from src import world as W
    from src import world_art as WA
    from src.settings import (AREA_FARM, AREA_MEADOW, AREA_MINE, AREA_TOWN, TILE,
                              P1_KEYS, BUILD_KEY, MAX_ENERGY)
    ev = pygame.event.Event

    def key(k):
        g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
        g._run_state("update", H.DT)

    # ---------------------------------------------------------------- mine
    def biomes():
        want = {1: "rock", 5: "ice", 10: "lava", 15: "crystal", 20: "abyss", 29: "abyss",
                30: "ruins", 60: "ruins"}
        for lvl, b in want.items():
            got = W._mine_biome(lvl)[0]
            assert got == b, (lvl, got, b)
            assert b in W.BIOME_STYLE and {"floor", "rock_tint", "ambient"} <= set(W.BIOME_STYLE[b])
        return "ok"
    check("world: mine biome table + BIOME_STYLE", biomes)

    def hazards_safe():
        n = 0
        for lvl in list(range(10, 15)) + list(range(20, 30)) + [30, 31, 45, 80]:
            a = W.build_mine(lvl)
            spawn = {(5, 3), (6, 3), (5, 1), (6, 1), a.ladder}
            assert not (spawn & set(a.hazards)), f"hazard on spawn/ladder at {lvl}"
            assert not (set(a.hazards) & set(a.rocks)), "hazard under a rock"
            for (x, y) in a.hazards:
                assert not a.is_solid(x, y), "hazards must be walkable"
            assert not (spawn & a.solid_extra), "ruins decor blocks the entry"
            if a.biome in ("lava", "abyss"):
                assert a.hazards, f"no hazards generated at {lvl}"
            n += len(a.hazards)
        return f"{n} hazard tiles checked"
    check("world: hazards never on spawn/ladder/rocks", hazards_safe)

    def hazard_hurts():
        g.world.regen_mine(12)
        g.warp(AREA_MINE, (5, 3))
        area = g.world.area
        (hx, hy), kind = next(iter(area.hazards.items()))
        p = g.players[0]
        p.health = 100
        p.hurt_cd = 0
        H.place(g, p, hx, hy)
        H.frames(g, 70)                     # ~1.2 s standing in lava
        lost = 100 - p.health
        H.frames(g, 30)
        assert 5 <= lost <= 14, f"lava dealt {lost}"
        lights = g._lights_world()
        assert lights, "lava should glow"
        g.draw()
        H.shot(g, "world_lava")
        p.health = 100
        g.world.regen_mine(33)
        g.warp(AREA_MINE, (5, 3))
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_ruins")
        g.world.regen_mine(22)
        g.warp(AREA_MINE, (5, 3))
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_abyss")
        return f"lava -{lost} HP in ~1.2s"
    check("world: lava hurts ~6 HP/s + glows", hazard_hurts)

    # ---------------------------------------------------------------- farm
    def farm_layout():
        farm = g.world.areas[AREA_FARM]
        till = sum(1 for y in range(farm.h) for x in range(farm.w)
                   if farm.tile(x, y) in (W.GRASS, W.GRASS2, W.DIRT, W.PATH)
                   and not farm.is_solid(x, y))
        frac = till / (farm.w * farm.h)
        assert frac >= 0.60, f"only {frac:.0%} of the farm is open tillable land"
        for wp in farm.warps:
            assert not farm.is_solid(wp["gx"], wp["gy"]), f"warp blocked {wp}"
        for (x, y) in ((12, 12), (13, 12), (10, 6), (34, 16), (5, 7), (6, 7)):
            assert not farm.is_solid(x, y), f"key tile blocked {(x, y)}"
        # central field stays clear of solids
        for y in range(10, 27):
            for x in range(12, 29):
                assert not farm.is_solid(x, y), f"solid in the field at {(x, y)}"
        return f"{frac:.0%} tillable"
    check("world: farm keeps >=60% open farmland, warps clear", farm_layout)

    def old_save_compat():
        # an old save that tilled an orchard tile + parked P1 on a (now) lamp post
        g.warp(AREA_FARM, (12, 12))
        d = json.loads(json.dumps(g._collect_save()))
        d.pop("world_promise", None)
        d.pop("world_orchard", None)
        d.setdefault("tilled", [])
        from src.settings import TILE as T
        g.reset()
        g._apply_save(d)
        g.world.tilled.add((AREA_FARM, 13, 28))
        g.world.crops.pop((AREA_FARM, 13, 28), None)
        lamp = W.FARM_LAMPS[0]
        g.players[0].x, g.players[0].y = lamp[0] * T + T / 2, lamp[1] * T + T / 2
        g._on_load_world({})
        farm = g.world.areas[AREA_FARM]
        assert not farm.is_solid(13, 28), "tilled orchard tile must be freed"
        p = g.players[0]
        assert not farm.is_solid(int(p.x // T), int(p.y // T)), "player left inside a solid"
        assert g.world_promise == {"carved": "", "day": "", "count": 0}
        g.world.tilled.discard((AREA_FARM, 13, 28))
        g.state = "play"
        return "ok"
    check("world: old-save compatibility (unblock + unstick)", old_save_compat)

    def farm_night():
        g.weather = "sunny"
        g.time.minutes = 10 * 60
        for name, (gx, gy) in (("top", (20, 5)), ("pond", (30, 9)), ("west", (8, 14)),
                               ("home", (7, 8)),
                               ("south", (20, 25))):
            g.warp(AREA_FARM, (gx, gy))
            H.frames(g, 90)
            g.draw()
            H.shot(g, f"world_farm_{name}")
        g.warp(AREA_FARM, (16, 9))
        g.time.minutes = 21 * 60
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_farm_night")
        assert g._lights_world(), "farm lamps should glow at night"
        g.time.minutes = 9 * 60
        return "ok"
    check("world: farm lamps glow at night", farm_night)

    def orchard():
        import src.systems.world_system as WS
        g.time.season_idx = 1                             # summer: apples
        g.warp(AREA_FARM, (10, 26))
        H.frames(g, 3)
        p = g.players[0]
        H.place(g, p, 10, 27)
        p.fx, p.fy = 0, 1
        old = WS.ORCHARD_CHANCE
        WS.ORCHARD_CHANCE = 1.0
        try:
            n0 = p.inv.count("apple")
            g.player_action(0)
            H.settle(g)
            assert p.inv.count("apple") == n0 + 1, "shaking a summer tree drops an apple"
            g.player_action(0)                            # once a day per tree
            H.settle(g)
            assert p.inv.count("apple") == n0 + 1
        finally:
            WS.ORCHARD_CHANCE = old
        from src import loot
        assert "apple" in loot.MATERIALS and "persimmon" in loot.MATERIALS
        g.time.season_idx = 0
        return "apple shaken"
    check("world: orchard shake", orchard)

    # ---------------------------------------------------------------- meadow
    def meadow_walk():
        assert AREA_MEADOW in g.world.areas
        farm = g.world.areas[AREA_FARM]
        north = [w for w in farm.warps if w["to"] == AREA_MEADOW]
        assert north, "farm has no warp to the meadow"
        mead = g.world.areas[AREA_MEADOW]
        back = [w for w in mead.warps if w["to"] == AREA_FARM]
        assert back, "meadow has no warp back"
        for w in north:
            sx, sy = w["spawn"]
            assert not mead.is_solid(sx, sy) and not mead.is_solid(sx + 1, sy)
        for w in back:
            sx, sy = w["spawn"]
            assert not farm.is_solid(sx, sy) and not farm.is_solid(sx + 1, sy)
            assert all((sx, sy) != (v["gx"], v["gy"]) for v in farm.warps)
        # walk from the farm gate into the meadow for real
        g.warp(AREA_FARM, (20, 2))
        p = g.players[0]
        for _ in range(200):
            p.update(H.DT, H.Keys([P1_KEYS["up"]]), g.world.area)
            g.update(H.DT)
            if g.world.current == AREA_MEADOW:
                break
        assert g.world.current == AREA_MEADOW, "walking north did not reach the meadow"
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_meadow")
        return "farm -> meadow by walking"
    check("world: meadow reachable both ways", meadow_walk)

    def promise():
        g.warp(AREA_MEADOW, (20, 27))
        mead = g.world.area
        tx, ty = mead.promise_tree
        p1, p2 = g.players
        g.world_promise = {"carved": "", "day": "", "count": 0}
        H.place(g, p1, tx - 1, ty + 1)
        H.place(g, p2, tx + 1, ty + 1)
        p1.energy = p2.energy = 100
        # a lone press only hints
        g._wp_press = [-99.0, -99.0]
        g.player_action(0)
        H.settle(g)
        assert g.world_promise["count"] == 0, "one press must not trigger it"
        g.player_action(1)                          # partner joins within the window
        H.settle(g)
        wp = g.world_promise
        assert wp["count"] == 1 and wp["carved"], wp
        assert p1.energy == 140 and p2.energy == 140, (p1.energy, p2.energy)
        # once per day: a second promise gives no more energy
        g._wp_press = [-99.0, -99.0]
        g.player_action(0)
        g.player_action(1)
        H.settle(g)
        assert g.world_promise["count"] == 1 and p1.energy == 140
        H.frames(g, 150)                            # let the title card fade
        g.world_promise["day"] = ""                 # replay the moment for the shot
        g._wp_press = [-99.0, -99.0]
        g.player_action(0)
        g.player_action(1)
        H.settle(g)
        H.frames(g, 25)
        g.draw()
        H.shot(g, "world_promise")
        assert g.world_promise["count"] == 2
        # the rope swing sways when pushed (+ a little energy once a day)
        sw = mead.swing
        H.place(g, p1, sw[0], sw[1] + 1)
        e0 = p1.energy
        g.player_action(0)
        H.settle(g)
        assert g._w_swing_amp > 5 and p1.energy == min(MAX_ENERGY, e0 + 8)
        # the love bench: a quiet moment (+10 energy once a day), hearts together
        b = mead.bench
        H.place(g, p1, b[0], b[1] + 1)
        H.place(g, p2, b[0] - 1, b[1] - 1)
        p1.fx, p1.fy = 0, 1                           # not facing the partner (gift)
        e0 = p1.energy
        g.player_action(0)
        H.settle(g)
        assert p1.energy == min(MAX_ENERGY, e0 + 10), (e0, p1.energy)
        # milestones: the 100th promise crowns the tree (ribbons+lanterns+gold)
        g.world_promise["count"] = 99
        g.world_promise["day"] = ""
        H.place(g, p1, tx - 1, ty + 1)
        H.place(g, p2, tx + 1, ty + 1)
        g._wp_press = [-99.0, -99.0]
        g.player_action(0)
        g.player_action(1)
        H.settle(g)
        assert g.world_promise["count"] == 100 and WA.TIER == 3, (g.world_promise, WA.TIER)
        H.frames(g, 200)
        g.draw()
        H.shot(g, "world_promise_tier3")
        # carving + day survive a save round-trip exactly
        d1 = json.dumps(g._collect_save(), sort_keys=True)
        g.reset()
        g._apply_save(json.loads(d1))
        assert g.world_promise["carved"] == wp["carved"]
        assert json.dumps(g._collect_save(), sort_keys=True) == d1
        g.state = "play"
        return f"carved {g.world_promise['carved']}"
    check("world: Promise Tree couple moment", promise)

    def lookout():
        g.warp(AREA_MEADOW, (32, 6))
        H.frames(g, 90)
        mead = g.world.area
        lk = mead.lookout
        p = g.players[0]
        H.place(g, p, lk[0], lk[1] + 1)
        e0 = p.energy
        g.player_action(0)
        H.settle(g)
        assert p.energy >= min(MAX_ENERGY, e0 + 15) - 0.01
        H.frames(g, 5)
        g.draw()
        H.shot(g, "world_lookout")
        return "view enjoyed"
    check("world: meadow lookout", lookout)

    def meadow_night_perf():
        import time as _t
        g.weather = "sunny"
        g.warp(AREA_MEADOW, (20, 14))
        g.time.minutes = 21 * 60 + 30
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_meadow_night")
        g.time.minutes = 10 * 60
        t0 = _t.perf_counter()
        for _ in range(30):
            g.update(H.DT)
            g.draw()
        ms = (_t.perf_counter() - t0) * 1000 / 30
        return f"meadow {ms:.1f} ms/frame"
    check("world: meadow night + frame time", meadow_night_perf)

    def meadow_winter():
        g.time.season_idx = 3
        g.warp(AREA_MEADOW, (20, 12))
        H.frames(g, 90)
        mead = g.world.area
        assert mead.grid is mead.grid_snow, "meadow should be snowy in winter"
        g.draw()
        H.shot(g, "world_meadow_winter")
        g.warp(AREA_FARM, (12, 12))
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_farm_winter")
        g.warp(AREA_MEADOW, (20, 12))
        H.frames(g, 2)
        g.time.season_idx = 1
        H.frames(g, 2)
        assert mead.grid is mead.grid_green
        g.draw()
        H.shot(g, "world_meadow_summer")
        g.time.season_idx = 0
        H.frames(g, 1)
        return "ok"
    check("world: meadow seasons", meadow_winter)

    # ---------------------------------------------------------------- decor mode
    def decor():
        g.warp(AREA_FARM, (12, 12))
        H.frames(g, 90)
        g.gold = 1000
        g.state = "play"
        g.on_keydown(BUILD_KEY)
        assert g.state == "decor", g.state
        # pick the wood fence, aim at an open tile away from the field
        g._wd["sel"] = 0
        g._wd["cx"], g._wd["cy"] = 16, 5
        assert g._world_decor_check(16, 5)[0], g._world_decor_check(16, 5)
        key(P1_KEYS["action"])
        assert g.world.farm_objects.get((16, 5)) == "decor_wood_fence"
        assert g.gold == 1000 - WA.DECOR_INFO["wood_fence"]["price"]
        assert g.world.areas[AREA_FARM].is_solid(16, 5), "fence must block"
        # flat stone path: walkable
        key(pygame.K_e)
        key(pygame.K_e)                               # -> stone_path
        key(P1_KEYS["right"])
        key(P1_KEYS["action"])
        assert g.world.farm_objects.get((17, 5)) == "decor_stone_path"
        assert not g.world.areas[AREA_FARM].is_solid(17, 5)
        # never on warps / players / crops
        wp = g.world.areas[AREA_FARM].warps[0]
        assert not g._world_decor_check(wp["gx"], wp["gy"])[0]
        p = g.players[0]
        assert not g._world_decor_check(int(p.x // TILE), int(p.y // TILE))[0]
        g.world.tilled.add((AREA_FARM, 18, 5))
        assert not g._world_decor_check(18, 5)[0]
        g.world.tilled.discard((AREA_FARM, 18, 5))
        # mouse placement + draw
        g._run_state("event", ev(pygame.MOUSEMOTION, pos=(300, 200), rel=(0, 0), buttons=(0, 0, 0)))
        g.draw()
        H.shot(g, "world_decor_mode")
        # sell back for half
        gold0 = g.gold
        g._wd["cx"], g._wd["cy"] = 16, 5
        key(pygame.K_x)
        assert (16, 5) not in g.world.farm_objects
        assert g.gold == gold0 + WA.DECOR_INFO["wood_fence"]["price"] // 2
        assert not g.world.areas[AREA_FARM].is_solid(16, 5)
        # a little garden: connecting fences (a row + a column) and assorted decor
        names = [d[0] for d in WA.DECOR]
        g.gold = 5000
        placed = 0
        for (cx, cy, nm) in ([(x, 13, "wood_fence") for x in range(14, 18)]
                             + [(14, y, "wood_fence") for y in range(14, 17)]
                             + [(x, 19, "stone_fence") for x in range(14, 17)]
                             + [(16 + i, 15, n) for i, n in enumerate(
                                 ("garden_gnome", "bird_bath", "flower_bed", "pumpkin_stack",
                                  "garden_arch", "lantern_string", "picnic_blanket",
                                  "scarecrow_deluxe", "bench", "brick_path"))]):
            g._wd["sel"] = names.index(nm)
            placed += bool(g._world_decor_place(cx, cy))
        assert placed >= 12, placed
        g.draw()
        H.shot(g, "world_decor_garden")
        # place a lamp for the round-trip + night glow, then close with B
        g._wd["sel"] = [d[0] for d in WA.DECOR].index("lamp_post")
        g._wd["cx"], g._wd["cy"] = 16, 5
        key(P1_KEYS["action"])
        key(BUILD_KEY)
        assert g.state == "play"
        d1 = json.dumps(g._collect_save(), sort_keys=True)
        g.reset()
        g._apply_save(json.loads(d1))
        g.state = "play"
        assert g.world.farm_objects.get((16, 5)) == "decor_lamp_post"
        assert g.world.areas[AREA_FARM].is_solid(16, 5), "decor solids must survive load"
        g.warp(AREA_FARM, (15, 11))
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_decor_placed")
        g.time.minutes = 22 * 60
        H.frames(g, 10)
        g.draw()
        H.shot(g, "world_decor_night")
        g.time.minutes = 10 * 60
        # the journal "Places" tab renders
        tab = g._journal_tab_55_world()
        surf = pygame.Surface((900, 520))
        tab["draw"](surf, pygame.Rect(0, 0, 900, 520))
        # B inside the house is still the furniture Build mode
        from src.settings import AREA_HOME
        g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
        g.on_keydown(BUILD_KEY)
        assert g.state == "build", g.state
        H.settle(g)
        return "place/sell/solid/save ok"
    check("world: outdoor decor mode", decor)

    # ---------------------------------------------------------------- town board
    def board():
        town = g.world.areas[AREA_TOWN]
        rb = getattr(town, "restoration_board", None)
        assert rb and ("restoration_board", rb[0], rb[1]) in town.props
        for w in town.warps:
            assert (w["gx"], w["gy"]) != rb
        g.warp(AREA_TOWN, (rb[0], rb[1] + 2))
        H.frames(g, 90)
        g.draw()
        H.shot(g, "world_town_board")
        return f"board at {rb}"
    check("world: town restoration board", board)

    # ---------------------------------------------------------------- fix round (review findings)
    def decor_key_rebound():
        from src.settings import P2_KEYS
        g.warp(AREA_FARM, (12, 12))
        H.frames(g, 30)
        g.state = "play"
        old = dict(P2_KEYS)
        try:
            P2_KEYS["next"] = BUILD_KEY               # P2 rebinds 'Next Tool' to B
            inv = g.players[1].inv
            s0 = inv.selected
            g.on_keydown(BUILD_KEY)
            assert g.state == "play", f"B opened {g.state} although P2 bound it"
            assert inv.selected != s0 or len(inv.hotbar()) <= 1, "P2 tool did not cycle"
        finally:
            P2_KEYS.clear()
            P2_KEYS.update(old)
            g.state = "play"
        g.on_keydown(BUILD_KEY)                       # default bindings: decor opens
        assert g.state == "decor", g.state
        key(BUILD_KEY)
        assert g.state == "play"
        return "bound key wins"
    check("world: decor hotkey never steals a rebound key", decor_key_rebound)

    def decor_during_warp_fade():
        g.warp(AREA_TOWN, (20, 20))
        H.frames(g, 20)
        g.warp(AREA_FARM, (12, 12))
        g.update(H.DT)                                # iris still mostly closed
        assert g.fade > 0.5, g.fade
        g.on_keydown(BUILD_KEY)
        assert g.state == "decor"
        for _ in range(60):
            g._run_state("update", H.DT)
        assert g.fade == 0.0, f"iris frozen at {g.fade:.3f} in decor mode"
        g.draw()
        key(pygame.K_ESCAPE)
        assert g.state == "play"
        return "iris opens"
    check("world: warp iris opens while decorating", decor_during_warp_fade)

    def decor_palette():
        slots = g._world_decor_slots()
        for (dn, dl, *_r), r in zip(WA.DECOR, slots):
            lab = g._w_decor_label(dl, r.w - 6, (255, 255, 255))
            assert lab.get_width() <= r.w - 4, (dl, lab.get_width(), r.w)
            assert lab.get_height() <= g.ui.tiny.get_linesize() * 2
        bar = g._w_decor_bar_bg()
        assert not (bar.get_flags() & pygame.SRCALPHA) and bar.get_alpha() in (None, 255), \
            "decor bar must be opaque (HUD panels showed through)"
        from src.settings import SCREEN_H
        assert max(r.bottom for r in slots) <= SCREEN_H - 4, "slots run off the screen"
        return f"{len(slots)} full labels"
    check("world: decor palette labels + opaque bar", decor_palette)

    def meadow_daily_persist():
        g.warp(AREA_MEADOW, (32, 6))
        H.frames(g, 20)
        mead = g.world.area
        p1 = g.players[0]
        g._wl_seen, g._w_swing_seen = set(), set()
        lk = mead.lookout
        H.place(g, p1, lk[0], lk[1] + 1)
        p1.energy = 50
        g.player_action(0)
        H.settle(g)
        assert p1.energy == 50 + 15, p1.energy
        sw = mead.swing
        H.place(g, p1, sw[0], sw[1] + 1)
        g.player_action(0)
        H.settle(g)
        b = mead.bench
        H.place(g, p1, b[0], b[1] + 1)
        p1.fx, p1.fy = 0, 1
        g.player_action(0)
        H.settle(g)
        d1 = json.dumps(g._collect_save(), sort_keys=True)
        dd = json.loads(d1)["world_daily"]
        assert dd["lookout"] == [0] and dd["swing"] == [0] and dd["bench"] == [0], dd
        g.reset()                                     # "quit + relaunch"
        g._apply_save(json.loads(d1))
        g.state = "play"
        assert json.dumps(g._collect_save(), sort_keys=True) == d1, "world_daily round-trip"
        g.warp(AREA_MEADOW, (32, 6))
        H.frames(g, 20)
        p1 = g.players[0]
        H.place(g, p1, lk[0], lk[1] + 1)
        p1.energy = 50
        g.player_action(0)
        H.settle(g)
        assert p1.energy == 50, f"lookout re-granted after reload: {p1.energy}"
        # a save from an earlier day restores nothing (and old saves lack the key)
        old = json.loads(d1)
        old["world_daily"]["day"] = "0|0|0"
        g._on_load_world(old)
        assert not g._wl_seen and not g._w_swing_seen
        del old["world_daily"]
        g._on_load_world(old)
        assert not g._wl_seen
        return "once a day survives a relaunch"
    check("world: meadow daily energy persists across reload", meadow_daily_persist)

    def swing_west_side():
        g.warp(AREA_MEADOW, (20, 14))
        H.frames(g, 20)
        mead = g.world.area
        p1, p2 = g.players
        H.place(g, p2, 30, 20)
        sw = mead.swing
        for (x, y) in ((sw[0] - 1, sw[1] - 1), (sw[0] - 1, sw[1]), (sw[0] - 1, sw[1] + 1)):
            H.place(g, p1, x, y)
            p1.fx, p1.fy = 1, 0
            g._w_swing_amp = 1.0
            g.player_action(0)
            H.settle(g)
            assert g._w_swing_amp > 5, f"swing not pushed from {(x, y)}"
        # facing the trunk from the same tile is still the Promise Tree
        H.place(g, p1, sw[0] - 1, sw[1])
        p1.fx, p1.fy = -1, 0
        assert g._w_at_promise_tree(p1)
        # the bench's east side belongs to the bench
        b = mead.bench
        H.place(g, p1, b[0] + 1, b[1])
        p1.fx, p1.fy = -1, 0
        assert not g._w_at_promise_tree(p1)
        return "swing + bench reachable beside the tree"
    check("world: swing/bench not swallowed by the Promise Tree", swing_west_side)

    def promise_pill():
        # visual pass: world prompts now share ui_kit.key_pill's cream/wood style
        from src import ui_kit as K
        pill = g._w_hint_pill("Promised today", "heart")
        c = pill.get_at((pill.get_width() // 2, 3))
        assert tuple(c)[:3] == K.CREAM, f"label should be a cream key_pill, got {c}"
        e = pill.get_at((pill.get_width() // 2, 0))
        assert tuple(e)[:3] == K.WOOD, f"key_pill wooden rim expected, got {e}"
        return "cream key pill"
    check("world: Promise Tree label uses the key_pill prompt style", promise_pill)

    def lan_client_tip():
        had = "net_mode" in vars(g)
        old = getattr(g, "net_mode", None)
        warned = set(g._wh_warned)
        try:
            g.warp(AREA_FARM, (12, 12))
            g.net_mode = "client"
            g._wh_warned.discard("farm")
            g.ui.messages = []
            g._on_area_enter_world()
            assert not any("decorate" in m[0] for m in g.ui.messages), g.ui.messages
        finally:
            if had:
                g.net_mode = old
            else:
                vars(g).pop("net_mode", None)
            g._wh_warned = warned
        return "no host-only tip on a client"
    check("world: LAN client not told to press B", lan_client_tip)

    def creator_style():
        cr = g.creator
        saved = [dict(L) for L in cr.looks]
        cr.load(g.look)
        cr.update(H.DT)
        cr.draw(g.screen)
        cr.update(H.DT)
        cr.draw(g.screen)
        H.shot(g, "world_creator")
        f, _lab, y, left, right = cr._field_rows(1)[2]
        v0 = cr.looks[1][f]
        cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=right.center))
        assert cr.looks[1][f] != v0 or cr._count(f) == 1
        rows_bottom = max(r[3].bottom for r in cr._field_rows(0))
        from src import creator as C
        assert C.PANEL_Y + C.PANEL_H - rows_bottom < 40, "panel should hug its rows"
        assert cr._start_rect().bottom < 700 and cr._name_rect(0).bottom < rows_bottom
        cr.looks = saved
        g.state = "play"
        return "cosy creator"
    check("world: character creator restyle", creator_style)

    # ---------------------------------------------------------------- fix round 2
    def _creator_session(looks):
        """Open the creator on ``looks`` with start_new stubbed (records the looks
        instead of wiping the running game). Returns (creator, started list)."""
        started = []
        g.start_new = lambda lk: started.append([dict(L) for L in lk])
        cr = g.creator
        cr.load(looks)
        g.state = "create"
        cr.update(0.3)
        return cr, started

    def _creator_done(saved):
        vars(g).pop("start_new", None)                # back to Game.start_new
        g.creator.looks = saved
        g.state = "play"

    def _look(name):
        return {"name": name, "skin": 0, "hair_style": 0, "hair_color": 0, "shirt_color": 0}

    def creator_keyboard():
        from src import creator as C
        saved = [dict(L) for L in g.creator.looks]

        def kd(k, u="", mod=0):
            g.creator.handle_event(ev(pygame.KEYDOWN, key=k, mod=mod, unicode=u, scancode=0))
        try:
            cr, started = _creator_session([_look("Player 1"), _look("Player 2")])
            assert cr.cur == (0, C.ROW_NAME) and cr.focus is None
            kd(pygame.K_RETURN)                       # Enter on a name box -> typing
            assert cr.focus == 0 and cr.looks[0]["name"] == "", cr.looks[0]
            for ch in "Ben":
                kd(ord(ch.lower()), ch)
            kd(pygame.K_RETURN)
            assert cr.focus is None and cr.looks[0]["name"] == "Ben", cr.looks[0]
            kd(pygame.K_DOWN)                         # -> Skin row
            assert cr.cur == (0, 1), cr.cur
            v0 = cr.looks[0]["skin"]
            kd(pygame.K_RIGHT)
            assert cr.looks[0]["skin"] == (v0 + 1) % cr._count("skin")
            kd(pygame.K_a)                            # A/D work like the arrows
            assert cr.looks[0]["skin"] == v0
            for _ in range(4):                        # Tab: Skin -> ... -> P2 name
                kd(pygame.K_TAB)
            assert cr.cur == (1, C.ROW_NAME), cr.cur
            kd(pygame.K_TAB, mod=pygame.KMOD_SHIFT)   # Shift+Tab goes back
            assert cr.cur == (0, len(C.FIELDS)), cr.cur
            kd(pygame.K_RIGHT)                        # on a look row: changes the shirt
            kd(pygame.K_TAB)
            kd(pygame.K_d)                            # on a name row: hops panels / stays
            assert cr.cur == (1, C.ROW_NAME), cr.cur
            kd(pygame.K_UP)                           # wraps up to START
            assert cr.cur == (None, C.ROW_START), cr.cur
            cr.draw(g.screen)
            H.shot(g, "world_creator_keyboard")
            kd(pygame.K_RETURN)                       # Enter on START starts
            assert len(started) == 1, "Enter on START did not start the game"
            assert [L["name"] for L in started[0]] == ["Ben", "Player 2"], started
            # the footer tells keyboard players what to press
            assert "Enter" in C.FOOTER_HINT and "Arrows" in C.FOOTER_HINT
            assert g.ui.small.size(C.FOOTER_HINT)[0] < 1240
        finally:
            _creator_done(saved)
        return "Enter/Tab/arrows/WASD drive the creator"
    check("world: creator is keyboard-driven", creator_keyboard)

    def creator_name_glyphs():
        from src import creator as C
        saved = [dict(L) for L in g.creator.looks]
        try:
            cr, started = _creator_session([_look("Player 1"), _look("Player 2")])
            cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=cr._name_rect(1).center))
            assert cr.focus == 1
            for u in ("B", "e", "n", "ฟ", "é", "漢"):      # Thai, e-acute, Kanji
                cr.handle_event(ev(pygame.KEYDOWN, key=pygame.K_f, mod=0, unicode=u, scancode=0))
            assert cr.looks[1]["name"] == "Ben", repr(cr.looks[1]["name"])
            assert cr._warn_t > 0 and cr._warn_pi == 1, "no 'English letters only' note"
            cr.draw(g.screen)
            H.shot(g, "world_creator_glyph_note")
            cr.update(3.0)
            assert cr._warn_t == 0.0
            assert all(C.name_char_ok(c) for c in "Ben & Mai 2!")
            assert not any(C.name_char_ok(c) for c in "ฟé\t")
        finally:
            _creator_done(saved)
        return "ASCII only, with a note"
    check("world: creator name refuses glyphs the font lacks", creator_name_glyphs)

    def creator_empty_names():
        saved = [dict(L) for L in g.creator.looks]
        try:
            # clicking both default boxes then START: the players stay distinct
            cr, started = _creator_session([_look("Player 1"), _look("Player 2")])
            for pi in (0, 1):
                cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=cr._name_rect(pi).center))
            cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=cr._start_rect().center))
            assert [L["name"] for L in started[-1]] == ["Player 1", "Player 2"], started
            # emptying a custom name then leaving the box brings the old name back
            cr, started = _creator_session([_look("Ben"), _look("Player 2")])
            cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=cr._name_rect(0).center))
            for _ in range(5):
                cr.handle_event(ev(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0, unicode="\b",
                                   scancode=0))
            assert cr.looks[0]["name"] == ""
            cr.handle_event(ev(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
            assert cr.looks[0]["name"] == "Ben" and g.state == "create", cr.looks[0]
            cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=cr._name_rect(0).center))
            cr.looks[0]["name"] = "   "
            cr.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=cr._start_rect().center))
            assert [L["name"] for L in started[-1]] == ["Ben", "Player 2"], started
            assert all(L["name"] != "Farmer" for L in started[-1])
        finally:
            _creator_done(saved)
        return "never 'Farmer & Farmer'"
    check("world: creator empty name keeps the players distinct", creator_empty_names)

    def area_hints_persist():
        g.state = "play"
        g.warp(AREA_MEADOW, (20, 27))
        g.warp(AREA_FARM, (12, 12))
        H.frames(g, 3)
        g._wh_warned |= {"meadow", "farm", "lava"}
        d1 = json.dumps(g._collect_save(), sort_keys=True)
        hints = json.loads(d1)["world_hints"]
        assert hints == sorted(hints) and {"meadow", "farm", "lava"} <= set(hints), hints
        g.reset()                                     # "quit + relaunch"
        g._apply_save(json.loads(d1))
        g.state = "play"
        assert json.dumps(g._collect_save(), sort_keys=True) == d1, "world_hints round-trip"
        g.ui.messages = []
        g.warp(AREA_MEADOW, (20, 27))
        H.frames(g, 3)
        g.warp(AREA_FARM, (12, 12))
        H.frames(g, 3)
        said = [m[0] for m in g.ui.messages]
        assert not any("promise made together" in m or "decorate outdoors" in m for m in said), said
        # an old save has no key: every hint is fresh again (and nothing crashes)
        old = json.loads(d1)
        del old["world_hints"]
        g._on_load_world(old)
        assert g._wh_warned == set()
        old["world_hints"] = "junk"
        g._on_load_world(old)
        assert g._wh_warned == set()
        # a LAN client's resync merges, so a hint the client already saw stays seen
        g._wh_warned = {"meadow"}
        g._net_applying_world = True
        try:
            g._on_load_world(dict(old, world_hints=["farm"]))
        finally:
            g._net_applying_world = False
        assert g._wh_warned == {"meadow", "farm"}, g._wh_warned
        g.reset()                                     # restore this run's state
        g._apply_save(json.loads(d1))
        g.state = "play"
        H.frames(g, 2)
        return f"{len(hints)} hints kept"
    check("world: one-time area hints survive a relaunch", area_hints_persist)

    def lookout_pill_beside():
        g.warp(AREA_MEADOW, (32, 6))
        H.frames(g, 30)
        mead = g.world.area
        lk = mead.lookout
        p1, p2 = g.players
        H.place(g, p1, lk[0], lk[1] + 1)
        H.place(g, p2, lk[0] - 4, lk[1] + 3)
        H.frames(g, 30)
        g.state = "play"
        g.draw()
        H.shot(g, "world_lookout_pill")
        from src.ui import key_label
        # visual pass: the eye icon sits INSIDE the key_pill-style prompt, and the
        # prompt is centred on its anchor (it used to hang off to the left)
        pill = g._w_hint_pill("enjoy the view", "eye", key_label(P1_KEYS['action']))
        sx, sy = 600, 300
        px, py = g._w_hint_pill_pos(sx, sy, "eye", pill)
        pr = pygame.Rect(px, py, pill.get_width(), pill.get_height())
        assert abs(pr.centerx - sx) <= 1 and abs(pr.centery - sy) <= 1, (pr, sx, sy)
        # at the top of the map it stays 8 px clear of the clock card (not hugging it)
        # and keeps its anchor band, so it never drops onto the deck below
        clock = pygame.Rect(978, 0, 302, 110)
        px, py = g._w_hint_pill_pos(1016, 124, "eye", pill)
        pr = pygame.Rect(px, py, pill.get_width(), pill.get_height())
        assert pr.top >= clock.bottom + 8, (pr, clock)
        assert pr.top <= 124, "lookout pill dropped onto the deck"
        assert abs(pr.centerx - 1016) <= 1, pr
        # the Promise Tree prompt follows the same rule
        tx, ty = g._w_hint_pill_pos(sx, sy, "heart", pill)
        assert abs((tx + pill.get_width() // 2) - sx) <= 1
        return "prompt centred on its anchor"
    check("world: lookout hint pill sits beside its bubble", lookout_pill_beside)

    def decor_header_gap():
        import src.systems.world_system as WS
        g.warp(AREA_FARM, (12, 12))
        H.frames(g, 20)
        g.state = "play"
        g.on_keydown(BUILD_KEY)
        assert g.state == "decor", g.state
        g._wd["sel"] = 0
        g.draw()
        from src.settings import SCREEN_H
        head = g.ui.font.render("OUTDOOR DECOR", True, (255, 255, 255))
        by = SCREEN_H - g._DECOR_BAR_H
        x0 = 16 + head.get_width()
        dx = x0 + WS.DECOR_HEAD_GAP // 2
        assert WS.DECOR_HEAD_GAP >= 24
        bright = 0
        for x in list(range(x0 + 3, dx - 6)) + list(range(dx + 6, x0 + WS.DECOR_HEAD_GAP - 1)):
            for y in range(by + 5, by + 5 + head.get_height()):
                c = g.screen.get_at((x, y))
                bright += c[0] > 150
        assert bright == 0, f"header text runs into the selection ({bright} px)"
        key(BUILD_KEY)
        assert g.state == "play"
        return f"{WS.DECOR_HEAD_GAP}px gap + diamond"
    check("world: decor bar header keeps a gap", decor_header_gap)

    g.warp(AREA_FARM, (12, 12))
    g.state = "play"
    return "world domain checks done"
