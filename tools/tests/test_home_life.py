"""Home Life checks (2026-09-28): the house cat, the aquarium and growing
house plants (systems/homelife_system.py, homelife.py, homelife_ui.py).

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import json
import random

import pygame


def run(g, check, H):
    from src.settings import AREA_HOME, TILE, P1_KEYS
    from src import furniture as F, homeiso, homelife as L

    area0 = g.world.current
    if g.world.current != AREA_HOME:
        g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    g.state = "play"
    home0 = g.world.home_furniture
    pos0 = [(p.x, p.y, p.fx, p.fy, p.energy, p.inv.selected) for p in g.players]
    life0 = (g.cat_name, g.cat_love, g._cat_day, list(g._cat_pets), list(g._life_relax))
    time0 = (g.time.minutes, g.time.day)
    area = g.world.area
    ev = pygame.event.Event

    def layout(pieces):
        g.world.home_furniture = [F.Placed(k, x, y, r, 0) for (k, x, y, r) in pieces]
        g.world.refresh_home_solids()
        g.cat = None
        for p in g.players:
            p.sitting = None

    def put(idx, tile, face):
        p = g.players[idx]
        p.sitting = None
        p.x, p.y = tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2
        p.fx, p.fy = face

    def tick(n=1, dt=1 / 30.0):
        for _ in range(n):
            g.state = "play"
            g.update(dt)

    def hold(p, entry):
        if entry not in p.inv.hotbar():
            p.inv.set_slot(0, entry)
        p.inv.selected = p.inv.hotbar().index(entry)

    def key(k, uni=""):
        g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode=uni, scancode=0))
        g._run_state("update", 1 / 30.0)

    try:
        # ------------------------------------------------ the cat
        def cat_needs_tower():
            layout([("sofa", 8, 1, 0), ("rug", 5, 3, 0), ("bed", 2, 2, 0)])
            put(0, (6, 6), (0, 1))
            put(1, (7, 6), (0, 1))
            tick(10)
            assert g.cat is None, "a cat appeared without a cat tower"
            g.world.home_furniture.append(F.Placed("cat_tower", 11, 5, 0, 4))
            g.world.refresh_home_solids()
            tick(3)
            assert g.cat is not None, "no cat after placing a cat tower"
            c = g.cat
            assert c.perch and c.perch[0].kind == "cat_tower" and c.z >= 30, \
                "the cat should start curled up on its tower"
            tw = next(q for q in g.world.home_furniture if q.kind == "cat_tower")
            g.world.home_furniture.remove(tw)
            g.world.refresh_home_solids()
            tick(2)
            assert g.cat is None, "the cat stayed after the tower was sold"
            return "only with a tower"
        check("home life: the cat lives here only with a cat tower", cat_needs_tower)

        def cat_never_on_solid():
            random.seed(7)
            layout([("sofa", 8, 1, 0), ("armchair", 12, 4, 1), ("rug", 5, 3, 0),
                    ("bed", 2, 2, 0), ("cat_tower", 11, 6, 0), ("dining_table", 4, 7, 0),
                    ("bookshelf", 11, 1, 0), ("plant", 1, 8, 0), ("counter", 1, 4, 0)])
            put(0, (6, 6), (0, 1))
            put(1, (9, 5), (0, 1))
            seen, perched, walked = set(), set(), 0
            for step in range(30 * 150):             # 2.5 minutes of cat life
                g.time.minutes = 10 * 60 if step < 30 * 100 else 22 * 60
                tick()
                c = g.cat
                assert c is not None
                seen.add(c.pose)
                if c.pose == "walk":
                    walked += 1
                if c.perch:
                    perched.add(c.perch[0].kind if c.perch[0] else "rug")
                if c.z <= 0.5 and not c.hop:
                    assert g._cat_free(int(c.x), int(c.y)), ("cat on a solid tile", c.x, c.y)
                    assert 1 <= c.x < area.w - 1 and 1 <= c.y < area.h - 1
                if step % 300 == 0:
                    homeiso.draw_room(g)
            assert walked > 0 and "sleep" in seen and "sit" in seen, seen
            # furniture dropped right on the cat: it pops out onto free floor
            c = g.cat
            c.perch, c.hop, c.path, c.z = None, None, [], 0.0
            c.x, c.y = 6.5, 5.5
            g.world.home_furniture.append(F.Placed("chest", 6, 5, 0, 0))
            g.world.refresh_home_solids()
            tick(2)
            assert g._cat_free(int(g.cat.x), int(g.cat.y)), "cat stuck inside a chest"
            return f"poses {sorted(seen)}, perched on {sorted(perched)}"
        check("home life: the cat never stands on solid tiles", cat_never_on_solid)

        def cat_every_pose_draws():
            layout([("cat_tower", 11, 6, 0), ("sofa", 8, 1, 0)])
            tick(1)
            c = g.cat
            ox, oy = homeiso.origin(area)
            n = 0
            for pose in L.POSES:
                for face in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    for fr in range(L.FRAMES[pose]):
                        img = L.cat_frame(pose, face, fr)
                        assert img.get_size() == (L.CAT_W, L.CAT_H)
                        assert pygame.mask.from_surface(img).count() > 60, (pose, face)
                        n += 1
            # the cat really shows up in the room where it stands
            c.perch, c.hop, c.path, c.z = None, None, [], 0.0
            c.x, c.y, c.pose, c.face = 6.5, 5.5, "sit", (1, 0)
            homeiso.draw_room(g)
            sx, sy = homeiso.proj(ox, oy, c.x, c.y)
            hits = sum(1 for dx in range(-8, 9) for dy in range(-22, 0)
                       if tuple(g.screen.get_at((sx + dx, sy + dy)))[:3] in (L.FUR, L.PATCH))
            assert hits > 20, f"cat fur not on screen ({hits})"
            return f"{n} frames, {hits} fur px in the room"
        check("home life: every cat pose / facing draws", cat_every_pose_draws)

        def pet_both_players():
            layout([("cat_tower", 11, 6, 0)])
            tick(1)
            g._cat_day, g._cat_pets = None, [0, 0]
            love0 = g.cat_love
            out = []
            for idx in (0, 1):
                c = g.cat
                c.perch, c.hop, c.path, c.next, c.z = None, None, [], None, 0.0
                c.mode, c.t = "sit", 30.0
                put(idx, (5, 5), (1, 0))
                put(1 - idx, (2, 8), (0, 1))
                c.x, c.y = 6.5, 5.5                  # right in front of the farmer
                p = g.players[idx]
                p.energy = 50
                g.state = "play"
                g.player_action(idx)
                assert g._cat_pets[idx] == 1, (idx, g._cat_pets)
                assert p.energy > 50, "petting gave no energy"
                assert g.cat.mode == "happy", g.cat.mode
                out.append(p.energy - 50)
            assert g.cat_love == min(100, love0 + 2), (love0, g.cat_love)
            # 4th pet of the day: still purrs, no more energy
            p = g.players[0]
            put(0, (5, 5), (1, 0))
            for _ in range(3):
                g.cat.mode, g.cat.x, g.cat.y = "sit", 6.5, 5.5
                g.player_action(0)
            e = p.energy
            g.cat.mode, g.cat.x, g.cat.y = "sit", 6.5, 5.5
            g.player_action(0)
            assert p.energy == e and g._cat_pets[0] == 5, (p.energy, e, g._cat_pets)
            # facing the tower opens the card; "call" makes the cat come for pets
            put(0, (10, 6), (1, 0))
            g.player_action(0)
            assert g.state == "cattower" and g.cat_card, g.state
            g.draw()
            key(P1_KEYS["action"])                   # "Call Mochi for pets"
            assert g.state == "play"
            g.cat.mode = "sit"
            for _ in range(30 * 8):
                tick()
                if g._cat_pets[0] > 5:
                    break
            assert g._cat_pets[0] > 5, "the called cat never came for pets"
            return f"energy +{out}, love {g.cat_love}"
        check("home life: both farmers can pet the cat", pet_both_players)

        def cat_greets_at_the_door():
            layout([("cat_tower", 11, 6, 0), ("sofa", 8, 1, 0)])
            tick(2)
            c = g.cat
            c.mode, c.t = "sit", 30.0
            sp = H.spawns_by_area(g)
            from src.settings import AREA_FARM
            g.warp(AREA_FARM, sp[AREA_FARM])
            g.warp(AREA_HOME, sp[AREA_HOME])
            c = g.cat
            assert c is not None and (c.hop or c.path), "the cat ignored the door"
            p = g.players[0]
            for _ in range(30 * 6):
                tick()
                if (c.x - p.x / TILE) ** 2 + (c.y - p.y / TILE) ** 2 < 1.6 ** 2 and not c.path:
                    break
            d = ((c.x - p.x / TILE) ** 2 + (c.y - p.y / TILE) ** 2) ** 0.5
            assert d < 1.6 and c.z == 0, f"cat {d:.2f} tiles from the door"
            return f"trotted to {d:.2f} tiles"
        check("home life: the cat greets you at the door", cat_greets_at_the_door)

        def tower_second_press_opens_card():
            layout([("cat_tower", 11, 6, 0)])
            tick(1)
            c = g.cat                                  # napping on its tower
            put(0, (10, 6), (1, 0))
            g.player_action(0)
            assert g.state == "play" and c.mode == "happy", (g.state, c.mode)
            g.player_action(0)
            assert g.state == "cattower", g.state
            key(pygame.K_ESCAPE)
            return "pet, then the card"
        check("home life: pet the cat on its tower, press again for its card",
              tower_second_press_opens_card)

        def cat_card_rename():
            layout([("cat_tower", 11, 6, 0)])
            tick(1)
            g._open_cat_card(0)
            assert g.state == "cattower"
            key(P1_KEYS["down"])
            key(P1_KEYS["action"])                   # Rename
            assert g.cat_card.naming == ""
            for ch in "Tofu":
                key(getattr(pygame, f"K_{ch.lower()}"), ch)
            key(pygame.K_RETURN)
            g.draw()
            assert g.cat_name == "Tofu", g.cat_name
            key(pygame.K_ESCAPE)
            assert g.state == "play"
            return "renamed to Tofu"
        check("home life: the tower card renames the cat", cat_card_rename)

        def sitting_farmer_evicts_cat():
            layout([("cat_tower", 11, 6, 0), ("armchair", 6, 4, 0)])
            tick(1)
            c = g.cat
            q = next(o for o in g.world.home_furniture if o.kind == "armchair")
            c.path, c.hop, c.next = [], None, None
            c.x, c.y, c.z = 6.5, 4.5, 16
            c.perch, c.mode, c.t = (q, 6.5, 4.5, 16), "sleep", 30.0
            spots = [s for s in g._cat_perches() if s[1] is q]
            assert spots, "a free armchair should be a nap spot"
            put(0, (6, 5), (0, -1))
            g.interact_furniture(g.players[0], q)
            assert g.players[0].sitting, "the farmer didn't sit"
            assert not [s for s in g._cat_perches() if s[1] is q], "occupied seat offered"
            tick(20)
            assert g.cat.perch is None or g.cat.perch[0] is not q, "cat still on the lap"
            g.players[0].sitting = None
            return "hopped off"
        check("home life: the cat never naps on a farmer's seat", sitting_farmer_evicts_cat)

        def lan_snapshot_has_cat():
            layout([("cat_tower", 11, 6, 0)])
            tick(1)
            c = g.cat
            c.perch, c.hop, c.path, c.z = None, None, [], 0.0
            c.x, c.y, c.face = 4.25, 6.5, (0, -1)
            c.pose = "walk"
            snap = json.loads(json.dumps(g._collect_snapshot()))
            assert isinstance(snap.get("CAT"), list), snap.get("CAT")
            mode = g.net_mode
            try:
                g.cat = None
                g.net_mode = "client"
                g._apply_snapshot(snap)
                c2 = g.cat
                assert c2 is not None and abs(c2.x - 4.25) < 1e-6 and c2.face == (0, -1), c2
                assert c2.pose == "walk"
                g._on_client_update_life(0.05)
                homeiso.draw_room(g)
                del snap["CAT"]                      # an old host: leave the cat alone
                g._apply_snapshot(snap)
                assert g.cat is c2
            finally:
                g.net_mode = mode
            g.cat = None
            return f"CAT={json.dumps(g._collect_snapshot().get('CAT'))}"
        check("home life: LAN snapshot round-trip carries the cat", lan_snapshot_has_cat)

        # ------------------------------------------------ the aquarium
        def aquarium_fish_only_cap6_persist():
            layout([("aquarium", 6, 4, 0), ("cat_tower", 11, 6, 0)])
            tank = g.world.home_furniture[0]
            p = g.players[0]
            p.inv.add("sardine", 5)
            p.inv.add("carp", 3)
            p.inv.add("wood", 2)
            ok, msg = g._aqua_op(0, tank, "put", "wood")
            assert not ok and "wood" not in tank.store, "wood went in the tank"
            ok, msg = g._aqua_op(0, tank, "put", "parsnip")
            assert not ok, "a parsnip swam in"
            for _ in range(5):
                assert g._aqua_op(0, tank, "put", "sardine")[0]
            assert g._aqua_op(0, tank, "put", "carp")[0]
            ok, msg = g._aqua_op(0, tank, "put", "carp")
            assert not ok and "full" in msg.lower(), msg
            assert sum(tank.store.values()) == 6, tank.store
            ok, _ = g._aqua_op(0, tank, "take", "sardine")
            assert ok and tank.store["sardine"] == 4
            assert g._aqua_op(0, tank, "put", "sardine")[0]
            # the menu shows only fish and draws the swimming tank
            put(0, (6, 5), (0, -1))
            g.player_action(0)
            assert g.state == "aquarium" and g.aqua_menu is not None, g.state
            m = g.aqua_menu
            assert all(i in __import__("src.fishing", fromlist=["FISH"]).FISH
                       for i in m.bag_items()), m.bag_items()
            for k in (P1_KEYS["right"], P1_KEYS["down"], P1_KEYS["action"], pygame.K_f,
                      P1_KEYS["left"], P1_KEYS["left"]):
                key(k)
                g.draw()
            key(pygame.K_ESCAPE)
            for _ in range(10):
                g._run_state("update", 1 / 30.0)
            assert g.state == "play"
            # the room paints the fish (LIVE_ART) and they persist through a save
            homeiso.draw_room(g)
            before = dict(tank.store)
            d = json.loads(json.dumps(g._collect_save()))
            g.world.home_furniture = []
            g._apply_save(d)
            tank2 = next(q for q in g.world.home_furniture if q.kind == "aquarium")
            assert tank2.store == before, (tank2.store, before)
            assert len(g._tank_fish(tank2)) == 6
            return f"tank {before}"
        check("home life: aquarium takes only fish, 6 max, survives save/load",
              aquarium_fish_only_cap6_persist)

        def aquarium_relax_once_a_day():
            layout([("aquarium", 6, 4, 0)])
            tank = g.world.home_furniture[0]
            g._life_relax = [None, None]
            p = g.players[0]
            p.energy = 40
            g._aqua_op(0, tank, "feed")
            assert p.energy == 40 + 12, p.energy
            assert (6, 4) in g._aqua_feed
            g._aqua_op(0, tank, "feed")
            assert p.energy == 52, "relaxed twice in one day"
            fk = L.feed_curve(2.0)
            assert fk == 1.0 and L.feed_curve(None) == 0.0 and L.feed_curve(20) == 0.0
            # fish rise toward the flakes when fed
            z0 = L.fish_pos("carp", 0, (6, 4), (6.12, 4.12, 6.88, 4.88), 3.0, 0.0)[2]
            z1 = L.fish_pos("carp", 0, (6, 4), (6.12, 4.12, 6.88, 4.88), 3.0, 1.0)[2]
            assert z1 > z0 + 0.5 or z1 >= L.TANK_WL - 6, (z0, z1)
            return "relaxed once"
        check("home life: aquarium feeding relaxes once a day", aquarium_relax_once_a_day)

        # ------------------------------------------------ plants
        def plants_grow_with_water():
            layout([("plant", 6, 4, 0), ("dining_table", 8, 4, 0)])
            pl = g.world.home_furniture[0]
            cac = F.Placed("cactus_small", 8, 4, 0, 0, ox=-0.2)
            g.world.home_furniture.append(cac)
            p = g.players[0]
            put(0, (6, 5), (0, -1))
            stages = []
            for day in range(6):
                g.state = "play"
                g.player_action(0)                   # water it
                assert pl.data.get("w") == 1, pl.data
                g._plant_tend(0, p, cac)
                g.player_action(0)                   # twice: no double watering
                g.on_new_day()
                g.state = "play"
                stages.append(g._plant_stage(pl))
            assert stages == [1, 1, 2, 2, 3, 3], stages
            assert g._plant_stage(cac) == 3, cac.data
            # a dry day doesn't grow
            g2 = pl.data.get("g")
            g.on_new_day()
            assert pl.data.get("g") == g2
            # the watering can works too
            pl2 = F.Placed("plant", 3, 4, 0, 0)
            g.world.home_furniture.append(pl2)
            g.world.refresh_home_solids()
            put(0, (3, 5), (0, -1))
            hold(p, ("tool", "watering_can"))
            g.player_action(0)
            assert pl2.data.get("w") == 1, pl2.data
            homeiso.draw_room(g)
            return f"stages {stages}"
        check("home life: plants grow with daily watering", plants_grow_with_water)

        def vase_wilts_and_refreshes():
            layout([("dining_table", 8, 4, 0)])
            vase = F.Placed("vase_flowers", 8, 4, 0, 0)
            g.world.home_furniture.append(vase)
            p = g.players[0]
            for _ in range(5):                       # an untouched vase never wilts
                g.on_new_day()
            assert not vase.data, vase.data
            g._plant_tend(0, p, vase)
            g.on_new_day()
            assert vase.data.get("g") == 1
            for _ in range(3):
                g.on_new_day()
            assert vase.data.get("wilt"), vase.data
            homeiso.draw_room(g)
            g._plant_tend(0, p, vase)                # water can't save wilted flowers
            assert vase.data.get("wilt")
            p.inv.add("sweet_pea", 1)
            hold(p, ("item", "sweet_pea"))
            g._plant_tend(0, p, vase)
            assert p.inv.count("sweet_pea") == 0, "the fresh flowers weren't used"
            assert not vase.data.get("wilt") and vase.data.get("fc"), vase.data
            homeiso.draw_room(g)
            return f"fresh {vase.data}"
        check("home life: vase flowers wilt, fresh ones revive it", vase_wilts_and_refreshes)

        def save_roundtrip_life():
            g.cat_name, g.cat_love = "Mochi", 7
            g._cat_day, g._cat_pets = (1, 0, 3), [2, 1]
            d = json.loads(json.dumps(g._collect_save()))
            s1 = json.dumps({k: d[k] for k in ("cat_name", "cat_love", "cat_day", "cat_pets",
                                               "life_relax")}, sort_keys=True)
            g._apply_save(d)
            d2 = g._collect_save()
            s2 = json.dumps({k: d2[k] for k in ("cat_name", "cat_love", "cat_day", "cat_pets",
                                                "life_relax")}, sort_keys=True)
            assert s1 == s2, (s1, s2)
            return s1
        check("home life: cat / relax state saves", save_roundtrip_life)
    finally:
        g.world.home_furniture = home0
        g.world.refresh_home_solids()
        g.cat = None
        g.aqua_menu = g.cat_card = None
        (g.cat_name, g.cat_love, g._cat_day, g._cat_pets, g._life_relax) = (
            life0[0], life0[1], life0[2], life0[3], life0[4])
        g.time.minutes = time0[0]
        for p, (x, y, fx, fy, e, sel) in zip(g.players, pos0):
            p.sitting = None
            p.x, p.y, p.fx, p.fy, p.energy, p.inv.selected = x, y, fx, fy, e, sel
        if g.world.current != area0:
            sp = H.spawns_by_area(g).get(area0)
            if sp:
                g.warp(area0, sp)
        g.state = "play"
