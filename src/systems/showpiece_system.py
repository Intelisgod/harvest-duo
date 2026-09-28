"""Showpiece furniture: the Art Studio easel + gallery paintings, the telescope
and the arcade cabinet.

Owner: Showpieces (2026-09-28). Plugs in through the hook bus; the seam edits
are one delegation line each at the top of ``HomeMixin._home_interact`` /
``_home_client_interact`` (-> ``_show_interact`` / ``_show_client_interact``).

* Easel -> ``studio.ArtStudio`` (state "studio"): paint 24x24 pixel art. The
  art is kept in the easel's ``Placed.data["art"]`` (compact string) and the
  room's easel shows it on its canvas (``isofurn.PIECE_ART``). "Hang on the
  wall" adds it to the farm's gallery (``art_gallery``, saved) and hangs it on
  the first free Painting frame. Using a Painting cycles which gallery piece
  it shows (``Placed.data["gid"]``; wallart draws it via ``wallart.ART_FOR``).
* Telescope -> ``stargaze.Stargazer`` (state "stargaze"): constellations to
  discover (``stars_found``, saved) and one shooting-star wish per night
  (``star_wish_day`` / ``star_wish_pending``): the next morning both farmers
  get a Luck buff for the whole day.
* Arcade cabinet (a TOGGLE piece) -> ``heartpong.HeartPong`` (state "arcade");
  results land in ``pong_stats`` (saved).

LAN: the client opens every screen locally; its results travel as menu ops
  {"m": "art",   "op": "save",  "gx", "gy", "art"}       the easel's canvas
  {"m": "art",   "op": "hang",  "art"}                     -> gallery (+ a frame)
  {"m": "art",   "op": "frame", "gx", "gy", "gid"}         a Painting's picture (SET)
  {"m": "stars", "op": "found", "c"}  /  {"m": "stars", "op": "wish"}
  {"m": "pong",  "op": "result", "cpu", "win", "rally"}
and the 1 s world resync (the save dict: Placed.data + our keys) brings the
host's truth back. The host never opens a screen for the remote farmer.
"""
from ..settings import (TILE, MAX_ENERGY, AREA_HOME, SECONDS_PER_STEP, DAY_START_MIN,
                        DAY_END_MIN)
from .. import furniture as F

GALLERY_MAX = 36
WISH_LUCK = 0.25
DAY_SECS = (DAY_END_MIN - DAY_START_MIN) / 10 * SECONDS_PER_STEP     # one whole game day
_ART_COL = (246, 200, 150)
_STAR_COL = (190, 200, 255)
_PONG_COL = (255, 160, 200)
POKES = {"easel", "painting", "telescope", "arcade_cabinet"}


