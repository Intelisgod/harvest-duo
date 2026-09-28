"""Seasonal forageables, ambient wildlife, fish collection.

Owner: Fishing & Foraging (Chat 3). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

Features (2026-09 upgrade):
  * FORAGING -- seasonal forageables spawn each morning (rolled lazily on the
    first visit of the day) in the forest / beach / farm edges / meadow. Face or
    stand on one and press action to pick it up (bob-and-pop, sparkle, SFX,
    foraging XP, ``emit("foraged")``). Today's spawns are saved so a reload never
    rerolls or duplicates them.
  * AMBIENT WILDLIFE -- butterflies, fireflies (with glows), birds that take
    off when you get close, fish jumping in the water and frogs in the rain
    (``critters.Wildlife``). Purely cosmetic, never saved.
  * COLLECTION -- journal tab ``_journal_tab_30_forage_collection``: every fish
    (count + record size) and every forageable by season, with completion %.
    Every 25% pays a one-time gold reward (``coll_milestones``, saved).
  * Extras: edible wild snacks (``_on_tool_forage_eat``), rain = more mushrooms
    (+1 find in forest/meadow), storms wash extra shells ashore, foraging side
    by side ("In Sync") gives bonus XP.
"""
import math
import random

import pygame

from .. import forage as FG
from .. import forage_art as FA
from .. import fishing
from .. import critters
from .. import ui_kit as K
from ..settings import TILE, SCREEN_W, SCREEN_H, WHITE, GOLD, MAX_ENERGY
from ..world import (PATH, WATER, STONE, WALL, FLOOR, DIRT, TFLOOR, TMAT, TWALL,
                     SAND, SAND2, PIER, PIER2, ICE, LAVA, CRYSTAL)

# ---- register the forage icons with the shared item-icon registry ----------
try:
    from .. import assets as _assets
    for _fid, _painter in FA.PAINTERS.items():
        _assets.register_item_icon(_fid, _painter)
except Exception:                       # art must never stop the game booting
    _assets = None

# tiles forageables never sit on (land spawns); anything else walkable is fair
# game -- so World's new meadow tiles (flowers, tall grass...) just work.
_NOT_LAND = {PATH, WATER, STONE, WALL, FLOOR, DIRT, TFLOOR, TMAT, TWALL,
             SAND, SAND2, PIER, PIER2, ICE, LAVA, CRYSTAL}
_POP_T = 0.6                            # pickup bob-and-pop duration (s)
_MILESTONES = ((25, 250), (50, 600), (75, 1200), (100, 3000))   # collection % -> gold


