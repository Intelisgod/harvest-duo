"""Achievements / milestones and other progression features.

Owner: Combat, Mining & Progression (Chat 1). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

Achievements (data in progress.ACHIEVEMENTS) are driven by the shared events
(_on_event_progress) plus a once-a-second scan of things that have no event
(gems held, villager hearts, tool tiers, mine depth). Unlocking: toast + SFX
"achievement" + gold + confetti + ``emit("achievement", key=...)``. Saved as
``ach_unlocked`` (sorted list) / ``ach_counters`` / ``ach_gems``. Journal tab
"Achievements" = a trophy grid with progress bars and total completion.
"""
import math
import pygame

from .. import progress as PR
from .. import loot
from .. import assets
from .. import ui_kit as K
from ..settings import WHITE, GOLD, AREA_MINE, DAYS_PER_SEASON

_ICON_CACHE = {}
_ACH_GOLD = (255, 214, 90)
_ACH_TOAST_WAIT = 4.0       # longest an achievement cheer waits for the toast stack
_TITLE_FONT = {}      # (max width, font ids) -> the one title font for the grid
_TITLE_SYS = {}       # size -> intermediate consolas font


def _special_icon(name):
    """Painted 28px icons for achievements without an item icon."""
    s = _ICON_CACHE.get(name)
    if s is not None:
        return s
    s = pygame.Surface((28, 28), pygame.SRCALPHA)
    if name == "@heart":
        c, d = (255, 120, 160), (200, 70, 110)
        pygame.draw.circle(s, c, (9, 11), 6)
        pygame.draw.circle(s, c, (19, 11), 6)
        pygame.draw.polygon(s, c, [(3, 13), (25, 13), (14, 25)])
        pygame.draw.circle(s, (255, 220, 230), (8, 9), 2)
        pygame.draw.lines(s, d, False, [(3, 13), (14, 25), (25, 13)], 1)
    elif name == "@coin":
        pygame.draw.circle(s, (180, 130, 40), (14, 15), 11)
        pygame.draw.circle(s, (250, 206, 80), (14, 14), 10)
        pygame.draw.circle(s, (255, 236, 150), (14, 14), 7, 2)
        pygame.draw.line(s, (190, 140, 40), (14, 9), (14, 19), 3)
        pygame.draw.circle(s, (255, 255, 230), (10, 9), 2)
    elif name == "@smile":
        pygame.draw.circle(s, (250, 214, 110), (14, 14), 11)
        pygame.draw.circle(s, (200, 160, 70), (14, 14), 11, 1)
        pygame.draw.circle(s, (70, 50, 40), (10, 12), 2)
        pygame.draw.circle(s, (70, 50, 40), (18, 12), 2)
        pygame.draw.arc(s, (70, 50, 40), (8, 11, 12, 9), 3.5, 5.9, 2)
        pygame.draw.circle(s, (255, 160, 150), (7, 17), 2)
        pygame.draw.circle(s, (255, 160, 150), (21, 17), 2)
    else:                                     # "@trophy"
        g, gd, gl = (246, 200, 80), (176, 130, 40), (255, 240, 170)
        pygame.draw.rect(s, g, (8, 4, 12, 11), border_bottom_left_radius=6, border_bottom_right_radius=6)
        pygame.draw.arc(s, g, (3, 5, 8, 8), 1.57, 4.71, 2)
        pygame.draw.arc(s, g, (17, 5, 8, 8), -1.57, 1.57, 2)
        pygame.draw.rect(s, gd, (12, 15, 4, 5))
        pygame.draw.rect(s, (150, 104, 64), (8, 20, 12, 5), border_radius=1)
        pygame.draw.line(s, gl, (10, 6), (10, 12), 2)
    _ICON_CACHE[name] = s
    return s


def ach_icon(icon):
    if icon.startswith("@"):
        return _special_icon(icon)
    try:
        return assets.item_icon(icon)
    except Exception:
        return _special_icon("@trophy")


