"""Furniture catalogue checks (2026-09-28 expansion): every CATALOG kind is
complete -- an interaction verb, a catalogue icon / sprite, a real model for
its layer (iso ground/floor piece in all 4 rotations, tabletop item in all 4
rotations, wall piece on both walls), tabletop radius, surface heights --
and every new piece can be used in the house without errors.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import pygame


def _ink(surf):
    """Number of non-transparent pixels drawn on an SRCALPHA surface."""
    return pygame.mask.from_surface(surf, 1).count()


def run(g, check, H):
    from src import furniture as F, isofurn, wallart, furnpack
    from src.settings import TILE, AREA_HOME
    from src.systems.actions_system import FURN_ACTION

    kinds = [c[0] for c in F.CATALOG]
    col = F.PALETTE[8][1]

    def P(a, b):
        return (200 + (a - b) * 32, 160 + (a + b) * 16)

    def catalog_complete():
        assert len(set(kinds)) == len(kinds), "duplicate catalogue ids"
        bad = [k for k in kinds if k not in FURN_ACTION]
        assert not bad, f"no FURN_ACTION verb: {bad}"
        cats = set(F.CATEGORIES)
        bad = [k for k in kinds if F.CAT[k]["cat"] not in cats]
        assert not bad, f"category not in CATEGORIES: {bad}"
        for k in kinds:
            d = F.CAT[k]
            assert d["layer"] in ("ground", "floor", "wall", "top"), (k, d["layer"])
            assert 5 <= d["price"] <= 1000, (k, d["price"])
        return f"{len(kinds)} kinds, {len(F.CATEGORIES)} categories"
    check("furniture: every kind has a verb + category", catalog_complete)

    def icons():
        for k in kinds:
            for on in (True, False):
                ic = F.icon(k, col, 40)
                assert ic.get_width() <= 40 and ic.get_height() <= 40, k
                assert _ink(F.base_sprite(k, col, 40, on)) > 20, f"blank icon: {k}"
            for rot in range(4):
                sp = F.sprite(k, col, rot)
                fw, fh = F.footprint(k, rot)
                assert sp.get_size() == (fw * TILE, fh * TILE), (k, rot, sp.get_size())
        return f"{len(kinds)} icons"
    check("furniture: icons + sprites render", icons)

    def models():
        n = 0
        for k in kinds:
            lay = F.CAT[k]["layer"]
            for rot in range(4):
                for on in (False, True):
                    s = pygame.Surface((400, 320), pygame.SRCALPHA)
                    if lay in ("ground", "floor"):
                        fw, fh = F.footprint(k, rot)
                        isofurn.draw(s, P, 1, 1, fw, fh, k, col, rot, on=on)
                    elif lay == "top":
                        isofurn.draw_top(s, P, 1.5, 1.5, k, col, 24, on=on, rot=rot)
                    else:
                        continue
                    assert _ink(s) > 30, f"{k} drew (almost) nothing at rot {rot}"
                    n += 1
            if lay == "wall":
                for side in ("back", "left"):
                    for on in (False, True):
                        assert _ink(wallart.sprite(k, col, side, on=on)) > 30, (k, side)
                        n += 1
        return f"{n} renders"
    check("furniture: every model draws in every rotation", models)

    def pack_models_are_real():
        # new kinds must have their own model, never the generic fallback box
        new = kinds[kinds.index("side_table"):]
        for k in new:
            lay = F.CAT[k]["layer"]
            if lay in ("ground", "floor"):
                assert k in furnpack.GROUND, f"{k}: no iso model"
            elif lay == "top":
                assert k in furnpack.TOP, f"{k}: no tabletop model"
        return f"{len(new)} expansion kinds modelled"
    check("furniture: expansion kinds have real models", pack_models_are_real)

    def contracts():
        tops = [k for k in kinds if F.CAT[k]["layer"] == "top"]
        bad = [k for k in tops if k not in F.TOP_RADIUS]
        assert not bad, f"top kinds without TOP_RADIUS: {bad}"
        for k in tops:
            assert 0.04 <= F.top_radius(k) <= 0.25, (k, F.top_radius(k))
        bad = [k for k in F.SURFACES if isofurn.surface_height(k) <= 0]
        assert not bad, f"SURFACES without a TOPH height: {bad}"
        for k in F.SURFACES:
            fw, fh = F.CAT[k]["w"], F.CAT[k]["h"]
            x0, y0, x1, y1 = F.surface_top_rect(k, fw, fh)
            assert 0 <= x0 < x1 <= fw and 0 <= y0 < y1 <= fh, (k, (x0, y0, x1, y1))
        bad = [k for k in F.SEATS if k not in F.SEAT_TOP]
        assert not bad, f"SEATS without SEAT_TOP: {bad}"
        for s in (F.SURFACES, F.SEATS, F.TOGGLE, F.MERGE, F.SIT_FACE):
            unknown = [k for k in s if k not in F.CAT]
            assert not unknown, f"unknown kinds in a set: {unknown}"
        return f"{len(tops)} top radii, {len(F.SURFACES)} surfaces"
    check("furniture: tabletop / surface / seat contracts", contracts)

    def save_roundtrip():
        for k in kinds[kinds.index("side_table"):]:
            q = F.Placed(k, 3, 2, 1, 4, on=k in F.TOGGLE, data={"note": "hi"})
            d = q.to_dict()
            q2 = F.Placed(**d)
            assert q2.to_dict() == d, (k, d)
        return "new kinds survive to_dict/Placed(**d)"
    check("furniture: new kinds round-trip through the save format", save_roundtrip)

    # ---- in the real house: place, draw, interact, toggle ------------------
    area0 = g.world.current
    home0 = list(g.world.home_furniture)
    try:
        def use_everything():
            if g.world.current != AREA_HOME:
                g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
            g.state = "play"
            p = g.players[0]
            used = 0
            for k in kinds[kinds.index("side_table"):]:
                lay = F.CAT[k]["layer"]
                if lay == "top":
                    table = F.Placed("side_table", 6, 5, 0, 0)
                    q = F.Placed(k, 6, 5, 0, 3)
                    g.world.home_furniture = [table, q]
                elif lay == "wall":
                    q = F.Placed(k, 5, 0, 0, 3)
                    g.world.home_furniture = [q]
                else:
                    q = F.Placed(k, 6, 5, 0, 3)
                    g.world.home_furniture = [q]
                g.world.refresh_home_solids()
                p.sitting = None
                p.x, p.y = 6.5 * TILE, 7.5 * TILE
                for _ in range(2 if k in F.TOGGLE else 1):
                    g.state = "play"
                    g.interact_furniture(p, q)
                    g.draw()
                if getattr(p, "sitting", None):
                    assert p.sitting[0] is q, k
                    p.sitting = None
                g.state = "play"
                used += 1
            # night: the new lights glow
            g.world.home_furniture = [
                F.Placed("lantern", 3, 3, 0, 0, on=True),
                F.Placed("christmas_tree", 5, 3, 0, 0, on=True),
                F.Placed("side_table", 7, 3, 0, 0),
                F.Placed("lava_lamp", 7, 3, 0, 8, on=True),
                F.Placed("string_lights", 4, 0, 0, 0, on=True)]
            g.world.refresh_home_solids()
            m0 = g.time.minutes
            g.time.minutes = 22 * 60
            try:
                lights = g._lights_home() if hasattr(g, "_lights_home") else ()
                assert len(lights) >= 4, f"new lights don't glow at night: {lights}"
                g.draw()
            finally:
                g.time.minutes = m0
            return f"{used} pieces used in the house"
        check("furniture: every new piece works in the house", use_everything)
    finally:
        g.world.home_furniture = home0
        g.world.refresh_home_solids()
        for p in g.players:
            p.sitting = None
        g.state = "play"
        if g.world.current != area0:
            g.warp(area0, H.spawns_by_area(g)[area0])
