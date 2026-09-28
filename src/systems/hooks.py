"""Domain hook bus -- lets every domain plug into the core lifecycle WITHOUT
editing the shared seam files (game.py / save_system / actions_system /
render_system).

Owner: Core. Everyone else only *defines* hook methods in their own mixin.

HOW IT WORKS
------------
Any method on ``Game`` (i.e. on any mixin) whose name starts with one of the
prefixes below is discovered automatically and called at that point of the
lifecycle. Hooks of the same prefix run in **name order**, so a numeric infix
sets priority (``_interact_early_10_x`` runs before ``_interact_early_50_y``).
Name your hooks ``<prefix><domain>_<what>`` so they never collide.

  prefix                     signature                  called from
  -------------------------  -------------------------  -----------------------------------
  _on_reset_                 ()                         end of Game.reset() (init YOUR state)
  _on_area_enter_            ()                         end of _spawn_area_entities (every warp)
  _on_new_day_               ()                         end of on_new_day (after crops/weather)
  _on_update_                (dt)                       Game.update, state "play", after mobs --
                                                        ONCE per frame, in the view area (global
                                                        timers, HUD, weather, achievements)
  _on_area_update_           (dt)                       once per OCCUPIED area per frame (online
                                                        each farmer can stand in a different area;
                                                        see systems/areactx_system.py): monsters,
                                                        critters, hazards, per-area fx. Loop over
                                                        self.players_here() for per-player work.
  _on_client_update_         (dt)                       LAN CLIENT only, every frame (the client
                                                        never runs update): cosmetic ticks such
                                                        as critter animation. Never mutate saved
                                                        state here -- the host owns it. Core
                                                        already ages UI toasts/cards, shake,
                                                        popups and runs client-local screens.
  _on_keydown_               (key) -> bool              on_keydown in "play"; True = consumed
  _interact_early_           (idx, p) -> bool           player_action, BEFORE NPC/shop/bed...
  _interact_late_            (idx, p) -> bool           player_action, just before use_tool
  _on_tool_                  (idx, p, tool, gx, gy)->bool   use_tool before default tool logic
  _on_save_                  () -> dict                 merged into the save dict (unique keys!)
  _on_load_                  (d)                        end of _apply_save; use d.get(k, default)
                                                        (if one raises, Core writes that domain's
                                                        ORIGINAL loaded keys back on save, so a
                                                        load bug never wipes progress)
  _draw_world_               ()                         world-space pass after entities
  _draw_sky_                 ()                         after night lighting, BEFORE the HUD
                                                        (screen-wide effects: lightning flash)
  _draw_hud_                 ()                         after the HUD (screen space)
  _on_event_                 (event, data)              every self.emit(event, **data)

CUSTOM STATES (new full-screen menus / overlays) -- for ``self.state = "<name>"``:
  _state_event_<name>(e)     pygame event routing while in that state
  _state_update_<name>(dt)   per-frame update while in that state
  _state_draw_<name>()       drawn AFTER the world+HUD (overlay); fill the
                             screen yourself for a full-screen page
Return to play with ``self.state = "play"``. Key-repeat is enabled for them.

EVENTS (``self.emit(name, **data)``) -- the shared vocabulary; add new ones freely:
  harvest(p, item, qty)       fish_caught(p, fish, size?)   monster_killed(p, kind, boss)
  item_sold(p, item, qty, gold)  gift_given(p, npc, item)   cooked(p, food)
  crafted(p, what)            mine_depth(level)             day_started(day, season, year)
  foraged(p, item)            quest_done(p, quest)          warp(area)
  tool_upgraded(p, tool, tier)  animal_product(p, item)     emote(p, kind)
  partner_gift(p, to, item)   rock_broken(p, area)          tree_chopped(p, area)
  crop_planted(p, crop)       animal_petted(p, animal)      love_boost(players)
  weather_changed(weather, tomorrow)   day_report(day, stats)
  (subscribers must read ``data.get(...)`` defensively -- keys may be missing)

CORE HELPERS (2026-09) -- guard with getattr, they may be absent in old builds:
  self.parts.star_burst(x, y, color, n) / coin_burst(x, y, n) / ring(x, y, color, radius)
            / petal(x, y, color) / poof(x, y, color, n) / rain_splash(x, y)
  self.audio.play(name): + emote, gift, thunder, achievement, coin, forage, unlock,
            page, bell, crit, boss_roar, craft, splash_big, error
  self.weather_tomorrow / self.forecast_text()   pre-rolled forecast (WeatherMixin)
  self.stats_life / self.stats_today             co-op counters (CoopMixin)
  state "day_report"                             shown after sleeping (the LAN host ships
                                                 a read-only copy to the client, 'dr' msg)
  LAN (fix round 2): self.net_leave()            menu "Leave online game" (client/host)
            self._net_send_fx(kind, **data)      host -> client one-shot effect ('boom')
            snapshot 'hs' (host state), 'BM' (lit bombs [x, y, t, kind, owner]); Combat
            may override _cb_net_pack_bombs / _cb_net_unpack_bombs / _cb_net_boom_fx
  self._bed_confirmed(idx, p, facing)            two-press guard before sleeping

ERRORS: a hook that raises must not crash a play session. In normal play the
error is written once per hook to ``hook_errors.txt`` next to the save and the
game carries on. With ``HD_STRICT_HOOKS=1`` (the smoke test sets it) hook
errors are re-raised so tests fail loudly.
"""
import os
import traceback

