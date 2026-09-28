"""NPC social rewards: talk gifts and heart-milestone friendship bonuses.

Owner: "Temple, Fortune, NPC & Quests" chat.
Related modules: npc.py (NPC behaviour & hearts), quests.py, festival.py.
"""
import random
from ..crops import CROPS, shop_seeds
from .. import quests
from ..fishing import FISH
from ..settings import TILE, MAX_ENERGY


class SocialMixin:
    """Small rewards for chatting with and gifting NPCs."""

    def _talk_reward(self, p, npc):
        """Small chance to hand the player a fish / seed / ore when chatting
        (once per NPC per day so it can't be farmed)."""
        if npc.name in self.npc_gifted_today or random.random() > 0.4:
            return
        self.npc_gifted_today.add(npc.name)
        pool = [("wood", 2), ("stone", 2), ("copper", 1)]
        fishes = list(FISH.keys())
        if fishes:
            pool.append((random.choice(fishes), 1))
        seeds = shop_seeds(self.time.season)
        if seeds:
            pool.append(("seed:" + random.choice(seeds), 2))
        item, qty = random.choice(pool)
        p.inv.add(item, qty)
        nm = (item.split(":", 1)[1].title() + " seeds") if item.startswith("seed:") \
            else quests.label(item)
        self.parts.sparkle(npc.x, npc.y - 6, n=6, color=(235, 200, 130))
        self.dialogue_text += f"   (gives you {qty} {nm}!)"

    def _friendship_reward(self, p, npc):
        """Granted when an NPC crosses into a new heart level from gifts."""
        hc = npc.heart_count
        reward = 30 + hc * 20
        self.gold += reward
        loved = npc.data.get("loves")
        gift = ""
        if loved and loved in CROPS:
            p.inv.add("seed:" + loved, 2)
            gift = f", {loved.title()} seeds x2"
        self.audio.play("levelup")
        self.parts.sparkle(npc.x, npc.y - 8, n=14, color=(235, 130, 150))
        hb = getattr(self.parts, "heart_burst", None)
        if hb:
            hb(npc.x, npc.y - 20, n=12)
        self._popup(npc.x, npc.y - 12, f"+{reward}g", (255, 220, 120))
        self.ui.log(f"{npc.name} reached {hc} heart(s)! +{reward}g{gift}")
        toast = getattr(self, "toast", None)
        if toast:
            from .. import story_data as SD
            nxt = next((lv for lv in SD.EVENT_LEVELS if lv >= hc and lv in SD.events_for(npc.name)),
                       None)
            sub = f"+{reward}g{gift}" + ("  -  talk to them soon!" if nxt == hc else "")
            toast(f"{SD.display(npc.name)}: {hc} hearts!", sub, color=(255, 150, 180))

    def update_coop_bond(self, dt):
        """Co-op 'In-Sync': when the two farmers stay close they build a gentle
        bond -- little hearts drift up between them and both slowly regain energy.
        Ephemeral (never saved); a soft reward for actually playing side by side."""
        ps = self.players
        if len(ps) < 2:
            self.in_sync = False
            self.sync_t = 0.0
            return
        a, b = ps[0], ps[1]
        near = ((abs(a.x - b.x) + abs(a.y - b.y)) < TILE * 2.4
                and a.health > 0 and b.health > 0)
        if near:
            self.sync_t = min(self.sync_t + dt, 6.0)
        else:
            self.sync_t = max(self.sync_t - dt * 2.0, 0.0)
        self.in_sync = self.sync_t >= 0.8
        if not self.in_sync:
            return
        # a slow shared energy trickle -- gentle, never overpowered
        for p in ps:
            p.energy = min(MAX_ENERGY, p.energy + dt * 4.0)
        # an occasional heart drifting up from the midpoint between them
        self._sync_heart_t += dt
        if self._sync_heart_t >= 0.9:
            self._sync_heart_t = 0.0
            mx = (a.x + b.x) * 0.5
            my = (a.y + b.y) * 0.5
            self.parts.heart_float(mx + random.uniform(-6, 6), my - TILE * 0.2)
# co-op In-Sync bond lives in update_coop_bond (called from Game.update)
