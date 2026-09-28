"""Temple: daily fortune readings and the alms/merit donation box.

Owner: "Temple, Fortune, NPC & Quests" chat.
Related modules: world.build_temple (map), npc.py (the monk "Luang Por").
The fortune effect itself is applied across combat (_reward_kill), fishing
(_land_fish) and farming (harvest in actions_system) -- all keyed on
``self.fortune[idx]`` which is reset each dawn in ``Game.on_new_day``.
"""
from ..settings import TILE


class TempleMixin:
    """Once-per-day fortune reading plus merit donations that improve the odds."""

    DONATION_COST = 250
    BELL_SYNC = 3.0          # seconds within which both bells count as "together"

    # ---------- temple bells (2026-09): ring one each, together -> Harmony ----------
    def _on_reset_temple_bells(self):
        self._bell_rung = {}            # player idx -> anim_t of their last ring
        self.temple_bells_today = set() # player idx who already got today's calm
        self._bell_swing = {}           # (gx, gy) -> seconds of swing left (visual)

    def _on_new_day_temple_bells(self):
        self.temple_bells_today = set()
        self._bell_rung = {}

    def _temple_day_key(self):
        t = self.time
        return f"{t.year}|{t.season_idx}|{t.day}"

    def _on_save_temple_bells(self):
        """Today's once-a-day temple state (bell calm, fortune reading, merit),
        stamped with the date so quitting + relaunching can't re-grant it."""
        fortune = getattr(self, "fortune", {}) or {}
        merit = getattr(self, "merit", {}) or {}
        return {"temple_today": {
            "day": self._temple_day_key(),
            "bells": sorted(int(i) for i in self.temple_bells_today),
            "fortune_read": sorted(int(i) for i in (getattr(self, "fortune_read", ()) or ())),
            "fortune": {str(k): v for k, v in sorted(fortune.items()) if v},
            "merit": {str(k): int(v) for k, v in sorted(merit.items()) if v}}}

    def _on_load_temple_bells(self, d):
        self._bell_rung = {}
        t = d.get("temple_today") or {}
        if not (isinstance(t, dict) and t.get("day") == self._temple_day_key()):
            self.temple_bells_today = set()      # old save / another day: fresh
            return
        try:
            self.temple_bells_today = set(int(i) for i in (t.get("bells") or []))
            if hasattr(self, "fortune_read"):
                self.fortune_read = set(int(i) for i in (t.get("fortune_read") or []))
            if isinstance(getattr(self, "fortune", None), dict):
                fo = {0: None, 1: None}
                fo.update({int(k): v for k, v in (t.get("fortune") or {}).items()
                           if v in ("lucky", "unlucky")})
                self.fortune = fo
            if isinstance(getattr(self, "merit", None), dict):
                me = {0: 0, 1: 0}
                me.update({int(k): max(0, min(3, int(v)))
                           for k, v in (t.get("merit") or {}).items()})
                self.merit = me
        except (TypeError, ValueError):
            self.temple_bells_today = set()

    def _interact_early_45_temple_bells(self, idx, p):
        """The two bronze bells by the temple door: ring one for a moment of
        calm (+energy once a day); when BOTH farmers ring within a few seconds
        of each other they share a 'Harmony' regen buff."""
        area = self.world.area
        if area.name != "temple":
            return False
        pgx, pgy = int(p.x // TILE), int(p.y // TILE)
        bell = next(((gx, gy) for k, gx, gy in getattr(area, "props", ())
                     if k == "bell" and abs(gx - pgx) <= 1 and abs(gy - pgy) <= 1), None)
        if bell is None:
            return False
        now = self.anim_t
        self._bell_rung[idx] = now
        self._bell_swing[bell] = 1.2
        wx, wy = bell[0] * TILE + TILE / 2, bell[1] * TILE
        self.audio.play("bell")
        self.parts.sparkle(wx, wy - 10, n=10, color=(255, 226, 150))
        ring = getattr(self.parts, "ring", None)
        if ring:
            try:
                ring(wx, wy - 10)
            except Exception:
                pass
        if idx not in self.temple_bells_today:
            self.temple_bells_today.add(idx)
            p.energy = min(270, p.energy + 20)
            self._popup(p.x, p.y - 16, "+20 energy  (calm)", (200, 230, 255))
        other = 1 - idx
        t_other = self._bell_rung.get(other)
        if (len(self.players) > 1 and t_other is not None
                and 0 <= now - t_other <= self.BELL_SYNC):
            for q in self.players:
                if hasattr(q, "add_buff"):
                    q.add_buff("regen", 90, 1.5, "Harmony")
                hb = getattr(self.parts, "heart_burst", None)
                if hb:
                    hb(q.x, q.y - 20, n=8, color=(255, 214, 150))
            self._bell_rung = {}
            toast = getattr(self, "toast", None)
            if toast:
                toast("Harmony", "The bells ring as one -- energy slowly returns",
                      color=(255, 226, 150))
            self.ui.log("The two bells ring together... Harmony!")
        else:
            self.ui.log(f"{p.name} rings the temple bell. (Ring both together for Harmony!)")
        return True

    def _draw_world_temple_bells(self):
        """A little shimmer ring + swing marker on a bell that was just rung."""
        if self.world.current != "temple" or not self._bell_swing:
            return
        import math as _m
        import pygame as _pg
        cam = self.cam
        dt = 1 / 60.0
        for (gx, gy), t in list(self._bell_swing.items()):
            t -= dt
            if t <= 0:
                del self._bell_swing[(gx, gy)]
                continue
            self._bell_swing[(gx, gy)] = t
            cx = int(gx * TILE + TILE / 2 - cam.x)
            cy = int(gy * TILE - cam.y)
            r = int(10 + (1.2 - t) * 40)
            a = max(0, int(200 * t / 1.2))
            s = _pg.Surface((r * 2 + 4, r * 2 + 4), _pg.SRCALPHA)
            _pg.draw.circle(s, (255, 226, 150, a), (r + 2, r + 2), r, 2)
            self.screen.blit(s, (cx - r - 2, cy - r - 2))
            sw = int(_m.sin(t * 14) * 4 * t)
            _pg.draw.line(self.screen, (255, 236, 170), (cx + sw - 3, cy + 12), (cx + sw + 3, cy + 12), 2)

    def _donate(self, idx, p):
        """Drop coins in the alms box: spend gold for merit that raises the lucky
        odds of your next reading, and lets you seek a fresh reading today."""
        cost = self.DONATION_COST
        if self.merit.get(idx, 0) >= 3:
            return ("The alms box is heavy with your merit today (3/3). "
                    "Go and let Luang Por read your fortune.")
        if self.gold < cost:
            return (f"The alms box asks for {cost}g, but your purse is short. "
                    "Earn a little more, then return to make merit.")
        self.gold -= cost
        self.merit[idx] = min(3, self.merit.get(idx, 0) + 1)
        self.fortune_read.discard(idx)        # may seek a fresh reading after donating
        db = self.world.area.donation_box
        self.parts.sparkle(db[0] * TILE + TILE / 2, db[1] * TILE + TILE / 2,
                           n=16, color=(255, 224, 150))
        self.audio.play("levelup")
        self._popup(p.x, p.y - 10, f"-{cost}g  +merit", (255, 220, 140))
        return (f"You offer {cost}g to the temple. Merit rises ({self.merit[idx]}/3). "
                "Luang Por will look kindly on your next reading -- go and ask again.")

    def _monk_fortune(self, idx, p):
        """Luang Por reads the player's fortune once per day: 2/3 lucky buff,
        1/3 unlucky debuff. The effect lasts until dawn (cleared in on_new_day)."""
        import random as _r
        if idx in self.fortune_read:
            cur = self.fortune.get(idx)
            mood = {"lucky": "Fortune still smiles on you today.",
                    "unlucky": "The shadow over you has not yet passed.",
                    None: "You are at peace today."}[cur]
            return f"Luang Por: You have already received your reading. {mood}"
        self.fortune_read.add(idx)
        # base 2/3 lucky, raised by today's alms-box merit (up to ~0.92)
        lucky_p = min(0.92, 2 / 3 + 0.08 * self.merit.get(idx, 0))
        if _r.random() < lucky_p:
            self.fortune[idx] = "lucky"
            self.parts.sparkle(p.x, p.y - 8, n=18, color=(255, 222, 120))
            self.audio.play("catch")
            self._popup(p.x, p.y - 12, "LUCKY!", (255, 224, 120))
            # a visible "Blessed" luck buff (buff HUD) -- stronger with merit
            if hasattr(p, "add_buff"):
                p.add_buff("luck", 150, 0.15 + 0.05 * self.merit.get(idx, 0), "Blessed")
            hb = getattr(self.parts, "heart_burst", None)
            if hb:
                hb(p.x, p.y - 16, n=10, color=(255, 222, 120))
            toast = getattr(self, "toast", None)
            if toast:
                toast(f"{p.name}: Blessed!", "Lucky until dusk -- finer loot, maybe double",
                      color=(255, 222, 120))
            return ("Luang Por blesses you: A bright star shines on your path! "
                    "Until dusk your hunts yield finer loot -- and may even double. "
                    "Go forth with merit, " + p.name + ".")
        self.fortune[idx] = "unlucky"
        self.parts.sparkle(p.x, p.y - 8, n=10, color=(120, 90, 150))
        self._popup(p.x, p.y - 12, "UNLUCKY...", (170, 120, 200))
        return ("Luang Por frowns: Dark clouds gather over you today. "
                "Until dusk, beasts may swallow part of what they drop. "
                "Stay mindful, " + p.name + ".")