def _silhouette(icon):
    key = ("sil", icon)
    s = _ICON_CACHE.get(key)
    if s is None:
        src = ach_icon(icon)
        s = pygame.mask.from_surface(src).to_surface(setcolor=(*K.INK_FAINT, 255),
                                                     unsetcolor=(0, 0, 0, 0))
        _ICON_CACHE[key] = s
    return s


_COUNTED = {"harvest", "fish_caught", "monster_killed", "item_sold", "cooked", "crafted",
            "tool_upgraded", "mine_depth", "partner_gift", "emote", "bundle_done",
            "festival_won", "mist_run_end"}


class ProgressMixin:
    """Achievements / milestones and other progression features."""

    # ------------------------------------------------------------ state
    def _on_reset_progress(self):
        self.ach_unlocked = set()
        self.ach_counters = {}
        self.ach_gems = set()
        self._ach_scan_t = 0.0
        self._ach_scanned = False       # first scan after reset/load stays quiet
        self._ach_sel = 0
        self._ach_txt = {}
        self._ach_toast_q = []          # [key, waited] celebrations not shown yet
        self._ach_toast_gap = 0.0

    def _on_save_progress(self):
        return {"ach_unlocked": sorted(self.ach_unlocked),
                "ach_counters": {k: int(v) for k, v in sorted(self.ach_counters.items())},
                "ach_gems": sorted(self.ach_gems)}

    def _on_load_progress(self, d):
        self.ach_unlocked = set(str(k) for k in (d.get("ach_unlocked") or []))
        raw = d.get("ach_counters") or {}
        self.ach_counters = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    self.ach_counters[str(k)] = int(v)
                except (TypeError, ValueError):
                    pass
        self.ach_gems = set(str(g) for g in (d.get("ach_gems") or []))
        # the first scan after a load records already-met goals quietly (no gold);
        # the LAN client's 1 Hz world resync is not a fresh load
        if not getattr(self, "_net_applying_world", False) or \
                not getattr(self, "_net_world_seen", False):
            self._ach_scanned = False
            self._ach_toast_q = []       # a fresh load drops the old session's cheers

    # ------------------------------------------------------------ counting
    def _ach_add(self, counter, n=1):
        self.ach_counters[counter] = int(self.ach_counters.get(counter, 0)) + int(n)

    def _ach_max(self, counter, v):
        if int(v) > int(self.ach_counters.get(counter, 0)):
            self.ach_counters[counter] = int(v)

    def _ach_daily(self, counter):
        """Count ``counter`` at most once per in-game day (saved in ach_counters)."""
        t = self.time
        seasons = (int(getattr(t, "year", 1)) - 1) * 4 + int(getattr(t, "season_idx", 0))
        day = seasons * DAYS_PER_SEASON + int(getattr(t, "day", 1))
        mark = "_day:" + counter
        if int(self.ach_counters.get(mark, 0)) == day:
            return
        self.ach_counters[mark] = day
        self._ach_add(counter)

    def _on_event_progress(self, event, data):
        if event not in _COUNTED:
            return
        if not self._ach_scanned:        # settle old progress quietly before this event
            self._ach_quiet_sync()
        g = data.get
        if event == "harvest":
            self._ach_add("harvest", max(1, int(g("qty", 1) or 1)))
        elif event == "fish_caught":
            self._ach_add("fish")
            try:
                from .. import fishing
                fd = fishing.FISH_DATA.get(g("fish"))
                if fd and fd[2] in getattr(fishing, "SPECIAL_TIERS", ("legendary", "leviathan")):
                    self._ach_add("legendary_fish")
            except Exception:
                pass
        elif event == "monster_killed":
            self._ach_add("kills")
            kind = str(g("kind") or "")
            if kind.startswith("mist_"):                # Mist City zombies
                self._ach_add("mist_kills")
            if g("boss") and kind:
                self._ach_add(f"boss:{kind}")
        elif event == "item_sold":
            self._ach_add("gold_earned", max(0, int(g("gold", 0) or 0)))
        elif event == "cooked":
            self._ach_add("cooked")
        elif event == "crafted":
            if g("what") in ("bomb", "mega_bomb"):
                self._ach_add("bombs")
            if g("machine"):                             # artisan goods (Farming)
                self._ach_add("artisan")
        elif event == "tool_upgraded":
            self._ach_max("tool_tier", int(g("tier", 0) or 0))
        elif event == "mine_depth":
            self._ach_max("depth", int(g("level", 0) or 0))
        elif event == "partner_gift":
            self._ach_add("partner_gifts")
            self._ach_daily("partner_gift_days")
        elif event == "emote":
            self._ach_add("emotes")
            self._ach_daily("emote_days")
        elif event == "bundle_done":
            self._ach_add("bundles")
            if g("name") == "Valley Restored":
                self._ach_max("valley_restored", 1)
        elif event == "festival_won":
            self._ach_add("festivals")
            name = str(g("name") or "")
            if name:
                self.ach_counters["fest:" + name] = 1
            self._ach_fest_sync()
        elif event == "mist_run_end":
            try:
                zi = int(g("zone_index", 0) or 0)
            except (TypeError, ValueError):
                zi = 0
            self._ach_max("mist_zone", zi)
            # bailing out on Main Street is not a finished run
            if g("reason") == "victory" or zi >= 1:
                self._ach_add("mist_runs")
        self._ach_check()

    def _on_area_enter_progress(self):
        self._ach_toast_flush()
        if self.world.current == AREA_MINE:
            self._ach_max("depth", getattr(self.world, "mine_level", 1))
            if self._ach_scanned:
                self._ach_check()

    def _ach_scan(self):
        """Things without an event: gems held, villager hearts, tool tiers."""
        for p in self.players:
            for gem in loot.GEMS:
                if gem not in self.ach_gems and p.inv.count(gem) > 0:
                    self.ach_gems.add(gem)
                    if self._ach_scanned:            # a brand-new kind of gem!
                        self.toast("New gem discovered!", loot.label(gem), gem,
                                   loot.color(gem), 3.0)
                        self.parts.sparkle(p.x, p.y - 20, n=14, color=loot.color(gem))
            tiers = getattr(p, "tool_tiers", None) or {}
            if tiers:
                self._ach_max("tool_tier", max(tiers.values()))
        self._ach_scanned = True
        self._ach_max("gems", len(self.ach_gems & set(loot.GEMS)))
        friend = getattr(self.world, "friend", None) or {}
        if friend:
            try:
                self._ach_max("friend_hearts", max(int(v) for v in friend.values()) // 50)
            except (TypeError, ValueError):
                pass
        if getattr(self, "story_restored", False):
            self._ach_max("valley_restored", 1)
        self._ach_fest_sync()
        try:                                         # deepest floor (old saves too)
            self._ach_max("depth", int(getattr(self.world, "mine_level", 0) or 0))
        except (TypeError, ValueError):
            pass

    def _ach_fest_sync(self):
        """Festival Star counts one star per festival. The Egg Hunt, Luau and Fair
        send festival_won; Lantern Night is cooperative (Story sends no winner), so
        a year in Story's ``story_lantern_nights`` -- the duo released lanterns
        together -- is its star. Old saves that already did it count too."""
        if getattr(self, "story_lantern_nights", None) and \
                "fest:lantern_night" not in self.ach_counters:
            self.ach_counters["fest:lantern_night"] = 1
        self._ach_max("festival_kinds",
                      sum(1 for k in self.ach_counters if k.startswith("fest:")))

    def _ach_quiet_sync(self):
        """First scan after a reset/load: goals already met by earlier play (old
        saves, achievements added later) are recorded WITHOUT gold, with one
        summary toast -- only new progress from now on pays out."""
        self._ach_scan()                 # sets _ach_scanned (gem toasts stay quiet)
        quiet = PR.newly_unlocked(self.ach_counters, self.ach_unlocked)
        if quiet:
            self.ach_unlocked.update(quiet)
            n = len(quiet)
            self.toast("Achievements recorded", f"{n} from earlier play - see Journal (J)",
                       _special_icon("@trophy"), _ACH_GOLD, 3.5)
            self.ui.log(f"{n} achievement{'s' if n != 1 else ''} from earlier play recorded "
                        "in the Journal (no reward).")
    def _on_update_progress(self, dt):
        self._ach_toast_tick(dt)
        self._ach_scan_t -= dt
        if self._ach_scan_t <= 0:
            self._ach_scan_t = 1.0
            if not self._ach_scanned:
                self._ach_quiet_sync()
            else:
                self._ach_scan()
                self._ach_check()

    # ------------------------------------------------------------ unlocking
    def _ach_check(self):
        if not self._ach_scanned:        # the quiet first scan has not run yet
            return
        for key in PR.newly_unlocked(self.ach_counters, self.ach_unlocked):
            self._ach_unlock(key)

    def _ach_unlock(self, key):
        if key in self.ach_unlocked or key not in PR.ACH:
            return False
        a = PR.ACH[key]
        self.ach_unlocked.add(key)
        self.gold += a["gold"]
        # the reward is paid now; the cheer (toast, chime, confetti) waits for a
        # quiet moment so it never piles onto the catch / harvest cards
        q = getattr(self, "_ach_toast_q", None)
        if q is None:
            q = self._ach_toast_q = []
        q.append([key, 0.0])
        del q[:-8]
        self._ach_toast_tick(0.0)        # a calm stack cheers right away
        self.emit("achievement", key=key)
        return True

    def _ach_toast_flush(self):
        """A warp is a natural beat: cheers still waiting show on arrival."""
        q = getattr(self, "_ach_toast_q", None)
        if q:
            while q:
                self._ach_celebrate(q.pop(0)[0])
            self._ach_toast_gap = 0.8

    def _ach_toast_tick(self, dt):
        """Show queued achievement cheers one at a time, once at most one other
        toast is still up (or after _ACH_TOAST_WAIT s at the latest)."""
        q = getattr(self, "_ach_toast_q", None)
        self._ach_toast_gap = max(0.0, getattr(self, "_ach_toast_gap", 0.0) - dt)
        if not q:
            return
        q[0][1] += dt
        if self._ach_toast_gap > 0:
            return
        busy = len(getattr(self, "toasts", None) or ())
        if busy <= 1 or q[0][1] >= _ACH_TOAST_WAIT:
            self._ach_toast_gap = 0.8
            self._ach_celebrate(q.pop(0)[0])

    def _on_client_update_progress(self, dt):
        self._ach_toast_tick(dt)         # cosmetic only (the host owns the counters)

    def _ach_celebrate(self, key):
        a = PR.ACH.get(key)
        if not a:
            return
        if getattr(self, "_ctx_view_saved", None) is not None:
            # inside the online partner's area: queue it for the host screen
            self.__dict__.setdefault("_ach_toast_q", []).append([key, 0.0])
            return
        f = getattr(self, "_net_toast", None)
        if f and getattr(self, "net_mode", None) == "host":
            f(f"Achievement unlocked! {a['title']} (+{a['gold']}g)")
        icon = a["icon"]
        self.toast("Achievement unlocked!", f"{a['title']}  (+{a['gold']}g)",
                   ach_icon(icon) if icon.startswith("@") else icon, _ACH_GOLD, 4.0)
        bank = getattr(self.audio, "sfx", None) or {}
        self.audio.play("achievement" if "achievement" in bank else "levelup")
        conf = getattr(self.parts, "confetti", None)
        for p in self.players:
            if conf:
                conf(p.x, p.y - 30, n=10)
            self.parts.sparkle(p.x, p.y - 16, n=10, color=_ACH_GOLD)
        p0 = self.players[0]
        self._popup(p0.x, p0.y - 44, f"+{a['gold']}g", _ACH_GOLD)
        # no ui.log line: the toast already says it, the Journal has the details

    # ------------------------------------------------------------ journal tab
    def _journal_tab_20_progress(self):
        return {"title": "Achievements", "draw": self._ach_draw_tab, "key": self._ach_tab_key}

    def _ach_cols(self, w):
        return max(3, min(7, int(w) // 168))

    def _ach_tab_key(self, key):
        from ..settings import P1_KEYS, P2_KEYS
        n = len(PR.ACH_KEYS)
        cols = getattr(self, "_ach_last_cols", 6)
        d = 0
        if key in (pygame.K_LEFT, P1_KEYS["left"], P2_KEYS["left"]):
            d = -1
        elif key in (pygame.K_RIGHT, P1_KEYS["right"], P2_KEYS["right"]):
            d = 1
        elif key in (pygame.K_UP, P1_KEYS["up"], P2_KEYS["up"]):
            d = -cols
        elif key in (pygame.K_DOWN, P1_KEYS["down"], P2_KEYS["down"]):
            d = cols
        if not d:
            return False
        self._ach_sel = max(0, min(n - 1, self._ach_sel + d))
        return True

    def _ach_text(self, text, font, color):
        cache = self.__dict__.setdefault("_ach_txt", {})
        key = (text, id(font), color)
        s = cache.get(key)
        if s is None:
            if len(cache) > 300:
                cache.clear()
            s = font.render(text, True, color)
            cache[key] = s
        return s

    def _ach_title_font(self, maxw):
        """The largest font in which EVERY achievement title fits ``maxw`` px, so
        the whole trophy grid uses one title size (cached per width)."""
        ui = self.ui
        key = (int(maxw), id(ui.small), id(ui.tiny))
        f = _TITLE_FONT.get(key)
        if f is None:
            cands = [ui.small]
            for sz in (13, 12):
                ff = _TITLE_SYS.get(sz)
                if ff is None:
                    try:
                        ff = pygame.font.SysFont("consolas", sz)
                    except Exception:
                        ff = None
                    _TITLE_SYS[sz] = ff
                if ff is not None:
                    cands.append(ff)
            cands.append(ui.tiny)
            f = cands[-1]
            for c in cands:
                if max(c.size(PR.ACH[k]["title"])[0] for k in PR.ACH_KEYS) <= maxw:
                    f = c
                    break
            _TITLE_FONT[key] = f
        return f

    def _ach_draw_tab(self, surf, rect):
        rect = pygame.Rect(rect)
        ui = self.ui
        keys = PR.ACH_KEYS
        n = len(keys)
        done = sum(1 for k in keys if k in self.ach_unlocked)
        pct = int(round(100 * done / max(1, n)))
        # header: completion + bar (one line, optically centred on hy)
        hy = rect.y + 13
        hr = K.blit_text(surf, K.font(20, True), f"Achievements   {done} / {n}   ({pct}%)",
                         K.INK, (rect.x + 8, hy), "left")
        bx, bw = hr.right + 24, max(80, rect.right - 8 - hr.right - 24)
        bar = pygame.Rect(bx, hy - 7, bw, 14)
        pygame.draw.rect(surf, K.WELL, bar, border_radius=7)
        if done:
            pygame.draw.rect(surf, K.GOLD_RIM, (bx, bar.y, max(14, int(bw * done / n)), bar.h),
                             border_radius=7)
        pygame.draw.rect(surf, K.WELL_LINE, bar, 2, border_radius=7)
        # trophy grid
        cols = self._ach_cols(rect.w)
        self._ach_last_cols = cols
        rows = int(math.ceil(n / cols))
        top = rect.y + 32
        foot = 40
        cw = rect.w / cols
        ch = max(56, min(96, (rect.h - (top - rect.y) - foot) / rows))
        sel = max(0, min(n - 1, getattr(self, "_ach_sel", 0)))
        t = pygame.time.get_ticks() / 1000.0
        last_row = (n - 1) // cols
        last_shift = (cols - (n - last_row * cols)) * cw / 2     # centre a short last row
        for i, key in enumerate(keys):
            a = PR.ACH[key]
            c, r = i % cols, i // cols
            x = rect.x + c * cw + (last_shift if r == last_row else 0)
            cell = pygame.Rect(int(x) + 3, int(top + r * ch) + 3, int(cw) - 6, int(ch) - 6)
            got = key in self.ach_unlocked
            if i == sel:                     # the keyboard cursor: the menus' gold band
                pulse = 0.5 + 0.5 * math.sin(t * 5)
                rim = tuple(int(a0 + (b0 - a0) * pulse) for a0, b0 in zip(K.GOLD_RIM, (240, 192, 104)))
                pygame.draw.rect(surf, K.HILITE, cell, border_radius=8)
                pygame.draw.rect(surf, rim, cell, 3, border_radius=8)
            elif got:
                pygame.draw.rect(surf, K.CREAM_HI, cell, border_radius=8)
                pygame.draw.rect(surf, K.GOLD_RIM, cell, 2, border_radius=8)
            else:
                K.well(surf, cell)
            # medallion
            mr = min(20, int(ch * 0.26))
            mx, my = cell.x + 8 + mr, cell.centery
            if got:
                glow = 0.5 + 0.5 * math.sin(t * 2 + i)
                pygame.draw.circle(surf, (190 + int(40 * glow), 140, 60), (mx, my), mr + 2)
                pygame.draw.circle(surf, _ACH_GOLD, (mx, my), mr)
                pygame.draw.circle(surf, (255, 240, 180), (mx, my), mr - 3, 1)
                ic = ach_icon(a["icon"])
            else:
                pygame.draw.circle(surf, (230, 212, 182), (mx, my), mr)
                pygame.draw.circle(surf, K.WELL_LINE, (mx, my), mr, 2)
                ic = _silhouette(a["icon"])
            surf.blit(ic, (mx - ic.get_width() // 2, my - ic.get_height() // 2))
            # title (one font for every card, see _ach_title_font) + progress,
            # the three lines centred as a block in the cell
            tx = mx + mr + 8
            maxw = cell.right - tx - 8
            title = a["title"]
            tcol = K.INK if got else K.INK_SOFT
            tfont = self._ach_title_font(maxw)
            if tfont.size(title)[0] > maxw:                 # last resort only
                title = K.ellipsize(tfont, title, maxw)
            cur, tgt = PR.ach_progress(key, self.ach_counters)
            if got:
                cur = tgt
            lab = "Done!" if got else (f"{cur:,} / {tgt:,}")
            lf = K.font(12, True)
            cap_t, cap_l = tfont.metrics("H")[0][3], lf.metrics("H")[0][3]
            block = cap_t + 7 + 7 + 7 + cap_l
            y0 = cell.centery - block // 2
            K.blit_text(surf, tfont, title, tcol, (tx, y0 + cap_t // 2), "left")
            py = y0 + cap_t + 7
            pw = maxw
            pygame.draw.rect(surf, (226, 206, 176), (tx, py, pw, 7), border_radius=3)
            if cur:
                pygame.draw.rect(surf, K.GOLD_RIM if got else K.LEAF,
                                 (tx, py, max(6, int(pw * cur / tgt)), 7), border_radius=3)
            K.blit_text(surf, lf, lab, K.GOLD_TXT if got else K.INK_SOFT,
                        (tx, py + 7 + 7 + cap_l // 2), "left")
        # footer: details of the selected achievement
        a = PR.ACH[keys[sel]]
        got = keys[sel] in self.ach_unlocked
        fy = rect.bottom - foot // 2
        hint = "W A S D / Up Down: browse"
        hf = K.font(12, True)
        hw = hf.size(hint)[0]
        line = f"{a['title']}: {a['desc']}   -   reward {a['gold']}g" + ("   (unlocked)" if got else "")
        ff = K.font(15, True)
        K.blit_text(surf, ff, K.ellipsize(ff, line, rect.w - hw - 40),
                    K.GOLD_TXT if got else K.INK, (rect.x + 8, fy), "left")
        K.blit_text(surf, hf, hint, K.INK_SOFT, (rect.right - 8, fy), "right")
