"""Free-form tabletop placement (2026-09-28): surfaces (single, merged, wall
shelf), no overlaps, slide-to-free-spot, magnet guides, ray-cast aiming, drag
between surfaces, items riding/turning with their table, save round-trip.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import math

import pygame


def run(g, check, H):
    from src.settings import AREA_HOME
    from src import furniture as F, homeiso as HI, tabletop as TT

    area0 = g.world.current
    if g.world.current != AREA_HOME:
        g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    home0 = g.world.home_furniture
    gold0 = g.gold
    pos0 = [(p.x, p.y) for p in g.players]
    P = F.Placed
    b = g.build
    area = g.world.area

    def layout(pieces):
        g.world.home_furniture = list(pieces)
        g.world.refresh_home_solids()
        for p in g.players:
            p.x = p.y = 30 * 48
        b.brush = None
        b.selected = None
        b.dragging = False
        b.top_target = None
        g.gold = 999999

    def spt(x, y, h):
        ox, oy = HI.origin(area)
        px, py = HI.proj(ox, oy, x, y)
        return (px, py - h)

    def ev(t, **k):
        b.handle_event(pygame.event.Event(t, **k))

    def place(kind, x, y, h, rot=0):
        b.brush, b.rot = kind, rot
        pt = spt(x, y, h)
        ev(pygame.MOUSEMOTION, pos=pt, rel=(0, 0), buttons=(0, 0, 0))
        ev(pygame.MOUSEBUTTONDOWN, pos=pt, button=1)
        ev(pygame.MOUSEBUTTONUP, pos=pt, button=1)

    def tops():
        return [q for q in g.world.home_furniture if F.CAT[q.kind]["layer"] == "top"]

    def no_overlap():
        surfs = TT.surfaces(g.world)
        qs = tops()
        for i, a in enumerate(qs):
            sa = TT.support_of(a, surfs)
            assert sa is not None, (a.kind, "orphaned")
            assert sa.fits(*TT.pos(a), F.top_radius(a.kind)), (a.kind, "hangs off the edge")
            for c in qs[i + 1:]:
                if TT.support_of(c, surfs) is not sa:
                    continue
                d = math.dist(TT.pos(a), TT.pos(c))
                need = (F.top_radius(a.kind) + F.top_radius(c.kind)) * TT.PACK
                assert d >= need - 1e-6, (a.kind, c.kind, round(d, 3), round(need, 3))

    try:
        def crowd_spreads():
            layout([P("dining_table", 3, 3, 0, 0)])
            kinds = ["vase_flowers", "coffee_mug", "fruit_bowl", "candle_small",
                     "photo_frame", "book_stack", "desk_lamp", "pen_holder",
                     "cactus_small", "coffee_mug"]
            for i, k in enumerate(kinds):
                place(k, 4.0, 3.5, 24, rot=i % 4)
            assert len(tops()) == len(kinds), len(tops())
            no_overlap()
            return f"{len(kinds)} items aimed at one spot, all spread out"
        check("tabletop: a crowd aimed at one spot spreads out, no overlaps", crowd_spreads)

        def full_surface_refuses():
            layout([P("nightstand", 3, 3, 0, 0)])
            for _ in range(20):
                place("paper_stack", 3.5, 3.5, 22)
            n = len(tops())
            assert 1 <= n < 20, n
            no_overlap()
            return f"nightstand holds {n} paper stacks, then says no"
        check("tabletop: a full surface stops accepting items", full_surface_refuses)

        def merged_worktop():
            layout([P("counter", 4, 2, 0, 0), P("counter", 5, 2, 0, 0)])
            surfs = TT.surfaces(g.world)
            assert len(surfs) == 1, "two counters did not fuse into one worktop"
            place("fruit_bowl", 5.0, 2.5, 27)           # right on the seam
            q = tops()[0]
            assert abs(TT.pos(q)[0] - 5.0) < 0.07, TT.pos(q)
            return "item straddles the seam at x=%.2f" % TT.pos(q)[0]
        check("tabletop: merged counters are one seamless worktop", merged_worktop)

        def shelf_over_nightstand():
            layout([P("nightstand", 3, 1, 0, 0), P("wall_shelf", 3, 0, 0, 3)])
            place("cactus_small", 3.5, 1.15, TT.WALL_SHELF_H)
            place("desk_lamp", 3.5, 1.6, 22)
            surfs = TT.surfaces(g.world)
            got = sorted((q.kind, TT.support_of(q, surfs).kind) for q in tops())
            assert got == [("cactus_small", "wall_shelf"), ("desk_lamp", "nightstand")], got
            return "shelf and the nightstand under it each keep their own item"
        check("tabletop: wall shelf above a nightstand (ray-cast picks the right top)",
              shelf_over_nightstand)

        def magnet_and_free():
            layout([P("dining_table", 3, 3, 0, 0)])
            surfs = TT.surfaces(g.world)
            s = surfs[0]
            cx, cy = s.centre()
            x, y, ok, guides = TT.resolve(s, "coffee_mug", cx + 0.03, cy - 0.02, [])
            assert ok and abs(x - cx) < 1e-9 and abs(y - cy) < 1e-9, (x, y)
            assert {gd[0] for gd in guides} == {"x", "y"}, guides
            x2, y2, ok2, g2 = TT.resolve(s, "coffee_mug", cx + 0.03, cy - 0.02, [], snap=False)
            assert ok2 and not g2 and abs(x2 - (cx + 0.03)) < 1e-9
            return "snaps to the centre lines; Shift places freely"
        check("tabletop: magnet guides + free placement", magnet_and_free)

        def drag_between_surfaces():
            layout([P("dining_table", 3, 3, 0, 0), P("coffee_table", 8, 5, 0, 0)])
            place("vase_flowers", 4.0, 3.5, 24)
            v = tops()[0]
            b.brush = None
            x, y = TT.pos(v)
            p0 = spt(x, y, 30)
            ev(pygame.MOUSEMOTION, pos=p0, rel=(0, 0), buttons=(0, 0, 0))
            ev(pygame.MOUSEBUTTONDOWN, pos=p0, button=1)
            assert b.selected is v and id(v) in HI.LIFT, "item not picked up"
            tgt = spt(8.5, 5.5, 22)
            for i in range(1, 9):
                ev(pygame.MOUSEMOTION, pos=(p0[0] + (tgt[0] - p0[0]) * i / 8,
                                            p0[1] + (tgt[1] - p0[1]) * i / 8),
                   rel=(0, 0), buttons=(1, 0, 0))
            HI.draw_room(g, build=True)
            b.draw(g.screen)                              # held ghost + guides
            ev(pygame.MOUSEBUTTONUP, pos=tgt, button=1)
            assert not HI.LIFT, "item still floating after release"
            s = TT.support_of(v, TT.surfaces(g.world))
            assert s.kind == "coffee_table", s.kind
            return "picked up, carried, set down on the coffee table"
        check("tabletop: drag an item from one table to another", drag_between_surfaces)

        def rides_and_turns():
            t = P("dining_table", 3, 3, 0, 0)
            layout([t])
            for k in ("coffee_mug", "photo_frame", "book_stack"):
                place(k, 3.4, 3.4, 24)
            b.brush = None
            b.selected = t
            b.rotate()                                     # turns in place
            surfs = TT.surfaces(g.world)
            s = next(x for x in surfs if t in x.pieces)
            assert len(TT.items_on(s, g.world, surfs)) == 3
            no_overlap()
            assert {q.rot for q in tops()} == {1}, [q.rot for q in tops()]
            b.selected = t
            b.dragging = True
            before = [TT.pos(q) for q in tops()]
            ox, oy = HI.origin(area)
            ev(pygame.MOUSEMOTION, pos=HI.proj(ox, oy, 6.5, 4.5), rel=(0, 0),
               buttons=(1, 0, 0))
            ev(pygame.MOUSEBUTTONUP, pos=(0, 0), button=1)
            moved = (t.gx - 3, t.gy - 3)
            assert moved != (0, 0), "table did not move"
            after = [TT.pos(q) for q in tops()]
            for (a0, b0), (a1, b1) in zip(before, after):
                assert abs(a1 - a0 - moved[0]) < 1e-9 and abs(b1 - b0 - moved[1]) < 1e-9
            return f"3 items turned with the table and rode {moved}"
        check("tabletop: items turn and travel with their table", rides_and_turns)

        def sell_table_sells_items():
            layout([P("dining_table", 3, 3, 0, 0)])
            place("candle_small", 4.0, 3.5, 24)
            b.brush = None
            b.selected = g.world.home_furniture[0]
            b.sell_selected()
            assert not tops(), "tabletop items left floating"
            return "table sold -> its decor sold along"
        check("tabletop: selling a table sells what stood on it", sell_table_sells_items)

        def nudge_and_wheel():
            layout([P("dining_table", 3, 3, 0, 0)])
            place("coffee_mug", 4.0, 3.5, 24)
            q = tops()[0]
            b.brush = None
            b.selected = q
            x0, y0 = TT.pos(q)
            ev(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=0, unicode="", scancode=0)
            assert abs(TT.pos(q)[0] - x0 - F.TOP_SNAP) < 1e-9, TT.pos(q)
            r0 = q.rot
            pygame.mouse.set_pos(spt(4.0, 3.5, 24))
            ev(pygame.MOUSEWHEEL, x=0, y=1, flipped=False)
            ok_wheel = q.rot == (r0 + 1) % 4
            b.rotate()
            assert q.rot in ((r0 + 1) % 4, (r0 + 2) % 4)
            return "arrows nudge 1/16 tile, R turns" + (", wheel turns" if ok_wheel else "")
        check("tabletop: arrow-key nudge + rotate a selected item", nudge_and_wheel)

        def save_roundtrip():
            layout([P("dining_table", 3, 3, 0, 0), P("wall_shelf", 5, 0, 0, 2)])
            place("fruit_bowl", 3.7, 3.4, 24, rot=2)
            place("book_stack", 5.5, 1.15, TT.WALL_SHELF_H)
            d = [q.to_dict() for q in g.world.home_furniture]
            back = [F.Placed(**x) for x in d]
            surfs = TT.surfaces(type("W", (), {"home_furniture": back})())
            for a, c in zip(g.world.home_furniture, back):
                if F.CAT[a.kind]["layer"] == "top":
                    assert TT.pos(a) == TT.pos(c) and a.rot == c.rot
                    assert TT.support_of(c, surfs) is not None
            return "positions, facing and shelf height survive a save"
        check("tabletop: free positions round-trip through the save dict", save_roundtrip)

        def legacy_slots_still_draw():
            layout([P("dining_table", 3, 3, 0, 0),
                    P("coffee_mug", 3, 3, 0, 0, ox=-0.22, oy=0.22),
                    P("candle_small", 4, 3, 0, 0, ox=0.22, oy=-0.22)])
            surfs = TT.surfaces(g.world)
            assert all(TT.support_of(q, surfs) is not None for q in tops())
            HI.draw_room(g)
            return "old quarter-slot decor still sits on its table"
        check("tabletop: old saves' quarter-slot decor still works", legacy_slots_still_draw)
    finally:
        HI.LIFT.clear()
        b.brush = None
        b.selected = None
        b.dragging = False
        b.top_target = None
        g.world.home_furniture = home0
        g.world.refresh_home_solids()
        g.gold = gold0
        for p, (x, y) in zip(g.players, pos0):
            p.x, p.y = x, y
        if g.world.current != area0:
            sp = H.spawns_by_area(g).get(area0)
            if sp:
                g.warp(area0, sp)
        g.state = "play"