class ForageMixin:
    """Seasonal forageables, ambient wildlife, fish collection."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_forage(self):
        self.forage_spawns = {}          # area -> {(gx, gy): item_id}  (today)
        self.forage_rolled = set()       # areas already rolled today
        self.forage_found = {}           # item_id -> lifetime count picked
        self.forage_pops = []            # [item, wx, wy, t] pickup animations
        self.wildlife = critters.Wildlife()
        self._coll_scroll = 0
        self.coll_milestones = set()     # collection % milestones already rewarded

    def _on_new_day_forage(self):
        """Fresh forage every morning: yesterday's leftovers wither away."""
        self.forage_spawns = {}
        self.forage_rolled = set()
        area = self.world.area
        if area.name in FG.SPAWN_COUNTS:          # passed out outdoors
            self._forage_roll(area)

    def _on_area_enter_forage(self):
        area = self.world.area
        if area.name in FG.SPAWN_COUNTS and area.name not in self.forage_rolled:
            self._forage_roll(area)
        self.forage_pops = []
        self.wildlife.enter(self._wild_ctx())

    # ------------------------------------------------------------ save
    def _on_save_forage(self):
        return {
            "forage_spawns": {a: sorted(f"{gx}|{gy}|{it}" for (gx, gy), it in sp.items())
                              for a, sp in self.forage_spawns.items()},
            "forage_rolled": sorted(self.forage_rolled),
            "forage_found": {k: int(v) for k, v in self.forage_found.items()},
            "coll_milestones": sorted(int(m) for m in self.coll_milestones),
        }

    def _on_load_forage(self, d):
        self.forage_spawns = {}
        for a, lst in (d.get("forage_spawns") or {}).items():
            sp = {}
            for s in lst or ():
                try:
                    gx, gy, it = str(s).split("|", 2)
                    if it in FG.FORAGE:
                        sp[(int(gx), int(gy))] = it
                except (ValueError, TypeError):
                    continue
            self.forage_spawns[str(a)] = sp
        self.forage_rolled = set(str(a) for a in (d.get("forage_rolled") or ()))
        self.coll_milestones = set()
        for m in d.get("coll_milestones") or ():
            try:
                self.coll_milestones.add(int(m))
            except (TypeError, ValueError):
                pass
        self.forage_found = {}
        for k, v in (d.get("forage_found") or {}).items():
            try:
                self.forage_found[str(k)] = int(v)
            except (ValueError, TypeError):
                pass

    # ------------------------------------------------------------ spawning
    def _forage_blocked(self, area):
        """Tiles a forageable must never sit on: warps (+ neighbours), props,
        interaction anchors, players, tilled soil / crops / farm objects."""
        blocked = set()
        for w in area.warps:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    blocked.add((w["gx"] + dx, w["gy"] + dy))
        for pr in getattr(area, "props", ()):
            try:
                blocked.add((int(pr[1]), int(pr[2])))
            except (TypeError, ValueError, IndexError):
                pass
        for k, v in vars(area).items():          # shop/bed/ladder/board/gate... anchors
            if k.startswith("_"):
                continue
            if (isinstance(v, tuple) and len(v) == 2
                    and all(isinstance(c, int) for c in v)):
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        blocked.add((v[0] + dx, v[1] + dy))
        for p in self.players:
            blocked.add((int(p.x // TILE), int(p.y // TILE)))
        for (a, gx, gy) in self.world.tilled:
            if a == area.name:
                blocked.add((gx, gy))
        for (a, gx, gy) in self.world.crops:
            if a == area.name:
                blocked.add((gx, gy))
        if area.name == "farm":
            blocked.update(self.world.farm_objects.keys())
        return blocked

    def _forage_candidates(self, area, beach=False):
        blocked = self._forage_blocked(area)
        out = []
        for gy in range(1, area.h - 1):
            row = area.grid[gy]
            for gx in range(1, area.w - 1):
                t = row[gx]
                if beach:
                    if t not in (SAND, SAND2):
                        continue
                    # only the lower beach near the tideline (water within 5 rows)
                    if not any(area.tile(gx, gy + k) == WATER for k in range(1, 6)):
                        continue
                elif t in _NOT_LAND:
                    continue
                if (gx, gy) in blocked or area.is_solid(gx, gy):
                    continue
                if area.name == "farm" and min(gx, gy, area.w - 1 - gx, area.h - 1 - gy) > 3:
                    continue                      # farm: only the wild edges
                out.append((gx, gy))
        return out

    def _forage_roll(self, area, rng=random):
        """Roll today's forageables for one area (idempotent per day)."""
        name = area.name
        if name not in FG.SPAWN_COUNTS:
            return
        self.forage_rolled.add(name)
        season = self.time.season
        lo, hi = FG.SPAWN_COUNTS[name]
        weather = getattr(self, "weather", "sunny")
        wet = weather in ("rain", "storm")
        n = rng.randint(lo, hi) + FG.extra_for_weather(name, weather)
        spawns = {}
        if name == "beach":
            cands = self._forage_candidates(area, beach=True)
            rng.shuffle(cands)
            for t in cands[:n]:
                spawns[t] = FG.pick(name, season, beach=True, rng=rng)
            if rng.random() < 0.6:                # a seasonal find on the headland
                land = self._forage_candidates(area)
                if land:
                    it = FG.pick(name, season, rng=rng, wet=wet)
                    if it:
                        spawns[rng.choice(land)] = it
        else:
            cands = self._forage_candidates(area)
            rng.shuffle(cands)
            picked = []
            for t in cands:                       # keep them a little spread out
                if len(picked) >= n:
                    break
                if any(abs(t[0] - q[0]) + abs(t[1] - q[1]) < 3 for q in picked):
                    continue
                picked.append(t)
            for t in picked:
                it = FG.pick(name, season, rng=rng, wet=wet)
                if it:
                    spawns[t] = it
        self.forage_spawns[name] = {t: it for t, it in spawns.items() if it}

    # ------------------------------------------------------------ pickup
    def _interact_early_forage_pickup(self, idx, p):
        spawns = self.forage_spawns.get(self.world.current)
        if not spawns:
            return False
        here = (int(p.x // TILE), int(p.y // TILE))
        fobj = self.world.farm_objects if self.world.current == "farm" else {}
        for t in (tuple(p.target_tile()), here):
            if t in spawns and t not in fobj:
                self._forage_pick(p, t, spawns.pop(t))
                return True
        return False

    def _forage_pick(self, p, tile, item):
        gx, gy = tile
        wx, wy = gx * TILE + TILE / 2, gy * TILE + TILE / 2
        skills = getattr(p, "skills", None)
        luck = (getattr(skills, "foraging_luck", 0.0) if skills else 0.0) * 0.4
        luck += p.buff("luck") * 0.5 if hasattr(p, "buff") else 0.0
        qty = 2 if random.random() < min(0.45, luck) else 1
        p.inv.add(item, qty)
        first = item not in self.forage_found
        self.forage_found[item] = self.forage_found.get(item, 0) + qty
        self._grant_xp(p, "foraging", FG.xp_for(item))
        together = bool(getattr(self, "in_sync", False))
        if together:                                 # foraging side by side
            self._grant_xp(p, "foraging", 3)
            if hasattr(self.parts, "heart_float"):
                self.parts.heart_float(wx, wy - 26)
        self.forage_pops.append([item, wx, wy, 0.0])
        col = FG.FORAGE[item][2]
        self.parts.sparkle(wx, wy + 4, n=8, color=_soft(col))
        self.parts.dust(wx, wy + 12, n=5, color=(170, 190, 130))
        self.audio.play("forage")
        try:
            p.trigger_item_use(item, "generic", 0.45)
        except Exception:
            pass
        lab = FG.label(item)
        # one line (the "together" bonus used to be a second popup on top of it)
        self._popup(wx, wy - 26, (f"+{qty} {lab}" if qty > 1 else f"+{lab}")
                    + (" (together +3xp)" if together else ""),
                    (255, 196, 214) if together else (200, 244, 170))
        if first and hasattr(self, "toast"):
            self.toast("New Forage Find!", f"{lab} -- added to your collection",
                       icon=item, color=_soft(col))
        self.ui.log(f"{p.name} foraged {lab}" + (" x2 -- lucky!" if qty > 1 else "!"))
        self.emit("foraged", p=p, item=item, qty=qty)
        self._coll_check_milestones()

    def _coll_check_milestones(self):
        """Every 25% of the Collection (fish + forage) pays a little reward."""
        nf, tf, ng, tg = self._coll_stats()
        pct = 100 * (nf + ng) // max(1, tf + tg)
        for m, gold in _MILESTONES:
            if pct >= m and m not in self.coll_milestones:
                self.coll_milestones.add(m)
                self.gold += gold
                self.audio.play("achievement")
                for p in self.players:
                    if hasattr(self.parts, "confetti"):
                        self.parts.confetti(p.x, p.y - 30, n=14)
                    self.parts.sparkle(p.x, p.y - 20, n=10, color=(255, 226, 120))
                if hasattr(self, "toast"):
                    self.toast(f"Collection {m}%!", f"+{gold}g -- the valley has more to find",
                               color=(255, 214, 110))
                self.ui.log(f"Collection {m}% complete! +{gold}g")

    def _on_tool_forage_eat(self, idx, p, name, gx, gy):
        """Wild snacks: using an edible forageable from the hotbar eats it."""
        en = FG.EDIBLE.get(name)
        if not en or p.inv.count(name) <= 0:
            return False
        lab = FG.label(name)
        if p.energy >= MAX_ENERGY - 1:
            self.ui.log(f"{p.name} isn't hungry right now.")
            return True
        p.inv.remove(name, 1)
        p.energy = min(MAX_ENERGY, p.energy + en)
        try:
            p.trigger_item_use(name, "eat", 0.7)
        except Exception:
            pass
        self.parts.sparkle(p.x, p.y - 10, n=6, color=_soft(FG.FORAGE[name][2]))
        self.audio.play("harvest")
        self._popup(p.x, p.y - 34, f"+{en} energy", (170, 232, 150))
        self.ui.log(f"{p.name} snacked on {lab} (+{en} energy).")
        return True

    # ------------------------------------------------------------ update
    def _on_area_update_forage(self, dt):
        if self.forage_pops:
            for pop in self.forage_pops:
                pop[3] += dt
                if pop[3] >= _POP_T and len(pop) == 4:
                    pop.append(True)              # popped: burst once
                    col = _soft(FG.FORAGE[pop[0]][2] if pop[0] in FG.FORAGE else (220, 220, 220))
                    self.parts.sparkle(pop[1], pop[2] - 30, n=10, color=col)
                    self.parts.sparkle(pop[1], pop[2] - 30, n=4, color=(255, 255, 255))
            self.forage_pops = [pp for pp in self.forage_pops if pp[3] < _POP_T]
        self.wildlife.update(dt, self._wild_ctx())

    def _wild_ctx(self):
        return critters.WildCtx(
            area=self.world.area, minutes=self.time.minutes, season=self.time.season,
            weather=getattr(self, "weather", "sunny"), players=self.players,
            cam=self.cam, parts=self.parts, audio=self.audio)

    # ------------------------------------------------------------ drawing
    def _world_sprites_forage_items(self):
        spawns = self.forage_spawns.get(self.world.current)
        if not spawns:
            return ()
        cam = self.cam
        t = self.anim_t
        shadow = FA.ground_shadow()
        near = set()
        for p in self.players:
            near.add(tuple(p.target_tile()))
            near.add((int(p.x // TILE), int(p.y // TILE)))
        out = []
        fobj = self.world.farm_objects if self.world.current == "farm" else {}
        for (gx, gy), item in spawns.items():
            if (gx, gy) in fobj:                         # something got built on it
                continue
            sx = gx * TILE - cam.x
            sy = gy * TILE - cam.y
            if sx < -TILE or sx > SCREEN_W or sy < -TILE * 2 or sy > SCREEN_H:
                continue
            ph = ((gx * 37 + gy * 91) % 100) / 100.0 * 6.28
            bob = math.sin(t * 2.4 + ph) * 1.6
            base = gy * TILE + 30
            ic = FA.world_icon(item)
            out.append((base - 0.5, shadow, (sx + TILE / 2 - 11, sy + 34)))
            out.append((base, ic, (sx + (TILE - 36) / 2, sy + 3 + bob)))
            period = 1.5 if FG.FORAGE[item][1] >= 150 else 3.2   # rare finds twinkle more
            gt = (t * 0.8 + ph) % period                 # an occasional twinkle
            if gt < 0.4:
                g = FA.glint(9 if gt < 0.2 else 7)
                out.append((base + 0.1, g, (sx + 34 - g.get_width() / 2, sy + 5 + bob)))
            if (gx, gy) in near:                         # "you can pick this" cue
                out.append((base + 0.2, _chevron(), (sx + TILE / 2 - 5, sy - 4 + math.sin(t * 6) * 2)))
        return out

    def _draw_world_forage_pops(self):
        cam = self.cam
        for pop in self.forage_pops:
            item, wx, wy, tt = pop[0], pop[1], pop[2], pop[3]
            k = min(1.0, tt / _POP_T)
            rise = 30 * (1 - (1 - k) ** 3)               # ease-out hop
            sc = 1.0 + 0.35 * math.sin(k * math.pi) - (0.6 * max(0.0, k - 0.8) / 0.2)
            spr = FA.icon(item)
            if abs(sc - 1.0) > 0.02:
                spr = pygame.transform.rotozoom(spr, math.sin(k * 9) * 8, max(0.2, sc))
            self.screen.blit(spr, (int(wx - cam.x - spr.get_width() / 2),
                                   int(wy - cam.y - rise - spr.get_height() / 2)))
        self.wildlife.draw_above(self.screen, cam)

    def _draw_hud_forage_fireflies(self):
        """Fireflies twinkle above the night tint (but under menus / HUD bars)."""
        if self.wildlife.ff:
            self.wildlife.draw_fireflies(self.screen, self.cam, top=112, bottom=SCREEN_H - 96,
                                         fade=1.0 - min(1.0, getattr(self, "fade", 0.0) * 1.5))

    def _world_sprites_forage_wildlife(self):
        if getattr(self, "net_mode", None) == "client":
            # LAN client: _on_update_* hooks don't run here, so step the purely
            # cosmetic critters locally off the animation clock
            t = self.anim_t
            last = getattr(self, "_wild_client_t", None)
            self._wild_client_t = t
            if last is not None and 0 < t - last < 0.1:
                self.wildlife.update(t - last, self._wild_ctx())
        return self.wildlife.sprites(self.cam)

    def _lights_forage_fireflies(self):
        return self.wildlife.lights()

    # ------------------------------------------------------------ collection tab
    def _journal_tab_30_forage_collection(self):
        return {"title": "Collection", "draw": self._coll_draw, "key": self._coll_key}

    def _coll_key(self, key):
        if key in (pygame.K_DOWN, pygame.K_s):
            self._coll_scroll += 40
            return True
        if key in (pygame.K_UP, pygame.K_w):
            self._coll_scroll = max(0, self._coll_scroll - 40)
            return True
        return False

    def _coll_stats(self):
        recs = getattr(self, "fish_records", {}) or {}
        fish_ids = list(fishing.FISH_DATA)
        nf = sum(1 for f in fish_ids if recs.get(f, {}).get("n", 0) > 0)
        forage_ids = list(FG.FORAGE)
        ng = sum(1 for f in forage_ids if self.forage_found.get(f, 0) > 0)
        return nf, len(fish_ids), ng, len(forage_ids)

    def _coll_biggest(self):
        """(fish_id, cm, angler) of the biggest fish ever landed, or None."""
        recs = getattr(self, "fish_records", {}) or {}
        best = None
        for fid, r in recs.items():
            cm = int((r or {}).get("big", 0))
            if cm and fid in fishing.FISH_DATA and (best is None or cm > best[1]):
                best = (fid, cm, str(r.get("by", "")))
        return best

    def _coll_draw(self, surf, rect):
        rect = pygame.Rect(rect)
        font = K.font(18, True)
        small = K.font(14)
        nf, tf, ng, tg = self._coll_stats()
        pct = int(round(100 * (nf + ng) / max(1, tf + tg)))
        clip0 = surf.get_clip()
        surf.set_clip(rect.clip(clip0))
        # ---- header: completion % + bar + chests (one line, centred on hy) ----
        x0, hy = rect.x + 8, rect.y + 13
        hr = K.blit_text(surf, K.font(20, True), f"Collection  {pct}%", K.INK, (x0, hy), "left")
        bits = []
        best = self._coll_biggest()
        if best:
            fid, cm, who = best
            bits.append(f"Biggest: {fishing.display_name(fid)} {cm} cm" + (f" ({who})" if who else ""))
        chests = int(getattr(self, "fish_treasures", 0))
        if chests:
            bits.append(f"Treasure chests: {chests}")
        bw = min(280, rect.w - 560)
        if bits:
            bw_max = rect.right - hr.right - 44 - (bw + 12 if bw > 60 else 0)
            line = K.ellipsize(small, "   -   ".join(bits), max(40, bw_max))
            K.blit_text(surf, small, line, K.INK_SOFT, (hr.right + 22, hy), "left")
        if bw > 60:
            bar = pygame.Rect(rect.right - bw - 8, hy - 7, bw, 14)
            pygame.draw.rect(surf, K.WELL, bar, border_radius=7)
            if pct:
                pygame.draw.rect(surf, K.LEAF, (bar.x, bar.y, max(14, int(bw * pct / 100)), bar.h),
                                 border_radius=7)
            pygame.draw.rect(surf, K.WELL_LINE, bar, 2, border_radius=7)
        top = rect.y + 34
        body = pygame.Rect(rect.x, top, rect.w, rect.bottom - top)
        wide = rect.w >= 900
        if wide:
            fw = int(rect.w * 0.62)
            fish_box = pygame.Rect(rect.x, top, fw, 0)
            forage_box = pygame.Rect(rect.x + fw + 14, top, rect.w - fw - 14, 0)
            content = max(self._coll_fish_h(fish_box.w), self._coll_forage_h(forage_box.w))
        else:
            fish_box = pygame.Rect(rect.x, top, rect.w, 0)
            fh = self._coll_fish_h(rect.w)
            forage_box = pygame.Rect(rect.x, top + fh + 10, rect.w, 0)
            content = fh + 10 + self._coll_forage_h(rect.w)
        max_scroll = max(0, content - body.h)
        self._coll_scroll = max(0, min(self._coll_scroll, max_scroll))
        off = -self._coll_scroll
        surf.set_clip(body.clip(clip0))
        self._coll_draw_fish(surf, fish_box.move(0, off), body, font, small, nf, tf)
        self._coll_draw_forage(surf, forage_box.move(0, off), body, font, small, ng, tg)
        if wide:                                         # soft divider between the halves
            pygame.draw.line(surf, K.WELL_LINE, (forage_box.x - 8, top + 4),
                             (forage_box.x - 8, body.bottom - 4), 2)
        if max_scroll > 0:                               # scroll hint
            K.blit_text(surf, K.font(12, True), "UP/DOWN: scroll", K.INK_SOFT,
                        (rect.right - 8, rect.bottom - 9), "right")
        surf.set_clip(clip0)

    # layout metrics ------------------------------------------------
    _CELL_H = 50

    @staticmethod
    def _coll_fish_cols(w):
        return max(3, min(8, w // 104))

    @staticmethod
    def _coll_fish_groups():
        fresh = [f for f in fishing.FISH_DATA if not fishing.is_saltwater(f)]
        sea = [f for f in fishing.FISH_DATA if fishing.is_saltwater(f)]
        return [("Freshwater", fresh), ("Saltwater", sea)]

    def _coll_fish_h(self, w):
        cols = self._coll_fish_cols(w - 8)
        h = 26
        for _, ids in self._coll_fish_groups():
            h += 20 + -(-len(ids) // cols) * (self._CELL_H + 4)
        return h

    @staticmethod
    def _coll_forage_layout(w):
        """Greedy column packing of the season groups -> [(col, y, head, ids)]."""
        cols = max(1, min(5, w // 190))
        heights = [26] * cols
        out = []
        for head, ids in FG.by_season():
            c = heights.index(min(heights))
            out.append((c, heights[c], head, ids))
            heights[c] += 20 + len(ids) * 27 + 6
        return out, max(heights), cols

    def _coll_forage_h(self, w):
        return self._coll_forage_layout(w)[1]

    # drawing ------------------------------------------------------
    def _coll_draw_fish(self, surf, box, body, font, small, nf, tf):
        recs = getattr(self, "fish_records", {}) or {}
        x0, y = box.x + 8, box.y
        K.blit_text(surf, font, f"Fish  {nf}/{tf}", K.INK, (x0, y + 11), "left")
        # legend: whose dot marks a size record
        lx = box.right - 8
        for i in (1, 0):
            if i >= len(self.players):
                continue
            lab = K.ellipsize(small, f"{self.players[i].name} record", 150)
            lx -= small.size(lab)[0]
            K.blit_text(surf, small, lab, K.INK_SOFT, (lx, y + 11), "left")
            _rec_dot(surf, i, (lx - 9, y + 11))
            lx -= 28
        y += 26
        cols = self._coll_fish_cols(box.w - 8)
        cw = (box.w - 8) // cols
        ch = self._CELL_H
        for head, ids in self._coll_fish_groups():
            got = sum(1 for f in ids if (recs.get(f) or {}).get("n", 0) > 0)
            K.blit_text(surf, K.font(14, True), f"{head}  {got}/{len(ids)}", K.SPROUT, (x0, y + 8), "left")
            y += 20
            for i, fid in enumerate(ids):
                cx = x0 + (i % cols) * cw
                cy = y + (i // cols) * (ch + 4)
                if cy > body.bottom or cy + ch < body.y:
                    continue
                self._coll_fish_cell(surf, fid, recs.get(fid) or {},
                                     pygame.Rect(cx, cy, cw - 6, ch), small)
            y += -(-len(ids) // cols) * (ch + 4)

    def _coll_fish_cell(self, surf, fid, rec, box, small):
        n = int(rec.get("n", 0))
        tier = fishing.tier_of(fid)
        tcol = _ink_tone(fishing.TIER_COLOR.get(tier, (150, 200, 240)))
        if n:                                   # caught: bright paper, tier-coloured rim
            pygame.draw.rect(surf, K.CREAM_HI, box, border_radius=8)
            pygame.draw.rect(surf, tcol, box, 2, border_radius=8)
        else:
            K.well(surf, box)
        ic = _icon(fid)
        if ic is not None:
            surf.blit(ic if n else _sil(ic, fid), (box.x + 5, box.y + (box.h - 28) // 2 + 2))
        tx = box.x + 37
        tw = box.w - 41
        l1, l2 = box.y + 15, box.y + 34         # optical centres of the two text lines
        if n:
            name = fishing.display_name(fid)
            nfont = K.fit_font(name, tw, (14, 13, 12, 11), bold=True)
            K.blit_text(surf, nfont, K.ellipsize(nfont, name, tw), K.INK, (tx, l1), "left")
            r = K.blit_text(surf, small, f"x{n}", K.INK_SOFT, (tx, l2), "left")
            big = int(rec.get("big", 0))
            if big:
                K.blit_text(surf, small, f"{big}cm", K.GOLD_TXT, (r.right + 7, l2), "left")
                who = str(rec.get("by", ""))            # whose record? (a friendly rivalry)
                for i, pl in enumerate(self.players):
                    if who and pl.name == who:
                        # a badge on the icon's top-left corner, clear of the name
                        _rec_dot(surf, i, (box.x + 8, box.y + 8))
                        break
        else:                                   # unknown: tier colour + where to look
            K.blit_text(surf, small, "???", K.INK_FAINT, (tx, l1), "left")
            where = fishing.where_short(fid)
            K.blit_text(surf, small, K.ellipsize(small, where, tw), tcol, (tx, l2), "left")

    def _coll_draw_forage(self, surf, box, body, font, small, ng, tg):
        x0 = box.x + 4
        K.blit_text(surf, font, f"Forage  {ng}/{tg}", K.INK, (x0, box.y + 11), "left")
        layout, _h, cols = self._coll_forage_layout(box.w)
        gw = (box.w - 4) // cols
        cur = self.time.season
        head_f = K.font(14, True)
        for c, gy0, head, ids in layout:
            gx = x0 + c * gw
            gy = box.y + gy0
            now = head == cur
            got = sum(1 for f in ids if self.forage_found.get(f, 0) > 0)
            label = f"{head} (now)  {got}/{len(ids)}" if now else f"{head}  {got}/{len(ids)}"
            K.blit_text(surf, head_f, label, K.GOLD_TXT if now else K.SPROUT, (gx, gy + 8), "left")
            for j, fid in enumerate(ids):
                ry = gy + 19 + j * 27
                if ry > body.bottom or ry + 28 < body.y:
                    continue
                n = self.forage_found.get(fid, 0)
                ic = _icon(fid)
                if ic is not None:
                    surf.blit(ic if n else _sil(ic, fid), (gx, ry))
                cy = ry + 14
                if n:
                    lab = K.ellipsize(small, FG.label(fid), gw - 80)
                    r = K.blit_text(surf, small, lab, K.INK, (gx + 33, cy), "left")
                    K.blit_text(surf, small, f"x{n}", K.INK_SOFT, (r.right + 6, cy), "left")
                else:
                    K.blit_text(surf, small, "???", K.INK_FAINT, (gx + 33, cy), "left")


# ---------------------------------------------------------------- helpers
def _soft(c):
    return tuple(min(255, int(v * 0.6 + 100)) for v in c[:3])


def _dim(c, f=0.6):
    return tuple(int(v * f) for v in c[:3])


_TONE = {}


def _ink_tone(c):
    """A light accent colour (tier blue/green/purple/gold) darkened until it
    reads as text on the cream journal page."""
    c = tuple(c[:3])
    r = _TONE.get(c)
    if r is None:
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        f = min(1.0, 100.0 / max(1.0, lum))
        r = _TONE[c] = tuple(int(v * f) for v in c)
    return r


_SIL = {}


def _sil(ic, key):
    """Warm, faint 'not found yet' silhouette for the cream page (cached)."""
    s = _SIL.get(key)
    if s is None:
        s = _SIL[key] = pygame.mask.from_surface(ic).to_surface(
            setcolor=(*K.INK_FAINT, 255), unsetcolor=(0, 0, 0, 0))
    return s


def _rec_dot(surf, i, center):
    """Player ``i``'s size-record marker (their P1/P2 colour, ink rim)."""
    col = K.P_COL[i % len(K.P_COL)]
    pygame.draw.circle(surf, col, center, 5)
    pygame.draw.circle(surf, K.INK, center, 5, 1)


def _icon(item_id):
    try:
        if _assets is not None:
            return _assets.item_icon(item_id)
    except Exception:
        pass
    return FA.icon(item_id) if item_id in FA.PAINTERS else None


_TXT_FIT = {}


def _fit(font, text, width):
    """Trim ``text`` with '..' so it fits ``width`` px (cached)."""
    key = (id(font), text, width)
    r = _TXT_FIT.get(key)
    if r is None:
        r = text
        while r and font.size(r)[0] > width:
            r = r[:-1]
        if r != text:
            r = r[:-2].rstrip() + ".."
        _TXT_FIT[key] = r
    return r


_CHEV = []


def _chevron():
    if not _CHEV:
        s = pygame.Surface((10, 7), pygame.SRCALPHA)
        pygame.draw.polygon(s, (255, 255, 255), [(0, 0), (10, 0), (5, 6)])
        pygame.draw.polygon(s, (120, 110, 150), [(0, 0), (10, 0), (5, 6)], 1)
        _CHEV.append(s)
    return _CHEV[0]