class ShowpieceMixin:
    """Easel studio + gallery, telescope stargazing, Heart Pong arcade."""

    # ------------------------------------------------------------ lifecycle
    def _on_reset_showpieces(self):
        self.studio = None
        self.stargazer = None
        self.pong = None
        self.art_gallery = []            # [{"id", "art", "title", "by"}], oldest first
        self.stars_found = set()
        self.star_wish_day = None        # [year, season_idx, day] of the last wish
        self.star_wish_pending = False   # a wish waiting for the next morning
        self.pong_stats = self._pong_blank()
        try:
            from .. import isofurn, wallart
            isofurn.PIECE_ART = self._show_piece_art
            wallart.ART_FOR = self._show_wall_art
        except Exception:
            pass

    @staticmethod
    def _pong_blank():
        return {"best_rally": 0, "cpu_w": 0, "cpu_l": 0, "duel": [0, 0], "games": 0}

    def _on_area_enter_showpieces(self):
        if self.world.current == AREA_HOME:
            self._show_build_sfx()

    def _on_save_showpieces(self):
        return {"art_gallery": [dict(e) for e in self.art_gallery],
                "stars_found": sorted(self.stars_found),
                "star_wish_day": list(self.star_wish_day) if self.star_wish_day else None,
                "star_wish_pending": bool(self.star_wish_pending),
                "pong_stats": {k: (list(v) if isinstance(v, list) else v)
                               for k, v in self.pong_stats.items()}}

    def _on_load_showpieces(self, d):
        from .. import studio as S
        from .. import stargaze as SG
        gal = []
        seen = set()
        for e in d.get("art_gallery") or []:
            if not isinstance(e, dict):
                continue
            try:
                gid = int(e.get("id"))
            except (TypeError, ValueError):
                continue
            art = e.get("art")
            if gid in seen or not S.valid(art):
                continue
            seen.add(gid)
            gal.append({"id": gid, "art": art, "title": str(e.get("title", ""))[:40],
                        "by": str(e.get("by", ""))[:24]})
        self.art_gallery = gal
        found = {c for c in (d.get("stars_found") or []) if c in SG.BY_ID}
        if getattr(self, "net_mode", None) == "client":
            found |= self.stars_found          # our own find may still be on its way
        self.stars_found = found
        wd = d.get("star_wish_day")
        try:
            self.star_wish_day = [int(x) for x in wd] if isinstance(wd, (list, tuple)) \
                and len(wd) == 3 else None
        except (TypeError, ValueError):
            self.star_wish_day = None
        self.star_wish_pending = bool(d.get("star_wish_pending", False))
        st = self._pong_blank()
        raw = d.get("pong_stats")
        if isinstance(raw, dict):
            for k in ("best_rally", "cpu_w", "cpu_l", "games"):
                try:
                    st[k] = max(0, int(raw.get(k, 0)))
                except (TypeError, ValueError):
                    pass
            du = raw.get("duel")
            if isinstance(du, (list, tuple)) and len(du) == 2:
                try:
                    st["duel"] = [max(0, int(du[0])), max(0, int(du[1]))]
                except (TypeError, ValueError):
                    pass
        self.pong_stats = st

    def _on_new_day_showpieces(self):
        if not self.star_wish_pending:
            return
        self.star_wish_pending = False
        for p in self.players:
            if hasattr(p, "add_buff"):
                p.add_buff("luck", DAY_SECS, WISH_LUCK, "Wish")
        self.ui.log("Last night's wish came true: a lucky day for you both! (+Luck)")
        self._show_toast("Your wish came true", "A lucky day for you both! (+Luck all day)",
                         color=_STAR_COL)
        if getattr(self, "net_mode", None) == "host":
            self._net_toast("Last night's wish came true: a lucky day! (+Luck)")

    # ------------------------------------------------------------ helpers
    def _show_today(self):
        t = self.time
        return [int(t.year), int(t.season_idx), int(t.day)]

    def _show_toast(self, title, body, icon=None, color=_ART_COL, seconds=3.5):
        t = getattr(self, "toast", None)
        if t:
            try:
                t(title, body, icon=icon, color=color, seconds=seconds)
            except Exception:
                pass

    def _show_sfx(self, name, fallback):
        a = getattr(self.audio, "_real", None) or self.audio
        ready = getattr(a, "sfx", {}).get(name) is not None
        self.audio.play(name if ready else fallback)

    def _show_energy(self, idx, fr, what=None):
        """The usual furniture pick-me-up (FURN_ACTION) for opening a piece."""
        from .actions_system import FURN_ACTION
        p = self.players[idx]
        verb, gain = FURN_ACTION.get(fr.kind, ("enjoy it", 4))
        gain = int(gain * getattr(fr, "level", 1))
        p.energy = min(MAX_ENERGY, p.energy + gain)
        self.ui.log(f"{p.name}: {what or verb} (+{gain} energy)")

    def _show_piece_at(self, kind, gx, gy):
        return next((q for q in self.world.home_furniture
                     if q.kind == kind and (q.gx, q.gy) == (gx, gy)), None)

    def _gallery_get(self, gid):
        if gid is None:
            return None
        return next((e for e in self.art_gallery if e["id"] == gid), None)

    def _paintings(self):
        return [q for q in self.world.home_furniture if q.kind == "painting"]

    @staticmethod
    def _art_icon(art, size=28):
        import pygame
        from .. import studio as S
        s = S.art_surface(art)
        if s is None:
            return None
        out = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(out, (158, 112, 64), out.get_rect(), border_radius=3)
        inner = size - 6
        out.blit(pygame.transform.scale(s, (inner, inner)), (3, 3))
        return out

    # ------------------------------------------------------------ interact
    def _show_interact(self, idx, p, fr, remote=False):
        """HomeMixin._home_interact delegates here first. True = handled."""
        k = fr.kind
        if k not in POKES:
            return False
        if k == "painting":
            return self._paint_cycle(p, fr)
        if remote:
            return False                        # the client opens its own screen
        if k == "easel":
            self._studio_open(idx, fr)
        elif k == "telescope":
            self._stars_open(idx, fr)
        elif k == "arcade_cabinet":
            self._pong_open(idx, fr)
        return True

    def _show_client_interact(self, p, fr):
        """LAN client: HomeMixin._home_client_interact delegates here first."""
        k = fr.kind
        if k not in POKES:
            return False
        if k == "painting":
            return self._paint_cycle(p, fr, client=True)
        if k == "easel":
            self._studio_open(1, fr, client=True)
        elif k == "telescope":
            self._stars_open(1, fr, client=True)
        elif k == "arcade_cabinet":
            self._pong_open(1, fr, client=True)
        return True

    # ------------------------------------------------------------ studio
    def _studio_open(self, idx, fr, client=False):
        from .. import studio as S
        if client:
            self._net_send_menu({"m": "furn", "kind": fr.kind, "gx": fr.gx, "gy": fr.gy})
        else:
            self._show_energy(idx, fr, "sets up at the easel")
        self.studio = S.ArtStudio(self, idx, fr, client=client)
        self.state = "studio"
        self.audio.play("ui_select")

    def _art_store(self, easel, art, by):
        from .. import studio as S
        if easel is None:
            return
        px = S.decode(art)
        if px is None:
            return
        if S.is_blank(px):
            easel.data.pop("art", None)
            easel.data.pop("by", None)
        else:
            easel.data["art"] = art
            easel.data["by"] = str(by)[:24]

    def _studio_save(self, scr):
        from .. import studio as S
        art = S.encode(scr.px)
        p = self.players[scr.pidx]
        self._art_store(scr.easel, art, p.name)
        if scr.client:
            e = scr.easel
            self._net_send_menu({"m": "art", "op": "save", "gx": e.gx, "gy": e.gy, "art": art})
        self._show_sfx("studio_save", "ui_select")
        if S.is_blank(scr.px):
            return "A fresh canvas waits on the easel"
        self.emit("art_saved", p=p)
        return "Saved! The easel shows your painting"

    def _studio_hang(self, scr):
        from .. import studio as S
        self._studio_save(scr)
        art = S.encode(scr.px)
        p = self.players[scr.pidx]
        if scr.client:
            self._net_send_menu({"m": "art", "op": "hang", "art": art})
            self._show_sfx("studio_hang", "coin")
            return "Sent to the gallery - it goes up on a free frame!"
        entry, frame, new = self._gallery_add(art, p.name)
        self._show_sfx("studio_hang", "coin")
        self.emit("art_hung", p=p)
        return self._hang_msg(entry, frame, new)

    def _hang_msg(self, entry, frame, new):
        if frame is not None:
            self._show_toast("Hung on the wall!", f"\"{entry['title']}\" by {entry['by']}",
                             icon=self._art_icon(entry["art"]))
            return "Hung on the wall! Use a Painting to change what it shows"
        if not new:
            return "It's already in the gallery - use a Painting to show it"
        return "Added to the gallery! Use a Painting frame to show it"

    def _gallery_add(self, art, by):
        """Add ``art`` to the gallery (once) and hang it on the first Painting
        showing no gallery piece. Returns (entry, frame or None, is_new)."""
        entry = next((e for e in self.art_gallery if e["art"] == art), None)
        new = entry is None
        if new:
            nid = max([e["id"] for e in self.art_gallery], default=0) + 1
            t = self.time
            entry = {"id": nid, "art": art, "title": f"{t.season} {t.day}, year {t.year}",
                     "by": str(by)[:24]}
            self.art_gallery.append(entry)
            self._gallery_trim()
        frame = None
        shown = {q.data.get("gid") for q in self._paintings()}
        if entry["id"] not in shown:
            frame = next((q for q in self._paintings()
                          if self._gallery_get(q.data.get("gid")) is None), None)
            if frame is not None:
                frame.data["gid"] = entry["id"]
        if getattr(self, "net_mode", None) == "host":
            self._net_world_t = 99.0
        return entry, frame, new

    def _gallery_trim(self):
        while len(self.art_gallery) > GALLERY_MAX:
            shown = {q.data.get("gid") for q in self._paintings()}
            old = next((e for e in self.art_gallery if e["id"] not in shown), self.art_gallery[0])
            self.art_gallery.remove(old)

    def _studio_closed(self, scr):
        if scr.dirty:
            self._studio_save(scr)            # the canvas stays on the easel as you left it
        if self.studio is scr:
            self.studio = None
        if self.state == "studio":
            self.state = "play"
        self.audio.play("ui_move")

    # ------------------------------------------------------------ paintings
    def _paint_cycle(self, p, fr, client=False):
        """A Painting frame: show the next gallery piece (then the original
        landscape again). False when the gallery is empty (plain admire)."""
        if not self.art_gallery:
            if not client:
                self.ui.log("Tip: paint something at an easel and hang it on the wall!")
            return False
        ids = [e["id"] for e in self.art_gallery]
        cur = fr.data.get("gid")
        if cur in ids:
            i = ids.index(cur)
            nxt = ids[i + 1] if i + 1 < len(ids) else None
        else:
            nxt = ids[0]
        self._frame_set(fr, nxt)
        if client:
            self._net_send_menu({"m": "art", "op": "frame", "gx": fr.gx, "gy": fr.gy, "gid": nxt})
        e = self._gallery_get(nxt)
        if e is not None:
            self.ui.log(f"{p.name} hangs \"{e['title']}\" by {e['by']} in the frame")
            self._show_toast("Now showing", f"\"{e['title']}\" by {e['by']}",
                             icon=self._art_icon(e["art"]), seconds=2.5)
        else:
            self.ui.log(f"{p.name} puts the old landscape back in the frame")
            self._show_toast("Now showing", "The original landscape", seconds=2.5)
        self.audio.play("ui_toggle")
        return True

    def _frame_set(self, fr, gid):
        if gid is None or self._gallery_get(gid) is None:
            fr.data.pop("gid", None)
        else:
            fr.data["gid"] = gid

    # ------------------------------------------------------------ telescope
    def _stars_open(self, idx, fr, client=False):
        from .. import stargaze as SG
        if client:
            self._net_send_menu({"m": "furn", "kind": fr.kind, "gx": fr.gx, "gy": fr.gy})
        else:
            self._show_energy(idx, fr, "peers through the telescope")
        self.stargazer = SG.Stargazer(self, idx, fr, client=client)
        self.state = "stargaze"
        self.audio.play("ui_select")

    def _stars_found(self, scr, cid):
        from .. import stargaze as SG
        if cid not in SG.BY_ID or cid in self.stars_found:
            return
        self.stars_found.add(cid)
        _i, name, cap, _s, _l = SG.BY_ID[cid]
        if scr is not None and scr.client:
            self._net_send_menu({"m": "stars", "op": "found", "c": cid})
        who = self.players[scr.pidx].name if scr is not None else "You"
        self.ui.log(f"{who} found a constellation: {name}!")
        self._show_sfx("star_found", "achievement")
        n = len(self.stars_found & set(SG.IDS))
        if n == len(SG.IDS):
            self._show_toast("Every constellation!", "The whole sky is yours - all six found",
                             color=_STAR_COL, seconds=4.5)
        else:
            self._show_toast("Constellation found!", f"{name}  ({n}/{len(SG.IDS)})",
                             color=_STAR_COL)
        self.emit("constellation_found", name=cid)

    def _stars_wished_tonight(self):
        return self.star_wish_day == self._show_today()

    def _stars_wish(self, scr):
        if self._stars_wished_tonight():
            return False, "You already made a wish tonight - save some for tomorrow"
        self.star_wish_day = self._show_today()
        self.star_wish_pending = True
        if scr is not None and scr.client:
            self._net_send_menu({"m": "stars", "op": "wish"})
        who = self.players[scr.pidx].name if scr is not None else "Someone"
        self.ui.log(f"{who} made a wish upon a shooting star...")
        self._show_sfx("wish_chime", "levelup")
        self._show_toast("A wish upon a star", "Tomorrow will be a lucky day...", color=_STAR_COL)
        self.emit("star_wish")
        return True, "You made a wish! Tomorrow will be a lucky day..."

    def _stars_closed(self, scr):
        if self.stargazer is scr:
            self.stargazer = None
        if self.state == "stargaze":
            self.state = "play"
        self.audio.play("ui_move")

    # ------------------------------------------------------------ arcade
    def _pong_open(self, idx, fr, client=False):
        from .. import heartpong as HP
        if not fr.on:
            if client:                          # the host owns the real switch: SET it
                self._net_send_menu({"m": "furn", "kind": fr.kind, "gx": fr.gx, "gy": fr.gy,
                                     "on": True})
            else:
                self._show_energy(idx, fr, "switches the Arcade Cabinet ON - "
                                  "play a round of Heart Pong")
            fr.on = True
            self._show_sfx("pong_on", "ui_toggle")
        else:
            self.audio.play("ui_select")
        self.pong = HP.HeartPong(self, idx, fr, client=client)
        self.state = "arcade"

    def _pong_result(self, scr):
        st = self.pong_stats
        st["games"] += 1
        best = scr.best_rally > st["best_rally"]
        st["best_rally"] = max(st["best_rally"], scr.best_rally)
        names = scr.names()
        if scr.vs_cpu:
            if scr.winner == 0:
                st["cpu_w"] += 1
            else:
                st["cpu_l"] += 1
        else:
            st["duel"][scr.winner] += 1
        if scr.client:
            self._net_send_menu({"m": "pong", "op": "result", "cpu": bool(scr.vs_cpu),
                                 "win": int(scr.winner), "rally": int(scr.best_rally)})
        w = names[scr.winner]
        self.ui.log(f"Heart Pong: {w} wins {max(scr.score)}-{min(scr.score)}!")
        self._show_toast("Heart Pong", f"{w} wins {max(scr.score)}-{min(scr.score)}!",
                         color=_PONG_COL)
        self.emit("pong_won", winner=w, cpu=bool(scr.vs_cpu))
        if best and scr.best_rally > 1:
            return f"New best rally: {scr.best_rally} hits!"
        return f"Longest rally: {scr.best_rally}   |   farm best: {st['best_rally']}"

    def _pong_closed(self, scr, power_off):
        if power_off:
            cab = scr.cab
            live = self._show_piece_at(cab.kind, cab.gx, cab.gy) or cab
            if scr.client:
                self._net_send_menu({"m": "furn", "kind": live.kind, "gx": live.gx,
                                     "gy": live.gy, "on": False})
            elif live.on:
                self.ui.log(f"{self.players[scr.pidx].name}: switches the Arcade Cabinet off")
            live.on = False
            self._show_sfx("pong_off", "ui_toggle")
        else:
            self.audio.play("ui_move")
        if self.pong is scr:
            self.pong = None
        if self.state == "arcade":
            self.state = "play"

    # ------------------------------------------------------------ room art hooks
    def _show_piece_art(self, kind, gx, gy):
        """isofurn.PIECE_ART: the art string an easel drawn at (gx, gy) shows."""
        if kind != "easel":
            return None
        for q in self.world.home_furniture:
            if q.kind == "easel" and abs(q.gx + q.ox - gx) < 1e-6 and abs(q.gy + q.oy - gy) < 1e-6:
                return (q.data or {}).get("art")
        return None

    def _show_wall_art(self, kind, side, foot):
        """wallart.ART_FOR: the gallery art a Painting on ``side`` whose wall
        cell starts at screen point ``foot`` shows (None = the landscape)."""
        if kind != "painting" or not self.art_gallery or self.world.current != AREA_HOME:
            return None
        from .. import homeiso
        area = self.world.area
        ox, oy = homeiso.origin(area)
        for q in self._paintings():
            gid = (q.data or {}).get("gid")
            if gid is None or homeiso.wall_side(q.gx, q.gy) != side:
                continue
            if side == "back":
                f = homeiso.proj(ox, oy, max(1, min(area.w - 2, q.gx)), 1)
            else:
                f = homeiso.proj(ox, oy, 1, max(1, min(area.h - 2, q.gy)) + 1)
            if abs(f[0] - foot[0]) <= 1 and abs(f[1] - foot[1]) <= 1:
                e = self._gallery_get(gid)
                return e["art"] if e else None
        return None

    def _lights_showpieces(self):
        """A switched-on arcade cabinet glows pink at night."""
        if self.world.current != AREA_HOME:
            return ()
        cabs = [q for q in self.world.home_furniture if q.kind == "arcade_cabinet" and q.on]
        if not cabs:
            return ()
        try:
            from .. import homeiso
            ox, oy = homeiso.origin(self.world.area)
        except Exception:
            return ()
        out = []
        for q in cabs:
            sx, sy = homeiso.proj(ox, oy, q.gx + q.ox + 0.5, q.gy + q.oy + 0.5)
            out.append((sx + self.cam.x, sy - 44 + self.cam.y, 100, (255, 130, 210)))
        return out

    # ------------------------------------------------------------ sounds
    def _show_build_sfx(self):
        a = getattr(self, "audio", None)
        a = getattr(a, "_real", None) or a
        if (not a or not getattr(a, "enabled", False) or a.sfx.get("pong_hit") is not None
                or getattr(a, "_show_sfx_busy", False)):
            return
        a._show_sfx_busy = True
        import threading
        threading.Thread(target=self._show_synth_sfx, args=(a,), daemon=True).start()

    @staticmethod
    def _show_synth_sfx(a):
        try:
            R, S = a._render, a._to_sound
            a.sfx["studio_dab"] = S(R(0.035, [900], "sine", 0.10, noise=0.3, release=0.8))
            a.sfx["studio_save"] = S(a._seq(R(0.06, [660], "tri", 0.22), R(0.10, [990], "tri", 0.22,
                                                                             release=0.6)))
            a.sfx["studio_hang"] = S(a._seq(R(0.05, [220], "sine", 0.3, noise=0.4),
                                            R(0.08, [784], "tri", 0.2), R(0.14, [1175], "tri", 0.2,
                                                                          release=0.7)))
            a.sfx["pong_hit"] = S(R(0.05, [520], "square", 0.16, release=0.5))
            a.sfx["pong_wall"] = S(R(0.04, [330], "square", 0.12, release=0.5))
            a.sfx["pong_serve"] = S(R(0.08, [440, 660], "tri", 0.18, sweep=0.3, release=0.5))
            a.sfx["pong_score"] = S(a._seq(R(0.07, [523], "square", 0.14), R(0.07, [659], "square", 0.14),
                                           R(0.12, [784], "square", 0.14, release=0.6)))
            a.sfx["pong_win"] = S(a._seq(*[R(0.09, [f], "tri", 0.2) for f in (523, 659, 784, 1047)],
                                         R(0.3, [1047, 1319], "tri", 0.2, release=0.7)))
            a.sfx["pong_on"] = S(R(0.25, [220, 440], "square", 0.1, sweep=1.2, release=0.5))
            a.sfx["pong_off"] = S(R(0.22, [660], "square", 0.1, sweep=-0.8, release=0.6))
            a.sfx["star_found"] = S(a._seq(*[R(0.08, [f, f * 2], "sine", 0.18) for f in (784, 988, 1175)],
                                           R(0.35, [1568], "sine", 0.16, release=0.8)))
            a.sfx["wish_chime"] = S(a._seq(*[R(0.07, [f], "sine", 0.2) for f in
                                             (1319, 1175, 988, 1175, 1568)],
                                           R(0.5, [1319, 1976], "sine", 0.16, vibrato=6, release=0.8)))
        except Exception:
            pass
        finally:
            a._show_sfx_busy = False

    # ------------------------------------------------------------ custom states
    def _show_screen(self):
        return {"studio": getattr(self, "studio", None),
                "stargaze": getattr(self, "stargazer", None),
                "arcade": getattr(self, "pong", None)}.get(self.state)

    def _show_state_event(self, e):
        scr = self._show_screen()
        if scr is None:
            self.state = "play"
            return
        scr.handle_event(e)

    def _show_state_update(self, dt):
        scr = self._show_screen()
        if scr is None:
            self.state = "play"
            return
        scr.update(dt)

    def _show_state_draw(self):
        scr = self._show_screen()
        if scr is not None:
            scr.draw(self.screen)

    _state_event_studio = _state_event_stargaze = _state_event_arcade = _show_state_event
    _state_update_studio = _state_update_stargaze = _state_update_arcade = _show_state_update
    _state_draw_studio = _state_draw_stargaze = _state_draw_arcade = _show_state_draw

    # ------------------------------------------------------------ LAN
    def _net_menu_showpieces(self, mm, m):
        """Host: Player 2's art / stargazing / pong results from the client."""
        from .. import studio as S
        from .. import stargaze as SG
        p = self.players[1]
        if mm == "art":
            op = m.get("op")
            art = m.get("art")
            if op == "save" and S.valid(art):
                easel = self._show_piece_at("easel", m.get("gx"), m.get("gy"))
                if easel is not None:
                    self._art_store(easel, art, p.name)
                    if not S.is_blank(S.decode(art)):
                        self.ui.log(f"{p.name} finished a painting at the easel")
            elif op == "hang" and S.valid(art) and not S.is_blank(S.decode(art)):
                entry, frame, new = self._gallery_add(art, p.name)
                self.ui.log(f"{p.name} hangs a painting: \"{entry['title']}\"")
                self._net_toast(self._hang_msg(entry, frame, new))
            elif op == "frame":
                fr = self._show_piece_at("painting", m.get("gx"), m.get("gy"))
                gid = m.get("gid")
                if fr is not None and (gid is None or isinstance(gid, int)):
                    self._frame_set(fr, gid)
            self._net_world_t = 99.0
            return True
        if mm == "stars":
            op = m.get("op")
            if op == "found" and m.get("c") in SG.BY_ID and m.get("c") not in self.stars_found:
                self.stars_found.add(m.get("c"))
                self.ui.log(f"{p.name} found a constellation: {SG.BY_ID[m.get('c')][1]}!")
            elif op == "wish" and not self._stars_wished_tonight():
                self.star_wish_day = self._show_today()
                self.star_wish_pending = True
                self.ui.log(f"{p.name} made a wish upon a shooting star...")
            self._net_world_t = 99.0
            return True
        if mm == "pong":
            if m.get("op") == "result":
                st = self.pong_stats
                try:
                    win = int(m.get("win", 1)) % 2
                    rally = max(0, min(999, int(m.get("rally", 0))))
                except (TypeError, ValueError):
                    return True
                st["games"] += 1
                st["best_rally"] = max(st["best_rally"], rally)
                if m.get("cpu", True):
                    st["cpu_w" if win == 0 else "cpu_l"] += 1
                self.ui.log(f"Heart Pong: {p.name} " + ("beats the CPU!" if win == 0
                                                          else "loses to the CPU"))
                self._net_world_t = 99.0
            return True
        return False
