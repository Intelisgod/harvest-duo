"""Farming / Animals / Cooking / Shop domain checks (Chat 2).

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests). Every step
is a separate check; the game is left in a sane "play" state on the farm.
"""
import json


def _select(H, p, item):
    """Put ``item`` on the hotbar (if needed) and select it."""
    idx = H.hotbar_index(p, "item", item)
    if idx is None:
        p.inv.set_slot(len(p.inv.hotbar()) - 1, ("item", item))
        idx = H.hotbar_index(p, "item", item)
    assert idx is not None, f"could not select {item}"
    p.inv.selected = idx
    return idx


def _select_tool(H, p, tool):
    p.inv.selected = H.hotbar_index(p, "tool", tool)


def _face(H, g, p, gx, gy):
    """Stand just above (gx, gy) facing down at it."""
    H.place(g, p, gx, gy - 1)
    p.fx, p.fy = 0, 1


def _free_tiles(g, n, avoid=()):
    """n open farm tiles (tillable/placeable) whose north neighbour is walkable."""
    area = g.world.area
    out = []
    # interaction points (shipping bin, bed, collector...) grab presses made
    # next to them, so never stand within 1 tile of one
    pois = [v for v in vars(area).values()
            if isinstance(v, tuple) and len(v) == 2 and all(isinstance(c, int) for c in v)]
    for gy in range(6, area.h - 3):
        for gx in range(8, area.w - 3):
            if (gx, gy) in avoid:
                continue
            if any(abs(gx - px) <= 2 and abs(gy - 1 - py) <= 2 for px, py in pois):
                continue
            if g._art_place_ok(area, gx, gy) and not area.is_solid(gx, gy - 1) \
                    and all(abs(gx - ox) > 1 or abs(gy - oy) > 1 for ox, oy in out):
                out.append((gx, gy))
                if len(out) >= n:
                    return out
    return out


class _Events:
    def __init__(self, g):
        self.g = g
        self.seen = []
        self._orig = g.emit

    def __enter__(self):
        orig = self._orig

        def emit(event, **data):
            self.seen.append((event, data))
            return orig(event, **data)
        self.g.emit = emit
        return self

    def __exit__(self, *a):
        try:
            del self.g.emit
        except AttributeError:
            pass

    def names(self):
        return [e for e, _ in self.seen]


