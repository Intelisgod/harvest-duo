"""Core (Chat 0) domain checks: events, emotes + love boost, partner gifting,
stats + day report, new weather, particles, LAN snapshot. Run by
tools/smoke_test.py (section "domain") as run(g, check, H)."""
import json

import pygame


def run(g, check, H):
    from src.settings import (P1_KEYS, P2_KEYS, AREA_FARM, AREA_MINE, AREA_FOREST,
                              TILE, MAX_ENERGY)
    from src import weather
    sp = H.spawns_by_area(g)
    p1, p2 = g.players
    ev = pygame.event.Event

    def key(k):
        return ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)

    def select(p, kind, name, slot=7):
        """Put an entry on the hotbar (it may sit in the backpack) and select it."""
        i = H.hotbar_index(p, kind, name)
        if i is None and hasattr(p.inv, "set_slot"):
            p.inv.set_slot(slot, (kind, name))
            i = H.hotbar_index(p, kind, name)
        if i is not None:
            p.inv.selected = i
        return p.inv.selected_entry() == (kind, name)

    def back_to_play():
        H.settle(g)
        g.state = "play"

    # ---------------------------------------------------------- settings merge
    def settings_merge():
        assert P1_KEYS.get("emote") == pygame.K_f and P2_KEYS.get("emote") == pygame.K_SLASH
        old = {"keys": {"p1": {"up": pygame.K_w, "action": pygame.K_SPACE},
                        "p2": {"up": pygame.K_UP}}}       # an old settings.json
        g._apply_settings(old)
        assert P1_KEYS["emote"] == pygame.K_f, "old settings wiped the emote key"
        assert P2_KEYS["emote"] == pygame.K_SLASH
        assert any(a == "emote" for a, _l in __import__("src.settings", fromlist=["x"]).KEY_ACTIONS)
    check("core: old settings keep emote default", settings_merge)

    # ---------------------------------------------------------- emotes
    def emotes():
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        H.frames(g, 90)                                   # let the warp card clear
        g.emotes = [None, None]
        g.on_keydown(P1_KEYS["emote"])
        assert g.emotes[0] and g.emotes[0][0] == "heart", g.emotes
        g.on_keydown(P1_KEYS["emote"])                    # press again = next on wheel
        assert g.emotes[0][0] == "happy", g.emotes
        for _ in range(6):
            g.on_keydown(P1_KEYS["emote"])
        g.on_keydown(P2_KEYS["emote"])
        H.frames(g, 14)
        g.draw()
        H.shot(g, "core_emote_bubble")
        # a key ALSO bound to a real action is never swallowed by the emote hook
        old = P1_KEYS["next"]
        try:
            P1_KEYS["next"] = P1_KEYS["emote"]
            sel = p1.inv.selected
            g.emotes = [None, None]
            g.on_keydown(P1_KEYS["emote"])
            assert g.emotes[0] is None, "emote stole a key bound to 'next'"
            assert p1.inv.selected != sel or len(p1.inv.hotbar()) <= 1
        finally:
            P1_KEYS["next"] = old
        H.frames(g, int(2.6 / H.DT))
        assert g.emotes[0] is None, "bubble never expired"
        return "wheel ok"
    check("core: emote wheel + expiry", emotes)

    def love_boost():
        g.state = "play"
        H.place(g, p1, sp[AREA_FARM][0], sp[AREA_FARM][1])
        H.place(g, p2, sp[AREA_FARM][0] + 1, sp[AREA_FARM][1])
        g.emotes = [None, None]
        g._love_cd = 0.0
        p1.energy = p2.energy = 100
        before = g.stats_today.get("love", 0)
        g.on_keydown(P1_KEYS["emote"])
        H.frames(g, 10)
        g.on_keydown(P2_KEYS["emote"])
        assert p1.energy >= 115 and p2.energy >= 115, (p1.energy, p2.energy)
        assert g._love_cd > 50, g._love_cd
        assert g.stats_today["love"] == before + 1
        g.draw()
        H.shot(g, "core_love_boost")
        # on cooldown: no second boost
        g.emotes = [None, None]
        e = p1.energy
        g.on_keydown(P1_KEYS["emote"])
        g.on_keydown(P2_KEYS["emote"])
        assert p1.energy == e, "love boost ignored its cooldown"
        g._love_cd = 0.0
        g.emotes = [None, None]
    check("core: love boost + cooldown", love_boost)

    # ---------------------------------------------------------- partner gifting
    def partner_gift():
        g.state = "play"
        gx, gy = sp[AREA_FARM]
        H.place(g, p1, gx, gy)
        H.place(g, p2, gx + 1, gy)
        p1.fx, p1.fy = 1, 0
        p1.inv.add("wood", 3)
        assert select(p1, "item", "wood"), "could not select wood"
        a0, b0 = p1.inv.count("wood"), p2.inv.count("wood")
        n0 = sum(g.stats_today["n"]["partner_gifts"])
        p1.moving = False
        g.emotes = [None, None]
        assert g._gift_target(0) is not None, "facing partner not detected"
        g.draw()
        H.shot(g, "core_gift_hint")
        g.player_action(0)
        assert p1.inv.count("wood") == a0 - 1 and p2.inv.count("wood") == b0 + 1, \
            (p1.inv.count("wood"), p2.inv.count("wood"))
        assert sum(g.stats_today["n"]["partner_gifts"]) == n0 + 1
        g.draw()
        H.shot(g, "core_partner_gift")
        # facing AWAY from the partner: no gift (press falls through)
        p1.fx, p1.fy = -1, 0
        assert select(p1, "item", "wood")
        a1 = p1.inv.count("wood")
        b1 = p2.inv.count("wood")
        g.player_action(0)
        back_to_play()
        assert p2.inv.count("wood") == b1, "gifted while not facing the partner"
        # a tool selected never gifts
        p1.fx, p1.fy = 1, 0
        assert select(p1, "tool", "hoe")
        g.player_action(0)
        back_to_play()
        assert p2.inv.count("wood") == b1
        return f"wood {a1}->{p1.inv.count('wood')}"
    check("core: partner gift (facing only)", partner_gift)

    # ---------------------------------------------------------- core events
    def plant_event():
        g.state = "play"
        gx, gy = sp[AREA_FARM]
        n0 = sum(g.stats_today["n"]["planted"])
        g.world.tilled.add((AREA_FARM, gx, gy + 3))
        g.world.crops.pop((AREA_FARM, gx, gy + 3), None)
        crop = next((c for c, d in __import__("src.crops", fromlist=["CROPS"]).CROPS.items()
                     if d["season"] == g.time.season), None)
        if crop is None:
            return "no crop this season"
        p1.inv.add("seed:" + crop, 2)
        assert select(p1, "item", "seed:" + crop), "could not select seed"
        g.use_tool(0, (gx, gy + 3))
        assert sum(g.stats_today["n"]["planted"]) == n0 + 1
    check("core: crop_planted event -> stats", plant_event)

    def rock_tree_events():
        g.warp(AREA_FOREST, sp[AREA_FOREST])
        g.state = "play"
        area = g.world.area
        if area.trees:
            t = next(iter(area.trees))
            assert select(p1, "tool", "axe")
            n0 = sum(g.stats_today["n"]["trees"])
            g.use_tool(0, t)
            assert sum(g.stats_today["n"]["trees"]) == n0 + 1
        g.world.regen_mine(max(1, g.world.mine_level))
        g.warp(AREA_MINE, sp.get(AREA_MINE, (5, 3)))
        g.state = "play"
        area = g.world.area
        if area.rocks:
            r = next(iter(area.rocks))
            assert select(p1, "tool", "pickaxe")
            n0 = sum(g.stats_today["n"]["rocks"])
            g.use_tool(0, r)
            assert sum(g.stats_today["n"]["rocks"]) == n0 + 1
        # ladder -> mine_depth
        if area.ladder:
            g.monsters = []
            H.place(g, p1, area.ladder[0], area.ladder[1])
            lvl = g.world.mine_level
            g.player_action(0)
            back_to_play()
            assert g.stats_today["deepest"] >= lvl + 1, (g.stats_today["deepest"], lvl)
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
    check("core: rock/tree/mine_depth events -> stats", rock_tree_events)

    # ---------------------------------------------------------- day report
    def day_report():
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        g.emit("harvest", p=p1, item="parsnip", qty=4)
        g.emit("fish_caught", p=p2, fish=next(iter(__import__("src.fishing", fromlist=["FISH"]).FISH)))
        g.emit("item_sold", p=p2, item="parsnip", qty=3, gold=105)
        g.emit("partner_gift", p=p1, to=p2, item="wood")
        g.emit("partner_gift", p=p2, to=p1, item="parsnip")
        g.stats_life["days"] = max(1, g.stats_life.get("days", 0))
        g.stats_life["best_gold_day"] = 0
        g._day_gold0 = g.gold                  # today's delta = exactly this sale
        g.gold += 105
        days0 = g.stats_life.get("days", 0)
        g.do_sleep()
        assert g.state == "sleep"
        for _ in range(100):
            g.update_sleep(0.05)
            g.draw()
            if g.state != "sleep":
                break
        assert g.state == "day_report", g.state
        assert g._dr.get("record"), "a +gold day beating best_gold_day should be a record"
        assert "spoiled each other" in g._dr["flavour"], g._dr["flavour"]
        assert g.stats_life.get("days", 0) == days0 + 1
        assert sum(g.stats_today["n"]["crops"]) == 0, "today's stats not reset"
        for _ in range(12):
            g._run_state("update", 0.05)
        g.draw()
        H.shot(g, "core_day_report_anim")
        for _ in range(60):
            g._run_state("update", 0.05)
        g.draw()
        H.shot(g, "core_day_report")
        g._run_state("event", key(P2_KEYS["action"]))
        assert g.state == "play", g.state
        # skip-then-close with the action key
        g._dr = None
        g.state = "day_report"
        g._run_state("event", key(P1_KEYS["action"]))    # skip the count-up
        assert g.state == "day_report"
        g._run_state("event", key(P1_KEYS["action"]))    # close
        assert g.state == "play"
        # online client: never shows the report
        g.day_report = {"x": 1}
        g.net_mode = "client"
        try:
            assert g._open_day_report() is False and g.state == "play"
        finally:
            g.net_mode = None
    check("core: sleep -> day report -> play", day_report)

    def stats_tab():
        tab = g._journal_tab_90_coop_stats()
        assert tab["title"] == "Stats"
        s = pygame.Surface((900, 520))
        tab["draw"](s, pygame.Rect(20, 20, 860, 480))
        return f"{len(g.stats_life)} lifetime keys"
    check("core: journal Stats tab draws", stats_tab)

    # ---------------------------------------------------------- weather
    def weather_kinds():
        for season in ("Spring", "Summer", "Fall", "Winter"):
            seen = {weather.pick(season) for _ in range(400)}
            for w in seen:
                assert weather.valid(w, season), (w, season)
        assert weather.waters("storm") and weather.waters("rain") and not weather.waters("fog")
        assert "storm" in weather.LABEL and "fog" in weather.LABEL and "windy" in weather.LABEL
        assert g.weather_tomorrow in weather.ALL
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        for w, mins in (("storm", 14 * 60), ("fog", 7 * 60), ("windy", 10 * 60)):
            g.weather = w
            g.time.minutes = mins
            g.time.season_idx = 2 if w != "windy" else 0
            H.frames(g, 40)
            g._wx["flash"] = 0.0
            g.draw()
            H.shot(g, f"core_weather_{w}")
            if w == "storm":
                g._wx["flash"] = 0.8
                from src.systems.weather_system import _make_bolt
                g._wx["bolt"] = _make_bolt()
                g.draw()
                H.shot(g, "core_weather_storm_flash")
        g.weather = "sunny"
        g.time.season_idx = 0
        g.time.minutes = 8 * 60
        g._wx["rainbow"] = True
        H.frames(g, 2)
        g.draw()
        H.shot(g, "core_weather_rainbow")
        g._wx["rainbow"] = False
        from src import lighting
        lighting.set_weather_tint(None)
    check("core: storm / fog / windy", weather_kinds)

    def forecast_roll():
        g.weather_tomorrow = "storm"
        g.time.season_idx = 1          # summer: storm valid
        w = g._roll_weather()
        assert w == "storm", w
        assert g.weather_tomorrow in weather.ALL
        g.time.season_idx = 3          # winter: a pre-rolled storm is re-rolled
        g.weather_tomorrow = "storm"
        assert g._roll_weather() in ("snow", "sunny")
        g.time.season_idx = 0
        g.weather = "sunny"
    check("core: forecast pre-roll", forecast_roll)

    def tv_forecast():
        from src import furniture as F
        tv = F.Placed("tv", 6, 3, 0, 0)
        tv.on = False
        g.weather_tomorrow = "storm"
        g.interact_furniture(p1, tv)
        assert tv.on, "TV did not switch on"
        txt = " ".join(str(x) for x in getattr(g.ui, "messages", getattr(g.ui, "log_lines", [])))
        assert g.forecast_text() == "Stormy"
        return txt[-80:] if txt else "logged"
    check("core: TV weather forecast", tv_forecast)

    # ---------------------------------------------------------- particles
    def particles():
        parts = g.parts
        parts.star_burst(100, 100, (255, 220, 120), 8)
        parts.coin_burst(120, 100, 6)
        parts.ring(140, 100, (255, 255, 255), 12)
        parts.petal(160, 100, (255, 190, 210))
        parts.poof(180, 100, (230, 230, 240), 6)
        parts.rain_splash(200, 100)
        for _ in range(20):
            parts.update(H.DT)
            parts.draw(g.screen, g.cam)
    check("core: shaped particles", particles)

    def home_projection():
        from src.settings import AREA_HOME
        from src import homeiso
        g.warp(AREA_HOME, sp[AREA_HOME])
        g.state = "play"
        H.frames(g, 2)
        wx, wy = 5 * TILE + TILE / 2, 4 * TILE + TILE / 2
        g.parts.items.clear()
        g.parts.ring(wx, wy, (255, 255, 255), 8)
        ox, oy = homeiso.origin(g.world.area)
        sx, sy = homeiso.proj(ox, oy, wx / TILE, wy / TILE)
        q = g.parts.items[-1]
        assert abs(q.x - (sx + g.cam.x)) < 1 and abs(q.y - (sy + g.cam.y)) < 1, (q.x, q.y)
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        g.parts.ring(wx, wy, (255, 255, 255), 8)
        assert g.parts.items[-1].x == wx, "farm particles must not be projected"
    check("core: iso home particle projection", home_projection)

    # ---------------------------------------------------------- LAN
    def net_snapshot():
        g.emotes = [["heart", 0.4], None]
        snap = json.loads(json.dumps(g._collect_snapshot()))
        g.emotes = [None, None]
        g._apply_snapshot(snap)
        assert g.emotes[0] and g.emotes[0][0] == "heart", g.emotes
        g.emotes = [None, None]
        json.dumps(g._collect_save())
    check("core: LAN snapshot carries emotes", net_snapshot)

    # ------------------------------------------------ fix round (2026-09-26)
    from src.settings import AREA_TEMPLE, AREA_BEACH, AREA_TOWN, SCREEN_W, SCREEN_H
    from src.systems import net_system as NS, hooks as HK

    class FakeNet:
        """Stand-in transport: records sends, never touches a socket."""
        def __init__(self, connected=True):
            self.connected, self.error, self.sent, self.inbox = connected, None, [], []

        def send(self, m):
            self.sent.append(m)

        def poll(self):
            out, self.inbox = self.inbox, []
            return out

        def close(self):
            self.connected = False

    def snapshot_fishing_buffs():
        g.fishing[1].state, g.fishing[1].fish, g.fishing[1].reel_needed = "bite", "carp", 3
        p2.buffs = {"speed": [0.25, 120.0, "Coffee"]}
        snap = json.loads(json.dumps(g._collect_snapshot()))
        g.fishing[1].state, g.fishing[1].fish = "idle", None
        p2.buffs = {}
        g._apply_snapshot(snap)
        try:
            assert g.fishing[1].state == "bite" and g.fishing[1].fish == "carp", "fishing not synced"
            assert p2.buff("speed") == 0.25, p2.buffs
        finally:
            g.fishing[1].state, g.fishing[1].fish, g.fishing[1].reel_needed = "idle", None, 0
            p2.buffs = {}
    check("core: LAN snapshot carries fishing + buffs", snapshot_fishing_buffs)

    def client_resync_no_respawn():
        g.warp(AREA_MINE, sp.get(AREA_MINE, (5, 5)))
        g.world.regen_mine(5)
        g._spawn_area_entities()
        w = json.loads(json.dumps(g._collect_world()))
        g.net_mode, g._net_world_seen = "client", True
        seen = []
        orig = g._spawn_area_entities
        g._spawn_area_entities = lambda: seen.append(1) or orig()
        try:
            for _ in range(3):
                g._apply_world(w)                  # same area + floor: no area re-entry
            assert not seen, f"resync respawned area entities {len(seen)}x"
            w2 = dict(w, save=dict(w["save"], mine_level=6))
            g._apply_world(w2)                     # a real floor change still respawns
            assert seen, "floor change did not respawn"
        finally:
            del g._spawn_area_entities
            g.net_mode = None
        g.shake = 16.0
        g.net_mode = "client"
        try:
            for _ in range(60):
                g._net_client_step(1 / 60)
            assert g.shake == 0.0, f"client shake never decays ({g.shake})"
        finally:
            g.net_mode = None
        g.world.regen_mine(1)
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
    check("core: LAN 1 Hz resync keeps area entities + shake decays", client_resync_no_respawn)

    def host_disconnect_and_overlay():
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        g.net, g.net_mode = FakeNet(True), "host"
        try:
            g._remote_dirs = [False, False, False, True]
            H.place(g, p2, sp[AREA_FARM][0] + 1, sp[AREA_FARM][1])
            x0 = p2.x
            g.state = "journal"                     # P1 reads the journal...
            for _ in range(30):
                g._net_host_overlay_step(1 / 60)
            assert p2.x > x0 + 4, "P2 frozen while P1 has an overlay open"
            g.state = "play"
            # P2 talks to a villager: the line goes to P2's screen, the host
            # never gets stuck behind a dialogue box P1 didn't open
            g.warp(AREA_TOWN, sp[AREA_TOWN])
            g.state = "play"
            if g.npcs:
                n = g.npcs[0]
                p2.x, p2.y = n.x + TILE * 0.5, n.y
                select(p2, "tool", "hoe")            # talk, not a gift
                g._story_last_talk = {}
                g.net.sent.clear()
                g._apply_remote_event("action")
                assert g.state in ("play", "heart_event"), g.state
                if g.state == "play":
                    assert any(m.get("t") == "toast" for m in g.net.sent), g.net.sent
                g.state = "play"
            g.warp(AREA_FARM, sp[AREA_FARM])
            g.state = "play"
            g.net.connected = False                 # ...then the link drops
            g._net_host_broadcast(1 / 60)
            assert g._remote_dirs == [False] * 4, "P2 input stays latched after a drop"
        finally:
            g.net, g.net_mode = None, None
            g.state = "play"
    check("core: host keeps P2 alive under overlays, drop releases input", host_disconnect_and_overlay)

    def net_ops_parity():
        from src import quests
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        seen = []
        orig_emit = g.emit
        g.emit = lambda ev, **d: (seen.append(ev), orig_emit(ev, **d))
        try:
            p2.inv.add("parsnip", 2)
            q = {"item": "parsnip", "qty": 2, "reward": 120, "npc": "Fah"}
            g.active_quests.append(dict(q))
            f0 = int(g.world.friend.get("Fah", 0))
            g._net_quest_op("turnin", q, buyer=1)
            assert "quest_done" in seen, seen
            assert int(g.world.friend.get("Fah", 0)) > f0, "no villager friendship for P2's quest"
            from src import cooking
            fid = next(iter(cooking.RECIPES))
            for i, n in cooking.RECIPES[fid].items():
                p2.inv.add(i, n)
            g._net_cook_op(fid, buyer=1)
            assert "cooked" in seen, seen
        finally:
            del g.emit
    check("core: LAN client quest/cook emit the shared events", net_ops_parity)

    def fishing_beats_villager():
        g.warp(AREA_BEACH, sp.get(AREA_BEACH, (10, 10)))
        g.state = "play"
        area = g.world.area
        spot = None
        for gy in range(1, area.h - 1):
            for gx in range(1, area.w - 1):
                if not area.is_water(gx, gy) and area.is_water(gx - 1, gy) \
                        and not area.is_water(gx + 1, gy):
                    spot = (gx, gy)
                    break
            if spot:
                break
        assert spot, "no shore tile on the beach"
        H.place(g, p1, *spot)
        p1.fx, p1.fy, p1.dirname = -1, 0, "left"
        from src.npc import NPC
        saved = g.npcs
        g.npcs = [NPC("Somchai", spot[0], spot[1] + 1, friend=g.world.friend)]
        g.npcs[0].x, g.npcs[0].y = p1.x + TILE * 0.8, p1.y + TILE * 0.5
        try:
            assert select(p1, "tool", "fishing_rod"), "no rod"
            g.fishing[0].state = "idle"
            g.player_action(0)
            assert g.state == "play", f"villager hijacked the cast ({g.state})"
            assert g.fishing[0].state == "casting", g.fishing[0].state
        finally:
            g.npcs = saved
            g.fishing[0].state = "idle"
            g.state = "play"
            g.warp(AREA_FARM, sp[AREA_FARM])
    check("core: a villager beside you never steals a fishing cast", fishing_beats_villager)

    def temple_camera_centred():
        g.warp(AREA_TEMPLE, sp.get(AREA_TEMPLE, (10, 10)))
        area = g.world.area
        for _ in range(120):
            g._update_camera(area)
        if area.w * TILE < SCREEN_W:
            want = (area.w * TILE - SCREEN_W) / 2
            assert abs(g.cam.x - want) < 2, (g.cam.x, want)
        g.draw()
        H.shot(g, "core_temple_centred")
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        return f"cam.x={g.cam.x:.0f}"
    check("core: small maps (Temple) are centred", temple_camera_centred)

    def esc_during_sleep():
        g.state = "play"
        g.do_sleep()
        assert g.state == "sleep"
        g.on_keydown(pygame.K_ESCAPE)
        assert g.state == "sleep", f"ESC left the sleep banner ({g.state})"
        g.update_sleep(0.01)
        assert g.state in ("day_report", "play"), g.state
        ok = g.state == "day_report"
        H.settle(g)
        g.state = "play"
        return "report shown" if ok else "no report"
    check("core: ESC on the sleep banner skips to the day report", esc_during_sleep)

    def pgift_persists():
        g._pgift_bonus = {0, 1}
        d = json.loads(json.dumps(g._collect_save()))
        g._pgift_bonus = set()
        g._on_load_coop(d)
        assert g._pgift_bonus == {0, 1}, g._pgift_bonus
    check("core: partner first-gift bonus survives reload", pgift_persists)

    def mist_stats():
        life = g.stats_life
        r0, z0 = life.get("mist_runs", 0), life.get("mist_zombies", 0)
        g.emit("mist_run_end", kills=7, loot=2, reason="leave", boss=False)
        assert life.get("mist_runs") == r0 + 1 and life.get("mist_zombies") == z0 + 7, life
        surf = pygame.Surface((1068, 498))
        g._draw_stats_tab(surf, surf.get_rect())
    check("core: Stats tab counts Mist City runs", mist_stats)

    def load_hook_failure_keeps_data():
        d = json.loads(json.dumps(g._collect_save()))
        d["coop_tips"] = ["kept-tip"]
        cls = type(g)
        orig = cls._on_load_coop

        def boom(self, dd):
            raise ValueError("simulated domain load bug")
        old_strict = HK._STRICT
        HK._STRICT, cls._on_load_coop = False, boom
        try:
            g._apply_save(d)
        finally:
            cls._on_load_coop, HK._STRICT = orig, old_strict
        try:
            assert g._load_failed_hooks == ["_on_load_coop"], g._load_failed_hooks
            out = g._collect_save()
            assert out.get("coop_tips") == ["kept-tip"], out.get("coop_tips")
        finally:
            g._load_failed_hooks, g._load_raw = [], None
            g.load_failed = False
            g._on_load_coop(d)
            g.toasts = []
    check("core: a failing _on_load_ hook never wipes that domain's save keys",
          load_hook_failure_keeps_data)

    def client_never_saves_host_world():
        from src import savegame
        g.state = "play"
        g._save()
        own = savegame.load_game()
        assert own, "no local save to protect"
        own_gold = own["gold"]
        host = json.loads(json.dumps(g._collect_world()))
        host["save"]["gold"] = own_gold + 777
        host["save"]["players"][0]["name"] = "HostFarmer"
        oldc = NS.Client
        NS.Client = lambda ip, port=None: FakeNet(True)
        try:
            g.start_client("127.0.0.1")
            g._apply_world(host)
            assert g.gold == own_gold + 777
            g._save()                               # e.g. an ESC / sleep save
            assert savegame.load_game()["gold"] == own_gold, "client wrote the host world"
            g.net_stop()                            # quit path: net_stop() then _save()
            g._save()
        finally:
            NS.Client = oldc
        disk = savegame.load_game()
        assert disk["gold"] == own_gold, "host world reached the client's disk"
        assert disk["players"][0]["name"] != "HostFarmer"
        assert g.gold == own_gold and not getattr(g, "_net_client_session", False), \
            "local farm not restored after leaving"
        g.state = "play"
    check("core: LAN client never overwrites its own save", client_never_saves_host_world)

    # ------------------------------------------------ fix round 2 (2026-09-26)
    from src.settings import AREA_HOME
    from src.inventory import Inventory

    def logs():
        return " | ".join(str(m[0]) for m in g.ui.messages)

    def transport_never_blocks():
        """A peer that stops reading must never block send() on the game
        thread; the link drops itself once the backlog can't drain."""
        import socket
        import time as _t
        from src.net import transport as T
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        old_stall = T._STALL_S
        T._STALL_S = 0.6
        h = T.Host(port)
        peer = None
        try:
            for _ in range(40):
                try:
                    peer = socket.create_connection(("127.0.0.1", port), timeout=1)
                    break
                except OSError:
                    _t.sleep(0.05)
            assert peer, "could not connect to the test host"
            peer.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
            t_end = _t.time() + 1.0
            while not h.connected and _t.time() < t_end:
                _t.sleep(0.01)
            assert h.connected
            blob = "x" * 9000
            worst = 0.0
            for i in range(600):                   # ~5 MB offered, never read
                a = _t.perf_counter()
                h.send({"t": "world" if i % 30 == 0 else "snap", "b": blob})
                worst = max(worst, _t.perf_counter() - a)
            assert worst < 0.05, f"send() blocked the game loop for {worst:.2f}s"
            assert h.backlog() <= T._BACKLOG_MAX + 20000, f"backlog {h.backlog()}"
            t_end = _t.time() + 4.0
            while h.connected and _t.time() < t_end:
                h.send({"t": "snap", "b": blob})
                _t.sleep(0.02)
            assert not h.connected, "stalled peer never dropped"
            assert h.error == "peer not responding", h.error
            # inbound cap: stale snapshots collapse to the newest one
            msgs = [{"t": "snap", "i": i} for i in range(900)] + [{"t": "toast", "text": "hi"}]
            out = T._trim_inbox(msgs)
            assert len(out) == 2 and out[0]["i"] == 899, out[:3]
        finally:
            T._STALL_S = old_stall
            h.close()
            if peer:
                peer.close()
    check("core: LAN send never blocks on a stalled peer; link drops itself",
          transport_never_blocks)

    def client_rejoin_and_host_left():
        from src import savegame
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        g.started = True
        g._save()
        own_gold = savegame.load_game()["gold"]
        host = json.loads(json.dumps(g._collect_world()))
        host["save"]["gold"] = own_gold + 555
        host["save"]["current"] = AREA_BEACH if AREA_BEACH in g.world.areas else AREA_TOWN
        links = []
        oldc = NS.Client

        def mk(ip, port=None):
            links.append(FakeNet(True))
            return links[-1]
        NS.Client = mk
        try:
            g.start_client("127.0.0.1")
            assert g._card_welcome is False, "client greets with its OWN pre-sync area"
            g._apply_world(host)
            card = getattr(g, "_area_card", None)
            want = host["save"]["current"].replace("_", " ").title()
            assert card and card[0] == want, f"client area card {card!r} != {want}"
            # a second Join while connected closes the first link (never orphaned)
            g.start_client("127.0.0.1")
            assert len(links) == 2 and not links[0].connected, "old link left open"
            assert g.net is links[1] and g._net_world_seen is False
            links[1].ip = "127.0.0.1"               # same host, live link: kept as is
            g.start_client("127.0.0.1")
            assert len(links) == 2 and g.net is links[1] and links[1].connected
            g._apply_world(host)
            g._net_client_step(1 / 60)
            assert g.net_mode == "client"
            # the host quits: back to our own farm with a message
            links[1].connected = False
            links[1].error = "[WinError 10054] reset"
            g._net_client_step(1 / 60)
            assert g.net_mode is None and not getattr(g, "_net_client_session", False)
            assert g.gold == own_gold, "joiner's own farm not restored"
            assert "host left" in logs(), logs()
            assert g.state in ("play", "menu"), g.state
            # a failed join (nothing ever connected) also returns home
            g.start_client("127.0.0.1")
            links[-1].connected = False
            links[-1].error = "timed out"
            g._net_client_step(1 / 60)
            assert g.net_mode is None and "Could not reach" in logs(), logs()
            # the menu's "Leave online game" helper
            g.start_client("127.0.0.1")
            g.net_leave()
            assert g.net_mode is None and g.gold == own_gold and g.state == "play"
            assert "left the online game" in logs(), logs()
        finally:
            NS.Client = oldc
            if g.net_mode:
                g.net_stop()
        g.state = "play"
    check("core: LAN rejoin closes the old link; host leaving returns home; area card",
          client_rejoin_and_host_left)

    def lan_bombs_and_host_notices():
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        if getattr(g, "_cb_bombs", None) is None:
            return
        g._cb_bombs = [{"x": 100.0, "y": 120.0, "t": 1.5, "owner": 1, "kind": "mega_bomb"}]
        snap = json.loads(json.dumps(g._collect_snapshot()))
        assert snap.get("BM") and snap["BM"][0][3] == "mega_bomb", snap.get("BM")
        assert snap.get("hs") == "play"
        g._cb_bombs = []
        g._apply_snapshot(snap)
        assert len(g._cb_bombs) == 1 and g._cb_bombs[0]["kind"] == "mega_bomb"
        g.draw()                                   # Combat draws the synced fuse
        # host: a bomb vanishing at the end of its fuse ships one blast fx
        g.net, g.net_mode = FakeNet(True), "host"
        try:
            g._net_bomb_seen = None
            g._cb_bombs[0]["t"] = 0.04
            g._net_host_bomb_fx()
            g._cb_bombs = []
            g._net_host_bomb_fx()
            fx = [m for m in g.net.sent if m.get("t") == "fx"]
            assert fx and fx[0]["kind"] == "boom" and fx[0]["mega"] == 1, g.net.sent
            g.shake = 0.0
            g._net_apply_fx(fx[0])
            assert g.shake > 0, "client blast has no shake"
            # join / drop notices on the host
            g.ui.messages = []
            g._net_host_seen_conn = False
            g._net_host_broadcast(1 / 60)
            assert "joined" in logs(), logs()
            g.state = "mistcity"
            g.net.sent.clear()
            g._net_host_broadcast(1 / 60)
            assert any("Mist City" in m.get("text", "") for m in g.net.sent), g.net.sent
            g.state = "play"
            g.net.connected = False
            g._net_host_broadcast(1 / 60)
            assert "disconnected" in logs(), logs()
            # P2's bed press while P1 is busy gets an honest answer
            g.net.connected = True
            g.net, g.net_mode = None, None
            g.warp(AREA_HOME, sp[AREA_HOME])            # both farmers home
            g.net, g.net_mode = FakeNet(True), "host"
            g.state = "journal"
            g.net.sent.clear()
            g._net_sleep_op()
            assert any("busy" in m.get("text", "") for m in g.net.sent), g.net.sent
            g._ctx_rest_tasks()
            assert g.state == "journal", "P1's screen was yanked shut by P2's bed"
            g._sleep_pending = False
        finally:
            g.net, g.net_mode = None, None
            g._cb_bombs = []
            g.state = "play"
    check("core: LAN bombs + blast fx, host join/drop/pause notices", lan_bombs_and_host_notices)

    def client_day_report_press():
        p1, p2 = g.players            # a LAN session end rebuilds the players
        oldc = NS.Client
        NS.Client = lambda ip, port=None: FakeNet(True)
        try:
            g.start_client("127.0.0.1")
            home = g.world.areas[AREA_HOME]
            g.world.current = AREA_HOME
            snap = json.loads(json.dumps(g._collect_snapshot()))
            snap["hs"] = "day_report"
            snap["area"] = AREA_HOME
            g._apply_snapshot(snap)
            if home.bed:
                H.place(g, p2, home.bed[0] + 1, home.bed[1])
            g.net.sent.clear()
            g._client_events = []
            g._client_capture_key(NS.CLIENT_KEYS["action"])
            assert g._client_events == ["action"], g._client_events
            assert not any(m.get("m") == "sleep" for m in g.net.sent), g.net.sent
            g._client_events = []
            # the host ships its report: P2 sees the same card, and closing it
            # dismisses the host's card too
            if hasattr(g, "_build_report"):
                rep = json.loads(json.dumps({k: v for k, v in g._build_report().items()}))
                g.state = "play"
                g.net.inbox.append({"t": "dr", "r": rep})
                g._net_client_step(1 / 60)
                assert g.state == "day_report", g.state
                g.draw()
                g._close_day_report()
                g.net.sent.clear()
                g._net_client_step(1 / 60)
                ins = [m for m in g.net.sent if m.get("t") == "input"]
                assert ins and ins[0]["ev"] == ["action"], g.net.sent
        finally:
            NS.Client = oldc
            g.net_stop()
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
    check("core: LAN client press dismisses the host's day report", client_day_report_press)

    def bed_needs_confirm():
        p1, p2 = g.players            # a LAN session end rebuilds the players
        home = g.world.areas[AREA_HOME]
        if not home.bed:
            return
        g.warp(AREA_HOME, sp.get(AREA_HOME, (home.bed[0], home.bed[1] + 2)))
        g.state = "play"
        g.time.minutes = 6 * 60
        day0 = g.time.day
        bx, by = home.bed
        spot = None
        for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
            x, y = bx + dx, by + dy
            if not g.world.furniture_at(x, y) and not g.world.furniture_at(x + dx, y + dy):
                spot = (x, y, dx, dy)
                break
        if spot is None:
            return
        H.place(g, p1, spot[0], spot[1])
        p1.fx, p1.fy = spot[2], spot[3]                    # facing AWAY from the bed
        H.place(g, p2, bx + 6, by + 6)                     # no partner-gift target
        g._bed_ask = None
        assert select(p1, "tool", "hoe")
        g.player_action(0)
        assert g.state == "play" and g.time.day == day0, "hoe press beside bed slept"
        p1.inv.add("stone", 1)
        assert select(p1, "item", "stone")
        g.player_action(0)
        assert g.state == "play" and g.time.day == day0, "one press slept at 6 AM"
        assert "Press again" in logs(), logs()
        g.player_action(0)
        assert g.state == "sleep", "second press did not sleep"
        H.settle(g)
        g.state = "play"
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
    check("core: the bed asks before ending the day", bed_needs_confirm)

    def reserved_keys_and_hotkeys():
        from src.settings import DEFAULT_P1_KEYS
        saved1, saved2 = dict(P1_KEYS), dict(P2_KEYS)
        try:
            g._apply_settings({"keys": {"p1": {"action": pygame.K_j},
                                        "p2": {"action": pygame.K_b}}})
            assert P1_KEYS["action"] == DEFAULT_P1_KEYS["action"], "J kept on P1 action"
            assert P2_KEYS["action"] != pygame.K_b, "B kept on P2 action"
            g._settings_notes = []
            # a binding forced onto I (bypassing the guard) beats the hotkey
            P2_KEYS["action"] = pygame.K_i
            g.warp(AREA_FARM, sp[AREA_FARM])
            g.state = "play"
            called = []
            g.player_action = lambda idx: called.append(idx)
            try:
                g.on_keydown(pygame.K_i)
            finally:
                del g.player_action
            assert g.state == "play" and called == [1], (g.state, called)
        finally:
            P1_KEYS.clear(); P1_KEYS.update(saved1)
            P2_KEYS.clear(); P2_KEYS.update(saved2)
            g.state = "play"
    check("core: reserved hotkeys cleaned from old settings; bound keys win", reserved_keys_and_hotkeys)

    def save_sets_sorted_and_misc():
        w = g.world
        old_t, old_w = set(w.tilled), set(w.watered)
        try:
            for i in range(400):
                w.tilled.add((AREA_FARM, 5 + i % 30, 5 + i // 30))
            for i in range(397):
                w.tilled.discard((AREA_FARM, 5 + i % 30, 5 + i // 30))
            w.tilled.update({(AREA_FARM, 28, 13), (AREA_FARM, 12, 14)})
            w.watered.update({(AREA_FARM, 12, 14), (AREA_FARM, 6, 7)})
            g.npc_gifted_today = {"Mali", "Ben", "Fah"}
            d = g._collect_save()
            for k in ("tilled", "watered", "npc_gifted", "claimed_festivals"):
                assert d[k] == sorted(d[k]), f"{k} not stored sorted"
            snap = json.loads(json.dumps(d))
            g.reset()
            g._apply_save(snap)
            d2 = g._collect_save()
            for k in ("tilled", "watered", "npc_gifted", "tilled_idle"):
                assert d2[k] == snap[k], f"{k} changed across save/load"
        finally:
            w = g.world
            w.tilled, w.watered = old_t, old_w
            g.npc_gifted_today = set()
        # popups never follow a warp; the iris opens under dialogue
        g.warp(AREA_FARM, sp[AREA_FARM])
        g._popup(100, 100, "+350g")
        g.warp(AREA_TOWN, sp[AREA_TOWN])
        assert "+350g" not in [pu[2] for pu in g.popups], "popup survived the warp"
        g.state = "dialogue"
        g.fade = 0.9
        for _ in range(30):
            g._iris_tick(1 / 60)
        assert g.fade == 0.0, f"iris frozen under dialogue ({g.fade})"
        g.state = "play"
        # labels read like names
        assert Inventory.label(("item", "seed:parsnip")) == "Parsnip Seeds"
        lab = Inventory.label(("item", "wildflower_honey"))
        assert "Honey" in lab and "Wildflo" not in lab.replace("Wildflower", ""), lab
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
    check("core: save sets sorted, popups cleared on warp, iris, labels", save_sets_sorted_and_misc)

    def passed_out_feedback():
        g.warp(AREA_FARM, sp[AREA_FARM])
        g.state = "play"
        g.ui.messages = []
        from src.settings import DAY_END_MIN
        g.time.minutes = DAY_END_MIN - 1
        g.slept_in_bed = False
        for _ in range(400):
            g.update(0.05)
            if g.state != "play":
                break
        assert g.state == "sleep", g.state
        assert "passed out" in logs(), logs()
        H.settle(g)
        g.state = "play"
    check("core: passing out at 2 AM says so", passed_out_feedback)

    # ------------------------------------------------ final fix round (2026-09-26)
    def quest_board_empty_survives_load():
        old = [dict(q) for q in g.quest_offers]
        try:
            g.quest_offers = []
            d = json.loads(json.dumps(g._collect_save()))
            assert d["quest_offers"] == []
            g._apply_save(d, respawn=False)
            assert g.quest_offers == [], "empty board refilled on load"
            g.quest_offers = old
            d = json.loads(json.dumps(g._collect_save()))
            g._apply_save(d, respawn=False)
            a = [dict(q) for q in g.quest_offers]
            g._apply_save(d, respawn=False)
            assert g.quest_offers == a and len(a) == len(old), "offers re-rolled on a repeat load"
            d.pop("quest_offers")                         # an old save: fresh roll
            g._apply_save(d, respawn=False)
            assert len(g.quest_offers) == 3, g.quest_offers
        finally:
            g.quest_offers = old
    check("core: an empty quest board stays empty across save/load", quest_board_empty_survives_load)

    def bed_interleaved_presses():
        q1, q2 = g.players
        g._bed_ask = None
        g.time.minutes = 16 * 60
        got = [g._bed_confirmed(0, q1, True), g._bed_confirmed(1, q2, True),
               g._bed_confirmed(0, q1, True)]
        assert got == [False, False, True], got
        assert g._bed_confirmed(1, q2, True) is False, "partner's stale ask carried over"
        g._bed_ask = None
    check("core: interleaved P1/P2 bed presses still confirm", bed_interleaved_presses)

    def reserved_reset_never_collides():
        from src.settings import DEFAULT_P1_KEYS, DEFAULT_P2_KEYS
        saved1, saved2 = dict(P1_KEYS), dict(P2_KEYS)
        try:
            g._settings_notes = []
            g._apply_settings({"keys": {"p1": {"action": pygame.K_j,
                                               "emote": pygame.K_SPACE}}})
            codes = list(P1_KEYS.values()) + list(P2_KEYS.values())
            assert len(codes) == len(set(codes)), (P1_KEYS, P2_KEYS)
            assert P1_KEYS == DEFAULT_P1_KEYS and P2_KEYS == DEFAULT_P2_KEYS
            assert any("defaults" in n for n in g._settings_notes), g._settings_notes
        finally:
            g._settings_notes = []
            P1_KEYS.clear(); P1_KEYS.update(saved1)
            P2_KEYS.clear(); P2_KEYS.update(saved2)
    check("core: reserved-key cleanup never leaves two actions on one key",
          reserved_reset_never_collides)

    def host_resends_day_report_on_rejoin():
        sent = []
        old_dr, old_state = getattr(g, "_dr", None), g.state
        g.net, g.net_mode = FakeNet(True), "host"
        g._net_send_report = lambda: sent.append(1)
        try:
            g._net_host_seen_conn = True
            g._net_dr_sent = True                      # the card already went out
            g._dr = {"dummy": 1}
            g.state = "day_report"
            g.net.connected = False
            g._net_host_broadcast(1 / 60)
            g.net.connected = True
            g._net_host_broadcast(1 / 60)
            assert sent == [1], f"rejoined P2 never got the card ({sent})"
        finally:
            del g._net_send_report
            g.net, g.net_mode = None, None
            g._dr, g.state = old_dr, old_state
            g._net_dr_sent = False
            g.state = "play"
    check("core: a rejoining P2 gets the host's End-of-Day card", host_resends_day_report_on_rejoin)

    def leave_online_without_own_farm():
        from src import savegame
        real = (savegame.has_save, savegame.load_game, savegame.save_game)
        writes = []
        oldc = NS.Client
        NS.Client = lambda ip, port=None: FakeNet(True)
        savegame.has_save = lambda: False               # a fresh install: no save
        savegame.load_game = lambda: None
        savegame.save_game = lambda data: writes.append(data)
        try:
            g.started, g.has_save = False, False
            g.start_client("127.0.0.1")
            g.net_leave()
            assert not g.started and g.state == "menu", (g.started, g.state)
            g._save()
            assert writes == [], "a blank farm was written after leaving"
        finally:
            NS.Client = oldc
            savegame.has_save, savegame.load_game, savegame.save_game = real
            if g.net_mode:
                g.net_stop()
            g.reset()
            own = savegame.load_game()
            if own:
                g._apply_save(own)
            g.started, g.has_save = True, savegame.has_save()
            g.state = "play"
    check("core: leaving online with no own farm returns to the menu", leave_online_without_own_farm)

    back_to_play()
    g.warp(AREA_FARM, sp[AREA_FARM])
    g.state = "play"
    return "core ok"
