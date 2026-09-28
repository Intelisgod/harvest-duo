"""Mist City — 2D side-scroller zombie-town mode ("เมืองนาฬิกาหยุดเดิน").

Owner: Chat 7 (Mist City) — this whole package, see docs/TASK_mist_city.md.
Public surface is ``MistMixin`` (core mixes it into Game via a guarded import);
everything else in here is internal to the mode:
  mist_system  MistRun (zones, noise, events, boss, HUD) + MistMixin (records, journal)
  world2d      Main Street + ZoneMixin      zones   Old Factory, Clock Tower courtyard
  player2d     platformer co-op controller  zombies walker/runner/worker/hazmat
  boss         The Bell Keeper              events  outage / acid rain / siren / supply drop
  items        cursed_gear + city_key (loot registry + icons)
"""
from .mist_system import MistMixin

__all__ = ["MistMixin", "gallery_entries"]


def gallery_entries():
    """(name, render_fn) pairs for the Gallery screen — single source of truth:
    every fn calls the REAL Mist City draw code, so the gallery always matches
    the mode pixel-for-pixel (new zombies added to zombies.ARCHETYPES show up
    here automatically)."""
    import pygame
    from .zombies import Zombie, ARCHETYPES
    from .world2d import MistWorld
    from .mist_system import medkit_surface

    def zombie_fn(kind):
        def fn():
            s = pygame.Surface((70, 64), pygame.SRCALPHA)
            z = Zombie(35, kind)
            z.y, z.anim, z.facing = 58.0, 0.7, -1
            z.draw(s, 0, 0.0)
            return s
        return fn

    def scene_fn():
        surf = pygame.Surface((1280, 720))
        w = MistWorld()
        w.draw_back(surf, 260.0, 0.0)
        w.draw_main(surf, 260.0, 0.0)
        try:
            w.draw_fog(surf, 260.0, 0.0)
        except Exception:
            pass
        return pygame.transform.smoothscale(surf, (320, 180))

    def zone_fn(cls, camx):
        def fn():
            surf = pygame.Surface((1280, 720))
            w = cls()
            w.draw_back(surf, camx, 0.0)
            w.draw_main(surf, camx, 0.0)
            w.draw_fog(surf, camx, 0.0)
            return pygame.transform.smoothscale(surf, (320, 180))
        return fn

    def boss_fn():
        import random
        from .boss import BellKeeper
        from .world2d import GROUND_Y
        # BellKeeper.draw puts its shadow / floor rings on GROUND_Y, so pose it
        # standing on the real street line and crop to the drawn pixels after
        s = pygame.Surface((280, GROUND_Y + 24), pygame.SRCALPHA)
        b = BellKeeper(140, 600, random.Random(1))
        b.wait = b.intro = 0.0          # skip the belfry drop-in (draw bails while waiting)
        b.drop, b.y = 0.0, float(GROUND_Y)
        b.anim = 0.5                    # eyes open (anim 0 is mid-blink)
        b.draw(s, 0, 0.4)
        box = s.get_bounding_rect()
        if box.w <= 0 or box.h <= 0:
            return s
        return s.subsurface(box.inflate(8, 8).clip(s.get_rect())).copy()

    from .zones import FactoryWorld, TowerWorld
    out = [("Street (scene)", scene_fn),
           ("Old Factory (scene)", zone_fn(FactoryWorld, 900.0)),
           ("Clock Tower (scene)", zone_fn(TowerWorld, 0.0)),
           ("The Bell Keeper", boss_fn)]
    for kind, a in ARCHETYPES.items():
        out.append((a.get("label", kind.title()), zombie_fn(kind)))
    out.append(("First-aid Kit", medkit_surface))
    return out