def run(g, check, H):
    from src.settings import AREA_FARM, AREA_COOP
    from src import cooking, crops
    from src.systems import shop_system as shop
    from src.systems import artisan_system as art

    g.state = "play"
    g.warp(AREA_FARM, (12, 12))
    p = g.players[0]
    p.energy = 270
    tiles = {}
    _warp = g.warp

    def warp(area, spawn):          # keep villagers / forageables out of the way of our presses
        _warp(area, spawn)
        g.npcs = []
        fs = getattr(g, "forage_spawns", None)
        if isinstance(fs, dict):
            fs.pop(area, None)
    g.warp = warp

    # ---------------------------------------------------------- farming e2e
    def farm_e2e():
        g.warp(AREA_FARM, (12, 12))
        (gx, gy), = _free_tiles(g, 1)
        tiles["crop"] = (gx, gy)
        key = (AREA_FARM, gx, gy)
        _face(H, g, p, gx, gy)
        _select_tool(H, p, "hoe")
        g.player_action(0)
        assert key in g.world.tilled, "hoe did not till"
        p.inv.add("fertilizer", 1)
        _select(H, p, "fertilizer")
        g.player_action(0)
        assert g.fert_tiles.get(key) == "fertilizer", "fertilizer not applied"
        p.inv.add("seed:parsnip", 1)
        _select(H, p, "seed:parsnip")
        g.player_action(0)
        assert key in g.world.crops, "parsnip not planted"
        H.frames(g, 2)
        assert g.world.crops[key].fert == "fertilizer", "crop did not pick up fertilizer"
        nights = 0
        before = p.inv.count("parsnip")
        while not g.world.crops[key].ready_to_harvest and nights < 8:
            _face(H, g, p, gx, gy)
            _select_tool(H, p, "watering_can")
            g.player_action(0)
            assert g.world.crops[key].watered, "watering did not reach the crop"
            g.do_sleep()
            H.settle(g)
            g.warp(AREA_FARM, (12, 12))
            H.frames(g, 1)
            nights += 1
            assert key in g.world.crops, f"crop vanished after night {nights}"
        assert g.world.crops[key].ready_to_harvest, "parsnip never ripened"
        assert nights < crops.CROPS["parsnip"]["grow"], f"fertilizer gave no speed-up ({nights} nights)"
        _face(H, g, p, gx, gy)
        _select_tool(H, p, "hoe")
        g.player_action(0)
        got = p.inv.count("parsnip") - before
        assert got >= 1, "harvest gave nothing"
        # sell one through the shop path -> gold + item_sold event
        gold0 = g.gold
        with _Events(g) as ev:
            earned = g._sell_items(p, "parsnip", 1)
        assert earned > 0 and g.gold == gold0 + earned, "sale did not pay"
        assert "item_sold" in ev.names(), "item_sold not emitted"
        return f"ripe after {nights} nights (fertilized), harvested {got}, sold +{earned}g"
    check("farming: till/fert/plant/water/sleep/harvest/sell", farm_e2e)

    # ---------------------------------------------------------- machines
    def machines():
        g.warp(AREA_FARM, (12, 12))
        spots = _free_tiles(g, 5, avoid={tiles.get("crop")})
        assert len(spots) == 5, "not enough free farm tiles"
        kinds = ["machine_preserves_jar", "machine_keg", "machine_cheese_press",
                 "machine_mayo_machine", "machine_bee_house"]
        for kind, (gx, gy) in zip(kinds, spots):
            p.inv.add(kind, 1)
            _face(H, g, p, gx, gy)
            _select(H, p, kind)
            g.draw()                                 # green placement ghost
            p.fy = -1                                # face back north (ghost may be red)
            g.draw()
            p.fy = 1
            g.player_action(0)
            assert g.world.farm_objects.get((gx, gy)) == kind, f"{kind} not placed"
            assert g.world.area.is_solid(gx, gy), f"{kind} not solid"
            tiles[kind] = (gx, gy)
        # can't place on tilled soil
        cx, cy = tiles["crop"]
        g.world.tilled.add((AREA_FARM, cx, cy))
        assert not g._art_place_ok(g.world.area, cx, cy), "placed on tilled soil"
        # feed them
        feed = {"machine_preserves_jar": "melon", "machine_keg": "parsnip",
                "machine_cheese_press": "milk", "machine_mayo_machine": "egg"}
        for kind, item in feed.items():
            gx, gy = tiles[kind]
            p.inv.add(item, 1)
            _face(H, g, p, gx, gy)
            _select(H, p, item)
            n0 = p.inv.count(item)
            g.player_action(0)
            assert p.inv.count(item) == n0 - 1, f"{kind} did not take {item}"
            assert art._ks(gx, gy) in g.artisan_jobs, f"{kind} has no job"
        # invalid input is refused
        gx, gy = tiles["machine_cheese_press"]
        p.inv.add("stone", 1)
        _select(H, p, "stone")
        mx, my = tiles["machine_cheese_press"]
        for i, pl in enumerate(g.players):
            H.place(g, pl, mx + i, my + 2)
        H.frames(g, 50)
        g.draw()
        H.shot(g, "farming_machines_working")
        # save round-trip mid-job keeps contents exactly
        d1 = json.dumps(g._on_save_artisan(), sort_keys=True)
        g._on_load_artisan(json.loads(json.dumps(g._collect_save())))
        assert json.dumps(g._on_save_artisan(), sort_keys=True) == d1, "artisan save mismatch"
        # hour machines finish after ~4 game hours of play
        g.time.minutes = min(g.time.minutes, 12 * 60)
        for _ in range(26):
            g.time.minutes += 10
            H.frames(g, 1)
        ch = g.artisan_jobs[art._ks(*tiles["machine_cheese_press"])]
        assert ch["mins"] == 0, f"cheese press still busy ({ch})"
        # sleep twice -> jar (1 morning), keg (2), bee house (2) done
        for _ in range(2):
            g.do_sleep()
            H.settle(g)
            g.warp(AREA_FARM, (12, 12))
            H.frames(g, 1)
        mx, my = tiles["machine_cheese_press"]
        for i, pl in enumerate(g.players):          # stand by the machines for the shot
            H.place(g, pl, mx + i, my + 2)
        H.frames(g, 50)
        g.draw()
        H.shot(g, "farming_machines_ready")
        got = {}
        with _Events(g) as ev:
            for kind in kinds:
                gx, gy = tiles[kind]
                job = g.artisan_jobs.get(art._ks(gx, gy))
                assert job and g._art_ready(job), f"{kind} not ready: {job}"
                out = job["out"]
                _face(H, g, p, gx, gy)
                _select_tool(H, p, "hoe")
                n0 = p.inv.count(out)
                g.player_action(0)
                assert p.inv.count(out) > n0, f"{kind} product {out} not collected"
                got[kind] = out
        assert ev.names().count("crafted") == len(kinds), "crafted not emitted per product"
        assert got["machine_preserves_jar"] == "jam_melon"
        assert got["machine_keg"] == "juice_parsnip"
        assert got["machine_cheese_press"] == "cheese_wheel"
        assert got["machine_mayo_machine"] == "mayonnaise"
        assert got["machine_bee_house"] in ("honey", "wildflower_honey")
        assert art._ks(*tiles["machine_bee_house"]) in g.artisan_jobs, "bee house did not restart"
        for out in got.values():
            assert shop.sell_value(out) > 0, f"{out} unsellable"
        assert shop.sell_value("jam_melon") > shop.sell_value("melon")
        # pickaxe picks a machine back up
        gx, gy = tiles["machine_mayo_machine"]
        _face(H, g, p, gx, gy)
        _select_tool(H, p, "pickaxe")
        g.player_action(0)
        assert (gx, gy) not in g.world.farm_objects, "pickaxe did not remove machine"
        assert not g.world.area.is_solid(gx, gy), "removed machine still solid"
        assert p.inv.count("machine_mayo_machine") >= 1
        # tidy up: leave the farm as we found it for the other domains' tests
        farm = g.world.areas[AREA_FARM]
        for kind in kinds:
            gx, gy = tiles[kind]
            g.world.farm_objects.pop((gx, gy), None)
            farm.solid_extra.discard((gx, gy))
            g.artisan_jobs.pop(art._ks(gx, gy), None)
        g.world.tilled.discard((AREA_FARM,) + tuple(tiles["crop"]))
        return ", ".join(sorted(got.values()))
    check("artisan machines: place/feed/save/wait/collect/pickup", machines)

    # ---------------------------------------------------------- recipe table
    def recipes():
        R = art.machine_recipe
        assert R("machine_preserves_jar", "strawberry")[0] == "jam_strawberry"
        assert R("machine_preserves_jar", "potato")[0] == "pickles_potato"
        assert R("machine_keg", "grape")[:1] == ("wine_grape",) and R("machine_keg", "grape")[3] == 2
        assert R("machine_keg", "honey")[0] == "mead"
        assert R("machine_cheese_press", "goat_milk")[0] == "goat_cheese_wheel"
        assert R("machine_mayo_machine", "duck_egg")[0] == "duck_mayonnaise"
        assert R("machine_keg", "milk") is None and R("machine_mayo_machine", "melon") is None
        n_forage = 0
        for src in art._FORAGE_FRUIT + art._FORAGE_VEG:
            if src in art.SOURCES:
                assert R("machine_preserves_jar", src), f"jar refuses {src}"
                n_forage += 1
        for gid in art.GOODS:
            assert shop.sell_value(gid) > 0, f"{gid} has no price"
            src = art.GOOD_SOURCE.get(gid)
            if src:
                assert shop.sell_value(gid) > art.SOURCES[src]["sell"], f"{gid} not worth more than {src}"
        # no id clash with cooked dishes (cheese / goat_cheese stay foods)
        assert not (set(art.GOODS) & set(cooking.FOODS)), "artisan good clashes with a food id"
        # regression (review 2026-09): the Keg must never be a trap -- per item it
        # beats the Preserves Jar for every shared input, and per machine-day it
        # stays comparable (juice is next-morning, wine ages 2 days)
        assert R("machine_keg", "potato")[3] == 1, "juice should be ready next morning"
        n_keg = 0
        for src in art.SOURCES:
            jar, keg = R("machine_preserves_jar", src), R("machine_keg", src)
            if not (jar and keg):
                continue
            jv, kv = shop.sell_value(jar[0]), shop.sell_value(keg[0])
            assert kv > jv, f"keg {keg[0]} {kv}g <= jar {jar[0]} {jv}g"
            per_day = (kv / max(1, keg[3])) / (jv / max(1, jar[3]))
            assert per_day >= 0.75, f"keg per-day value for {src} only {per_day:.2f}x the jar"
            n_keg += 1
        assert n_keg >= 20, f"only {n_keg} keg inputs compared"
        # regression (review round 2): player-facing Keg text must match KEG_DAYS
        # (it once implied juice took 2 days like wine)
        kdesc = art.MACHINES["machine_keg"]["desc"]
        for form, days in art.KEG_DAYS.items():
            want = f"{days} day" + ("s" if days != 1 else "")
            assert want in kdesc, f"keg desc {kdesc!r} lacks '{want}' for {form}"
        from src import loot
        for fruit in art._ORCHARD_FRUIT:                  # World's orchard fruit -> jam / wine
            if loot.is_material(fruit):
                assert R("machine_preserves_jar", fruit)[0] == f"jam_{fruit}", f"jar refuses {fruit}"
                assert R("machine_keg", fruit)[0] == f"wine_{fruit}", f"keg refuses {fruit}"
        return f"{len(art.GOODS)} goods ({n_forage} forage inputs, keg > jar on {n_keg})"
    check("artisan recipe table + prices", recipes)

    # ---------------------------------------------------------- buff foods
    def buff_foods():
        g.warp(AREA_FARM, (12, 12))
        H.place(g, p, 12, 12)
        p.fx, p.fy = 0, 1
        n = 0
        for fid, (kind, amt, secs) in cooking.BUFFS.items():
            assert fid in cooking.FOODS and fid in cooking.RECIPES, f"{fid} not cookable"
            for ing in cooking.RECIPES[fid]:
                assert shop.sell_value(ing) > 0 or ing in crops.CROPS, f"unknown ingredient {ing}"
            p.buffs.pop(kind, None)
            p.inv.add(fid, 1)
            _select(H, p, fid)
            c0 = p.inv.count(fid)
            g.use_tool(0, p.target_tile())
            assert p.inv.count(fid) == c0 - 1, f"{fid} not eaten"
            assert p.buff(kind) > 0, f"{fid} gave no {kind} buff"
            n += 1
        # the cooking menu can cook one (ingredients from both bags)
        from src.cooking import CookingMenu
        for ing, q in cooking.RECIPES["farmers_lunch"].items():
            p.inv.add(ing, q)
        g.cook = CookingMenu(g, p)
        g.cook.sel = g.cook.items.index("farmers_lunch")
        with _Events(g) as ev:
            before = p.inv.count("farmers_lunch")
            g.cook.confirm()
        assert p.inv.count("farmers_lunch") == before + 1, "cooking failed"
        assert "cooked" in ev.names(), "cooked not emitted"
        g.state = "cook"
        g.draw()
        H.shot(g, "farming_cook_menu")
        g.state = "play"
        return f"{n} buff dishes ok"
    check("buff foods: eat -> buff, cook menu", buff_foods)

    # ---------------------------------------------------------- shop & market
    def market():
        hot = shop.HOT.get("item")
        assert hot, "no hot item today"
        assert shop.sell_value(hot) > 0 or hot in crops.CROPS, f"hot item {hot} unsellable"
        base = shop.sell_value(hot)
        unit = shop.unit_sell_value(p, hot)
        assert unit >= int(base * 1.5) - 1, f"hot bonus missing ({base} -> {unit})"
        g.shop.build(g.time.season, allow_buy=True, title="General Store")
        kinds = [o[2] for o in g.shop.options]
        for mid in art.MACHINES:
            assert "buyitem:" + mid in kinds, f"{mid} not in shop"
        assert "buyitem:fertilizer" in kinds and "buyitem:quality_fertilizer" in kinds
        assert any(k.startswith("buy:") and crops.CROPS[k[4:]].get("premium") for k in kinds), \
            "no premium seed"
        assert g.shop.options[g.shop.sel][2] not in ("hot", "header"), "cursor on a label row"
        # regression (review round 2): seed rows read 'Buy parsnip seed' next to
        # 'Buy Chicken' / 'Buy Keg' -- every buy row is Title Case now, seeds plural
        for label, _price, kind in g.shop.options:
            if kind.startswith(("buy:", "buyitem:", "animal:")):
                name = label[4:].split(" (")[0]
                assert label.startswith("Buy ") and all(w[:1].isupper() for w in name.split()), \
                    f"shop row not Title Case: {label!r}"
            if kind.startswith("buy:"):
                assert name == crops.crop_label(kind[4:]) + " Seeds", f"seed row {label!r}"
        # buy a keg through the menu
        g.gold = 5000
        g.shop_buyer = 0
        g.shop.sel = kinds.index("buyitem:machine_keg")
        k0 = p.inv.count("machine_keg")
        g.do_shop_select()
        assert p.inv.count("machine_keg") == k0 + 1 and g.gold == 5000 - art.MACHINES["machine_keg"]["price"]
        g.state = "shop"
        g.draw()
        H.shot(g, "farming_shop")
        g.state = "play"
        # sell all emits item_sold per stack and applies the hot bonus
        p.inv.add(hot, 2)
        with _Events(g) as ev:
            g.sell_all()
        sold = [d for e, d in ev.seen if e == "item_sold"]
        assert any(d.get("item") == hot for d in sold), "hot item not sold / no event"
        # hot item is date-deterministic (survives save/load without a key)
        t = g.time
        assert shop.pick_hot_item(t.season, t.day, t.year) == hot
        return f"hot={hot} {base}g->{unit}g, {len(sold)} item_sold events"
    check("shop: farm supplies, hot item, item_sold", market)

    # ---------------------------------------------------------- display names
    def display_names():
        # regression (review round 3): artisan short tags ('GtChWhl', 'Fertlzr')
        # leaked into Inventory.label via inventory.ITEM_LABELS, and buying the
        # premium sprinkler logged 'Bought Sprinkler2'
        from src.inventory import Inventory
        ids = list(art.GOODS) + list(art.MACHINES) + list(art.SUPPLIES) + ["sprinkler2"]
        for iid in ids:
            a, b = shop.item_label(iid), Inventory.label(("item", iid))
            assert a == b, f"{iid}: item_label {a!r} != Inventory.label {b!r}"
        assert Inventory.label(("item", "goat_cheese_wheel")) == "Goat Cheese Wheel"
        assert Inventory.label(("item", "quality_fertilizer")) == "Quality Fertilizer"
        assert shop.item_label("sprinkler2") == "Premium Sprinkler"
        g.gold = 5000
        g.shop_buyer = 0
        g.shop.build(g.time.season, allow_buy=True, title="General Store")
        g.shop.sel = [o[2] for o in g.shop.options].index("buyitem:sprinkler2")
        n0 = p.inv.count("sprinkler2")
        g.state = "shop"
        try:
            g.do_shop_select()
        finally:
            g.state = "play"
        assert p.inv.count("sprinkler2") == n0 + 1, "premium sprinkler not bought"
        msgs = [m[0] for m in g.ui.messages]
        assert any(m == "Bought Premium Sprinkler (-1500g)" for m in msgs), msgs[-3:]
        p.inv.remove("sprinkler2", 1)
        return f"{len(ids)} ids agree"
    check("labels: artisan goods + premium sprinkler read in full", display_names)

    # ---------------------------------------------------------- sell all keeps keepsakes
    def sell_all_keeps():
        from src import loot
        # regression (review 2026-09): 'Sell all' / the shipping bin used to sell the
        # Twin Heart Locket, Golden Egg, City Key, bombs, rope ladders and buff food
        keep = [i for i in ("twin_locket", "golden_egg", "city_key", "ancient_relic", "bomb",
                            "mega_bomb", "rope_ladder", "fertilizer", "machine_keg")
                if loot.is_material(i)] + ["honey_tea", "fried_egg", "mushroom_soup"]
        for i in keep:
            p.inv.add(i, 1)
        before = {i: p.inv.count(i) for i in keep}
        p.inv.add("parsnip", 3)
        gold0 = g.gold
        with _Events(g) as ev:
            g.sell_all()
        sold = {d.get("item") for e, d in ev.seen if e == "item_sold"}
        assert p.inv.count("parsnip") == 0 and "parsnip" in sold, "crops not sold"
        assert g.gold > gold0
        for i in keep:
            assert p.inv.count(i) == before[i], f"sell all sold keepsake/tool/meal {i}"
            assert i not in sold, f"item_sold emitted for kept {i}"
            assert not shop.bulk_sellable(i)
        # ... but each can still be sold on its own from the 'Sell items...' list
        g.shop_buyer = 0
        g.shop.build_sell(p)
        rows = [o[2] for o in g.shop.options]
        for i in keep:
            if shop.sell_value(i) > 0:
                assert "sellitem:" + i in rows, f"{i} missing from the per-item sell list"
        for i in keep:                                   # tidy: take the test items back
            p.inv.remove(i, 1)
        g.shop.build(g.time.season, allow_buy=True, title="General Store")
        return f"kept {len(keep)} kinds, sold the crops"
    check("shop: sell all keeps keepsakes, tools and meals", sell_all_keeps)

    # ---------------------------------------------------------- forage dishes
    def forage_dishes():
        from src import forage, assets
        from src.cooking import CookingMenu
        n = 0
        for fid in cooking.FORAGE_DISHES:
            assert fid in cooking.FOODS and fid in cooking.RECIPES, f"{fid} not cookable"
            assert any(i in forage.FORAGE for i in cooking.RECIPES[fid]), f"{fid} uses no forage"
            for i in cooking.RECIPES[fid]:
                assert shop.sell_value(i) > 0, f"{fid}: unknown ingredient {i}"
            assert assets.item_icon(fid) is not None
            n += 1
        need = cooking.RECIPES["mushroom_soup"]
        for i, q in need.items():
            p.inv.add(i, q)
        g.cook = CookingMenu(g, p)
        g.cook.sel = g.cook.items.index("mushroom_soup")
        before = p.inv.count("mushroom_soup")
        g.cook.confirm()
        assert p.inv.count("mushroom_soup") == before + 1, "mushroom soup not cooked"
        p.inv.remove("mushroom_soup", 1)
        return f"{n} forage dishes"
    check("cooking: forage dishes", forage_dishes)

    # ---------------------------------------------------------- quality fertilizer
    def quality_fert():
        import random as _r
        g.warp(AREA_FARM, (12, 12))
        (gx, gy), = _free_tiles(g, 1, avoid=set(tiles.values()))
        key = (AREA_FARM, gx, gy)
        g.world.tilled.add(key)
        g.fert_tiles[key] = "quality_fertilizer"
        from src.crops import Crop
        extra = 0
        _r.seed(3)
        for _ in range(12):
            c = Crop("parsnip")
            c.age = c.data["grow"]
            g.world.crops[key] = c
            g.world.tilled.add(key)
            g.fert_tiles[key] = "quality_fertilizer"
            _face(H, g, p, gx, gy)
            _select_tool(H, p, "hoe")
            b = p.inv.count("parsnip")
            g.fortune[0] = None
            g.player_action(0)
            extra += max(0, p.inv.count("parsnip") - b - 1)
        assert extra > 0, "quality fertilizer never doubled in 12 harvests"
        g.world.crops.pop(key, None)
        g.world.tilled.discard(key)
        H.frames(g, 1)
        assert key not in g.fert_tiles, "fertilizer outlived its soil"
        return f"{extra}/12 bonus harvests"
    check("quality fertilizer doubles sometimes", quality_fert)

    # ---------------------------------------------------------- idle soil keeps fertilizer
    def fert_keeps_soil():
        g.warp(AREA_FARM, (12, 12))
        spots = _free_tiles(g, 2, avoid=set(tiles.values()))
        (fx, fy), (ex, ey) = spots
        fk, ek = (AREA_FARM, fx, fy), (AREA_FARM, ex, ey)
        g.world.tilled.update({fk, ek})
        g.fert_tiles[fk] = "fertilizer"
        for _ in range(3):
            g._revert_idle_tilled()
        assert fk in g.world.tilled and g.fert_tiles.get(fk) == "fertilizer",             "fertilized soil reverted"
        assert ek not in g.world.tilled, "plain idle soil should still revert"
        g.world.tilled.discard(fk)
        H.frames(g, 1)
        assert fk not in g.fert_tiles
        return "fertilized empty soil kept, plain soil reverted"
    check("fertilized idle soil does not revert", fert_keeps_soil)

    # ---------------------------------------------------------- animal affection
    def affection():
        from src.animals import Animal
        keep = list(g.animals)
        g.animals[:] = [Animal("cow", 6, 5)]
        g.warp(AREA_COOP, H.spawns_by_area(g).get(AREA_COOP, (7, 8)))
        coll = getattr(g.world.area, "collector", None)
        g.world.area.collector = None
        an = g.animals[-1]
        an.has_produce = False
        an.petted = False
        p.x, p.y = an.x, an.y + 20
        f0 = an.friend
        g.player_action(0)
        assert an.petted and an.friend > f0, "pet did not raise affection"
        f1 = an.friend
        p.x, p.y = an.x, an.y + 20
        g.player_action(0)
        assert an.friend == f1, "second pet today should not count"
        assert an.heart_t > 0
        q = g.players[1]                            # partner pets too -> small bonus
        q.x, q.y = an.x + 20, an.y + 20
        g.player_action(1)
        assert an.friend > f1 and sorted(an.petted_by) == [0, 1], "co-op pet bonus missing"
        f1 = an.friend
        for _ in range(40):
            g.fade = 0.0
            g.update(H.DT)
        an.heart_t = 2.0
        g.draw()
        H.shot(g, "farming_coop_hearts")
        d = g._collect_save()
        rec = [a for a in d["animals"] if a["kind"] == "cow"][-1]
        assert rec.get("petted_by") == [0, 1]
        g.do_sleep()
        H.settle(g)
        assert not an.petted, "petted flag not reset in the morning"
        # max hearts -> large produce sometimes
        import random as _r
        _r.seed(1)
        an.friend = 250
        big = sum(1 for _ in range(200) if an.produce_qty(_r) == 2)
        assert 20 < big < 110, f"large-produce rate off ({big}/200)"
        g.world.areas[AREA_COOP].collector = coll
        g.animals[:] = keep + [an]
        return f"friend {f0}->{f1}, 5-heart large rate {big}/200"
    check("animal affection: pet once/day, hearts, large produce", affection)

    g.state = "play"
    g.warp = _warp
    try:
        del g.warp
    except AttributeError:
        pass
    g.warp(AREA_FARM, (12, 12))
    return "farming domain ok"
