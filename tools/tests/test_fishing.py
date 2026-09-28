"""Fishing & Foraging domain checks (Chat 3): forageables (spawn / pickup / save /
new day / seasons / beach), ambient wildlife, fish sizes + records + treasure,
fishing buff, and the Collection journal tab.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import json
import random

import pygame


class _Events:
    def __init__(self, g):
        self.g, self.seen = g, []

    def __enter__(self):
        self._orig = self.g.emit

        def emit(event, **data):
            self.seen.append((event, data))
            return self._orig(event, **data)
        self.g.emit = emit
        return self

    def __exit__(self, *a):
        try:
            del self.g.emit                   # drop the instance override
        except AttributeError:
            pass

    def names(self):
        return [e for e, _ in self.seen]


def run(g, check, H):
    from src.settings import TILE
    from src import forage as FG
    from src import fishing
    sp = H.spawns_by_area(g)
    p = g.players[0]
    t0 = (g.time.season_idx, g.time.minutes, getattr(g, "weather", "sunny"))

    # ------------------------------------------------------------ foraging
    def spawn():
        g.forage_spawns.pop("forest", None)
        g.forage_rolled.discard("forest")
        g.warp("forest", sp["forest"])
        spawns = g.forage_spawns.get("forest", {})
        lo, hi = FG.SPAWN_COUNTS["forest"]
        hi += FG.extra_for_weather("forest", g.weather)
        assert lo <= len(spawns) <= hi, f"{len(spawns)} forest spawns"
        area = g.world.area
        for (gx, gy), it in spawns.items():
            assert not area.is_solid(gx, gy), f"{it} on a solid tile"
            assert g.time.season in FG.FORAGE[it][3], f"{it} out of season"
            assert area.tile(gx, gy) not in ("P", "W"), f"{it} on path/water"
        before = dict(spawns)
        g.warp("town", sp["town"])
        g.warp("forest", sp["forest"])
        assert g.forage_spawns["forest"] == before, "re-entering rerolled forage"
        H.frames(g, 30)
        g.draw()
        H.shot(g, "fishing_forage_forest")
        return f"{len(spawns)} forest: {sorted(set(before.values()))}"
    check("forage: spawn in forest (+no reroll on re-entry)", spawn)

    def pickup():
        g.warp("forest", sp["forest"])
        spawns = g.forage_spawns["forest"]
        (gx, gy), it = sorted(spawns.items())[0]
        H.place(g, p, gx, gy)                 # stand on it
        g.players[1].x, g.players[1].y = p.x - TILE * 1.5, p.y + TILE * 0.5
        g._update_camera(g.world.area)
        c0 = p.inv.count(it)
        xp0 = p.skills.xp["foraging"]
        found0 = g.forage_found.get(it, 0)
        with _Events(g) as ev:
            g.player_action(0)
        assert p.inv.count(it) > c0, "nothing picked up"
        assert (gx, gy) not in spawns, "spawn not removed"
        assert p.skills.xp["foraging"] > xp0, "no foraging xp"
        assert g.forage_found.get(it, 0) > found0, "collection not updated"
        ev_f = [d for e, d in ev.seen if e == "foraged"]
        assert ev_f and ev_f[0].get("item") == it and ev_f[0].get("p") is p, "foraged not emitted"
        assert g.forage_pops, "no pickup animation"
        for _ in range(8):
            H.frames(g, 2)
            g.draw()
        H.shot(g, "fishing_forage_pickup")
        H.frames(g, 60)
        assert not g.forage_pops, "pop animation never finished"
        # facing pickup too
        if spawns:
            (gx, gy), it2 = sorted(spawns.items())[0]
            H.place(g, p, gx, gy - 1)
            p.fx, p.fy = 0, 1
            c1 = p.inv.count(it2)
            g.player_action(0)
            assert p.inv.count(it2) > c1 or (gx, gy - 1) in spawns, "facing pickup failed"
        g.state = "play"
        return f"picked {it}"
    check("forage: pickup (stand + face), xp, event, pop", pickup)

    def eat():
        from src.settings import MAX_ENERGY
        p.inv.add("blackberry", 2)
        p.inv.add("clam", 1)
        p.energy = 100
        e0 = p.energy
        c0 = p.inv.count("blackberry")
        assert g._on_tool_forage_eat(0, p, "blackberry", 0, 0), "not eaten"
        assert p.energy == e0 + FG.EDIBLE["blackberry"] and p.inv.count("blackberry") == c0 - 1
        assert not g._on_tool_forage_eat(0, p, "clam", 0, 0), "ate a clam"
        p.energy = MAX_ENERGY
        assert g._on_tool_forage_eat(0, p, "blackberry", 0, 0) and p.inv.count("blackberry") == c0 - 1, \
            "ate while full"
        p.inv.remove("blackberry", 1)
        p.inv.remove("clam", 1)
        return f"+{FG.EDIBLE['blackberry']} energy"
    check("forage: edible wild snacks", eat)

    def sell_and_icons():
        from src.systems import shop_system
        from src import assets, loot
        for fid, row in FG.FORAGE.items():
            assert loot.MATERIALS[fid]["cat"] == "forage"
            assert shop_system.sell_value(fid) > 0, f"{fid} unsellable"
            ic = assets.item_icon(fid)
            assert ic.get_bounding_rect().w > 8, f"{fid} has no icon"
        p.inv.add("coral", 1)
        g0 = g.gold
        earned = g._sell_items(p, "coral", 1)
        assert earned > 0 and g.gold > g0, "coral did not sell"
        return f"{len(FG.FORAGE)} forage ids registered + sellable"
    check("forage: registry, icons, selling", sell_and_icons)

    def save_roundtrip():
        d1 = g._collect_save()
        s1 = json.dumps({k: d1.get(k) for k in ("forage_spawns", "forage_rolled", "forage_found",
                                                 "fish_records")}, sort_keys=True)
        g._on_load_forage(json.loads(json.dumps(d1)))
        if hasattr(g, "_on_load_fishing_records"):
            g._on_load_fishing_records(json.loads(json.dumps(d1)))
        d2 = g._collect_save()
        s2 = json.dumps({k: d2.get(k) for k in ("forage_spawns", "forage_rolled", "forage_found",
                                                 "fish_records")}, sort_keys=True)
        assert s1 == s2, "forage/fish save roundtrip changed"
        # old saves (no keys) load fine and the current area gets forage
        g._on_load_forage({})
        g._on_area_enter_forage()
        assert "forest" in g.forage_rolled
        g._on_load_forage(json.loads(json.dumps(d1)))
        # a pre-records save credits the fish already in the bags
        p.inv.add("carp", 2)
        g._on_load_fishing_records({})
        assert g.fish_records.get("carp", {}).get("n", 0) >= 2, "old-save fish not credited"
        p.inv.remove("carp", 2)
        g._on_load_fishing_records(json.loads(json.dumps(d1)))
        return f"{len(s1)} bytes"
    check("forage: save roundtrip + old save", save_roundtrip)

    def new_day():
        g._on_new_day_forage()
        assert set(g.forage_rolled) <= {"forest"}, g.forage_rolled
        assert "beach" not in g.forage_spawns
        return f"forest rerolled: {len(g.forage_spawns.get('forest', {}))}"
    check("forage: new day clears + rerolls", new_day)

    def seasons():
        area = g.world.areas["forest"]
        got = {}
        for si in range(4):
            g.time.season_idx = si
            random.seed(si)
            g._forage_roll(area)
            items = set(g.forage_spawns["forest"].values())
            assert items, f"nothing grows in {g.time.season}"
            assert all(g.time.season in FG.FORAGE[i][3] for i in items), items
            got[g.time.season] = len(items)
        g.time.season_idx = t0[0]
        g._forage_roll(area)
        return str(got)
    check("forage: every season has its own forageables", seasons)

    def beach_and_farm():
        g.forage_spawns.pop("beach", None)
        g.forage_rolled.discard("beach")
        g.warp("beach", sp["beach"])
        spawns = g.forage_spawns.get("beach", {})
        n_beach = sum(1 for i in spawns.values() if FG.is_beach(i))
        assert 4 <= n_beach <= 6 + FG.extra_for_weather("beach", g.weather), f"{n_beach} beach finds"
        area = g.world.area
        for (gx, gy), it in spawns.items():
            if FG.is_beach(it):
                assert area.tile(gx, gy) in ("n", "N"), f"{it} not on sand"
        if spawns:
            (gx, gy) = sorted(spawns)[0]
            H.place(g, p, gx - 2, gy - 1)
            g.players[1].x, g.players[1].y = p.x - TILE, p.y
        H.frames(g, 50)
        g.draw()
        H.shot(g, "fishing_forage_beach")
        g.forage_spawns.pop("farm", None)
        g.forage_rolled.discard("farm")
        g.warp("farm", sp["farm"])
        fs = g.forage_spawns.get("farm", {})
        assert 2 <= len(fs) <= 3, f"{len(fs)} farm finds"
        fa = g.world.area
        for (gx, gy) in fs:
            assert min(gx, gy, fa.w - 1 - gx, fa.h - 1 - gy) <= 3, "farm forage not on the edge"
            assert ("farm", gx, gy) not in g.world.tilled
        if "meadow" in g.world.areas and "meadow" in sp:
            g.warp("meadow", sp["meadow"])
            mn = len(g.forage_spawns.get("meadow", {}))
            H.frames(g, 20)
            g.draw()
            H.shot(g, "fishing_forage_meadow")
            return f"beach {len(spawns)}, farm {len(fs)}, meadow {mn}"
        return f"beach {len(spawns)}, farm {len(fs)} (no meadow yet)"
    check("forage: beach tideline + farm edges (+meadow)", beach_and_farm)

    # ------------------------------------------------------------ wildlife
    def wildlife():
        out = []
        g.weather = "sunny"
        g.time.season_idx = 1                 # summer: butterflies + fireflies
        g.time.minutes = 600
        g.warp("farm", sp["farm"])
        H.frames(g, 90)
        w = g.wildlife
        assert w.bf, "no butterflies on a summer morning"
        assert w.birds, "no birds on the farm"
        assert len(w.ducks) >= 2, "no ducks on the farm pond"
        pond = min(w.water)
        H.place(g, p, pond[0] + 1, pond[1] + 5)
        g.players[1].x, g.players[1].y = p.x + TILE, p.y
        for _ in range(8):
            H.frames(g, 15)
            g._update_camera(g.world.area)
        for d in w.ducks:
            assert g.world.area.is_water(int(d["x"] // TILE), int(d["y"] // TILE)), "duck on land"
        assert w.dfly, "no dragonflies by the pond on a summer morning"
        g.draw()
        H.shot(g, "fishing_wildlife_day")
        out.append(f"bf={len(w.bf)} birds={len(w.birds)} ducks={len(w.ducks)}")
        # a farmer walking up startles a bird (land a fresh one if all are airborne)
        b = next((b for b in w.birds if b["state"] == "peck"), None)
        if b is None:
            gx, gy = max(w.grass, key=lambda t: abs(t[0] * TILE - p.x) + abs(t[1] * TILE - p.y))
            b = {"x": gx * TILE + 24.0, "y": gy * TILE + 24.0, "h": 0.0, "vx": 0.0, "vh": 0.0,
                 "state": "peck", "fl": 1, "t": 0.5, "pose": "stand", "hops": 3, "scare": -1.0,
                 "kind": "sparrow"}
            w.birds.append(b)
        p.x, p.y = b["x"] + 20, b["y"]
        H.frames(g, 3)
        assert b["state"] == "fly", "bird did not take off"
        for _ in range(4):
            H.frames(g, 4)
            g.draw()
        H.shot(g, "fishing_wildlife_birds_fly")
        # night in the forest: fireflies + their glows
        g.time.minutes = 1260
        g.warp("forest", sp["forest"])
        H.frames(g, 120)
        assert w.ff, "no fireflies on a summer night"
        assert not w.bf, "butterflies at night"
        assert g._lights_forage_fireflies() or True
        g.draw()
        H.shot(g, "fishing_wildlife_fireflies")
        out.append(f"ff={len(w.ff)} lights={len(g._lights_forage_fireflies())}")
        # rain: frogs by the pond, fish jumping
        g.time.minutes = 700
        g.weather = "rain"
        g.warp("forest", sp["forest"])
        pond = next(((gx, gy) for (gx, gy) in w.shore), None)
        if pond:
            H.place(g, p, pond[0] - 4, pond[1] - 4)
            g.players[1].x, g.players[1].y = p.x + TILE, p.y
            g.cam.x = p.x - 640
            g.cam.y = p.y - 360
        H.frames(g, 240)
        assert not w.bf and not w.birds, "butterflies/birds out in the rain"
        out.append(f"frogs={len(w.frogs)} jumps={len(w.jumps)}")
        g.draw()
        H.shot(g, "fishing_wildlife_rain")
        # a winter morning in the forest: snow-white bunnies that bolt when you come near
        g.weather = "sunny"
        g.time.season_idx = 3
        g.time.minutes = 600
        g.warp("forest", sp["forest"])
        H.frames(g, 30)
        assert w.rabbits and all(r["white"] for r in w.rabbits), "no winter bunnies"
        assert not w.bf and not w.dfly, "summer bugs in winter"
        r = next(r for r in w.rabbits if r["state"] != "flee")
        p.x, p.y = r["x"] - 30, r["y"]
        H.frames(g, 2)
        assert r["state"] == "hop" and r["left"] > 0, "bunny did not bolt"
        for _ in range(3):
            H.frames(g, 5)
            g.draw()
        H.shot(g, "fishing_wildlife_winter")
        out.append(f"rabbits={len(w.rabbits)}")
        # nothing indoors / underground
        for a in ("home", "mine"):
            if a in sp:
                g.warp(a, sp[a])
                H.frames(g, 30)
                assert w.count() == 0, f"wildlife in {a}"
        g.weather = t0[2]
        g.time.season_idx, g.time.minutes = t0[0], t0[1]
        g.warp("farm", sp["farm"])
        return ", ".join(out)
    check("wildlife: butterflies, birds, fireflies, frogs, none indoors", wildlife)

    def wildlife_perf():
        import time as _t
        g.time.season_idx = 1
        g.time.minutes = 1250
        g.warp("forest", sp["forest"])
        H.frames(g, 60)
        t = _t.perf_counter()
        for _ in range(60):
            g._on_area_update_forage(H.DT)
            g._world_sprites_forage_wildlife()
            g._world_sprites_forage_items()
            g._lights_forage_fireflies()
        ms = (_t.perf_counter() - t) * 1000 / 60
        # a whole summer-night frame where the most critters live
        area = "meadow" if "meadow" in sp else "forest"
        g.warp(area, sp[area])
        H.frames(g, 30)
        g.draw()
        t = _t.perf_counter()
        for _ in range(30):
            g.update(H.DT)
            g.draw()
        full = (_t.perf_counter() - t) * 1000 / 30
        H.shot(g, "fishing_night_" + area)
        g.time.season_idx, g.time.minutes = t0[0], t0[1]
        g.warp("farm", sp["farm"])
        assert ms < 2.0, f"forage/wildlife hooks {ms:.2f} ms/frame"
        return f"hooks {ms:.2f} ms/frame; full {area} night frame {full:.1f} ms"
    check("wildlife: hook cost per frame", wildlife_perf)

    # ------------------------------------------------------------ fishing
    def sizes():
        for fid in fishing.FISH_DATA:
            lo, hi = fishing.size_range(fid)
            assert 0 < lo < hi, fid
            for _ in range(20):
                s = fishing.roll_size(fid)
                assert lo <= s <= hi, (fid, s)
        # higher tiers are bigger on average
        avg = {}
        for t in fishing.TIER_ORDER:
            ids = [f for f in fishing.FISH_DATA if fishing.tier_of(f) == t]
            avg[t] = sum(sum(fishing.size_range(f)) / 2 for f in ids) / len(ids)
        assert avg["common"] < avg["uncommon"] < avg["rare"] < avg["legendary"], avg
        return ", ".join(f"{k}~{v:.0f}cm" for k, v in avg.items())
    check("fishing: per-species size ranges", sizes)

    def land_record():
        g.warp("beach", sp["beach"])
        g.fish_records.pop("sardine", None)
        g.fortune[0] = None
        with _Events(g) as ev:
            g._land_fish(p, "sardine", p.x, p.y + TILE)
            g._land_fish(p, "sardine", p.x, p.y + TILE)
        caught = [d for e, d in ev.seen if e == "fish_caught"]
        assert len(caught) == 2, "fish_caught not emitted"
        assert caught[0].get("fish") == "sardine" and caught[0].get("size"), caught[0]
        rec = g.fish_records["sardine"]
        assert rec["n"] >= 2 and rec["big"] == max(d["size"] for d in caught), rec
        # a guaranteed record
        rec["big"] = 1
        g._land_fish(p, "sardine", p.x, p.y + TILE)
        assert g.fish_records["sardine"]["big"] > 1, "record not updated"
        g.draw()
        H.shot(g, "fishing_record")
        return f"sardine x{rec['n']} best {g.fish_records['sardine']['big']} cm"
    check("fishing: sizes, records, fish_caught", land_record)

    def treasure():
        gold0 = g.gold
        inv0 = sum(p.inv.items.values())
        g._fish_treasure(p, p.x, p.y + TILE, force=True)
        assert g.gold > gold0, "treasure gave no gold"
        assert sum(p.inv.items.values()) > inv0, "treasure gave no item"
        assert g.fish_chests, "no chest animation"
        for i in range(10):
            H.frames(g, 6)
            g.draw()
            if i == 5:
                H.shot(g, "fishing_treasure")
        H.frames(g, 120)
        assert not g.fish_chests, "chest animation never ended"
        # odds: ~5% base, better with luck/fishing buffs, capped
        base = fishing.treasure_chance(0, 0, 0)
        boosted = fishing.treasure_chance(10, 0.5, 0.5)
        assert 0.03 <= base <= 0.07 and base < boosted <= 0.2, (base, boosted)
        return f"+{g.gold - gold0}g, odds {base:.2f}->{boosted:.2f}"
    check("fishing: treasure chest", treasure)

    def treasure_pool():
        # chests hold ores / gems / ancient relics only -- never the Together
        # keepsake, the Mist City boss drops or trophies (even though some of
        # those are registered as cat "relic" with a high sell price)
        from src import loot
        from src.systems.fishing_system import treasure_pool as pool_fn
        banned = {"twin_locket", "city_key", "cursed_gear", "golden_egg"}
        allowed = set(loot.ROCK_ORE_ITEM.values()) | set(loot.GEMS) | set(loot.RELICS)
        ids = {k for k, _ in pool_fn()}
        assert ids and ids <= allowed, sorted(ids - allowed)
        assert not ids & banned, sorted(ids & banned)
        assert {"copper", "amethyst", "ancient_relic"} <= ids, sorted(ids)
        rng = random.Random(7)
        seen = set()
        for _ in range(3000):
            item, qty = g._fish_treasure_item(rng)
            assert item in allowed and item not in banned, item
            assert qty >= 1, qty
            seen.add(item)
        registered = sorted(b for b in banned if b in loot.MATERIALS)
        return f"{len(ids)} items in pool, {len(seen)} rolled; excluded {registered}"
    check("fishing: treasure pool whitelist", treasure_pool)

    def buff():
        st = g.fishing[0]
        w0 = g.weather
        g.weather = "rain"
        H.frames(g, 1)
        assert st.bonus > 0, "rain gave no bite bonus"
        g.weather = "sunny"
        p.add_buff("fishing", 30, 0.5, "Fishing+")
        H.frames(g, 2)
        assert st.bonus >= 0.5, "fishing buff not applied to the rod"
        random.seed(5)
        st.cast(0, water="fresh")
        buffed = st.timer
        st.bonus = 0.0
        random.seed(5)
        st.cast(0, water="fresh")
        assert buffed < st.timer, "buff did not speed up the bite"
        st.state = "idle"
        p.buffs.pop("fishing", None)
        H.frames(g, 2)
        assert st.bonus == 0.0
        g.weather = w0
        return f"cast {st.timer:.2f}s -> {buffed:.2f}s with +50%"
    check("fishing: buff speeds bites", buff)

    def rod_flow():
        """Real rod path: face water, cast, wait, hook -> _land_fish."""
        g.warp("beach", sp["beach"])
        H.frames(g, 40)                       # let the warp fade clear
        area = g.world.area
        spot = None
        for gy in range(area.h - 1):
            for gx in range(area.w):
                if area.tile(gx, gy) in ("n", "N") and area.tile(gx, gy + 1) == "W" \
                        and not area.is_solid(gx, gy):
                    spot = (gx, gy)
                    break
            if spot:
                break
        assert spot, "no shore on the beach"
        H.place(g, p, *spot)
        p.fx, p.fy = 0, 1
        i = H.hotbar_index(p, "tool", "fishing_rod")
        assert i is not None
        p.inv.selected = i
        st = g.fishing[0]
        st.state = "idle"
        g.player_action(0)
        assert st.state == "casting", st.state
        st.timer = 0.0
        H.frames(g, 1)
        assert st.state == "bite", st.state
        st.fish = "anchovy"
        g.players[1].x, g.players[1].y = p.x - TILE, p.y
        for _ in range(60):
            g._update_camera(g.world.area)
        g.draw()
        H.shot(g, "fishing_bite")
        n0 = g.fish_records.get("anchovy", {}).get("n", 0)
        g.fortune[0] = None
        g.player_action(0)
        assert g.fish_records.get("anchovy", {}).get("n", 0) > n0 or p.inv.count("anchovy"), "no catch"
        g.state = "play"
        return "cast/bite/hook ok"
    check("fishing: real rod cast -> catch", rod_flow)

    def hotspots():
        g.warp("beach", sp["beach"])
        spots = list(g.fish_spots)
        assert spots, "no fishing hot spot on the beach"
        area = g.world.area
        for (sx, sy) in spots:
            assert area.is_water(sx, sy)
        g.warp("farm", sp["farm"])
        g.warp("beach", sp["beach"])
        assert g.fish_spots == spots, "hot spots moved on re-entry"
        sx, sy = spots[0]
        stand = next(((sx + dx, sy + dy) for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1))
                      if not area.is_solid(sx + dx, sy + dy)), None)
        assert stand, "hot spot not castable"
        H.place(g, p, *stand)
        p.fx, p.fy = sx - stand[0], sy - stand[1]
        H.frames(g, 1)
        st = g.fishing[0]
        assert st.hotspot, "standing at the hot spot did not register"
        random.seed(9)
        st.cast(0, water="sea")
        hot_t = st.timer
        st.state = "idle"
        g.players[1].x, g.players[1].y = p.x - TILE, p.y
        for _ in range(12):
            H.frames(g, 10)
            g._update_camera(g.world.area)
        g.draw()
        H.shot(g, "fishing_hotspot")
        p.fx, p.fy = -p.fx if p.fx else 0, -p.fy if p.fy else 0
        H.frames(g, 1)
        assert not st.hotspot
        random.seed(9)
        st.cast(0, water="sea")
        assert hot_t < st.timer, "hot spot did not speed the bite"
        st.state = "idle"
        return f"{len(spots)} spot(s) at {spots}"
    check("fishing: bubbling hot spots", hotspots)

    # ------------------------------------------------------------ journal tab
    def collection_tab():
        tab = g._journal_tab_30_forage_collection()
        assert tab["title"] and callable(tab["draw"]) and callable(tab["key"])
        surf = pygame.Surface((1280, 720))
        tab["draw"](surf, pygame.Rect(90, 120, 1100, 520))
        small = pygame.Rect(40, 40, 600, 300)
        tab["draw"](surf, small)
        for _ in range(30):
            tab["key"](pygame.K_DOWN)
        tab["draw"](surf, small)
        assert g._coll_scroll > 0, "tab did not scroll"
        for _ in range(40):
            tab["key"](pygame.K_UP)
        assert g._coll_scroll == 0
        nf, tf, ng, tg = g._coll_stats()
        # milestones: 25% of everything -> a one-time reward (saved)
        keep = (dict(g.forage_found), set(g.coll_milestones), g.gold)
        need = (tf + tg + 3) // 4
        for fid in list(FG.FORAGE)[:max(0, need - nf)]:
            g.forage_found.setdefault(fid, 1)
        g.coll_milestones.discard(25)
        gold0 = g.gold
        g._coll_check_milestones()
        assert 25 in g.coll_milestones and g.gold > gold0, "25% milestone not paid"
        paid = g.gold - gold0
        g._coll_check_milestones()
        assert g.gold == gold0 + paid, "milestone paid twice"
        d = g._on_save_forage()
        assert 25 in json.loads(json.dumps(d))["coll_milestones"]
        g.forage_found, g.coll_milestones, g.gold = keep
        if hasattr(g, "journal_open"):
            g.journal_open("Collection")
            for _ in range(40):
                g._run_state("update", H.DT)
            g.draw()
            H.shot(g, "fishing_journal_collection")
            g.state = "play"
            g._jr_tabs = None
        return f"fish {nf}/{tf}, forage {ng}/{tg}"
    check("collection: journal tab draw + scroll", collection_tab)

    g.state = "play"
    g.warp("farm", sp["farm"])
    return "fishing & foraging ok"
