"""Story domain (Chat 4) end-to-end checks: villagers + schedules, talk/gift
tastes/birthdays, heart events, valley restoration, egg hunt, lantern night,
journal tabs, quest_done. Run by tools/smoke_test.py (section "domain")."""
import json
import pygame


def run(g, check, H):
    from src.settings import (AREA_TOWN, AREA_BEACH, AREA_FARM, AREA_TEMPLE, TILE,
                              P1_KEYS, P2_KEYS)
    from src import story_data as SD
    from src.npc import NPC_DATA
    ev = pygame.event.Event
    # start clean even if an earlier domain test left a side-mode running
    if getattr(g, "mist_run", None) is not None and hasattr(g, "mist_exit"):
        try:
            g.mist_exit("leave")
        except Exception:
            pass
    H.settle(g)
    g.state = "play"

    def key(k):
        g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
        g._run_state("update", H.DT)
        g.draw()

    def set_time(season, day, hour, weather="sunny"):
        g.time.season_idx, g.time.day, g.time.minutes = season, day, hour * 60
        g.weather = weather
        g._story_hour = None

    def select_non_item(p):
        for i, e in enumerate(p.inv.hotbar()):
            if e and e[0] != "item":
                p.inv.selected = i
                return
        p.inv.selected = 0

    def hold(p, item):
        """Put ``item`` in hotbar slot 0 and select it (hotbar may be full)."""
        e = ("item", item)
        p.inv._reconciled()
        if e in p.inv.hotbar_order:
            p.inv.hotbar_order.remove(e)
        p.inv.hotbar_order.insert(0, e)
        p.inv.selected = 0
        assert p.inv.selected_entry() == e, p.inv.selected_entry()

    def near(p, npc):
        p.x, p.y = npc.x, npc.y + TILE * 0.8

    def villager(name):
        return next((n for n in g.npcs if n.name == name), None)

    def data():
        for name in SD.VILLAGERS:
            assert name in NPC_DATA, name
            L = SD.LINES[name]
            n = sum(len(v) for k, v in L.items()
                    if k not in ("love", "like", "neutral", "dislike"))
            assert n >= 10, f"{name} has only {n} lines"
            ev_ = SD.events_for(name)
            assert 2 in ev_ and 4 in ev_, name
            assert SD.birthday_str(name) != "?"
        assert SD.taste("Somchai", "tuna") == "love"
        assert SD.taste("Kai", "cauliflower") == "dislike"
        assert SD.taste("Fah", "melon") == "love"
        return f"{len(SD.VILLAGERS)} villagers"
    check("story: villager data", data)

    def schedules():
        set_time(1, 3, 8)                                   # Summer 3, 8 AM, sunny
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 3)
        names = {n.name for n in g.npcs}
        assert {"Fah", "Kai", "Mira"} <= names, names
        g.warp(AREA_BEACH, H.spawns_by_area(g)[AREA_BEACH])
        H.frames(g, 3)
        assert villager("Somchai") is not None, [n.name for n in g.npcs]
        # hour change in town: Fah strolls to the square (walk target set)
        set_time(1, 3, 9)
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        g.time.minutes = 10 * 60 + 5
        H.frames(g, 2)
        fah = villager("Fah")
        assert fah is not None and fah.target is not None, "Fah should walk to the square"
        H.frames(g, 240)
        # evening: Fah on the beach -> leaves town
        g.time.minutes = 15 * 60
        H.frames(g, 400)
        assert villager("Fah") is None or villager("Fah").leaving
        g.time.minutes = 8 * 60
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        g.fade = 0.0
        H.frames(g, 60)
        g.draw()
        H.shot(g, "story_town_villagers")
        return sorted(names)
    check("story: schedules spawn/walk/leave", schedules)

    def rainy_day():
        set_time(0, 3, 9, weather="rain")
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        g.fade = 0.0
        H.frames(g, 40)
        g.draw()
        H.shot(g, "story_rain_umbrellas")
        assert villager("Fah") is not None
        return "umbrellas up"
    check("story: rainy-day schedule + umbrellas", rainy_day)

    def talk_and_gift():
        set_time(1, 3, 8)
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        fah = villager("Fah")
        p = g.players[0]
        g.world.friend["Fah"] = 0
        near(p, fah)
        select_non_item(p)
        g.player_action(0)
        assert g.state == "dialogue", g.state
        assert "Fah" in g.dialogue_text
        g.draw()
        H.shot(g, "story_dialogue_portrait")
        H.settle(g)
        h1 = g.world.friend["Fah"]
        near(p, fah)
        g.player_action(0)
        H.settle(g)
        assert g.world.friend["Fah"] == h1, "second chat must not add hearts"
        # partner chats right after -> the special "you two" line
        q = g.players[1]
        select_non_item(q)
        near(q, fah)
        g.player_action(1)
        assert g.state == "dialogue"
        assert any(ln.replace("{p}", "")[:12] in g.dialogue_text
                   for ln in SD.COUPLE_LINES["Fah"]), g.dialogue_text
        H.settle(g)
        # loved gift
        p.inv.add("melon", 2)
        hold(p, "melon")
        near(p, fah)
        g.player_action(0)
        H.settle(g)
        assert g.world.friend["Fah"] >= h1 + 60, g.world.friend["Fah"]
        assert "Fah|melon" in g.story_known_loves
        # second gift the same day is politely refused (item kept)
        before = p.inv.count("melon")
        near(p, fah)
        g.player_action(0)
        assert p.inv.count("melon") == before, "refused gift must not be consumed"
        H.settle(g)
        return f"Fah friendship {g.world.friend['Fah']}"
    check("story: talk + gift tastes + daily limits", talk_and_gift)

    def daily_limits_persist():
        # regression: quit + relaunch mid-day must not reset the gift / first-chat limits
        assert "Fah|0" in g.story_gifted_today and "Fah" in g.story_talked_today
        d = json.loads(json.dumps(g._collect_save()))
        assert d["story_today"]["day"] == g._story_day_key()
        g.story_gifted_today, g.story_talked_today = set(), set()
        g._on_load_story(d)
        assert "Fah|0" in g.story_gifted_today and "Fah" in g.story_talked_today
        # a save from another day (or an old save without the key) starts fresh
        d2 = dict(d, story_today=dict(d["story_today"], day="0|0|0"))
        g._on_load_story(d2)
        assert not g.story_gifted_today and not g.story_talked_today
        g._on_load_story({k: v for k, v in d.items() if k != "story_today"})
        assert not g.story_gifted_today
        g._on_load_story(d)                                  # back to today's state
        return "gift/talk limits survive a reload"
    check("story: daily limits saved", daily_limits_persist)

    def birthday():
        set_time(0, 22, 8)                                   # Fah: Spring 22
        g.story_gifted_today = set()
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        fah = villager("Fah")
        assert fah is not None
        assert g._story_is_birthday("Fah")
        p = g.players[1]
        p.inv.add("fruit_salad", 1)
        hold(p, "fruit_salad")
        f0 = g.world.friend["Fah"]
        near(p, fah)
        g.player_action(1)
        H.settle(g)
        assert g.world.friend["Fah"] >= min(500, f0 + 4 * 35), (f0, g.world.friend["Fah"])
        assert f"Fah|{g.time.year}" in g.story_bday_gifts
        g.draw()
        return "birthday gift x4"
    check("story: birthday gift", birthday)

    def heart_event():
        set_time(1, 3, 8)
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        kai = villager("Kai")
        g.world.friend["Kai"] = 110                          # 2 hearts
        g.story_seen_events.discard("Kai|2")
        g._story_refresh_flags()
        assert kai.event_ready
        p = g.players[0]
        select_non_item(p)
        near(p, kai)
        cu0 = p.inv.count("copper")
        g.player_action(0)
        assert g.state == "heart_event", g.state
        g.draw()
        H.shot(g, "story_heart_event")
        for _ in range(40):
            if g.state != "heart_event":
                break
            key(P2_KEYS["action"] if _ % 2 else P1_KEYS["action"])
            H.frames(g, 1)
            if _ == 4:
                for _k in range(30):
                    g._run_state("update", H.DT)
                g.draw()
                H.shot(g, "story_heart_event_p3")
        assert g.state == "play", g.state
        assert "Kai|2" in g.story_seen_events
        assert p.inv.count("copper") > cu0
        assert not kai.event_ready
        # replay it from the Friends journal (no second reward)
        cu1 = p.inv.count("copper")
        g._story_fr_sel = ["Mira", "Tomas", "Elya", "Luang Por", "Fah", "Somchai",
                           "Kai", "Luna"].index("Kai")
        assert g._story_friends_key(P1_KEYS["action"])
        assert g.state == "heart_event" and g._he.get("replay")
        for _ in range(30):
            if g.state != "heart_event":
                break
            key(P1_KEYS["action"])
        assert g.state == "play" and p.inv.count("copper") == cu1
        return "Kai 2-heart event done + replay"
    check("story: heart event", heart_event)

    def restoration():
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        b = g._story_board()
        assert b, "no restoration board"
        p = g.players[0]
        H.place(g, p, b[0], b[1] + 1)
        select_non_item(p)
        g.player_action(0)
        assert g.state == "restoration", g.state
        key(pygame.K_DOWN)
        key(pygame.K_UP)
        H.shot(g, "story_restoration_empty")
        # stock both players with everything the bundles need
        defs = g._story_bundles()
        for bd in defs:
            for item, qty in bd["slots"]:
                for pl in g.players:
                    pl.inv.add(item, qty)
        gold0 = g.gold
        for i, bd in enumerate(defs):
            g._rs["sel"] = i
            for s in range(len(bd["slots"])):
                g._rs["slot"] = s
                key(P1_KEYS["action"])
                if bd.get("together"):
                    key(P2_KEYS["action"])
            if i == 2:
                H.shot(g, "story_restoration")
        assert g.story_bundles_done == {bd["id"] for bd in defs}, g.story_bundles_done
        assert g.story_restored and g.gold > gold0
        key(pygame.K_ESCAPE)
        assert g.state == "play"
        town = g.world.areas[AREA_TOWN]
        assert any(k == "golden_statue" for k, *_ in town.props)
        H.frames(g, 30, draw_every=10)
        H.shot(g, "story_town_statue")
        # save round-trip keeps it all + the statue comes back after load
        s1 = json.dumps(g._collect_save(), sort_keys=True)
        g.reset()
        g._apply_save(json.loads(s1))
        assert json.dumps(g._collect_save(), sort_keys=True) == s1
        assert g.story_restored
        assert any(k == "golden_statue" for k, *_ in g.world.areas[AREA_TOWN].props)
        kinds = {k for k, *_ in g.world.areas[AREA_TOWN].props}
        assert {"restore_planter", "restore_lamp", "restore_heart_arch"} <= kinds, kinds
        assert any(k == "restore_fishrack" for k, *_ in g.world.areas[AREA_BEACH].props)
        g.state = "play"
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        g.time.minutes = 21 * 60
        H.frames(g, 20)
        g.draw()
        H.shot(g, "story_town_restored_night")
        return f"{len(defs)} bundles"
    check("story: valley restoration", restoration)

    def egg_hunt():
        set_time(0, 14, 10)                                  # Spring festival
        g.story_egg_hunts = set()
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        fb = g._story_stall()
        p = g.players[0]
        H.place(g, p, fb[0], fb[1] + 1)
        select_non_item(p)
        g.player_action(0)
        assert g._egg is not None and len(g._egg["eggs"]) >= 10, "hunt did not start"
        # regression: the year is only used up once the hunt resolves (quit-safe)
        assert str(g.time.year) not in g._collect_save()["story_egg_hunts"]
        g.fade = 0.0
        for _k in range(40):
            g.update(H.DT)
        g.draw()
        H.shot(g, "story_egg_hunt")
        for i in range(6):
            egg = g._egg["eggs"][0]
            pl = g.players[i % 2]
            pl.x, pl.y = egg["x"], egg["y"]
            H.frames(g, 1)
        assert sum(g._egg["score"]) >= 6, g._egg["score"]
        g._egg["t"] = 0.01
        H.frames(g, 2)
        assert g.state == "egg_hunt_end", g.state
        g._run_state("update", 1.0)
        g.draw()
        H.shot(g, "story_egg_results")
        key(P1_KEYS["action"])
        assert g.state == "play"
        assert g._count_all("golden_egg") >= 1
        assert str(g.time.year) in g.story_egg_hunts
        # second press at the stall -> the classic one-time festival gift
        H.place(g, p, fb[0], fb[1] + 1)
        g.player_action(0)
        H.settle(g)
        return "egg hunt OK"
    check("story: egg hunt", egg_hunt)

    def egg_hunt_edges():
        # regression: leaving town = hunt called off (no prize, year not used up);
        # a 0-0 finish has no winner (no Golden Egg, no festival_won)
        set_time(0, 14, 10)
        g.story_egg_hunts = set()
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        won = []
        orig = g.emit

        def spy(event, **d):
            if event == "festival_won":
                won.append(d.get("name"))
            return orig(event, **d)
        g.emit = spy
        try:
            ge0 = g._count_all("golden_egg")
            g._story_egg_start()
            g.warp(AREA_FARM, H.spawns_by_area(g)[AREA_FARM])
            H.frames(g, 2)
            assert g._egg is None and g.state == "play", g.state
            assert str(g.time.year) not in g.story_egg_hunts, "abandoned hunt used up the year"
            assert g._count_all("golden_egg") == ge0 and not won, won
            g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
            H.frames(g, 2)
            g._story_egg_start()
            g._egg["t"] = 0.01
            H.frames(g, 2)
            assert g.state == "egg_hunt_end", g.state
            assert g._egg_result["winners"] == [], g._egg_result
            g._run_state("update", 1.0)
            g.draw()                                         # 'no winner' results screen
            H.shot(g, "story_egg_no_winner")
            key(P1_KEYS["action"])
            assert g.state == "play"
            assert g._count_all("golden_egg") == ge0 and not won, won
            assert str(g.time.year) in g.story_egg_hunts
        finally:
            del g.emit
        return "0-0 = no winner; leaving town = called off"
    check("story: egg hunt edge cases", egg_hunt_edges)

    def potluck():
        set_time(1, 14, 10)                                  # Summer Luau
        g.story_potlucks = set()
        g._potluck = {}
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        fb = g._story_stall()
        gold0 = g.gold
        for i, item in ((0, "melon"), (1, "fruit_salad")):
            pl = g.players[i]
            pl.inv.add(item, 1)
            hold(pl, item)
            H.place(g, pl, fb[0], fb[1] + 1)
            g.player_action(i)
        assert g.state == "dialogue" and "Soup rating" in g.dialogue_text, g.dialogue_text
        g.draw()
        H.settle(g)
        assert g.gold > gold0 and str(g.time.year) in g.story_potlucks
        return g.dialogue_text[:60]
    check("story: luau potluck", potluck)

    def festival_pending():
        # regression: a lone Luau / Fair entry survives a reload the same day and
        # is handed back at dawn (never silently lost)
        set_time(1, 14, 10)
        g.story_potlucks = set()
        g._potluck = {}
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        fb = g._story_stall()
        p = g.players[0]
        p.inv.add("diamond", 1)
        n0 = p.inv.count("diamond")
        hold(p, "diamond")
        H.place(g, p, fb[0], fb[1] + 1)
        g.player_action(0)
        H.settle(g)
        assert g._potluck == {0: "diamond"} and p.inv.count("diamond") == n0 - 1
        d = json.loads(json.dumps(g._collect_save()))
        assert d["story_fest_pending"]["pot"] == {"0": "diamond"}, d.get("story_fest_pending")
        g._potluck = {}
        g._on_load_story_fest(d)
        assert g._potluck == {0: "diamond"}, g._potluck
        assert p.inv.count("diamond") == n0 - 1
        g._on_new_day_story_fest()                           # the festival day ends
        assert g._potluck == {} and p.inv.count("diamond") == n0
        # a pending entry saved on another day comes straight back on load
        d["story_fest_pending"]["day"] = "0|0|0"
        g._on_load_story_fest(d)
        assert g._potluck == {} and p.inv.count("diamond") == n0 + 1
        p.inv.remove("diamond", 1)
        return "lone entry kept + refunded"
    check("story: festival entry saved/refunded", festival_pending)

    def harvest_fair():
        set_time(2, 14, 11)                                  # Fall Harvest Fair
        g.story_fairs = set()
        g._fair = {}
        g.warp(AREA_TOWN, H.spawns_by_area(g)[AREA_TOWN])
        H.frames(g, 2)
        fb = g._story_stall()
        for i, item in ((0, "pumpkin"), (1, "parsnip")):
            pl = g.players[i]
            pl.inv.add(item, 1)
            hold(pl, item)
            H.place(g, pl, fb[0], fb[1] + 1)
            g.player_action(i)
        assert g.state == "dialogue" and "Best in Show" in g.dialogue_text, g.dialogue_text
        assert g.players[0].inv.count("pumpkin") >= 1, "entries come back"
        g.draw()
        H.settle(g)
        return g.dialogue_text[:70]
    check("story: harvest fair", harvest_fair)

    def lanterns():
        set_time(3, 14, 19)                                  # Winter festival night
        g.warp(AREA_BEACH, H.spawns_by_area(g)[AREA_BEACH])
        H.frames(g, 2)
        g._lantern_ready = [-9.0, -9.0]
        ls = g._story_lantern_spot()
        H.place(g, g.players[0], ls[0], ls[1] + 1)
        H.place(g, g.players[1], ls[0] + 1, ls[1] + 1)
        g.player_action(0)
        g.player_action(1)
        H.settle(g)
        assert len(g._lanterns) >= 10
        g.time.minutes = 22 * 60
        for _k in range(90):
            g.update(H.DT)
        g.draw()
        H.shot(g, "story_lanterns")
        return f"{len(g._lanterns)} lanterns"
    check("story: lantern night", lanterns)

    def lantern_no_swallow():
        # regression: the lantern spot must not eat presses meant for villagers,
        # tools or forage (before dusk it only shows a hint and falls through)
        set_time(3, 14, 10)
        g.warp(AREA_BEACH, H.spawns_by_area(g)[AREA_BEACH])
        H.frames(g, 2)
        ls = g._story_lantern_spot()
        p = g.players[0]
        H.place(g, p, ls[0], ls[1] + 1)
        assert g._interact_early_35_story_festival(0, p) is False
        assert g.state == "play", g.state
        g.time.minutes = 19 * 60
        npc = g.npcs[0] if g.npcs else None
        if npc is not None:
            p.x, p.y = npc.x, npc.y + TILE * 0.8
            assert g._interact_early_35_story_festival(0, p) is False, "villager press eaten"
        H.place(g, p, ls[0] + 3, ls[1] + 3)                  # outside the 3x3 spot
        assert g._interact_early_35_story_festival(0, p) is False
        g._lantern_ready = [-9.0, -9.0]
        H.settle(g)
        return "presses fall through"
    check("story: lantern spot fall-through", lantern_no_swallow)

    def temple_bells():
        set_time(0, 5, 10)
        g.warp(AREA_TEMPLE, H.spawns_by_area(g)[AREA_TEMPLE])
        H.frames(g, 2)
        bells = [(gx, gy) for k, gx, gy in g.world.area.props if k == "bell"]
        if len(bells) < 2:
            return "no bells in this temple layout"
        g.temple_bells_today = set()
        for i, (gx, gy) in enumerate(bells[:2]):
            pl = g.players[i]
            select_non_item(pl)
            H.place(g, pl, gx, gy - 1)
            pl.energy = 100
            g.player_action(i)
            H.settle(g)
        assert g.players[0].energy >= 120, g.players[0].energy
        assert all(pl.buff("regen") > 0 for pl in g.players if hasattr(pl, "buff")), "no Harmony"
        H.frames(g, 10, draw_every=5)
        # regression: today's bell calm / fortune / merit survive a reload
        g.fortune_read.add(1)
        g.fortune[1], g.merit[1] = "lucky", 2
        d = json.loads(json.dumps(g._collect_save()))
        g.temple_bells_today = set()
        g.fortune_read, g.fortune, g.merit = set(), {0: None, 1: None}, {0: 0, 1: 0}
        g._on_load_temple_bells(d)
        assert g.temple_bells_today == {0, 1}, g.temple_bells_today
        assert 1 in g.fortune_read and g.fortune[1] == "lucky" and g.merit[1] == 2
        d["temple_today"]["day"] = "0|0|0"                  # another day: fresh
        g._on_load_temple_bells(d)
        assert not g.temple_bells_today
        g.fortune_read, g.fortune, g.merit = set(), {0: None, 1: None}, {0: 0, 1: 0}
        return "Harmony buff; daily bell saved"
    check("story: temple bells harmony", temple_bells)

    def journal_tabs():
        surf = pygame.Surface((1000, 560))
        for n in ("_journal_tab_40_story_friends", "_journal_tab_45_story_restoration"):
            tab = getattr(g, n)()
            assert tab["title"]
            tab["draw"](surf, pygame.Rect(10, 10, 980, 540))
            if "key" in tab:
                tab["key"](P1_KEYS["down"])
            g.screen.fill((54, 48, 68))
            g.screen.blit(surf, (140, 80))
            H.shot(g, "story_" + n.rsplit("_", 1)[1] + "_tab")
        # and inside the real Journal screen (UI domain), when it is there
        if hasattr(g, "journal_open"):
            g.state = "play"
            g.journal_open()
            tabs = getattr(g, "_jr_tabs", None) or []
            for want in ("Friends", "Bundles"):
                ix = next((i for i, t in enumerate(tabs) if t.get("title") == want), None)
                if ix is not None:
                    g._jr_idx = ix
                    g._jr_flip = 0.0
                    g.draw()
                    H.shot(g, "story_journal_" + want.lower())
            H.settle(g)
            g.state = "play"
        return "2 tabs"
    check("story: journal tabs", journal_tabs)

    def quest_emit():
        from src import quests
        got = []
        orig = g.emit

        def spy(event, **d):
            got.append(event)
            return orig(event, **d)
        g.emit = spy
        try:
            q = {"item": "wood", "qty": 1, "reward": 10, "npc": "Kai"}
            g.active_quests = [q]
            g.quest_offers = [quests.generate() for _ in range(3)]
            g.players[0].inv.add("wood", 1)
            f0 = g.world.friend.get("Kai", 0)
            m = quests.QuestMenu(g, g.players[0])
            g.quest, g.state = m, "quest"
            g.draw()
            H.shot(g, "story_quest_board")
            m.sel = 0
            m.confirm()
            g.state = "play"
            assert g.world.friend.get("Kai", 0) > f0 or f0 >= 500
        finally:
            del g.emit
        assert "quest_done" in got, got
        # regression: no trophies / keepsakes / crafted consumables on the board
        quests._POOL = None
        pool = set(quests._pool())
        bad = pool & {"golden_egg", "twin_locket", "city_key", "cursed_gear",
                      "bomb", "mega_bomb", "rope_ladder"}
        assert not bad, bad
        return "quest_done emitted"
    check("story: quest_done emit", quest_emit)

    def town_intro():
        # regression (round 2): a brand-new farm must not hear that villagers
        # "moved in" (every Friends card is still "Not met yet"), the subtitle
        # has no dangling "--", and the Restoration Board hint follows later
        # instead of stacking on top of the intro + area title card.
        # Drives the story hooks directly (no global frames), so other domains'
        # timers -- e.g. the queued achievement cheers -- are left untouched.
        sp = H.spawns_by_area(g)
        keep = (g.story_intro, g.story_board_intro, g.story_newcomers,
                getattr(g, "started", False), list(getattr(g, "toasts", [])))
        g.started = True                    # the intro waits for real play (not boot)

        def enter_town():
            g.warp(AREA_FARM, sp[AREA_FARM])
            g.toasts = []
            g.warp(AREA_TOWN, sp[AREA_TOWN])
            return {t[0]: t[1] for t in g.toasts}

        def tick(n=3):
            for _ in range(n):
                g._on_area_update_story_villagers(H.DT)

        try:
            set_time(0, 1, 10)
            g.story_intro = g.story_board_intro = g.story_newcomers = False
            got = enter_town()
            assert "Meet the neighbours!" in got, got
            sub = got["Meet the neighbours!"]
            assert "moved in" not in sub and "--" not in sub, sub
            assert not any("Restoration Board" in t for t in got), got
            assert g._story_board_hint_t and g._story_board_hint_t > 4.0
            tick()
            assert not g.story_board_intro and g._story_board_hint_t > 4.0
            g._story_board_hint_t = 0.02                    # fast-forward the wait
            tick()
            assert g.story_board_intro and g._story_board_hint_t is None
            assert any("Restoration Board" in t[0] for t in g.toasts), g.toasts
            # leaving town before the hint shows re-arms it on the next visit
            g.story_board_intro = False
            got = enter_town()
            assert not ({"Meet the neighbours!", "New faces in the valley!"}
                        & set(got)), got                    # intro is one-shot
            assert g._story_board_hint_t is not None
            g.warp(AREA_FARM, sp[AREA_FARM])
            tick()
            assert g._story_board_hint_t is None and not g.story_board_intro
            enter_town()
            assert g._story_board_hint_t is not None
            g._story_board_hint_t = None
            g.story_board_intro = True
            # save round-trip; an old save without the keys gets the
            # "moved in" news (and it survives a save before the town visit)
            d = json.loads(json.dumps(g._collect_save()))
            assert d["story_board_intro"] is True and d["story_newcomers"] is False
            old = {k: v for k, v in d.items()
                   if k not in ("story_intro", "story_board_intro", "story_newcomers")}
            g._on_load_story(old)
            assert g.story_newcomers and not g.story_intro and not g.story_board_intro
            d2 = json.loads(json.dumps(g._collect_save()))
            g._on_load_story(d2)
            assert g.story_newcomers and not g.story_intro
            d3 = json.loads(json.dumps(g._collect_save()))
            assert {k: v for k, v in d3.items() if k.startswith("story_")} ==                 {k: v for k, v in d2.items() if k.startswith("story_")}
            got = enter_town()
            assert "New faces in the valley!" in got, got
            assert "moved in" in got["New faces in the valley!"]
            assert "--" not in got["New faces in the valley!"]
            g.draw()
            H.shot(g, "story_town_intro")
            # a save from before the board hint existed saw both at once
            mid = {k: v for k, v in d.items() if k != "story_board_intro"}
            g._on_load_story(mid)
            assert g.story_board_intro and not g.story_newcomers
            # the "Not met yet" Friends cards point at where to say hi
            from src.systems.story_system import VILLAGER_ORDER
            lost = [n for n in VILLAGER_ORDER if g._story_now_where(n) == "?"]
            assert not lost, lost
        finally:
            (g.story_intro, g.story_board_intro, g.story_newcomers, g.started,
             g.toasts) = keep
            g._story_board_hint_t = None
        return "fresh vs old-save intro wording, board hint deferred"
    check("story: town intro toast", town_intro)

    # leave a sane play state
    set_time(0, 3, 9)
    g.state = "play"
    g.warp(AREA_FARM, H.spawns_by_area(g)[AREA_FARM])
    return "story tests done"
