"""Settings + game-state persistence (collect / apply / save).

Owner: "Core & Save/Load" chat.
Related modules: savegame.py (disk I/O, corruption guard).
IMPORTANT: when any other system adds new persistent state, both
``_collect_save`` and ``_apply_save`` must be updated together, and
``_apply_save`` must tolerate older saves that lack the new keys.
PREFERRED since 2026-09: don't edit this file -- define ``_on_save_<domain>()``
(returns a dict with uniquely-named keys) and ``_on_load_<domain>(d)`` (reads
them back with ``d.get(key, default)``) in your own mixin; see systems/hooks.py.
"""
from ..settings import P1_KEYS, P2_KEYS, AREA_FARM
from .. import savegame, quests, weather, animals
from ..crops import Crop, CROPS
from .. import furniture as F
from ..animals import Animal


class SaveMixin:
    """Round-trips settings and the full game state to/from disk."""

    # ---------- settings persistence ----------
    def _settings_dict(self):
        return {"master": self.audio.master, "sfx": self.audio.sfx_vol,
                "music": self.audio.music_vol, "fullscreen": self.fullscreen,
                "keys": {"p1": dict(P1_KEYS), "p2": dict(P2_KEYS)}}

    def _apply_settings(self, s):
        self.audio.set_master(s.get("master", self.audio.master))
        self.audio.set_sfx(s.get("sfx", self.audio.sfx_vol))
        self.audio.set_music(s.get("music", self.audio.music_vol))
        if s.get("fullscreen") and not self.fullscreen:
            self.toggle_fullscreen()
        keys = s.get("keys", {})
        from ..settings import DEFAULT_P1_KEYS, DEFAULT_P2_KEYS, JOURNAL_KEY, BUILD_KEY
        import pygame as _pg
        # global single-purpose hotkeys (same set menu._reserved_keys refuses):
        # a settings.json from before that guard may still bind them to a player
        # action, which would make Build / Inventory / Journal unreachable
        reserved = {_pg.K_i, _pg.K_F11, _pg.K_ESCAPE, JOURNAL_KEY, BUILD_KEY}
        reset_who = []
        for dst, src, dflt, who in ((P1_KEYS, keys.get("p1", {}), DEFAULT_P1_KEYS, "P1"),
                                    (P2_KEYS, keys.get("p2", {}), DEFAULT_P2_KEYS, "P2")):
            for act, code in src.items():
                if act in dst and isinstance(code, int) and not isinstance(code, bool):
                    if code in reserved and dflt.get(act) != code:
                        reset_who.append((dst, dflt, who))
                        try:
                            nm = _pg.key.name(code).upper() or str(code)
                            self._settings_notes = getattr(self, "_settings_notes", [])
                            self._settings_notes.append(
                                f"Controls: {nm} is reserved - {who} {act} reset to "
                                f"{_pg.key.name(dflt.get(act, 0)).upper()}")
                        except Exception:
                            pass
                        dst[act] = dflt.get(act, dst[act])
                        continue
                    dst[act] = code
        # a reset-to-default may land on a key another action already uses
        # (e.g. action->SPACE while emote=SPACE): that silently kills a binding.
        # Fall back to that player's whole default map (collision-free), and to
        # both defaults if the partner's custom keys still clash.
        def _clash():
            codes = list(P1_KEYS.values()) + list(P2_KEYS.values())
            return len(codes) != len(set(codes))
        if reset_who and _clash():
            seen = []
            for dst, dflt, who in reset_who:
                if who not in seen:
                    seen.append(who)
                    dst.update(dflt)
            if _clash():
                P1_KEYS.update(DEFAULT_P1_KEYS)
                P2_KEYS.update(DEFAULT_P2_KEYS)
                seen = ["P1", "P2"]
            try:
                self._settings_notes = getattr(self, "_settings_notes", [])
                self._settings_notes.append(
                    "Controls: a reserved key clashed - " + " & ".join(seen)
                    + " keys reset to defaults")
            except Exception:
                pass

    def save_settings(self):
        savegame.save_settings(self._settings_dict())

    # ---------- game-state persistence ----------
    def _collect_save(self):
        w = self.world
        def kstr(k):
            return f"{k[0]}|{k[1]}|{k[2]}"
        players = []
        for p in self.players:
            players.append({
                "x": p.x, "y": p.y, "energy": p.energy, "health": p.health,
                "name": p.name, "look": dict(p.appearance),
                "skills": p.skills.to_dict(), "tiers": dict(p.tool_tiers),
                "inv": {"items": dict(p.inv.items), "order": list(p.inv.item_order),
                        "selected": p.inv.selected,
                        "hotbar": [list(e) for e in p.inv.hotbar_order]}})
        crops = [{"k": kstr(k), "name": c.name, "age": c.age,
                  "watered": c.watered, "dead": c.dead} for k, c in w.crops.items()]
        out = {
            "gold": self.gold,
            "time": {"minutes": self.time.minutes, "day": self.time.day,
                     "season_idx": self.time.season_idx, "year": self.time.year},
            "mine_level": w.mine_level, "current": w.current,
            "players": players,
            "tilled": sorted(kstr(k) for k in w.tilled),     # §0.3: sorted lists
            "tilled_idle": {kstr(k): v for k, v in sorted(self.tilled_idle.items(), key=lambda kv: kstr(kv[0]))},
            "watered": sorted(kstr(k) for k in w.watered),
            "crops": crops,
            "furniture": [pl.to_dict() for pl in w.home_furniture],
            "home_wall_idx": w.home_wall_idx, "home_floor_idx": w.home_floor_idx,
            "friend": dict(w.friend),
            "active_quests": [quests.to_dict(q) for q in self.active_quests],
            "quest_offers": [quests.to_dict(q) for q in self.quest_offers],
            "npc_gifted": sorted(self.npc_gifted_today, key=str),
            "weather": self.weather,
            "animals": [a.to_dict() for a in self.animals],
            "farm_objects": [[gx, gy, k] for (gx, gy), k in w.farm_objects.items()],
            "claimed_festivals": sorted(self.claimed_festivals, key=str),
            **self._gather_hooks("_on_save_"),     # domain state (systems/hooks.py)
        }
        self._keep_unloaded_domain_keys(out)
        return out

    def _keep_unloaded_domain_keys(self, out):
        """A domain whose ``_on_load_*`` hook failed this session is running on
        reset defaults. Write the values we originally LOADED for that domain's
        keys back instead, so one hook bug can never wipe saved progress."""
        raw = getattr(self, "_load_raw", None)
        failed = getattr(self, "_load_failed_hooks", None)
        if not raw or not failed:
            return
        for name in failed:
            f = getattr(self, "_on_save_" + name[len("_on_load_"):], None)
            keys = ()
            if f is not None:
                try:
                    keys = tuple((f() or {}).keys())
                except Exception:
                    keys = ()
            for k in keys:
                if k in raw:
                    out[k] = raw[k]
        for k, v in raw.items():            # keys no hook produced at all
            if k not in out:
                out[k] = v

    def _apply_save(self, d, respawn=True):
        w = self.world
        self.gold = d.get("gold", self.gold)
        t = d.get("time", {})
        self.time.minutes = t.get("minutes", self.time.minutes)
        self.time.day = t.get("day", self.time.day)
        self.time.season_idx = t.get("season_idx", self.time.season_idx)
        self.time.year = t.get("year", self.time.year)
        lvl = d.get("mine_level", 1)
        if lvl != 1:
            w.regen_mine(lvl)

        def parse(s):
            a, gx, gy = s.split("|")
            return (a, int(gx), int(gy))

        w.tilled = set(parse(s) for s in d.get("tilled", []))
        # idle-tilled counters; .get(...,{}) tolerates older saves without the key
        self.tilled_idle = {parse(s): v for s, v in d.get("tilled_idle", {}).items()}
        w.watered = set(parse(s) for s in d.get("watered", []))
        w.crops = {}
        for cd in d.get("crops", []):
            if cd.get("name") not in CROPS:        # skip crops a newer build renamed/removed
                continue
            try:
                c = Crop(cd["name"])
                c.age = cd.get("age", 0)
                c.watered = cd.get("watered", False)
                c.dead = cd.get("dead", False)
                w.crops[parse(cd["k"])] = c
            except Exception:
                pass
        w.home_furniture = []
        for fd in d.get("furniture", []):
            if fd.get("kind") not in F.CAT:        # skip unknown furniture kinds
                continue
            args = {k: fd[k] for k in ("kind", "gx", "gy", "rot", "ci", "level",
                                       "store", "ox", "oy", "on", "data") if k in fd}
            try:
                w.home_furniture.append(F.Placed(**args))
            except Exception:
                pass
        # migration: old saves had a FIXED bed at (2,2) that was never in the
        # furniture list -- give them the same bed as a movable piece
        if not any(pl.kind == "bed" for pl in w.home_furniture):
            w.home_furniture.append(F.Placed("bed", 2, 2, 0, 9))
        w.home_wall_idx = d.get("home_wall_idx", 0)
        w.home_floor_idx = d.get("home_floor_idx", 0)
        w.friend = dict(d.get("friend", {}))
        self.active_quests = [dict(q) for q in d.get("active_quests", [])]
        # an EMPTY board is legit (all of today's offers taken) -- only a save
        # that lacks the key gets a fresh roll; on_new_day refills each morning
        if "quest_offers" in d:
            self.quest_offers = [dict(q) for q in (d.get("quest_offers") or [])]
        else:
            self.quest_offers = [quests.generate() for _ in range(3)]
        self.npc_gifted_today = set(d.get("npc_gifted", []))
        self.weather = d.get("weather", weather.pick(self.time.season))
        self.animals = []
        for a in d.get("animals", []):
            if a.get("kind") not in animals.ANIMALS:   # skip unknown livestock kinds
                continue
            self.animals.append(Animal(a["kind"], a.get("gx", 34), a.get("gy", 16),
                                       a.get("friend", 0), a.get("has_produce", True)))
        w.farm_objects = {(o[0], o[1]): o[2] for o in d.get("farm_objects", [])}
        self.claimed_festivals = set(d.get("claimed_festivals", []))
        w.refresh_home_solids()
        for i, pd in enumerate(d.get("players", [])[:2]):
            p = self.players[i]
            if "look" in pd:
                self.look[i] = dict(pd["look"])
                p.set_appearance(pd["look"], pd.get("name"))
            p.x, p.y = pd.get("x", p.x), pd.get("y", p.y)
            p.energy = pd.get("energy", p.energy)
            p.health = pd.get("health", p.health)
            p.skills.load(pd.get("skills", {}))
            for t, tier in pd.get("tiers", {}).items():
                if t in p.tool_tiers:
                    p.tool_tiers[t] = int(tier)
            iv = pd.get("inv", {})
            p.inv.items = dict(iv.get("items", {}))
            p.inv.item_order = list(iv.get("order", list(p.inv.items.keys())))
            p.inv.selected = iv.get("selected", 0)
            # restore the player's hotbar arrangement; old saves without the key
            # keep the default order. reconcile() heals either against contents.
            saved_hot = iv.get("hotbar")
            if saved_hot:
                p.inv.hotbar_order = [tuple(e) for e in saved_hot if len(e) == 2]
            p.inv.reconcile()
        w.current = d.get("current", AREA_FARM)
        # domain state; must tolerate old saves. A failing hook is remembered so
        # _collect_save keeps that domain's ORIGINAL keys (see below).
        failed = self._run_hooks_tracked("_on_load_", d)
        if not getattr(self, "_net_applying_world", False):
            self._load_failed_hooks = failed
            self._load_raw = d if failed else None
            if failed:
                self._report_failed_load_hooks(failed)
        if respawn:
            self._spawn_area_entities()
        self._update_camera(self.world.area)

    def _report_failed_load_hooks(self, failed):
        """Keep a copy of the save, note why, and tell the player once."""
        try:
            savegame.preserve_corrupt()
            savegame.log_error("load hooks failed: " + ", ".join(failed))
        except Exception:
            pass
        # a domain hook we cannot map back to its save keys: lock saving (the
        # same guard Core uses when the whole save fails to load)
        if any(getattr(self, "_on_save_" + n[len("_on_load_"):], None) is None
               for n in failed):
            self.load_failed = True
        t = getattr(self, "toast", None)
        try:
            if t:
                t("Some progress couldn't load", "It is kept safe - your save won't lose it.",
                  color=(235, 170, 110), seconds=6.0)
            else:
                self.ui.log("Some progress couldn't load - it is kept safe in your save.")
        except Exception:
            pass

    def _save(self):
        # Don't save if a save existed but failed to load this session -- writing
        # now would overwrite the recoverable file with a blank/reset state.
        # Never save while (or right after) playing as a LAN client: the world in
        # memory is the HOST's farm, and it must never replace the joiner's save.
        if (getattr(self, "net_mode", None) == "client"
                or getattr(self, "_net_client_session", False)):
            return
        if self.started and not self.load_failed:
            try:
                unparked = getattr(self, "_unparked", None)
                if unparked:
                    with unparked():                 # never save a parked (off-map) farmer
                        data = self._collect_save()
                    if self.independent():           # the host's own area is "current"
                        data["current"] = self.view_area()
                else:
                    data = self._collect_save()
                savegame.save_game(data)
            except Exception:
                # a save error must never crash the game on exit -- but leave a
                # trace next to the save so a broken hook/state can be found
                try:
                    import traceback
                    savegame.log_error(traceback.format_exc())
                except Exception:
                    pass