_STRICT = os.environ.get("HD_STRICT_HOOKS") == "1"
_CACHE = {}
_REPORTED = set()


def _log_hook_error(name):
    if name in _REPORTED:
        return
    _REPORTED.add(name)
    try:
        from .. import savegame
        path = os.path.join(os.path.dirname(savegame.SAVE_PATH), "hook_errors.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"--- {name}\n{traceback.format_exc()}\n")
    except Exception:
        pass


class HooksMixin:
    """Discovery + dispatch of the per-domain hook methods described above."""

    def _hook_names(self, prefix):
        cls = type(self)
        key = (cls, prefix)
        names = _CACHE.get(key)
        if names is None:
            names = sorted(n for n in dir(cls)
                           if n.startswith(prefix) and callable(getattr(cls, n, None)))
            _CACHE[key] = names
        return names

    def _call_hook(self, name, *a):
        try:
            return getattr(self, name)(*a)
        except Exception:
            if _STRICT:
                raise
            _log_hook_error(name)
            return None

    def _run_hooks(self, prefix, *a):
        """Call every hook of ``prefix``; results are ignored."""
        for n in self._hook_names(prefix):
            self._call_hook(n, *a)

    def _run_hooks_tracked(self, prefix, *a):
        """Like _run_hooks, but returns the names of hooks that raised (the
        error is still logged; strict mode still re-raises)."""
        failed = []
        for n in self._hook_names(prefix):
            try:
                getattr(self, n)(*a)
            except Exception:
                if _STRICT:
                    raise
                _log_hook_error(n)
                failed.append(n)
        return failed

    def _first_hook(self, prefix, *a):
        """Call hooks in order until one returns truthy (it 'consumed' the input)."""
        for n in self._hook_names(prefix):
            if self._call_hook(n, *a):
                return True
        return False

    def _gather_hooks(self, prefix, *a):
        """Merge the dicts returned by every hook of ``prefix``."""
        out = {}
        for n in self._hook_names(prefix):
            r = self._call_hook(n, *a)
            if isinstance(r, dict):
                out.update(r)
        return out

    def emit(self, event, **data):
        """Broadcast a gameplay event to every ``_on_event_*`` hook."""
        for n in self._hook_names("_on_event_"):
            self._call_hook(n, event, data)

    # ---- custom states ----
    def _custom_state(self, what):
        """The bound ``_state_<what>_<state>`` method for the current state, if any."""
        st = getattr(self, "state", None)
        if not st:
            return None
        return getattr(self, f"_state_{what}_{st}", None)

    def _run_state(self, what, *a):
        """Run the current custom state's ``what`` handler. Returns True if the
        state has one. A crashing custom screen drops back to play (logged)."""
        f = self._custom_state(what)
        if f is None:
            return False
        try:
            f(*a)
        except Exception:
            if _STRICT:
                raise
            _log_hook_error(f"_state_{what}_{self.state}")
            self.state = "play"
        return True
