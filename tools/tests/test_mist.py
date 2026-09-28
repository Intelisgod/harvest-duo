"""Mist City (Chat 7) end-to-end checks, run by tools/smoke_test.py (section "domain").

enter -> move/jump/attack both players -> crate -> noise -> every random event ->
factory hazards -> zone doors -> Bell Keeper phases + kill -> portal home ->
records saved/loaded -> wipe/timeout exits -> journal tab + gallery.
"""
import json
import pygame


def run(g, check, H):
    from src.mistcity import mist_system as ms
    from src.mistcity.world2d import GROUND_Y

    ev = pygame.event.Event
    captured = []

    def key(k):
        g._mist_handle_event(ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def hold(codes, n):
        orig = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: H.Keys(codes)
        try:
            for _ in range(n):
                if g.state != "mistcity":
                    break
                g._mist_update(H.DT)
        finally:
            pygame.key.get_pressed = orig

    def heal():
        for p in g.players:
            p.health = p.max_health
            p.hurt_cd = 0.0
        run = getattr(g, "mist_run", None)
        if run is not None:
            for q in run.p2:
                if q.ghost:
                    q.revive(at_x=q.x)
                q.p.health = q.p.max_health

    def R():
        return g.mist_run

    orig_emit = g.emit

    def spy(event, **data):
        captured.append((event, data))
        return orig_emit(event, **data)

    g.emit = spy
    try:
        _run(g, check, H, ms, GROUND_Y, key, hold, heal, R, captured)
    finally:
        try:
            del g.emit
        except Exception:
            pass
        if g.state == "mistcity":
            g.mist_exit("leave")
        heal()
        g.state = "play"


def _run(g, check, H, ms, GROUND_Y, key, hold, heal, R, captured):
    P1, P2 = g.players[0].keys, g.players[1].keys
    rec_before = ms.clean_records(g.mist_records)

    def enter():
        g.state = "play"
        g.mist_enter(event="supply")
        assert g.state == "mistcity" and R() is not None
        assert R().world.key == "street" and R().zone_idx == 0
        H.frames(g, 30)
        g.draw()
        H.shot(g, "mist_street")
        from src.mistcity.world2d import mist_font
        run = R()                       # HUD uses the game's Consolas UI family
        assert run.font is mist_font(18) and run.font_big is mist_font(30, True), \
            "Mist HUD is not using the shared UI font"
    check("mist: enter Main Street", enter)

    def move_jump_attack():
        run = R()
        run.zombies = []
        x0 = [q.x for q in run.p2]
        hold({P1["right"], P2["right"]}, 40)
        assert all(q.x > x + 40 for q, x in zip(run.p2, x0)), "players did not walk right"
        assert run.noise > 0, "running made no noise"
        key(P1["up"])
        key(P2["up"])
        H.frames(g, 4)
        assert all(not q.on_ground for q in run.p2), "jump failed"
        H.frames(g, 70)
        assert all(q.on_ground for q in run.p2), "did not land"
        for i, K in enumerate((P1, P2)):
            q = run.p2[i]
            q.facing = 1
            q.swing = 0.0
            z = run._make_zombie(q.x + 26, "walker")
            z.hp = 1
            run.zombies.append(z)
            k0 = q.kills
            key(K["action"])
            assert q.kills == k0 + 1, f"P{i + 1} attack did not kill"
            H.frames(g, 20)
        assert any(e == "monster_killed" and d.get("kind") == "mist_walker" for e, d in captured)
    check("mist: move / jump / attack (both players)", move_jump_attack)

    def crate():
        run = R()
        c = next(c for c in run.world.crates if c.hp > 0 and c.y == GROUND_Y)
        q = run.p2[0]
        q.x, q.y, q.facing = c.x - 30, float(GROUND_Y), 1
        n0 = run.noise
        for _ in range(c.max_hp):
            q.swing = 0.0
            key(P1["action"])
        assert c.hp <= 0, "crate not broken"
        assert run.noise > n0 + ms.NOISE_CRATE_BREAK - 1, "breaking made no noise"
    check("mist: crate + noise", crate)

    def noise_alert():
        run = R()
        heal()
        run.noise_cd = 0.0
        run.noise = 100.0
        alive = lambda: sum(1 for z in run.zombies if z.hp > 0)
        n0 = alive()
        H.frames(g, 2)
        assert alive() >= n0 + 3 and run.noise < 70, "noise alert did not fire"
        g.draw()
        H.shot(g, "mist_noise")
    check("mist: full noise meter summons a pack", noise_alert)

    def events():
        run = R()
        out = []
        for kind in ("outage", "acid", "siren", "supply"):
            heal()
            run.zombies = []
            e = run.start_event(kind)
            if kind == "acid":
                q = run.p2[0]
                q.x = 120.0                        # open street, no awning
                assert not run.world.is_covered(q.x, q.y)
                hp0 = q.p.health
                for _ in range(int(e.TICK / H.DT) + 5):
                    q.x = 120.0
                    g._mist_update(H.DT)
                assert q.p.health < hp0, "acid rain did not sting"
                aw = run.world.awnings[0]
                assert run.world.is_covered(aw.centerx, GROUND_Y)
            elif kind == "siren":
                H.frames(g, int(3.0 / H.DT))
                assert len(run.zombies) >= e.COUNT, "no horde"
            elif kind == "supply":
                for _ in range(900):
                    g._mist_update(H.DT)
                    heal()
                    if e.landed:
                        break
                assert e.landed and e.crate in run.world.crates
            else:
                H.frames(g, 90)
            g.draw()
            H.shot(g, f"mist_event_{kind}")
            out.append(kind)
            e.stop()
            H.frames(g, 1)
        run.zombies = []
        return ",".join(out)
    check("mist: random events (outage/acid/siren/supply)", events)

    def banner_panel_fades():
        # the banner's dark backing panel must fade WITH its text (no empty
        # dark bar over the play area during the last ~0.8 s of a banner)
        run = R()
        keep = (run.banner, run.sub, run.hint_msg, run.zone_card, run.event)
        run.sub = run.hint_msg = run.zone_card = run.event = None
        text = "TOO LOUD! THE DEAD HEARD YOU..."
        bw = run.font_big.size(text)[0] + 36
        col_x = ms.SCREEN_W // 2 - bw // 2 + 4           # panel margin: panel only, no glyphs

        def column(banner):
            run.banner = banner
            surf = pygame.Surface((ms.SCREEN_W, ms.SCREEN_H))
            surf.fill((200, 200, 200))
            run._draw_hud(surf, 0.0)
            return [surf.get_at((col_x, y))[0] for y in range(100, 320)]

        try:
            base = column(None)

            def dark(tl):
                return max(b - c for b, c in zip(base, column([text, tl])))

            full, mid, tail, again = dark(2.0), dark(0.3), dark(0.02), dark(2.0)
            assert full > 40, f"banner panel not drawn at full strength ({full})"
            assert 0 < mid < 0.6 * full, f"panel does not fade with the text (full {full}, fading {mid})"
            assert tail == 0, f"empty panel still drawn as the banner ends ({tail})"
            assert again == full, f"cached panel alpha not restored ({again} vs {full})"
        finally:
            run.banner, run.sub, run.hint_msg, run.zone_card, run.event = keep
        return f"full {full} / fading {mid} / end {tail}"
    check("mist: banner panel fades with its text", banner_panel_fades)

    def door_to_factory():
        run = R()
        heal()
        run.zombies = []
        w = run.world
        a, b = run.p2
        a.x = float(w.exit_x)
        b.x = float(w.gate_x + 40)
        run.camx = max(0.0, w.exit_x - 900)
        key(P1["down"])
        assert run.trans is None, "door opened without the partner"
        b.x = float(w.exit_x - 30)
        H.frames(g, 1)
        t0 = run.t_left
        key(P1["down"])
        assert run.trans is not None, "door did not open with both players"
        H.frames(g, 60)
        assert run.zone_idx == 1 and run.world.key == "factory"
        assert run.t_left > t0, "no zone time bonus"
        H.frames(g, 30)
        g.draw()
        H.shot(g, "mist_factory")
    check("mist: zone door -> Old Factory", door_to_factory)

    def factory_hazards():
        run = R()
        w = run.world
        run.zombies = []
        a, b = run.p2
        b.x = 150.0
        # conveyor A pushes left
        heal()
        x1, x2, spd = w.conveyors[0]
        a.x, a.y, a.vy = float((x1 + x2) // 2), float(GROUND_Y), 0.0
        run.camx = max(0.0, a.x - 600)
        x0 = a.x
        H.frames(g, 20)
        assert (a.x - x0) * spd > 0, "conveyor did not carry the player"
        # acid pool hurts
        heal()
        ax1, ax2 = w.acids[0]
        a.x, a.y, a.vy = float((ax1 + ax2) // 2), float(GROUND_Y), 0.0
        hp0 = a.p.health
        H.frames(g, 2)
        assert a.p.health < hp0, "acid did not hurt"
        # broken catwalk crumbles
        heal()
        cw = next(c for c in w.catwalks if c.broken)
        a.x, a.y, a.vy, a.on_ground = float(cw.rect.centerx), float(cw.rect.top - 2), 0.0, False
        run.camx = max(0.0, a.x - 600)
        H.frames(g, 3)
        assert cw.state == "shake", f"catwalk did not start to crumble ({cw.state})"
        g.draw()
        H.shot(g, "mist_factory_catwalk")
        H.frames(g, int(0.7 / H.DT))
        assert cw.state == "gone" and cw.rect not in w.platforms
        H.frames(g, int(5.2 / H.DT))
        assert cw.state == "ok", "catwalk did not come back"
        # hazmat zombie leaves a temporary acid spill
        heal()
        run.zombies = []
        z = run._make_zombie(a.x + 400, "hazmat")
        z.hp = 1
        run.zombies.append(z)
        a.x, a.y, a.facing, a.swing = z.x - 26, float(GROUND_Y), 1, 0.0
        key(P1["action"])
        assert w.spills, "hazmat left no spill"
        g.draw()
        H.shot(g, "mist_factory_hazmat")
        # live wire
        heal()
        run.zombies = []
        wx = w.wires[0][0]
        ph = w.wires[0][1]
        from src.mistcity import zones
        run.elapsed = zones.WIRE_LIVE + 0.1 - ph + zones.WIRE_CYCLE * 3
        a.x, a.y, a.vy = float(wx), float(GROUND_Y), 0.0
        run.camx = max(0.0, a.x - 600)
        hp0 = a.p.health
        H.frames(g, 2)
        assert a.p.health < hp0, "wire did not zap"
        g.draw()
        H.shot(g, "mist_factory_wire")
        heal()
    check("mist: factory hazards (belt/acid/catwalk/wire)", factory_hazards)

    def to_tower():
        run = R()
        w = run.world
        a, b = run.p2
        run.zombies = []
        a.x, b.x = float(w.exit_x), float(w.exit_x - 40)
        run.camx = float(w.level_w - 1280)
        H.frames(g, 1)
        key(P2["down"])
        H.frames(g, 60)
        assert run.world.key == "tower" and run.boss is not None, "no boss arena"
        assert run.deepest == 2
        heal()
        H.frames(g, 160)
        heal()
        H.frames(g, 140)
        g.draw()
        H.shot(g, "mist_boss")
        assert run.boss.intro == 0.0, "boss never landed"
    check("mist: Clock Tower + Bell Keeper entrance", to_tower)

    def boss_fight():
        run = R()
        bk = run.boss
        a, b = run.p2
        # shockwave on the toll: grounded player gets hit
        heal()
        bk.facing = 1
        a.x, a.y = min(1200.0, bk.x + 240), float(GROUND_Y)
        b.x = 60.0
        bk._do("wave", run)
        assert bk.waves, "no shockwave"
        hp0 = a.p.health
        for _ in range(60):
            a.x = min(1200.0, bk.x + 240)
            b.x = 60.0
            g._mist_update(H.DT)
            if a.p.health < hp0:
                break
        assert a.p.health < hp0, "shockwave missed a grounded player"
        # gears + summon
        heal()
        bk._do("gears", run)
        assert bk.gears
        bk._do("summon", run)
        H.frames(g, 40)
        # gears land on ledges too (no safe camping above the bell)
        led = run.world.ledges[0]
        b.x, b.y, b.vy, b.on_ground = float(led.centerx), float(led.top), 0.0, True
        bk.gears = []
        bk._do("gears", run)
        assert any(gr[6] == led.top for gr in bk.gears), "no gear aimed at the ledge"
        g.draw()
        H.shot(g, "mist_boss_gears")
        # phases
        heal()
        bk.hp = int(bk.max_hp * 0.6)
        H.frames(g, 2)
        assert bk.phase == 2, "no phase 2"
        bk.hp = int(bk.max_hp * 0.3)
        H.frames(g, 2)
        assert bk.phase == 3, "no phase 3"
        H.frames(g, 40)
        heal()
        g.draw()
        H.shot(g, "mist_boss_p3")
        # finishing blow
        bk.invuln = 0.0
        bk.hp = 1
        a.x, a.y, a.facing, a.swing = bk.x - 70, float(GROUND_Y), 1, 0.0
        inv0 = a.p.inv.count("cursed_gear") if hasattr(a.p.inv, "count") else None
        key(P1["action"])
        assert bk.hp <= 0, f"finishing blow missed (hp={bk.hp})"
        H.frames(g, 1)
        assert bk.dead, "boss did not die"
        for _ in range(int(2.6 / H.DT)):
            heal()
            g._mist_update(H.DT)
        assert run.victory and run.boss_killed
        assert g.mist_records["boss_kills"] == rec_before["boss_kills"] + 1
        assert g.mist_records["best_time"] is not None
        assert any(e == "monster_killed" and d.get("boss") and d.get("kind") == "bell_keeper"
                   for e, d in captured), "boss kill not emitted"
        if inv0 is not None:
            assert a.p.inv.count("cursed_gear") == inv0 + 1
        H.frames(g, 40)
        g.draw()
        H.shot(g, "mist_victory")
    check("mist: Bell Keeper waves/gears/phases/kill", boss_fight)

    def portal_home():
        run = R()
        a = run.p2[0]
        a.x = float(run.world.portal_x)
        key(P1["down"])
        assert run.over == "victory"
        H.frames(g, 60)
        g.draw()
        H.shot(g, "mist_results")
        H.frames(g, 200)
        assert g.state == "play" and g.mist_run is None
        r = g.mist_records
        assert r["runs"] == rec_before["runs"] + 1 and r["deepest"] == 2
        ends = [d for e, d in captured if e == "mist_run_end"]
        assert ends and ends[-1]["reason"] == "victory" and ends[-1]["zone"] == "tower"
        return f"records {r}"
    check("mist: portal home + records + mist_run_end", portal_home)

    def save_load():
        d = json.loads(json.dumps(g._collect_save()))
        assert "mist_records" in d
        keep = dict(g.mist_records)
        g._on_load_mist({})
        assert g.mist_records == ms.REC_DEFAULT
        g._on_load_mist({"mist_records": {"runs": "4", "best_time": 0, "junk": 1}})
        assert g.mist_records["runs"] == 4 and g.mist_records["best_time"] is None
        g._on_load_mist(d)
        assert g.mist_records == keep, "records did not round-trip"
    check("mist: records save/load (+old saves)", save_load)

    def key_opens_locks():
        g.state = "play"
        g.mist_enter()
        run = R()
        run.zombies = []
        q = run.p2[0]
        if q.p.inv.count("city_key") <= 0:
            q.p.inv.add("city_key", 1)
        c = next(c for c in run.world.crates if c.rare and c.hp > 0)
        q.x, q.y, q.facing, q.swing = c.x - 30, float(c.y), 1, 0.0
        run.camx = max(0.0, c.x - 640)
        try:
            key(P1["action"])
            assert c.hp <= 0, "city key did not open the locked crate"
        finally:
            g.mist_exit("leave")
            heal()
    check("mist: City Key opens locked crates", key_opens_locks)

    def revive_hold():
        g.state = "play"
        g.mist_enter()
        run = R()
        run.zombies = []
        a, b = run.p2
        run._down(b)
        a.x = b.x = b.spawn_x
        H.frames(g, 5)
        assert b.ghost, "revived instantly"
        H.frames(g, 60)
        assert not b.ghost, "hold-to-revive did not revive"
        assert run.threat == min(ms.MAX_THREAT, g.mist_records["boss_kills"])
        g.mist_exit("leave")
        heal()
    check("mist: hold-to-revive + threat level", revive_hold)

    def buffs_tick():
        g.state = "play"
        g.mist_enter()
        run = R()
        run.zombies = []
        heal()
        p = g.players[0]
        saved = {k: list(v) for k, v in p.buffs.items()}
        try:
            p.buffs.pop("combat", None)
            p.buffs.pop("speed", None)
            p.add_buff("combat", 5.0, 0.25, "Test Stew")
            p.add_buff("speed", 30.0, 0.2, "Test Curry")
            hold(set(), 360)                            # 6 s inside the mist
            assert g.state == "mistcity"
            assert "combat" not in p.buffs, f"5 s buff still active after 6 s: {p.buffs.get('combat')}"
            left = p.buffs["speed"][1]
            assert 23.5 < left < 24.5, f"30 s buff should have ~24 s left, has {left:.2f}"
            g.draw()                                    # HUD buff chips under the panel
            H.shot(g, "mist_buffs")
        finally:
            p.buffs.pop("combat", None)
            p.buffs.pop("speed", None)
            p.buffs.update(saved)
            if g.state == "mistcity":
                g.mist_exit("leave")
            heal()
    check("mist: food buffs tick down inside the mist", buffs_tick)

    def wipe_and_timeout():
        g.state = "play"
        g.mist_enter()
        run = R()
        for q in run.p2:
            run._down(q)
        H.frames(g, 260)
        assert g.state == "play", "wipe did not end the run"
        assert all(p.health >= 1 for p in g.players)
        heal()
        g.mist_enter()
        R().t_left = 0.02
        H.frames(g, 260)
        assert g.state == "play", "timeout did not end the run"
        ends = [d["reason"] for e, d in captured if e == "mist_run_end"]
        assert ends[-2:] == ["wipe", "timeout"], ends
        heal()
    check("mist: wipe + timeout exits", wipe_and_timeout)

    def esc_twice():
        g.state = "play"
        g.mist_enter()
        key(pygame.K_ESCAPE)
        H.frames(g, 2)
        assert R() is not None and R().over is None, "one ESC should only arm the bail-out"
        key(pygame.K_ESCAPE)
        assert R().over == "leave"
        H.frames(g, 260)
        assert g.state == "play"
        heal()
    check("mist: ESC twice bails out", esc_twice)

    def journal_gallery():
        tab = g._journal_tab_60_mist()
        assert tab["title"]
        surf = pygame.Surface((900, 520))
        tab["draw"](surf, pygame.Rect(20, 20, 860, 480))
        from src.mistcity import gallery_entries
        n = 0
        for name, fn in gallery_entries():
            s = fn()
            assert isinstance(s, pygame.Surface), name
            box = s.get_bounding_rect()
            assert box.w > 8 and box.h > 8, f"gallery '{name}' draws nothing ({box})"
            n += 1
        return f"{n} gallery entries"
    check("mist: journal tab + gallery", journal_gallery)

    def toast_titles_fit():
        from src.mistcity.world2d import mist_font
        f = mist_font(18)                   # the toast title face (UI clips at ~330 px)
        for title in list(ms._TOAST.values()) + ["The Bell Keeper is silenced!"]:
            assert f.size(title)[0] <= 330, f"toast title too long: {title!r}"
    check("mist: toast titles fit the card", toast_titles_fit)
