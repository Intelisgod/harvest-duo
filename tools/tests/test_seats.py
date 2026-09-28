"""Seat rendering checks (Home, 2026-09-28): sitting on every seat kind in
every rotation, depth order of seated players on single pieces AND merged
sofa/bench groups, the merged sofa model itself, and the x-ray ghost.

Pixel checks draw the room with homeiso.draw_room (no day/night overlay), so
a seated player's shirt pixels can be compared exactly with their frame.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import pygame


def run(g, check, H):
    from src.settings import AREA_HOME, TILE
    from src import furniture as F, homeiso, isofurn
    from src.assets import chars

    area0 = g.world.current
    if g.world.current != AREA_HOME:
        g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    g.state = "play"
    home0 = g.world.home_furniture
    pos0 = [(p.x, p.y, p.fx, p.fy) for p in g.players]
    area = g.world.area
    FRONT = ((0, 1), (-1, 0), (0, -1), (1, 0))       # rot -> side the seat faces
    scr = g.screen

    def shirt(p):
        return tuple(chars.resolve_appearance(p.appearance)[3])

    def hair(p):
        return tuple(chars.resolve_appearance(p.appearance)[2])

    # a furniture colour well away from both farmers' shirts and hair
    def far_color():
        taken = [shirt(p) for p in g.players] + [hair(p) for p in g.players]
        return max(range(len(F.PALETTE)),
                   key=lambda i: min(sum(abs(a - b) for a, b in zip(F.PALETTE[i][1], t))
                                     for t in taken))
    CI = far_color()

    def layout(pieces):
        g.world.home_furniture = list(pieces)
        g.world.refresh_home_solids()
        for p in g.players:
            p.sitting = None
            p.x, p.y = 30 * TILE, 30 * TILE             # off-room until placed

    def sit(idx, tile, face):
        p = g.players[idx]
        p.sitting = None
        g.state = "play"
        p.x, p.y = tile[0] * TILE + TILE / 2, tile[1] * TILE + TILE / 2
        p.fx, p.fy = face
        g.player_action(idx)
        return p.sitting

    def sit_front(idx, q, cell, rot=None):
        f = FRONT[(q.rot if rot is None else rot) % 4]
        s = sit(idx, (cell[0] + f[0], cell[1] + f[1]), (-f[0], -f[1]))
        assert s and s[0] is q, (q.kind, q.rot, cell, s)
        return s

    def draw():
        homeiso.draw_room(g)

    def frame_rect(p):
        """(screen rect, frame) of a seated player's body frame."""
        s = p.sitting
        d = ("up" if p.fy < 0 else "down" if p.fy > 0
             else "left" if p.fx < 0 else "right")
        ox, oy = homeiso.origin(area)
        isx, isy = homeiso.proj(ox, oy, s[1], s[2])
        fr = chars.seated_frames(p.appearance)[d]
        st = F.SEAT_TOP.get(s[0].kind, 16)
        return pygame.Rect(isx - fr.get_width() // 2, isy - st - chars.SEATED_HIP_Y,
                           *fr.get_size()), fr

    def share(p, color, rows=None):
        """Fraction of the frame's `color` pixels (rows < `rows`) that show
        exactly that colour on screen right now."""
        r, fr = frame_rect(p)
        want = seen = 0
        for y in range(rows or fr.get_height()):
            for x in range(fr.get_width()):
                c = fr.get_at((x, y))
                if c.a == 255 and tuple(c)[:3] == color:
                    want += 1
                    if r.collidepoint(r.x + x, r.y + y) and \
                            tuple(scr.get_at((r.x + x, r.y + y)))[:3] == color:
                        seen += 1
        assert want, "frame has no pixels of that colour"
        return seen / want

    try:
        # ------------------------------------------------ every kind x rot
        def sit_every_kind():
            out = []
            for kind in sorted(F.SEATS):
                for rot in range(4):
                    q = F.Placed(kind, 6, 5, rot, CI)
                    for cell in q.cells():
                        for idx in (0, 1):
                            layout([q])
                            s = sit_front(idx, q, cell)
                            p = g.players[idx]
                            draw()
                            d = (p.fx, p.fy)
                            if d in ((0, 1), (1, 0)):
                                # camera-facing: the torso must be in FRONT of
                                # the seat's own cushions / backrest
                                v = share(p, shirt(p), homeiso.GHOST_CUT)
                                assert v > 0.85, (kind, rot, cell, idx, round(v, 2))
                            out.append(kind[:3] + str(rot))
            return f"{len(out)} sits drawn"
        check("seats: every kind x rot x cushion, both players", sit_every_kind)

        def default_sofa_left_cushion():
            # the new-game sofa (8,1) rot 0 seats you on its LEFT cushion from
            # (8,2); its own back cushion used to paint over the whole torso
            q = F.Placed("sofa", 8, 1, 0, CI)
            layout([q])
            s = sit(0, (8, 2), (0, -1))
            assert s and s[0] is q and abs(s[1] - 8.5) < 1e-6, s
            draw()
            v = share(g.players[0], shirt(g.players[0]), homeiso.GHOST_CUT)
            assert v > 0.9, f"torso hidden: {v:.2f} of shirt pixels visible"
            # rot 3's far (lower-y) cushion had the same bug
            q = F.Placed("sofa", 6, 4, 3, CI)
            layout([q])
            sit_front(1, q, (6, 4))
            draw()
            v3 = share(g.players[1], shirt(g.players[1]), homeiso.GHOST_CUT)
            assert v3 > 0.85, f"rot3 far cushion torso hidden: {v3:.2f}"
            return f"torso visible {v:.2f} / rot3 {v3:.2f}"
        check("seats: default sofa left cushion shows the torso", default_sofa_left_cushion)

        def body_box_stops_at_backrest():
            class P:
                appearance = g.players[0].appearance
            for kind, reach in (("sofa", 0.0), ("armchair", 0.0), ("chair", 0.20)):
                for rot in range(4):
                    fx, fy = FRONT[rot]
                    P.fx, P.fy = fx, fy
                    ops = homeiso._sitter_ops(scr, 0, 0, P, 6.5, 5.5, 16, kind)
                    roles = {getattr(fn, "role", "?"): b for b, fn in ops}
                    b = roles["body"]
                    back = {(0, 1): 5.5 - b[1], (0, -1): b[3] - 5.5,
                            (1, 0): 6.5 - b[0], (-1, 0): b[2] - 6.5}[(fx, fy)]
                    assert abs(back - reach) < 1e-9, (kind, rot, back)
                    away = (fx, fy) in ((0, -1), (-1, 0))
                    assert ("ghost" in roles) == away, (kind, rot, sorted(roles))
            return "ok"
        check("seats: body box reaches only to the backrest", body_box_stops_at_backrest)

        # ------------------------------------------------ merged groups
        def pair(kind, rot, n=2):
            if rot % 2 == 0:
                return [F.Placed(kind, 3 + 2 * i, 5, rot, CI) for i in range(n)]
            return [F.Placed(kind, 6, 2 + 2 * i, rot, CI) for i in range(n)]

        def merged_sitters_layer():
            res = []
            for kind in ("sofa", "bench"):
                for rot in range(4):
                    ps = pair(kind, rot)
                    layout(ps)
                    grp = F.merge_groups(g.world.home_furniture)
                    assert any(len(x) == 2 for x in grp), "pieces did not merge"
                    cells = sorted({c for q in ps for c in q.cells()})
                    sit_front(0, ps[0], cells[0])
                    sit_front(1, ps[1], cells[-1])
                    draw()
                    for p in g.players:
                        v = share(p, shirt(p), homeiso.GHOST_CUT)
                        h = share(p, hair(p))
                        away = (p.fx, p.fy) in ((0, -1), (-1, 0))
                        if kind == "sofa" and away:
                            # behind the backrest: torso hidden (ghosted, not
                            # painted in front), head still showing over it
                            assert v < 0.5, (kind, rot, "torso over backrest", round(v, 2))
                        else:
                            assert v > 0.85, (kind, rot, "torso hidden", round(v, 2))
                        assert h > 0.8, (kind, rot, "head hidden", round(h, 2))
                        res.append(round(v, 2))
            return f"torso shares {res}"
        check("seats: merged sofa/bench sitters layer like single pieces",
              merged_sitters_layer)

        def merged_sofa_model():
            color = F.PALETTE[CI][1]
            ox, oy = homeiso.origin(area)
            cushion_top = isofurn._lt(isofurn._lt(color, 1.12))
            bad = []
            for n in (2, 3):
                for rot in range(4):
                    layout(pair("sofa", rot, n))
                    draw()
                    cells = sorted({c for q in g.world.home_furniture for c in q.cells()})
                    for (cx, cy) in cells:
                        # rot 0/3: every seat cushion shows (the fused backrest
                        # strip used to cover the far ones); rot 1/2: the strip's
                        # outer face is clean (back cushions used to poke out)
                        if rot == 0:
                            pt, z, want = (cx + 0.5, cy + 0.70), 16, cushion_top
                        elif rot == 3:
                            pt, z, want = (cx + 0.70, cy + 0.5), 16, cushion_top
                        elif rot == 2:
                            pt, z, want = (cx + 0.5, cy + 0.94), 15, isofurn._dk(color, 0.86)
                        else:
                            pt, z, want = (cx + 0.94, cy + 0.5), 15, isofurn._dk(color, 0.72)
                        sx, sy = homeiso.proj(ox, oy, *pt)
                        got = tuple(scr.get_at((sx, sy - z)))[:3]
                        if got != tuple(want):
                            bad.append((n, rot, (cx, cy), got, want))
            assert not bad, bad[:4]
            return "cushions / backrest faces clean"
        check("seats: merged sofa parts depth-sort (2/3 long, 4 rots)", merged_sofa_model)

        def l_sofas():
            shapes = ([("sofa", 3, 4, 0), ("sofa", 5, 4, 0), ("sofa", 3, 5, 1)],
                      [("sofa", 3, 4, 0), ("sofa", 5, 4, 0), ("sofa", 6, 5, 1)],
                      [("sofa", 3, 4, 0), ("sofa", 3, 5, 0)])            # 2x2 block
            sat = 0
            for spec in shapes:
                for rot in range(4):
                    ps = []
                    for k, x, y, r in spec:
                        cs = F.Placed(k, x, y, r, CI).cells()
                        for _ in range(rot):
                            cs = [(10 - b, a) for (a, b) in cs]
                        ps.append(F.Placed(k, min(c[0] for c in cs),
                                           min(c[1] for c in cs), (r + rot) % 4, CI))
                    layout(ps)
                    draw()                                   # empty
                    cells = {c for q in ps for c in q.cells()}
                    solid = set(area.solid_extra)
                    for idx, q in ((0, ps[0]), (1, ps[-1])):
                        for c in q.cells():
                            for dx, dy in FRONT:
                                nb = (c[0] + dx, c[1] + dy)
                                if nb in cells or nb in solid:
                                    continue
                                if sit(idx, nb, (-dx, -dy)):
                                    break
                            if g.players[idx].sitting:
                                sat += 1
                                break
                    draw()                                   # with sitters
            return f"{sat} sits on L / block sofas"
        check("seats: L-shaped and 2x2 sofas draw empty and occupied", l_sofas)

        # ------------------------------------------------ x-ray ghost
        def ghost_upper_body_only():
            p = g.players[0]
            for d in ("up", "left"):
                img, mask = homeiso._ghost_frame(p.appearance, d)
                w, h = img.get_size()
                for y in range(homeiso.GHOST_CUT, h):
                    for x in range(w):
                        assert not mask.get_at((x, y)), ("mask below cut", d, x, y)
                        assert img.get_at((x, y)).a == 0, ("ghost below cut", d, x, y)
            # on an away-facing armchair the ghost only paints hidden pixels:
            # head stays crisp, some torso pixels are x-rayed, none below the cut
            q = F.Placed("armchair", 6, 5, 2, CI)
            layout([q])
            sit_front(0, q, (6, 5))
            real = homeiso._blit_ghost
            try:
                homeiso._blit_ghost = lambda *a, **k: None
                draw()
                before = scr.copy()
            finally:
                homeiso._blit_ghost = real
            draw()
            r, fr = frame_rect(p)
            changed = []
            for y in range(r.h):
                for x in range(r.w):
                    if scr.get_at((r.x + x, r.y + y)) != before.get_at((r.x + x, r.y + y)):
                        changed.append((x, y))
            assert changed, "no ghost painted over the hidden torso"
            assert all(y < homeiso.GHOST_CUT and fr.get_at((x, y)).a for x, y in changed), \
                "ghost outside the upper-body silhouette"
            assert share(p, hair(p)) > 0.95, "ghost washed over the visible head"
            return f"{len(changed)} x-rayed px"
        check("seats: x-ray ghost only on hidden upper body", ghost_upper_body_only)
    finally:
        g.world.home_furniture = home0
        g.world.refresh_home_solids()
        for p, (x, y, fx, fy) in zip(g.players, pos0):
            p.sitting = None
            p.x, p.y, p.fx, p.fy = x, y, fx, fy
        if g.world.current != area0:
            sp = H.spawns_by_area(g).get(area0)
            if sp:
                g.warp(area0, sp)
        g.state = "play"
