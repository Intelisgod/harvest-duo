"""Livestock, the auto-collector and overnight forest regrowth.

Owner: "Farming, Animals & Cooking" chat.
Related modules: crops.py, animals.py, cooking.py.
(Crop growth/harvest logic lives in crops.py; planting & watering tool logic
lives in actions_system.py.)
2026-09 animal affection: coop presses are handled here (``_interact_early_45``):
collect produce (happy animals may give a LARGE x2) or pet once a day (+hearts,
bonus when BOTH players pet it); hearts row drawn by ``_draw_world_farm_hearts``.
Artisan machines / fertilizer / buff foods live in artisan_system.py.
"""
import random

from ..settings import TILE, AREA_COOP, AREA_FOREST
from ..world import GRASS, GRASS2
from .. import animals as _animals


class FarmMixin:
    """Coop livestock placement, one-press produce collection, forest regrow."""

    def _rehome_animals(self):
        """Arrange livestock on free tiles inside the coop barn (called on entry)."""
        coop = self.world.areas[AREA_COOP]
        spots = [(gx, gy) for gy in range(2, coop.h - 2)
                 for gx in range(4, coop.w - 2) if not coop.is_solid(gx, gy)]
        for i, an in enumerate(self.animals):
            gx, gy = spots[i % len(spots)] if spots else (8, 5)
            an.x = gx * TILE + TILE / 2
            an.y = gy * TILE + TILE / 2
            an.home = (an.x, an.y)

    def _regrow_forest(self, lo=3, hi=6, cap=120):
        """Sprout a few new forest trees overnight, leaving the hunting clearing,
        pond and warp tiles clear. Caps total trees so the forest never fills in."""
        import random as _r
        forest = self.world.areas[AREA_FOREST]
        warp_tiles = {(18, 2), (19, 2)}
        want = _r.randint(lo, hi)
        grown = attempts = 0
        while grown < want and attempts < 120:
            attempts += 1
            if len(forest.trees) >= cap:
                break
            x = _r.randint(1, forest.w - 2)
            y = _r.randint(3, forest.h - 2)
            if 13 <= x <= 25 and 9 <= y <= 18:            # keep the central clearing open
                continue
            if forest.tile(x, y) not in (GRASS, GRASS2):  # grass only (skip pond/path)
                continue
            if (x, y) in forest.trees or (x, y) in warp_tiles:
                continue
            forest.trees.add((x, y))
            grown += 1

    def _revert_idle_tilled(self, days=2):
        """Tilled tiles left empty for `days` mornings revert to plain ground.

        Prevents a sea of mis-hoed dirt and keeps the farm tidy. A tile that
        holds a crop is "in use", so its idle counter is reset. Counter state
        lives in ``self.tilled_idle`` (a {(area, gx, gy): empty_days} dict that
        Core initialises in ``reset()`` and persists via save/load). Call this
        once per morning from ``on_new_day``.
        """
        idle = self.tilled_idle            # {(area, gx, gy): empty_days}
        fert = getattr(self, "fert_tiles", None) or {}
        for key in list(self.world.tilled):
            # has a crop, or was fertilized (prepared for planting) = in use
            if key in self.world.crops or key in fert:
                idle.pop(key, None)
                continue
            idle[key] = idle.get(key, 0) + 1
            if idle[key] >= days:
                self.world.tilled.discard(key)
                self.world.watered.discard(key)
                idle.pop(key, None)
        # sweep stale entries (tiles no longer tilled, e.g. planted-then-removed)
        for k in [k for k in idle if k not in self.world.tilled]:
            idle.pop(k, None)

    # ---------- animal affection (2026-09) ----------
    def _on_new_day_farm_animals(self):
        for an in self.animals:
            an.petted_by = []

    def _on_load_farm_animals(self, d):
        """Restore the per-animal 'petted today' flag (Core rebuilds Animal objects
        from the save but only passes kind/pos/friend/produce)."""
        saved = [a for a in d.get("animals", []) if a.get("kind") in _animals.ANIMALS]
        for an, a in zip(self.animals, saved):
            pb = a.get("petted_by")
            if isinstance(pb, list):
                an.petted_by = sorted(int(i) for i in pb if isinstance(i, (int, float)))
            else:                                # older build saved a plain bool
                an.petted_by = [0] if a.get("petted") else []

    def _on_reset_farm_animals(self):
        self._farm_heart_t = 0.0      # throttles the happy-animal floating hearts

    def _on_area_update_farm_animals(self, dt):
        """Very happy animals (4+ hearts) now and then float a little heart."""
        if self.world.current != AREA_COOP or not self.animals:
            return
        t = getattr(self, "_farm_heart_t", 0.0) - dt
        if t <= 0:
            t = random.uniform(2.5, 4.5)
            happy = [an for an in self.animals if an.hearts >= 4]
            if happy:
                an = random.choice(happy)
                self.parts.heart_float(an.x + random.uniform(-6, 6), an.y - an.size - 6)
        self._farm_heart_t = t

    def _draw_world_farm_hearts(self):
        """Affection rows above recently petted animals (top layer, so the
        players' held-item labels never cover them)."""
        if self.world.current != AREA_COOP:
            return
        cam = self.cam
        for an in self.animals:
            t = getattr(an, "heart_t", 0)
            if t > 0:
                rise = (2.4 - t) * 4 if t > 2.0 else 0
                r = _animals.draw_heart_row(self.screen, int(an.x - cam.x),
                                            int(an.y - cam.y - an.size - 46 - rise),
                                            an.friend, min(1.0, t / 0.5))
                f = getattr(self, "hud_reserve", None)      # floating texts step clear
                if f and r is not None:
                    f(r)

    def _interact_early_45_farm_animals(self, idx, p):
        """Coop animals: collect produce (happy animals may give a LARGE x2), or pet
        once a day to raise affection (0-5 hearts shown above the animal)."""
        area = self.world.area
        if area.name != AREA_COOP or not self.animals:
            return False
        cl = getattr(area, "collector", None)
        if cl:                                   # let Core's collector branch win there
            pgx, pgy = int(p.x // TILE), int(p.y // TILE)
            if abs(pgx - cl[0]) <= 1 and abs(pgy - cl[1]) <= 1:
                return False
        for an in self.animals:
            if abs(an.x - p.x) < TILE * 1.1 and abs(an.y - p.y) < TILE * 1.1:
                hearts0 = an.hearts
                self._farm_animal_press(p, an, idx)
                if an.hearts > hearts0:              # crossed a heart milestone
                    self.toast(f"{an.label} loves you!", f"{an.hearts}/5 hearts"
                               + ("  -  more large produce" if an.hearts >= 2 else ""),
                               color=(255, 160, 190))
                    hb = getattr(self.parts, "heart_burst", None)
                    if hb:
                        hb(an.x, an.y - 16, n=16)
                return True
        return False

    def _farm_animal_press(self, p, an, idx=0):
        """One action press on a coop animal: collect its produce, else pet it."""
        if an.has_produce:
            qty = an.produce_qty(random) if hasattr(an, "produce_qty") else 1
            p.inv.add(an.produce, qty)
            an.has_produce = False
            an.friend = min(250, an.friend + 8)
            self.parts.sparkle(an.x, an.y - 8, n=8 + 6 * (qty - 1), color=(255, 230, 160))
            self.audio.play("harvest")
            if qty > 1:
                self._popup(an.x, an.y - 34, "Large! x2", (255, 186, 64))
                sb = getattr(self.parts, "star_burst", None)
                if sb:
                    sb(an.x, an.y - 12, n=6)
            self.ui.log(f"Collected {qty} {an.produce.replace('_', ' ')} from the {an.label}!")
            for _ in range(qty):
                self.emit("animal_product", p=p, item=an.produce)
        else:
            res = an.pet(idx) if hasattr(an, "pet") else None
            self.parts.heart_float(an.x, an.y - 20)
            self.emit("animal_petted", p=p, animal=an.kind)      # same event Core's branch sends
            if res == "both":                    # the two of you both showed it love today
                hb = getattr(self.parts, "heart_burst", None)
                if hb:
                    hb(an.x, an.y - 14, n=14)
                self.audio.play("ui_select")
                self._popup(an.x, an.y - an.size - 72, "Loved by you both!", (255, 92, 140))
                self.ui.log(f"The {an.label} is loved by you both today! (bonus affection)")
            elif res:
                hb = getattr(self.parts, "heart_burst", None)
                if hb:
                    hb(an.x, an.y - 14, n=8)
                self.audio.play("pet")
                self.audio.play("ui_select")
                self._popup(an.x, an.y - an.size - 72, "+Affection", (255, 112, 156))
                self.ui.log(f"{p.name} pets the {an.label}. It looks happy! "
                            f"({an.friend / 50:.1f}/5 hearts)")
            else:
                self.ui.log(f"The {an.label} nuzzles {p.name}. (already petted today)")

    def _collect_all_produce(self, idx, p):
        """One-press livestock collector: gather ready produce from every animal,
        nudge their friendship, and drop it all into the player's inventory.
        Happy animals (hearts) sometimes give a large (double) produce."""
        collected = {}
        large = 0
        for an in self.animals:
            if an.has_produce:
                an.has_produce = False
                an.friend = min(250, an.friend + 4)
                q = an.produce_qty(random) if hasattr(an, "produce_qty") else 1
                large += q - 1
                collected[an.produce] = collected.get(an.produce, 0) + q
        cl = self.world.area.collector
        wx, wy = cl[0] * TILE + TILE / 2, cl[1] * TILE + TILE / 2
        if not collected:
            self.audio.play("ui_move")
            self.ui.log("The collector whirs... no produce ready right now.")
            return
        for prod, n in collected.items():
            p.inv.add(prod, n)
            for _ in range(n):
                self.emit("animal_product", p=p, item=prod)
        total = sum(collected.values())
        summary = ", ".join(f"{n} {prod.replace('_', ' ')}" for prod, n in collected.items())
        self.parts.sparkle(wx, wy - 6, n=16, color=(255, 230, 160))
        self.audio.play("harvest")
        self._popup(wx, wy - 10, f"+{total}", (255, 230, 160))
        extra = f" ({large} large!)" if large else ""
        self.ui.log(f"Auto-Collector gathered {summary} from your animals!{extra}")
