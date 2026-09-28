"""Showpieces: Art Studio easel + gallery paintings, telescope, arcade cabinet
(ShowpieceMixin + studio.py / stargaze.py / heartpong.py).

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import json
import random

import pygame


def run(g, check, H):
    from src import furniture as F, studio as S, stargaze as SG, heartpong as HP, wallart, isofurn
    from src import homeiso
    from src.settings import AREA_HOME, P1_KEYS

    ev = pygame.event.Event
    g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    g.state = "play"
    p1, p2 = g.players
    added = []

    def piece(kind, gx, gy, **kw):
        q = next((q for q in g.world.home_furniture if q.kind == kind), None)
        if q is None:
            q = F.Placed(kind, gx, gy, 0, 5, **kw)
            g.world.home_furniture.append(q)
            added.append(q)
        return q

    def key(k, up=True):
        g._run_state("event", ev(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
        if up:
            g._run_state("event", ev(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0))

    def frames(n=3):
        for _ in range(n):
            g._run_state("update", H.DT)

    def back_to_play():
        for _ in range(3):
            if g.state == "play":
                break
            key(pygame.K_ESCAPE)
            frames(2)
        assert g.state == "play", g.state

    easel = piece("easel", 7, 4)
    scope = piece("telescope", 9, 4)
    cab = piece("arcade_cabinet", 11, 4)
    paintings = [q for q in g.world.home_furniture if q.kind == "painting"]
    if not paintings:
        paintings = [F.Placed("painting", 9, 0, 0, 8), F.Placed("painting", 0, 4, 0, 5)]
        g.world.home_furniture.extend(paintings)
        added.extend(paintings)
    saved_state = (dict(easel.data), list(g.art_gallery), set(g.stars_found),
                   g.star_wish_day, g.star_wish_pending, json.dumps(g.pong_stats),
                   [dict(q.data) for q in paintings], g.time.minutes, g.weather)

    # ------------------------------------------------------------ encoding
    def encoding():
        assert S.encode(S.blank()) == "1:A576", S.encode(S.blank())
        rnd = random.Random(5)
        for _ in range(20):
            px = [rnd.choice((0, 0, 0, rnd.randrange(len(S.RGB)))) for _ in range(S.N * S.N)]
            enc = S.encode(px)
            assert S.decode(enc) == px
            assert len(enc) < 1300, len(enc)
        for bad in (None, "", "2:A576", "1:A575", "1:A577", "1:!4", "1:A0", 42, "1:" + "Z" * 576):
            assert S.decode(bad) is None, bad
        return "run-length strings round-trip; junk is rejected"
    check("showpieces: art encoding", encoding)

    # ------------------------------------------------------------ studio
    def studio():
        easel.data.pop("art", None)
        e0 = p1.energy = 100
        g.interact_furniture(p1, easel)
        assert g.state == "studio" and g.studio is not None, g.state
        assert p1.energy > e0, "no easel energy"
        scr = g.studio
        assert S.is_blank(scr.px)
        scr.cx = scr.cy = 12
        for _ in range(10):
            key(pygame.K_LEFT)
        for _ in range(10):
            key(pygame.K_UP)
        assert (scr.cx, scr.cy) == (2, 2), (scr.cx, scr.cy)
        key(pygame.K_SPACE)                                  # pencil, ink
        assert scr.get(2, 2) == 1, scr.get(2, 2)
        # hold Space and walk right: a painted stroke
        key(pygame.K_SPACE, up=False)
        for _ in range(3):
            key(pygame.K_RIGHT)
        g._run_state("event", ev(pygame.KEYUP, key=pygame.K_SPACE, mod=0, unicode="", scancode=0))
        assert all(scr.get(x, 2) == 1 for x in range(2, 6)), [scr.get(x, 2) for x in range(8)]
        # fill the bare canvas with Rose (tool 3, colour 4)
        key(pygame.K_3)
        assert scr.tool == "fill"
        while scr.color != 4:
            key(pygame.K_e)
        scr.cx, scr.cy = 12, 12
        before = list(scr.px)
        key(pygame.K_SPACE)
        assert scr.px.count(4) == S.N * S.N - 4, scr.px.count(4)
        key(pygame.K_z)
        assert scr.px == before, "undo didn't restore the canvas"
        key(pygame.K_y)
        assert scr.px.count(4) == S.N * S.N - 4, "redo lost the fill"
        key(pygame.K_z)
        # mirror + line
        key(pygame.K_m)
        key(pygame.K_1)
        scr.set_color(14)
        scr.cx, scr.cy = 0, 8
        key(pygame.K_SPACE)
        assert scr.get(0, 8) == 14 and scr.get(23, 8) == 14, "mirror didn't mirror"
        key(pygame.K_m)
        key(pygame.K_5)
        scr.cx, scr.cy = 0, 20
        key(pygame.K_SPACE)
        for _ in range(6):
            key(pygame.K_RIGHT)
        key(pygame.K_SPACE)
        assert all(scr.get(x, 20) == 14 for x in range(7)), [scr.get(x, 20) for x in range(8)]
        # picker takes a colour back
        key(pygame.K_4)
        scr.cx, scr.cy = 2, 2
        key(pygame.K_SPACE)
        assert scr.color == 1 and scr.tool == "pencil"
        # mouse: left paints, right erases, buttons click
        cv = scr.canvas
        pos = (cv.x + 20 * scr.CELL + 3, cv.y + 15 * scr.CELL + 3)
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        g._run_state("event", ev(pygame.MOUSEMOTION, pos=(pos[0] + scr.CELL * 2, pos[1]),
                                 rel=(0, 0), buttons=(1, 0, 0)))
        g._run_state("event", ev(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        assert [scr.get(x, 15) for x in (20, 21, 22)] == [1, 1, 1], [scr.get(x, 15) for x in range(19, 24)]
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=pos, button=3))
        g._run_state("event", ev(pygame.MOUSEBUTTONUP, pos=pos, button=3))
        assert scr.get(20, 15) == 0, "right-click didn't erase"
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=scr.swatch[9].center, button=1))
        assert scr.color == 9
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=scr.btns["fill"].center, button=1))
        assert scr.tool == "fill"
        g.draw()
        H.shot(g, "showpieces_studio")
        key(pygame.K_s)                                         # save
        assert easel.data.get("art") == S.encode(scr.px), "save didn't reach the easel"
        assert easel.data.get("by") == p1.name
        scr.use_tool(23, 23, tool="pencil")                      # unsaved change ...
        key(pygame.K_ESCAPE)                                     # ... leaving keeps it
        frames(2)
        assert g.state == "play" and g.studio is None, g.state
        art = easel.data.get("art")
        assert S.decode(art)[23 * 24 + 23] == 9, "leaving didn't keep the canvas"
        # the room's easel shows it
        assert g._show_piece_art("easel", easel.gx + easel.ox, easel.gy + easel.oy) == art
        for rot in range(4):
            easel.rot = rot
            g.draw()
        easel.rot = 0
        return f"{len(art)} chars on the easel"
    check("showpieces: studio paints, fills, undoes, saves to the easel", studio)

    # ------------------------------------------------------------ gallery + paintings
    def gallery():
        g.art_gallery = []
        for q in paintings:
            q.data.pop("gid", None)
        g.interact_furniture(p1, easel)
        scr = g.studio
        msg = scr.hang() and scr.msg
        assert len(g.art_gallery) == 1, g.art_gallery
        e = g.art_gallery[0]
        assert e["art"] == S.encode(scr.px) and e["by"] == p1.name, e
        hung = [q for q in paintings if q.data.get("gid") == e["id"]]
        assert len(hung) == 1, "the art didn't go up on a free frame"
        scr.hang()                                              # the same art: no duplicate
        assert len(g.art_gallery) == 1
        scr.clear()
        assert scr.hang() is False, "hung a blank canvas"
        scr.do_undo()
        scr.set_color(16)
        scr.use_tool(0, 0, tool="fill")
        scr.hang()
        assert len(g.art_gallery) == 2
        key(pygame.K_ESCAPE)
        frames(2)
        assert g.state == "play"
        # every Painting shows gallery art through wallart
        ox, oy = homeiso.origin(g.world.area)
        area = g.world.area
        for q in paintings:
            side = homeiso.wall_side(q.gx, q.gy)
            if side == "back":
                foot = homeiso.proj(ox, oy, max(1, min(area.w - 2, q.gx)), 1)
            else:
                foot = homeiso.proj(ox, oy, 1, max(1, min(area.h - 2, q.gy)) + 1)
            want = g._gallery_get(q.data.get("gid"))
            got = wallart._art_for("painting", side, foot)
            assert got == (want["art"] if want else None), (q.gx, q.gy, got is None)
            if want:
                a = pygame.image.tostring(wallart.sprite("painting", q.color, side, art=got), "RGBA")
                b = pygame.image.tostring(wallart.sprite("painting", q.color, side), "RGBA")
                assert a != b, "the frame ignores the art"
        # using a Painting cycles: next piece ... then the landscape again
        fr = paintings[0]
        ids = [x["id"] for x in g.art_gallery]
        seen = []
        for _ in range(len(ids) + 1):
            g.interact_furniture(p1, fr)
            seen.append(fr.data.get("gid"))
        assert None in seen and set(ids) <= set(seen), seen
        g.draw()
        H.shot(g, "showpieces_room")
        return msg
    check("showpieces: hang on the wall + paintings show gallery art", gallery)

    def roundtrip():
        before = g._collect_save()
        js = json.loads(json.dumps(before))
        g.reset()
        g._apply_save(js)
        g.state = "play"
        after = g._collect_save()
        assert after.get("art_gallery") == before.get("art_gallery")
        assert after.get("pong_stats") == before.get("pong_stats")
        home = g.world.home_furniture
        e2 = next(q for q in home if q.kind == "easel" and (q.gx, q.gy) == (easel.gx, easel.gy))
        assert e2.data.get("art") == easel.data.get("art"), "easel art lost in save/load"
        for q in paintings:
            q2 = next(x for x in home if x.kind == "painting" and (x.gx, x.gy) == (q.gx, q.gy))
            assert q2.data.get("gid") == q.data.get("gid")
        return "easel art, frames and gallery survive save/load"
    check("showpieces: art round-trips through save/load", roundtrip)

    # the reload made new Placed objects: pick them up again
    g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    g.state = "play"
    p1, p2 = g.players
    home = g.world.home_furniture
    easel = next(q for q in home if q.kind == "easel")
    scope = next(q for q in home if q.kind == "telescope")
    cab = next(q for q in home if q.kind == "arcade_cabinet")
    paintings = [q for q in home if q.kind == "painting"]
    added = [q for q in home if any((q.kind, q.gx, q.gy) == (a.kind, a.gx, a.gy) for a in added)]

    # ------------------------------------------------------------ telescope
    def telescope():
        g.weather = "sunny"
        g.time.minutes = 11 * 60
        g.stars_found = set()
        g.star_wish_day, g.star_wish_pending = None, False
        g.interact_furniture(p1, scope)
        assert g.state == "stargaze", g.state
        sg = g.stargazer
        assert sg.mode()[0] == "day" and not sg.mode()[1]
        frames(30)
        g.draw()
        H.shot(g, "showpieces_stars_day")
        assert sg.shooting is None and not sg.try_wish()
        key(pygame.K_ESCAPE)
        frames(2)
        assert g.state == "play"
        # a clear night: constellations + a wish
        g.time.minutes = 21 * 60
        g.interact_furniture(p1, scope)
        sg = g.stargazer
        assert sg.mode() == ("night", True, "sunny"), sg.mode()
        sg.rx, sg.ry = sg.centre("boat")
        frames(int(1.4 / H.DT))
        assert "boat" in g.stars_found, g.stars_found
        # walk the reticle with the keys
        x0 = sg.rx
        g._run_state("event", ev(pygame.KEYDOWN, key=P1_KEYS["left"], mod=0, unicode="", scancode=0))
        frames(10)
        g._run_state("event", ev(pygame.KEYUP, key=P1_KEYS["left"], mod=0, unicode="", scancode=0))
        assert sg.rx < x0 - 20, (sg.rx, x0)
        sg.spawn_shooting_star()
        frames(5)
        g.draw()
        H.shot(g, "showpieces_stars_night")
        assert sg.wishable()
        key(pygame.K_SPACE)
        assert g.star_wish_pending and g._stars_wished_tonight()
        sg.spawn_shooting_star()
        assert sg.try_wish() is False, "two wishes in one night"
        key(pygame.K_ESCAPE)
        frames(2)
        assert g.state == "play"
        # next morning: Luck for both, once
        for p in g.players:
            p.buffs.pop("luck", None)
        g._on_new_day_showpieces()
        assert all(p.buff("luck") > 0 for p in g.players), [p.buffs for p in g.players]
        assert not g.star_wish_pending
        for p in g.players:
            p.buffs.pop("luck", None)
        g._on_new_day_showpieces()
        assert all(p.buff("luck") == 0 for p in g.players), "the wish paid out twice"
        # clouds hide the stars: no shooting stars, no discoveries
        g.weather = "rain"
        g.interact_furniture(p1, scope)
        sg = g.stargazer
        assert sg.mode()[1] is False
        sg.rx, sg.ry = sg.centre("cat")
        for _ in range(int(16 / H.DT)):
            sg.update(H.DT)
        assert sg.shooting is None and "cat" not in g.stars_found
        g.draw()
        key(pygame.K_ESCAPE)
        frames(2)
        assert g.state == "play"
        return "day sky, night discovery, one wish -> Luck once, rain hides the stars"
    check("showpieces: telescope day/night, constellations, one wish", telescope)

    # ------------------------------------------------------------ arcade
    def arcade():
        cab.on = False
        g.pong_stats = g._pong_blank()
        e0 = p1.energy = 100
        g.interact_furniture(p1, cab)
        assert g.state == "arcade" and cab.on and p1.energy > e0
        pg = g.pong
        assert pg.local and not pg.vs_cpu
        key(pygame.K_TAB)
        assert pg.vs_cpu
        key(pygame.K_TAB)
        key(pygame.K_SPACE)
        assert pg.phase == "serve"
        frames(int(1.0 / H.DT))
        assert pg.phase == "play" and pg.vx != 0
        # paddles follow each player's own keys
        y0 = list(pg.pad)
        g._run_state("event", ev(pygame.KEYDOWN, key=P1_KEYS["up"], mod=0, unicode="", scancode=0))
        frames(10)
        g._run_state("event", ev(pygame.KEYUP, key=P1_KEYS["up"], mod=0, unicode="", scancode=0))
        assert pg.pad[0] < y0[0] and abs(pg.pad[1] - y0[1]) < 1e-6, (y0, pg.pad)
        # score points by sending the heart past the right paddle
        for n in range(1, 6):
            pg.phase = "play"
            pg.bx, pg.by = pg.court.right - 2, pg.court.y + 5
            pg.vx, pg.vy = 600.0, 0.0
            pg.pad[1] = pg.court.bottom - 50
            frames(3)
            assert pg.score[0] == n, pg.score
            frames(int(1.0 / H.DT))
        assert pg.phase == "over" and pg.winner == 0, (pg.phase, pg.winner)
        assert g.pong_stats["duel"] == [1, 0] and g.pong_stats["games"] == 1, g.pong_stats
        g.draw()
        H.shot(g, "showpieces_pong_over")
        # a real rally against the CPU: the CPU returns serves
        key(pygame.K_TAB)
        key(pygame.K_SPACE)
        assert pg.vs_cpu and pg.score == [0, 0]
        hits = 0
        for _ in range(int(20 / H.DT)):
            pg.pad[0] = pg._clamp_pad(pg.by)                    # a perfect human
            g._run_state("update", H.DT)
            hits = max(hits, pg.best_rally)
            if pg.phase == "over":
                break
        assert hits >= 3, f"no rally ({hits})"
        key(pygame.K_ESCAPE)
        frames(2)
        assert g.state == "play" and cab.on, (g.state, cab.on)
        g.interact_furniture(p1, cab)
        key(pygame.K_x)
        frames(2)
        assert g.state == "play" and not cab.on
        for rot in range(4):
            cab.rot = scope.rot = rot
            cab.on = rot % 2 == 0
            g.draw()
        cab.rot = scope.rot = 0
        return f"best CPU rally {hits}"
    check("showpieces: Heart Pong scores, ends at 5, CPU rallies, power", arcade)

    # ------------------------------------------------------------ LAN
    def lan():
        sent = []
        mode0 = g.net_mode
        g._net_send_menu = lambda d: sent.append(json.loads(json.dumps(d)))
        g._net_send_fx = lambda kind, **d: None
        try:
            # client side: everything opens locally, results go to the host
            g.net_mode = "client"
            g.state = "play"
            assert g._home_client_interact(p2, easel) is True and g.state == "studio"
            scr = g.studio
            assert scr.client
            scr.use_tool(5, 5, tool="pencil")
            key(pygame.K_s)
            key(pygame.K_h)
            key(pygame.K_ESCAPE)
            frames(2)
            ops = [(m.get("m"), m.get("op")) for m in sent]
            assert ("art", "save") in ops and ("art", "hang") in ops, ops
            assert g.state == "play"
            if g.art_gallery:
                sent.clear()
                assert g._home_client_interact(p2, paintings[0]) is True
                assert sent and sent[-1]["op"] == "frame", sent
            g.time.minutes = 22 * 60
            g.weather = "sunny"
            g.star_wish_day = None
            assert g._home_client_interact(p2, scope) is True and g.state == "stargaze"
            g.stargazer.spawn_shooting_star()
            key(pygame.K_RETURN)
            assert any(m.get("m") == "stars" and m.get("op") == "wish" for m in sent), sent
            key(pygame.K_ESCAPE)
            frames(2)
            cab.on = False
            assert g._home_client_interact(p2, cab) is True and g.state == "arcade"
            assert any(m.get("kind") == "arcade_cabinet" and m.get("on") is True for m in sent)
            pg = g.pong
            assert pg.vs_cpu, "LAN pong must be vs the CPU"
            pg.start()
            pg.score = [4, 0]
            pg.phase = "play"
            pg.bx, pg.vx, pg.vy = pg.court.right - 2, 600.0, 0.0
            pg.pad[1] = pg.court.bottom - 50
            frames(int(1.2 / H.DT))
            assert pg.phase == "over"
            assert any(m.get("m") == "pong" for m in sent), sent
            key(pygame.K_ESCAPE)
            frames(2)
            assert g.state == "play"
            # host side: apply the client's ops for Player 2
            g.net_mode = "host"
            n0 = len(g.art_gallery)
            px = S.blank()
            px[0] = 6
            art = S.encode(px)
            assert g._net_menu_showpieces("art", {"m": "art", "op": "save", "gx": easel.gx,
                                                  "gy": easel.gy, "art": art})
            assert easel.data.get("art") == art and easel.data.get("by") == p2.name
            g._net_menu_showpieces("art", {"m": "art", "op": "hang", "art": art})
            assert len(g.art_gallery) == n0 + 1
            g._net_menu_showpieces("art", {"m": "art", "op": "save", "gx": easel.gx,
                                           "gy": easel.gy, "art": "junk"})
            assert easel.data.get("art") == art, "junk art was accepted"
            gid = g.art_gallery[-1]["id"]
            g._net_menu_showpieces("art", {"m": "art", "op": "frame", "gx": paintings[0].gx,
                                           "gy": paintings[0].gy, "gid": gid})
            assert paintings[0].data.get("gid") == gid
            g._net_menu_showpieces("art", {"m": "art", "op": "frame", "gx": paintings[0].gx,
                                           "gy": paintings[0].gy, "gid": 99999})
            assert "gid" not in paintings[0].data
            g.stars_found = set()
            g._net_menu_showpieces("stars", {"m": "stars", "op": "found", "c": "lantern"})
            g._net_menu_showpieces("stars", {"m": "stars", "op": "found", "c": "not_a_star"})
            assert g.stars_found == {"lantern"}, g.stars_found
            g.star_wish_day, g.star_wish_pending = None, False
            g._net_menu_showpieces("stars", {"m": "stars", "op": "wish"})
            assert g.star_wish_pending
            st0 = dict(g.pong_stats)
            g._net_menu_showpieces("pong", {"m": "pong", "op": "result", "cpu": True, "win": 0,
                                            "rally": 7})
            assert g.pong_stats["cpu_w"] == st0["cpu_w"] + 1
            assert g._net_menu_showpieces("fridge", {}) is False
            # the host never pops a screen up for the remote farmer
            for q in (easel, scope):
                g.state = "play"
                g.interact_furniture(p2, q)
                assert g.state == "play", (q.kind, g.state)
        finally:
            g.net_mode = mode0
            del g._net_send_menu
            del g._net_send_fx
            g.state = "play"
        return f"{len(sent)} client ops"
    check("showpieces: LAN client + host paths", lan)

    def screens_close():
        for st in ("studio", "stargaze", "arcade"):
            g.state = st                                       # no screen object: back to play
            g._run_state("update", H.DT)
            assert g.state == "play", st
        return "orphan states fall back to play"
    check("showpieces: all screens close back to play", screens_close)

    # restore
    easel.data = saved_state[0]
    g.art_gallery = saved_state[1]
    g.stars_found = saved_state[2]
    g.star_wish_day, g.star_wish_pending = saved_state[3], saved_state[4]
    g.pong_stats = json.loads(saved_state[5])
    for q, d in zip(paintings, saved_state[6]):
        q.data = d
    g.time.minutes, g.weather = saved_state[7], saved_state[8]
    for q in added:
        if q in g.world.home_furniture:
            g.world.home_furniture.remove(q)
    for p in g.players:
        p.buffs.pop("luck", None)
    g.state = "play"
    return "easel studio, gallery, telescope, Heart Pong"
