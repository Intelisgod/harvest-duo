"""Guitar domain checks (2026-09-28): the playable guitar screen (a key is a
chord), its Karplus-Strong synth, the song book and the LAN strum relays.

run(g, check, H) is called by tools/smoke_test.py (s_domain_tests)."""
import json
import math

import pygame


def run(g, check, H):
    from src.settings import AREA_HOME, MAX_ENERGY
    from src import furniture as F
    from src import guitar as GT
    from src.systems import guitar_system as GS
    ev = pygame.event.Event
    area0 = g.world.current
    added = []

    def key(k, up=False, mod=0, scancode=0):
        g._run_state("event", ev(pygame.KEYUP if up else pygame.KEYDOWN, key=k, mod=mod,
                                 unicode="", scancode=scancode))

    def tap(k, frames=1, mod=0):
        key(k, mod=mod)
        for _ in range(frames):
            g._run_state("update", H.DT)
        key(k, up=True, mod=mod)

    def frames(n):
        for _ in range(n):
            g._run_state("update", H.DT)

    def close():
        if g.state == "guitar" and g.guitar_ui is not None:
            g.guitar_ui.close()
        for _ in range(40):
            if g.state != "guitar":
                break
            frames(1)
        assert g.state == "play" and g.guitar_ui is None, g.state

    def home_stand():
        if g.world.current != AREA_HOME:
            g.warp(AREA_HOME, H.spawns_by_area(g)[AREA_HOME])
        g.state = "play"
        q = next((q for q in g.world.home_furniture if q.kind == "guitar_stand"), None)
        if q is None:
            q = F.Placed("guitar_stand", 3, 4, 0, 10)
            g.world.home_furniture.append(q)
            added.append(q)
        return q

    def key_for(cid):
        return next(k for k, c in GT.KEY_CHORD.items() if c == cid)

    # ---------------------------------------------------------------- the chords
    def voicings():
        assert GT.TUNING == (40, 45, 50, 55, 59, 64), "standard tuning E2 A2 D3 G3 B3 E4"
        assert len(GT.CHORD_IDS) == 21 and len(set(GT.CHORD_IDS)) == 21
        assert [GT.GRID[0][c] for c in range(7)] == ["Bb", "F", "C", "G", "D", "A", "E"]
        out = []
        for cid in GT.CHORD_IDS:
            fr, vs = GT.frets(cid), GT.voicing(cid)
            played = [m for m in vs if m is not None]
            assert len(played) >= 4, (cid, "too few strings")
            assert all(f is None or 0 <= f <= 5 for f in fr), (cid, fr)
            pcs = {m % 12 for m in played}
            need = GT.chord_pcs(cid)
            assert pcs <= need, (cid, "a wrong note", sorted(pcs - need))
            r = GT.root_pc(cid)
            third = (r + (3 if GT.chord_kind(cid) == "m" else 4)) % 12
            assert r in pcs and third in pcs, (cid, "no root / third")
            if GT.chord_kind(cid) == "7":
                assert (r + 10) % 12 in pcs, (cid, "no seventh")
            assert min(played) % 12 == r, (cid, "not in root position")
            # a muted string is only ever a low one (you can't strum past it)
            first = next(i for i, m in enumerate(vs) if m is not None)
            assert all(m is not None for m in vs[first:]), (cid, "a muted string mid-chord")
            b = GT.BARRES.get(cid)
            if b:
                assert all(fr[i] is not None and fr[i] >= b[0] for i in range(b[1], b[2] + 1)), cid
            assert GT.KEY_LABEL[cid] in "QWERTYUASDFGHJZXCVBNM"
            out.append(f"{cid}={GT.SHAPES[cid]}")
        assert set(GT.KEY_CHORD.values()) == set(GT.CHORD_IDS)
        return " ".join(out)
    check("guitar: 21 chord voicings are real, in tune and in root position", voicings)

    def plans():
        import random
        rnd = random.Random(7)
        for cid in GT.CHORD_IDS:
            vs = GT.voicing(cid)
            strings = [i for i, m in enumerate(vs) if m is not None]
            for down in (True, False):
                for _ in range(8):
                    p = GT.plan_strum(vs, down, 1.0, rnd=rnd)
                    order = [i for i, _t, _v in p]
                    assert order == (strings if down else strings[::-1]), (cid, down, order)
                    ts = [t for _i, t, _v in p]
                    assert ts[0] == 0.0 and all(b > a for a, b in zip(ts, ts[1:])), ts
                    gaps = [b - a for a, b in zip(ts, ts[1:])]
                    assert all(0.007 <= d <= 0.027 for d in gaps), (cid, gaps)
                    assert all(0.05 <= v <= 1.0 for _i, _t, v in p)
            up = {i: v for i, _t, v in GT.plan_strum(vs, False, 1.0, rnd=rnd)}
            if 0 in up or 1 in up:
                lo = up.get(0, up.get(1))
                assert lo < up[5], ("an up-strum only brushes the bass", cid, up)
        return "down low->high, up high->low, 7-27 ms apart"
    check("guitar: strum plans (order, spacing, touch)", plans)

    # ---------------------------------------------------------------- the synth
    def synth_bake():
        import time
        s = GT.synth(g.audio)
        t0 = time.perf_counter()
        pcm = s.render(52)
        ms = (time.perf_counter() - t0) * 1000
        sr = s.sr
        assert abs(len(pcm) - GT.note_secs(52) * sr) < 2, len(pcm)
        assert max(abs(v) for v in pcm) <= GT.PEAK and max(abs(v) for v in pcm) > GT.PEAK * 0.8
        W = int(0.05 * sr)

        def rms(x):
            return math.sqrt(sum(v * v for v in x) / max(1, len(x)))
        head, tail = rms(pcm[:W]), rms(pcm[-int(GT.FADE * sr) - W:-int(GT.FADE * sr)])
        db = 20 * math.log10(tail / head)
        assert db < -20, f"still {db:.0f} dB when the final fade starts"
        assert rms(pcm[int(1.0 * sr):int(1.0 * sr) + W]) > head * 0.03, "rings on for a while"
        assert max(abs(v) for v in pcm[-int(0.005 * sr):]) < 40, "the end is a click"
        assert abs(sum(pcm) / len(pcm)) < 30, "DC offset"
        # in tune: autocorrelation of the ring (the first lag near the top,
        # refined between samples) -- Karplus-Strong's loop is a whole number
        # of samples long, so the note is resampled to its exact pitch
        def pitch(x, lo=70, hi=420):
            n = 2048
            best = [(sum(x[i] * x[i + lag] for i in range(0, n, 2)), lag)
                    for lag in range(sr // hi, sr // lo)]
            mx = max(best)[0]
            for j in range(1, len(best) - 1):
                a, b, c = best[j - 1][0], best[j][0], best[j + 1][0]
                if b >= 0.9 * mx and b >= a and b >= c:
                    d = 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0.0
                    return sr / (best[j][1] + d)
            return 0.0
        cents = []
        for m, p in ((52, pcm), (40, None), (59, None)):
            p = p or s.render(m)
            f = pitch(p[int(0.5 * sr):])
            c = 1200 * math.log2(max(1e-6, f) / (440.0 * 2 ** ((m - 69) / 12.0)))
            assert abs(c) < 8, f"{GT.note_name(m)} is {c:+.1f} cents out"
            cents.append(f"{GT.note_name(m)} {c:+.1f}c")
        q = s.render(40, secs=GT.QUICK_SECS)
        assert len(q) == int(sr * GT.QUICK_SECS) and abs(q[-1]) < 50
        mb = sum(GT.note_secs(m) for m in GT.warm_order()) * sr * 2 / 1e6
        assert mb < 12, f"{mb:.1f} MB"
        return f"E3 baked in {ms:.0f} ms, {db:.0f} dB before the fade, {' '.join(cents)}; " \
               f"{len(GT.warm_order())} string pitches ~{mb:.1f} MB"
    check("guitar: synth bakes a decaying, in-tune plucked string", synth_bake)

    # ---------------------------------------------------------------- play it
    def open_and_play():
        st = home_stand()
        p1, p2 = g.players
        for p in (p1, p2):
            p.sitting = None
        g._guitar_days.clear()
        p1.energy = 10
        g._guitar_open(0, st)
        assert g.state == "guitar" and g.guitar_ui is not None and g.guitar_ui.pidx == 0
        assert p1.energy > 10, "no energy for picking the guitar up"
        e1 = p1.energy
        ui = g.guitar_ui
        frames(25)                                        # (lifted into place)
        assert ui.phase == "play"
        # every pad strums its chord, down
        for cid in GT.CHORD_IDS:
            key(key_for(cid))
            assert ui.chord == cid and ui.down, (cid, ui.chord)
            vib = [i for i, v in enumerate(ui.vib) if v is not None]
            assert vib == [i for i, m in enumerate(GT.voicing(cid)) if m is not None], (cid, vib)
            key(key_for(cid), up=True)
            frames(2)
        # key repeat: one strum per press
        n0 = len(ui.trail)
        key(pygame.K_e)
        key(pygame.K_e)
        key(pygame.K_e, up=True)
        assert len(ui.trail) == n0 + 1, "key repeat strummed again"
        # Shift: an up-strum (strings from the top one down)
        key(pygame.K_LSHIFT)
        key(pygame.K_r, mod=pygame.KMOD_LSHIFT)
        assert ui.chord == "G" and not ui.down
        key(pygame.K_r, up=True, mod=pygame.KMOD_LSHIFT)
        key(pygame.K_LSHIFT, up=True)
        order = sorted((v[0], i) for i, v in enumerate(ui.vib) if v is not None)
        assert [i for _t, i in order] == [5, 4, 3, 2, 1, 0], order
        # Space: the same chord again (Shift + Space: up)
        tap(pygame.K_SPACE)
        assert ui.chord == "G" and ui.down and len(ui.trail) == n0 + 3
        tap(pygame.K_SPACE, mod=pygame.KMOD_SHIFT)
        assert not ui.down
        # a Thai layout: the scancode still finds the key cap
        key(0x0E1F, scancode=pygame.KSCAN_H)
        assert ui.chord == "Am", ui.chord
        key(0x0E1F, up=True, scancode=pygame.KSCAN_H)
        # mouse: left click = down, right click = up
        r = GT.PAD_RECTS["D7"]
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
        assert ui.chord == "D7" and ui.down
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=r.center, button=3))
        assert ui.chord == "D7" and not ui.down
        frames(3)
        g.draw()
        H.shot(g, "guitar_strum")
        frames(40)
        g.draw()
        H.shot(g, "guitar_free")
        s = ui.syn
        close()
        # the same day again: no more energy
        g._guitar_open(0, st)
        assert p1.energy == e1, "energy twice in one day"
        close()
        # Player 2 (local co-op) has their own day
        p2.energy = 10
        g._guitar_open(1, st)
        assert g.guitar_ui.pidx == 1 and p2.energy > 10
        tap(pygame.K_c)
        assert g.guitar_ui.chord == "C7"
        key(pygame.K_BACKSPACE)
        frames(30)
        assert g.state == "play" and g.guitar_ui is None
        return f"synth {'on' if s.enabled else 'silent'}, {len(s.cache)} strings baked"
    check("guitar: open (P1 / P2), every pad strums, repeat, Shift, Space, mouse, close",
          open_and_play)

    def from_the_room():
        """Action facing a guitar on its stand opens the guitar (a hook, no seat)."""
        from src.settings import TILE
        st = home_stand()
        p1, p2 = g.players
        was = [(p.x, p.y, p.fx, p.fy, p.sitting) for p in (p1, p2)]
        g._cat_in_front = lambda p: False
        try:
            p1.sitting = p2.sitting = None
            H.place(g, p1, st.gx, st.gy + 1)
            p1.fx, p1.fy = 0, -1
            p2.x, p2.y = p1.x + 6 * TILE, p1.y + 6 * TILE
            assert g.world.furniture_at(*p1.target_tile()) is st
            g.player_action(0)
            assert g.state == "guitar" and g.guitar_ui is not None, g.state
            assert g.guitar_ui.piece is st
            key(pygame.K_ESCAPE)
            frames(30)
            assert g.state == "play"
        finally:
            del g._cat_in_front
            for p, w in zip((p1, p2), was):
                p.x, p.y, p.fx, p.fy, p.sitting = w
        return "Action at the stand -> the guitar"
    check("guitar: Action at the guitar stand opens it", from_the_room)

    # ---------------------------------------------------------------- song book
    def song_book():
        for s in GT.SONGS:
            assert s["steps"] and all(c in GT.SHAPES and b > 0 and w for c, b, w in s["steps"]), s["id"]
            assert s["steps"][-1][0] == s["key"], (s["id"], "a song ends at home")
        st = home_stand()
        p = g.players[0]
        g._guitar_open(0, st)
        ui = g.guitar_ui
        frames(25)
        tap(pygame.K_TAB)
        assert ui.mode == 1 and ui.song["id"] == "twinkle", ui.mode
        g._guitar_songs.clear()
        p.energy = 50
        want = ui.target()
        wrong = next(c for c in GT.CHORD_IDS if c != want)
        tap(key_for(wrong))                               # a wrong chord: a wiggle, no step
        assert ui.song_i == 0 and ui.miss_t > 0
        n = 0
        while ui.target() is not None and n < 100:
            tgt = ui.target()
            if n % 3 == 2 and ui.chord == tgt:
                tap(pygame.K_SPACE)                       # the same chord again: Space works
            else:
                tap(key_for(tgt))
            n += 1
            if n == 6:
                frames(4)
                g.draw()
                H.shot(g, "guitar_song")
        steps = len(ui.song["steps"])
        assert n == steps and ui.done_t > 0, (n, ui.done_t)
        assert p.energy == min(MAX_ENERGY, 50 + GS.SONG_REWARD), p.energy
        frames(30)                                        # the flourish strums on its own
        g.draw()
        H.shot(g, "guitar_song_done")
        for _ in range(240):
            frames(1)
        assert ui.done_t == 0 and ui.song_i == 0
        # the same song again today: lovely, but no more energy
        assert g._guitar_reward(0, "twinkle") == "" and p.energy == min(MAX_ENERGY, 50 + GS.SONG_REWARD)
        # Listen: the guitar strums the chart itself; strumming yourself stops it
        tap(pygame.K_TAB)                                 # Happy Birthday (for the partner!)
        assert ui.song["id"] == "birthday"
        assert g.players[1].name in ui.words(ui.song["steps"][5])
        tap(pygame.K_RETURN)
        assert ui.demo is not None and ("Enter", "Stop") in ui.hint_pills()
        for _ in range(150):
            frames(1)
        assert ui.demo is not None and ui.demo["show"] >= 1 and ui.chord is not None, ui.demo
        tap(pygame.K_q)                                   # (Bb: not the song's first chord)
        assert ui.demo is None and ui.song_i == 0
        # Up / Down step through the book, Tab wraps back to free play
        tap(pygame.K_UP)
        assert ui.mode == 1
        for _ in range(len(GT.SONGS)):
            tap(pygame.K_TAB)
        assert ui.mode == 0, ui.mode
        # the song-book arrows / tab by mouse
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=GT.MODE_SONG.center, button=1))
        assert ui.mode == ui.last_song
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=GT.MODE_NEXT.center, button=1))
        assert ui.mode == ui.last_song
        g._run_state("event", ev(pygame.MOUSEBUTTONDOWN, pos=GT.MODE_FREE.center, button=1))
        assert ui.mode == 0
        close()
        # the song days are saved (and junk in a save is ignored)
        g._guitar_days["1"] = [1, 2, 3]
        d = json.loads(json.dumps(g._on_save_guitar()))
        songs, days = dict(g._guitar_songs), dict(g._guitar_days)
        g._on_load_guitar({"guitar_songs": {"x": "junk", 5: [1]}, "guitar_days": 7})
        assert g._guitar_songs == {} and g._guitar_days == {}
        g._on_load_guitar(d)
        assert g._guitar_songs == songs and g._guitar_days == days and "0:twinkle" in songs
        return f"twinkle: {steps} chords; {len(GT.SONGS)} songs in the book"
    check("guitar: song book (right chord advances, wrong wiggles, reward once, listen, save)",
          song_book)

    # ---------------------------------------------------------------- LAN
    def lan():
        st = home_stand()
        p1, p2 = g.players
        menu, fx = [], []
        g._guitar_rate = {}
        g._net_send_menu = lambda d: menu.append(dict(d))
        g._net_send_fx = lambda kind, **d: fx.append((kind, d))
        g._cat_in_front = lambda p: False
        mode0 = g.net_mode
        try:
            # client: Action at the stand opens the guitar HERE; strums go as menu ops
            g.net_mode = "client"
            assert g._guitar_client_interact(p2, F.Placed("tv", 0, 0)) is False
            assert g._home_client_interact(p2, st) is True
            assert g.state == "guitar" and g.guitar_ui.client and g.guitar_ui.pidx == 1
            assert {"m": "guitar", "op": "open", "gx": st.gx, "gy": st.gy} in menu, menu
            frames(25)
            tap(pygame.K_r)
            tap(pygame.K_h, mod=pygame.KMOD_SHIFT)
            assert {"m": "guitar", "c": "G", "d": 1, "gx": st.gx, "gy": st.gy} in menu, menu
            assert {"m": "guitar", "c": "Am", "d": 0, "gx": st.gx, "gy": st.gy} in menu, menu
            # a finished song: the host is asked; the banner guesses meanwhile
            g._guitar_songs.pop("1:row", None)
            ui = g.guitar_ui
            ui.set_mode(1 + [s["id"] for s in GT.SONGS].index("row"))
            while ui.target() is not None:
                tap(key_for(ui.target()))
            assert {"m": "guitar", "op": "song", "song": "row"} in menu, menu
            assert ui.reward == f"+{GS.SONG_REWARD} energy"
            g.draw()
            H.shot(g, "guitar_client")
            close()
            # host: P1's strums go to the client as fx
            g.net_mode = "host"
            g._guitar_open(0, st)
            assert ("guitar", {"op": "open"}) in fx, fx
            frames(25)
            tap(pygame.K_t)
            assert ("guitar", {"c": "D", "d": 1, "gx": st.gx, "gy": st.gy}) in fx, fx
            close()
        finally:
            g.net_mode = mode0
            del g._net_send_menu
            del g._net_send_fx
            del g._cat_in_front
        # receiving: only guitar ops are ours; junk is ignored
        assert g._net_menu_guitar("fridge", {}) is False
        assert g._net_menu_guitar("guitar", {"m": "guitar", "c": "H#dim"}) is True
        assert g._net_menu_guitar("guitar", {"m": "guitar", "c": None, "d": "x"}) is True
        assert g._net_menu_guitar("guitar", {"m": "guitar", "c": 12}) is True
        assert g._net_fx_guitar({"kind": "piano"}) is False
        assert g._net_fx_guitar({"kind": "guitar", "c": "Em", "d": 0}) is True
        assert GT.clean_chord("Em") == "Em" and GT.clean_chord("Em; drop") is None
        # a partner's strum floats a note off the stand in the live room
        g.state = "play"
        n0 = len(g.parts.items)
        g._guitar_rate = {}
        g._net_fx_guitar({"kind": "guitar", "c": "C", "d": 1, "gx": st.gx, "gy": st.gy})
        assert len(g.parts.items) > n0, "no note over the guitar"
        # a flood of strums is rate-limited
        g._guitar_rate = {}
        ok = sum(1 for _ in range(200) if g._guitar_rate_ok("in"))
        assert ok <= GS._BURST + 2, ok
        # the host pays P2's energy (once a day) and the song reward (once a day)
        g._guitar_days.pop("1", None)
        p2.energy = 40
        g._net_menu_guitar("guitar", {"m": "guitar", "op": "open", "gx": st.gx, "gy": st.gy})
        e = p2.energy
        assert e > 40, "no energy for the client picking the guitar up"
        g._net_menu_guitar("guitar", {"m": "guitar", "op": "open", "gx": st.gx, "gy": st.gy})
        assert p2.energy == e, "energy twice in a day"
        g._guitar_songs.pop("1:mary", None)
        p2.energy = 40
        for sid in ("mary", "mary", "<junk>", None):
            g._net_menu_guitar("guitar", {"m": "guitar", "op": "song", "song": sid})
        assert p2.energy == 40 + GS.SONG_REWARD, p2.energy
        # the partner picking it up prewarms THIS synth, only for a farmer in the house
        s = GT.synth(g.audio)
        warm = []
        s.prewarm = lambda ms: warm.append(list(ms))
        try:
            g._net_fx_guitar({"kind": "guitar", "op": "open"})
            assert warm and warm[-1] == GT.warm_order(), warm
            g._guitar_can_hear = lambda: False
            try:
                g._net_fx_guitar({"kind": "guitar", "op": "open"})
            finally:
                del g._guitar_can_hear
            assert len(warm) == 1, "prewarmed for a farmer out in the fields"
        finally:
            del s.prewarm
        return f"{len(menu)} menu ops, {len(fx)} fx, flood capped at {ok}"
    check("guitar: LAN (client opens + relays strums, host fx, junk, flood, rewards)", lan)

    # ---------------------------------------------------------------- loudness
    def headroom():
        """At master 1.0 x sfx 1.0 no strum clips -- not even with the
        partner's chord still ringing -- and at the default volume a strum is
        left at full level."""
        import time
        s = GT.synth(g.audio)
        if not (s.enabled and s._pool()):
            return "synth silent: skipped"
        a = getattr(g.audio, "_real", None) or g.audio
        vol0 = (a.master, a.sfx_vol)
        sr = s.sr
        N = int(0.2 * sr)
        pcm = {}

        def quiet():
            s.lanes.clear()
            for c in s._pool():
                c.stop()

        def voices(lane):
            return [(v[2], v[3], v[0].get_volume()) for v in s.lanes.get(lane, [])]

        def mix(vs, t0):
            out = [0.0] * (N + int(0.2 * sr))
            for m, start, vol in vs:
                p = pcm.get(m)
                if p is None:
                    p = pcm[m] = s.render(m)[:N + int(0.2 * sr)]
                off = int(round((start - t0) * sr))
                for j in range(max(0, -off), min(len(p), len(out) - off)):
                    out[off + j] += p[j] * vol
            return max(abs(x) for x in out)
        worst, gains = 0.0, []
        try:
            a.master, a.sfx_vol = 1.0, 1.0
            for cid in GT.CHORD_IDS:
                quiet()
                vs = GT.voicing(cid)
                t0 = time.monotonic()
                gains.append(s.strum(("hr",), vs, GT.plan_strum(vs, True, 1.0)))
                pk = mix(voices(("hr",)), t0)
                assert pk < 32767 * 0.95, (cid, "clips", pk)
                worst = max(worst, pk)
            # the partner's G rings on as I strum an E
            quiet()
            t0 = time.monotonic()
            vg, ve = GT.voicing("G"), GT.voicing("E")
            s.strum(("remote",), vg, GT.plan_strum(vg, True, 1.0))
            s.strum(("me",), ve, GT.plan_strum(ve, True, 1.0))
            both = voices(("remote",)) + voices(("me",))
            assert len(both) == 12, both
            pk2 = mix(both, t0)
            assert pk2 < 32767 * 0.97, ("two guitars clip", pk2)
            # my next strum damps my old chord (only mine)
            s.strum(("me",), vg, GT.plan_strum(vg, False, 1.0))
            mine = s.lanes[("me",)]
            assert any(v[5] is not None for v in mine), "the old chord wasn't damped"
            assert s.active(("me",)) == 6, s.active(("me",))
            assert all(v[5] is None for v in s.lanes.get(("remote",), [])), "damped the partner"
            # default volume: an ordinary strum keeps its full level
            quiet()
            a.master, a.sfx_vol = 0.8, 0.9
            vs = GT.voicing("C")
            gain = s.strum(("hr",), vs, GT.plan_strum(vs, True, 1.0))
            assert gain > 0.99, gain
        finally:
            a.master, a.sfx_vol = vol0
            quiet()
        return (f"worst strum {20 * math.log10(worst / 32767):+.1f} dBFS at full volume "
                f"(gain {min(gains):.2f}..{max(gains):.2f}); two guitars "
                f"{20 * math.log10(pk2 / 32767):+.1f} dBFS")
    check("guitar: headroom (no strum clips at full volume, two guitars either)", headroom)

    # ---------------------------------------------------------------- the room + music
    def hush_and_bake():
        from src.systems import areactx_system as AX
        from src.settings import AREA_FARM
        st = home_stand()
        a = g.audio
        ch = getattr(a, "music_chan", None)
        full = g._guitar_loop_level(a)
        g._guitar_open(0, st)
        if ch is not None:
            assert abs(ch.get_volume() - full * GS._HUSH) < 0.01, (ch.get_volume(), full)
        n0 = len(g.parts.items)
        for k in (pygame.K_q, pygame.K_w, pygame.K_e) * 3:
            tap(k)
        assert len(g.parts.items) <= n0, "notes piled up in the frozen room"
        close()
        if ch is not None:
            assert abs(ch.get_volume() - full) < 0.01, ("still hushed", ch.get_volume())
        # a reset while playing gives the loop back
        g._guitar_open(0, st)
        songs, days = dict(g._guitar_songs), dict(g._guitar_days)
        g._on_reset_guitar()
        g._guitar_songs.update(songs)
        g._guitar_days.update(days)
        g.state = "play"
        if ch is not None:
            assert abs(ch.get_volume() - full) < 0.01, ch.get_volume()
        assert g.guitar_ui is None and not g._guitar_hushed
        g.state = "guitar"                                # no screen: falls back to play
        key(pygame.K_e)
        assert g.state == "play"
        # walking into the house bakes the strings (also inside an area context)
        s = GT.synth(g.audio)
        calls = []
        s.prewarm = lambda ms: calls.append(list(ms))
        real = g.audio
        try:
            g._on_area_enter_guitar()
            assert calls and calls[-1] == GT.warm_order()
            g.audio = AX._Sink(real)
            g._on_area_enter_guitar()
            g.audio = real
            assert len(calls) == 2, "the area context's sink swallowed the bake"
            sp = H.spawns_by_area(g)
            g.warp(AREA_FARM, sp[AREA_FARM])
            n = len(calls)
            g._on_area_enter_guitar()
            assert len(calls) == n, "baked the guitar out on the farm"
            g.warp(AREA_HOME, sp[AREA_HOME])
            assert len(calls) > n, "entering the house didn't bake"
        finally:
            g.audio = real
            del s.prewarm
        return f"loop {full:.3f} -> {full * GS._HUSH:.3f} while playing; bakes on entering"
    check("guitar: music hush, frozen room, reset, bake on entering the house", hush_and_bake)

    # let the string bake finish, so later (timing-sensitive) tests get the CPU
    import time
    s = GT.synth(g.audio)
    t0 = time.monotonic()
    while s._busy and time.monotonic() - t0 < 15:
        time.sleep(0.02)
    s.lanes.clear()
    for c in s._pool() if s.enabled else ():
        c.stop()
    for q in added:
        if q in g.world.home_furniture:
            g.world.home_furniture.remove(q)
    if g.world.current != area0:
        sp = H.spawns_by_area(g).get(area0)
        if sp:
            g.warp(area0, sp)
    g.state = "play"
