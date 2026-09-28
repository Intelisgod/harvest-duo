"""Coffee station + bubble bath give real buffs (2026-09-28).

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""


def run(g, check, H):
    from src.settings import AREA_HOME
    from src import furniture as F

    area0 = g.world.current
    if g.world.current != AREA_HOME:
        g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
    home0 = g.world.home_furniture
    p = g.players[0]
    e0, b0 = p.energy, dict(p.buffs)
    try:
        def pamper():
            out = []
            for kind, buff in (("coffee_machine", "speed"), ("bathtub", "regen")):
                q = F.Placed(kind, 5, 5, 0, 0)
                g.world.home_furniture = [q]
                g.world.refresh_home_solids()
                p.buffs.clear()
                p.energy = 10
                assert g._home_interact(p, q) is True
                assert q.on and p.buff(buff) > 0, (kind, p.buffs)
                gained = p.energy - 10
                assert gained > 0
                p.energy = 10
                g._home_interact(p, q)                  # same day: buff only
                assert p.energy == 10, "energy boost should be once a day"
                for _ in range(8):
                    g._on_update_home_pamper(1.0)
                assert not q.on, "piece did not switch itself off"
                out.append(f"{kind} +{gained}")
            return ", ".join(out)
        check("pamper: coffee station + bubble bath buffs, once-a-day energy", pamper)
    finally:
        g.world.home_furniture = home0
        g.world.refresh_home_solids()
        p.energy = e0
        p.buffs.clear()
        p.buffs.update(b0)
        if g.world.current != area0:
            sp = H.spawns_by_area(g).get(area0)
            if sp:
                g.warp(area0, sp)
        g.state = "play"
