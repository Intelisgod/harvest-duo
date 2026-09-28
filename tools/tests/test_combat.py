"""Domain tests: Combat, Mining & Progression (Chat 1).

run(g, check, H) is called by tools/smoke_test.py (section "domain").
Covers: biome spawning, every new monster AI + art, bosses (spit / slam),
combat juice (crit numbers, knockback, poof, monster_killed), gems, bombs +
Workbench crafting tab, achievements (unlock, reward, no double unlock, save),
and the journal "Achievements" tab.
"""


def run(g, check, H):
    import pygame
    from src import monsters as M, loot, craft, progress as PR
    from src.entities import Monster
    from src.settings import TILE, AREA_MINE, AREA_FARM

    p = g.players[0]

    def go_mine(depth):
        g.state = "play"
        g.world.mine_level = depth
        g.world.regen_mine(depth)
        g.warp(AREA_MINE, (5, 3))
        H.frames(g, 2)
        for q in g.players:
            q.health = 9999
            q.hurt_cd = 0
        return g.world.area

    def free_tile(area, near):
        gx0, gy0 = near
        for r in range(0, 8):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    gx, gy = gx0 + dx, gy0 + dy
                    if 1 < gx < area.w - 2 and 1 < gy < area.h - 2 and not area.is_solid(gx, gy):
                        return gx, gy
        return near

    # ---------------------------------------------------------- spawning
    def biome_spawns():
        want = {4: "rock", 5: "ice", 12: "lava", 16: "crystal", 22: "abyss", 33: "ruins"}
        out = []
        for d, b in want.items():
            assert M.biome_for_depth(d) == b, (d, M.biome_for_depth(d))
            names = M.eligible(d)
            assert names, d
            for n in names:
                bs = M.ARCHETYPES[n].get("biomes")
                assert not bs or b in bs, (n, b)
            natives = [n for n in names if M.ARCHETYPES[n].get("biomes") == (b,)]
            assert len(natives) >= 2, (b, names)
            out.append(f"{b}:{len(natives)}")
        assert M.boss_for_depth(20) == "abyss_wyrm" and M.boss_for_depth(25) == "abyss_wyrm"
        assert M.boss_for_depth(30) == "ruin_colossus" and M.boss_for_depth(45) == "ruin_colossus"
        assert M.boss_for_depth(5) == "slime_king"
        for n, a in M.ARCHETYPES.items():            # sane scaling everywhere
            for d in (1, 30, 100):
                assert 0 < M.hp_for(n, d) < 5000 and M.damage_for(n, d) < 200, (n, d)
        return " ".join(out)
    check("combat: biome-aware spawns + bosses", biome_spawns)

    # ---------------------------------------------------------- every new monster in action
    new = ["ice_bat", "snow_golem", "magma_slime", "fire_imp", "crystal_golem", "prism_wisp",
           "shadow_stalker", "abyss_wraith", "ruin_guardian", "cursed_knight",
           "abyss_wyrm", "ruin_colossus"]

    def monster_ai(name):
        a = M.ARCHETYPES[name]
        depth = max(a["min_depth"], 1)
        area = go_mine(depth)
        g.monsters = []
        gx, gy = free_tile(area, (12, 10))
        place = free_tile(area, (gx + 3, gy))
        H.place(g, p, *place)
        H.place(g, g.players[1], *free_tile(area, (gx + 3, gy + 2)))
        m = Monster(gx, gy, name, depth)
        g.monsters.append(m)
        hp0 = p.health
        states = set()
        for i in range(360):
            g.update(H.DT)
            st = m.__dict__.get("ai") or {}
            states.add(st.get("mode", "-"))
            if st.get("charge", 0) > 0:
                states.add("charging")
            if st.get("blink", 0) > 0:
                states.add("blinking")
            if m.__dict__.get("shots"):
                states.add("shots")
            if i in (60, 200):
                g.draw()
            if i == 200:
                H.shot(g, f"combat_{name}")
            for q in g.players:
                q.health = max(q.health, 5000)
        g.draw()
        return f"{name}: modes={sorted(states)} dmg_taken={hp0 - p.health >= 0}"
    for n in new:
        check(f"combat: AI + art {n}", monster_ai, n)

    def imp_fireball():
        area = go_mine(12)
        g.monsters = []
        gx, gy = free_tile(area, (12, 10))
        m = Monster(gx, gy, "fire_imp", 12)
        g.monsters.append(m)
        H.place(g, p, *free_tile(area, (gx + 3, gy)))
        m.ai = {"base": m.speed, "cd": 0.0, "charge": 0.0, "strafe": 1}
        fired = False
        for _ in range(120):
            g.update(H.DT)
            if m.__dict__.get("shots"):
                fired = True
                break
        assert fired, "imp never threw a fireball"
        g.draw()
        return "fireball launched after telegraph"
    check("combat: fire imp telegraphed fireball", imp_fireball)

    def colossus_slam():
        area = go_mine(30)
        g.monsters = []
        gx, gy = free_tile(area, (12, 10))
        m = Monster(gx, gy, "ruin_colossus", 30)
        g.monsters.append(m)
        H.place(g, p, gx, gy)
        p.x += 20
        p.health = 500
        p.hurt_cd = 0
        m.ai = {"base": m.speed, "mode": "windup", "t": 1.2, "dur": 1.25, "prog": 0.0,
                "cd": 3, "wave": None, "combo": 0}
        for _ in range(45):
            p.health = 500
            g.update(H.DT)
        p.hurt_cd = 0
        g.draw()
        H.shot(g, "combat_colossus_windup")
        for _ in range(40):
            g.update(H.DT)
        assert p.health < 500, "slam did not land"
        g.draw()
        H.shot(g, "combat_colossus_slam")
        # walking out of the ring = safe
        m.ai.update({"mode": "windup", "t": 0.05, "dur": 1.0})
        p.health = 500
        p.hurt_cd = 0
        p.x = m.x + TILE * 6
        g.update(H.DT)
        g.update(H.DT)
        g.update(H.DT)
        return f"inside ring: hit; outside ring: {500 - p.health} dmg"
    check("combat: colossus slam telegraph", colossus_slam)

    # ---------------------------------------------------------- juice
    def juice():
        area = go_mine(3)
        g.monsters = []
        gx, gy = free_tile(area, (12, 10))
        m = Monster(gx, gy, "golem", 3)
        m.hp = m.max_hp = 999
        g.monsters.append(m)
        H.place(g, p, gx, gy - 1)
        p.fx, p.fy = 0, 1
        p.add_buff("luck", 10, 10.0, "Test")          # guaranteed crit
        x0, y0 = m.x, m.y
        n0 = len(g._cb_nums)
        g.sword_attack(p)
        assert len(g._cb_nums) > n0 and g._cb_nums[-1][6], "no big crit number"
        crit_dmg = 999 - m.hp
        assert crit_dmg >= 2 * 6, "crit did not double damage"
        for _ in range(5):
            g.update(H.DT)
        g.draw()
        H.shot(g, "combat_slash")
        for _ in range(7):
            g.update(H.DT)
        moved = ((m.x - x0) ** 2 + (m.y - y0) ** 2) ** 0.5
        g.draw()
        H.shot(g, "combat_crit")
        p.buffs.pop("luck", None)
        kills0 = g.ach_counters.get("kills", 0)
        m.hp = 1
        g.sword_attack(p)
        assert m.rewarded and g.ach_counters.get("kills", 0) == kills0 + 1, "monster_killed not emitted"
        g.update(H.DT)
        return f"crit {crit_dmg} dmg, knockback {moved:.0f}px"
    check("combat: crits, numbers, knockback, kill event", juice)

    # ---------------------------------------------------------- gems
    def gems():
        for gid in loot.GEMS + loot.RELICS:
            assert gid in loot.MATERIALS and loot.sell_value(gid) > 0, gid
            import src.assets as A
            A.item_icon(gid)
        class R:
            def random(self):
                return 0.0
        assert loot.roll_rock_gem("ice", 0, R()) == "amethyst"
        assert loot.roll_rock_gem("lava", 0, R()) == "ruby"
        assert loot.roll_rock_gem("nope", 0, R()) is None
        go_mine(6)
        old = loot.ROCK_GEMS["ice"]
        loot.ROCK_GEMS["ice"] = [("amethyst", 1.0)]
        try:
            c0 = p.inv.count("amethyst")
            g.emit("rock_broken", p=p, area=AREA_MINE)
            assert p.inv.count("amethyst") == c0 + 1
        finally:
            loot.ROCK_GEMS["ice"] = old
        return "gem icons + biome gem drop OK"
    check("combat: gems & relics", gems)

    # ---------------------------------------------------------- bombs
    def bombs():
        g.gold += 0
        for item, q in craft.CRAFTABLES["bomb"]["mats"].items():
            p.inv.add(item, q * 2)
        b0 = p.inv.count("bomb")
        assert craft.craft_item(g, p, "bomb")
        assert p.inv.count("bomb") == b0 + craft.CRAFTABLES["bomb"]["qty"]
        # workbench tab UI
        g.craft = craft.UpgradeMenu(g, p)
        g.state = "craft"
        g.craft.handle_key(pygame.K_RIGHT)
        assert g.craft.tab == 1
        g.craft.handle_key(p.keys["action"])
        g.draw()
        H.shot(g, "combat_workbench_crafting")
        g.craft.handle_key(pygame.K_ESCAPE)
        g.state = "play"
        # blast rocks in the mine
        area = go_mine(8)
        g.monsters = []
        rock = next(iter(sorted(area.rocks)))
        rx, ry = rock
        near = [r for r in area.rocks if (r[0] - rx) ** 2 + (r[1] - ry) ** 2 <= 2]
        spot = free_tile(area, (rx, ry + 1))
        H.place(g, p, spot[0], spot[1])
        m = Monster(spot[0], spot[1], "green_slime", 8)
        g.monsters.append(m)
        H.place(g, p, spot[0] + 4, spot[1])
        H.place(g, g.players[1], spot[0] - 4, spot[1])
        stone0 = p.inv.count("stone")
        assert g._on_tool_combat_bomb(0, p, "bomb", rx, ry + 1) is True
        g._cb_bombs[-1]["x"] = rx * TILE + TILE / 2
        g._cb_bombs[-1]["y"] = (ry + 1) * TILE + TILE / 2
        H.frames(g, 30)
        g.draw()
        H.shot(g, "combat_bomb_lit")
        H.frames(g, 80)
        g.draw()
        H.shot(g, "combat_bomb_boom")
        gone = [r for r in near if r not in area.rocks]
        assert gone, "bomb broke no rocks"
        assert p.inv.count("stone") > stone0
        assert m.hp < m.max_hp
        # mega bomb: craft + bigger blast
        for item, q in craft.CRAFTABLES["mega_bomb"]["mats"].items():
            p.inv.add(item, q)
        assert craft.craft_item(g, p, "mega_bomb")
        rocks0 = len(area.rocks)
        rx2, ry2 = sorted(area.rocks)[len(area.rocks) // 2]
        spot2 = free_tile(area, (rx2, ry2))
        H.place(g, p, spot2[0] + 5, spot2[1])
        assert g._on_tool_combat_bomb(0, p, "mega_bomb", spot2[0], spot2[1]) is True
        assert g._cb_bombs[-1]["kind"] == "mega_bomb"
        g._cb_bombs[-1]["x"] = spot2[0] * TILE + TILE / 2
        g._cb_bombs[-1]["y"] = spot2[1] * TILE + TILE / 2
        H.frames(g, 110)
        assert len(area.rocks) < rocks0, "mega bomb broke nothing"
        # rope ladder: craft + skip a level (blocked while a boss lives)
        for item, q in craft.CRAFTABLES["rope_ladder"]["mats"].items():
            p.inv.add(item, q)
        assert craft.craft_item(g, p, "rope_ladder")
        lvl = g.world.mine_level
        g.monsters = []
        assert g._on_tool_combat_ladder(0, p, "rope_ladder", 0, 0) is True
        assert g.world.mine_level == lvl + 1 and g.world.current == AREA_MINE
        # outside the mine: refused, bomb kept
        g.warp(AREA_FARM, H.spawns_by_area(g)[AREA_FARM])
        p.inv.add("bomb", 1)
        c = p.inv.count("bomb")
        g._on_tool_combat_bomb(0, p, "bomb", 5, 5)
        assert p.inv.count("bomb") == c
        return f"crafted; blast broke {len(gone)} rocks"
    check("combat: bombs + workbench crafting", bombs)

    # ---------------------------------------------------------- achievements
    def achievements():
        g.state = "play"
        gold0 = g.gold
        un0 = set(g.ach_unlocked)
        g.emit("harvest", p=p, item="parsnip", qty=1)
        g.emit("fish_caught", p=p, fish="the_legend", size=40)
        g.emit("item_sold", p=p, item="parsnip", qty=1, gold=1200)
        g.emit("monster_killed", p=p, kind="abyss_wyrm", boss=True)
        g.emit("mist_run_end", kills=3, loot={}, reason="leave", zone="mist", zone_index=1)
        new = set(g.ach_unlocked) - un0
        for k in ("first_harvest", "first_fish", "legendary_fish", "gold_1k",
                  "boss_abyss_wyrm", "mist_run"):
            assert k in g.ach_unlocked, k
        assert g.gold > gold0
        assert g._ach_unlock("first_harvest") is False       # no double unlock
        # save round trip keeps them
        d = g._collect_save()
        assert set(d["ach_unlocked"]) == set(g.ach_unlocked)
        g._on_load_progress(d)
        assert set(g.ach_unlocked) >= new
        H.frames(g, 70)                                       # periodic scan runs
        return f"{len(g.ach_unlocked)}/{len(PR.ACH_KEYS)} unlocked (+{len(new)} now)"
    check("progress: achievements unlock + reward + save", achievements)

    # ---------------------------------------------------------- review fixes
    def ach_no_quick_farm():
        """Emote spam / gift ping-pong / Mist bail-out must not pay on day 1."""
        g.state = "play"
        for k in ("emotes_20", "partner_gifts", "mist_run"):
            g.ach_unlocked.discard(k)
        for c in ("emote_days", "partner_gift_days", "mist_runs",
                  "_day:emote_days", "_day:partner_gift_days"):
            g.ach_counters.pop(c, None)
        gold0 = g.gold
        q = g.players[1] if len(g.players) > 1 else p
        for _ in range(25):
            g.emit("emote", p=p, kind="heart")
            g.emit("partner_gift", p=p, to=q, item="sardine")
        g.emit("mist_run_end", kills=0, loot=0, reason="leave", zone="mist",
               zone_index=0, boss=False, time=2.0)
        assert g.gold == gold0, f"paid {g.gold - gold0}g for spam"
        assert g.ach_counters.get("emote_days") == 1
        assert g.ach_counters.get("partner_gift_days") == 1
        assert "mist_run" not in g.ach_unlocked
        # ...but real play still gets there: one emote a day for 7 days
        day0 = (g.time.day, g.time.season_idx, g.time.year)
        try:
            for i in range(7):
                g.time.day = (day0[0] + i) % 28 + 1
                g.emit("emote", p=p, kind="wave")
            assert "emotes_20" in g.ach_unlocked
        finally:
            g.time.day, g.time.season_idx, g.time.year = day0
        g.emit("mist_run_end", kills=9, loot=2, reason="victory", zone="tower",
               zone_index=2, boss=True, time=300.0)
        g.emit("monster_killed", p=p, kind="bell_keeper", boss=True)
        g.emit("monster_killed", p=p, kind="mist_walker", boss=False)
        for k in ("mist_run", "mist_tower", "boss_bell_keeper"):
            assert k in g.ach_unlocked, k
        g.emit("bundle_done", name="Valley Restored")
        g.emit("crafted", p=p, what="honey", machine="machine_bee_house")
        for k in ("valley_restored", "first_artisan"):
            assert k in g.ach_unlocked, k
        return f"spam paid 0g; {len(g.ach_unlocked)}/{len(PR.ACH_KEYS)} unlocked"
    check("progress: no quick achievement farming", ach_no_quick_farm)

    def festival_star():
        """Festival Star is reachable: 3 contest wins (festival_won, as Story sends
        them) + Lantern Night released together (no festival_won, it is cooperative)."""
        import json
        g.state = "play"
        g.ach_unlocked.discard("festival_all")
        for k in [k for k in g.ach_counters if k.startswith("fest:")] + ["festival_kinds"]:
            g.ach_counters.pop(k, None)
        nights0 = set(getattr(g, "story_lantern_nights", set()) or ())
        try:
            g.story_lantern_nights = set()
            for name in ("egg_hunt", "luau_potluck", "harvest_fair"):
                g.emit("festival_won", p=p, name=name)
            H.frames(g, 70)
            assert g.ach_counters.get("festival_kinds") == 3
            assert "festival_all" not in g.ach_unlocked, "unlocked without Lantern Night"
            if hasattr(g, "_story_release_lanterns"):     # the real Story path
                g._story_release_lanterns()
            else:
                g.story_lantern_nights.add(str(g.time.year))
            gold0 = g.gold
            H.frames(g, 70)                                # periodic scan picks it up
            assert g.ach_counters.get("fest:lantern_night") == 1
            assert "festival_all" in g.ach_unlocked, g.ach_counters.get("festival_kinds")
            assert g.gold - gold0 == PR.ACH["festival_all"]["gold"], g.gold - gold0
            d = json.loads(json.dumps(g._collect_save()))
            assert d["ach_counters"]["festival_kinds"] == 4
            assert "Lantern" in PR.ACH["festival_all"]["desc"]
            # an old save that already had a Lantern Night records it quietly
            g._on_load_progress({"ach_counters": {"fest:egg_hunt": 1, "fest:luau_potluck": 1,
                                                  "fest:harvest_fair": 1, "festival_kinds": 3}})
            g.story_lantern_nights = {"1"}
            gold1 = g.gold
            H.frames(g, 70)
            assert "festival_all" in g.ach_unlocked and g.gold == gold1
            g._on_load_progress(d)
            H.frames(g, 2)
        finally:
            g.story_lantern_nights = nights0
        return "3 contests + Lantern Night = 4/4"
    check("progress: Festival Star reachable", festival_star)

    def ach_toast_no_pileup():
        """One achievement = one toast, no duplicate log line, and it waits while
        the toast stack is busy (first fish + intro cards)."""
        g.state = "play"
        g.ach_unlocked.discard("kills_100")
        g.toasts = []
        g._ach_toast_q = []
        g._ach_toast_gap = 0.0
        g.ui.messages = []
        for i in range(3):
            g.toast(f"Busy card {i}", "", None, None, 2.0)
        gold0 = g.gold
        g.ach_counters["kills"] = 99
        g.emit("monster_killed", p=p, kind="green_slime", boss=False)
        assert "kills_100" in g.ach_unlocked and g.gold >= gold0 + 600, "reward paid at once"
        titles = lambda: [t[0] for t in g.toasts]
        hunter = lambda: sum(1 for t in g.toasts if t[1].startswith("Monster Hunter"))
        assert "Achievement unlocked!" not in titles(), "cheer should wait for the busy stack"
        H.frames(g, 30)
        assert "Achievement unlocked!" not in titles()
        H.frames(g, 120)                                  # busy cards fade
        assert hunter() == 1, titles()
        assert len(g.toasts) <= 2, titles()
        assert not any("Achievement unlocked" in m[0] for m in g.ui.messages), g.ui.messages
        # a free stack shows the cheer right away; bursts cascade one by one
        g.toasts = []
        g._ach_toast_gap = 0.0
        for k in ("first_bomb", "cooked_5"):
            g.ach_unlocked.discard(k)
            g._ach_unlock(k)
        assert titles().count("Achievement unlocked!") == 1 and len(g._ach_toast_q) == 1
        H.frames(g, 60)
        assert titles().count("Achievement unlocked!") == 2 and not g._ach_toast_q
        # a warp shows whatever is still waiting (nothing leaks into the next area)
        for i in range(3):
            g.toast(f"Busy card {i}", "", None, None, 9.0)
        g.ach_unlocked.discard("first_bomb")
        g._ach_unlock("first_bomb")
        assert g._ach_toast_q
        g.warp(AREA_FARM, H.spawns_by_area(g)[AREA_FARM])
        assert not g._ach_toast_q and "Achievement unlocked!" in titles()
        # never stuck: a stack that stays full still shows it after the wait
        g.toasts = []
        for i in range(3):
            g.toast(f"Busy card {i}", "", None, None, 9.0)
        g._ach_toast_gap = 0.0
        g.ach_unlocked.discard("first_gem")
        g._ach_unlock("first_gem")
        assert g._ach_toast_q, "a full stack should make the cheer wait"
        for _ in range(int(4.5 * 60)):
            while len(g.toasts) < 3:
                g.toast("Spam", "", None, None, 9.0)
            H.frames(g, 1)
            if not g._ach_toast_q:
                break
        assert not g._ach_toast_q, "cheer waited forever"
        g.toasts = []
        return "1 toast, 0 duplicate log lines, waits for a calm stack"
    check("progress: achievement toast does not pile up", ach_toast_no_pileup)


    def boss_no_respawn():
        """Leaving a cleared boss floor and stepping back must not respawn it."""
        import json
        area = go_mine(20)
        boss = next((m for m in g.monsters if m.boss), None)
        assert boss is not None, "no boss on floor 20"
        boss.hp = 1
        g._cb_hit(g.players[0], boss, 50)
        assert 20 in g.cb_boss_cleared
        g.warp(AREA_FARM, H.spawns_by_area(g)[AREA_FARM])
        g.warp(AREA_MINE, (5, 3))
        assert not any(m.boss for m in g.monsters), "boss respawned on re-entry"
        assert g.monsters, "minions should still spawn"
        d = json.loads(json.dumps(g._collect_save()))
        assert d["cb_boss_cleared"] == sorted(g.cb_boss_cleared)
        g._on_load_combat({})                      # old save: nothing cleared
        assert g.cb_boss_cleared == set()
        g._on_load_combat(d)
        assert 20 in g.cb_boss_cleared
        # a new season lets the bosses regroup
        day = g.time.day
        g.time.day = 1
        g._on_new_day_combat()
        g.time.day = day
        assert not g.cb_boss_cleared
        return "cleared floor stays clear"
    check("combat: boss floor does not respawn", boss_no_respawn)

    def deep_damage_cap():
        """No monster hit one-shots a fresh 100 HP player, even at depth 100."""
        worst = 0
        for n, a in M.ARCHETYPES.items():
            for d in (30, 50, 75, 100):
                worst = max(worst, M.damage_for(n, d))
        from src import monster_ai as AI
        slam = min(AI.SLAM_CAP, int(M.damage_for("ruin_colossus", 100) * 1.4))
        assert worst <= M.BOSS_DMG_CAP and slam < 70, (worst, slam)
        assert M.damage_for("green_slime", 1) == 5          # early game untouched
        assert M.damage_for("skeleton", 20) == 18
        return f"max hit {worst}, slam {slam}"
    check("combat: deep-floor damage capped", deep_damage_cap)

    def net_and_old_saves():
        import json
        from src import monster_ai as AI
        area = go_mine(22)
        m = Monster(12, 10, "abyss_wyrm", 22)
        g.monsters = [m]
        H.frames(g, 90)
        row = json.loads(json.dumps(AI.net_pack(m)))
        m2 = Monster(12, 10, "abyss_wyrm", 22)
        AI.net_unpack(m2, row)
        m2.draw(g.screen, g.cam)
        # an old save without any achievement keys loads clean
        snap = (set(g.ach_unlocked), dict(g.ach_counters), set(g.ach_gems))
        g._on_load_progress({})
        assert not g.ach_unlocked and not g.ach_counters
        g.ach_unlocked, g.ach_counters, g.ach_gems = set(snap[0]), dict(snap[1]), set(snap[2])
        return f"net row {len(json.dumps(row))} bytes"
    check("combat: net pack/unpack + old save", net_and_old_saves)

    def journal_tab():
        tab = g._journal_tab_20_progress()
        assert tab["title"] == "Achievements"
        g.state = "play"
        g.journal_open("Achievements")                 # the real journal page
        try:
            cur = g._journal_tabs()[g._jr_idx]
            assert cur["title"] == "Achievements", cur["title"]
            for k in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_LEFT, pygame.K_UP, pygame.K_x):
                tab["key"](k)
                g._jr_flip = 0.0                       # no page-flip mid-shot
                g.draw()
            H.shot(g, "combat_journal_achievements")
        finally:
            g._journal_close()
            g.state = "play"
        return "drawn"
    check("progress: journal achievements tab", journal_tab)

    def ach_old_save_quiet():
        """A pre-upgrade save gets its met achievements recorded without gold."""
        import json
        g.state = "play"
        full = json.loads(json.dumps(g._collect_save()))
        old = json.loads(json.dumps(full))
        for k in ("ach_unlocked", "ach_counters", "ach_gems"):
            old.pop(k, None)
        g.reset()
        g._apply_save(json.loads(json.dumps(old)))
        g.state = "play"
        g.world.friend[next(iter(g.world.friend), "Mira")] = 250
        g.players[0].tool_tiers["pickaxe"] = 4
        gold0 = g.gold
        H.frames(g, 90)
        gained = g.gold - gold0
        assert "friend_5" in g.ach_unlocked and "master_smith" in g.ach_unlocked
        assert gained == 0, f"old save paid {gained}g on load"
        n = len(g.ach_unlocked)
        # new progress after the quiet scan pays again
        g.emit("monster_killed", p=g.players[0], kind="ruin_colossus", boss=True)
        assert "boss_ruin_colossus" in g.ach_unlocked and g.gold > gold0
        g.reset()
        g._apply_save(full)
        g.state = "play"
        H.frames(g, 2)
        return f"{n} recorded quietly, 0g"
    check("progress: old save achievements are quiet", ach_old_save_quiet)

    g.state = "play"
    g.warp(AREA_FARM, H.spawns_by_area(g)[AREA_FARM])
    for q in g.players:
        q.health = q.max_health
    return "combat domain tests done"
