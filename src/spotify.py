"""A tiny remote for the real Spotify app on THIS PC (the record player's brain).

No Web API, no login, no dependencies. The Windows desktop app already tells
everyone what it plays through its window title ("Artist - Song"; just
"Spotify" / "Spotify Free" / "Spotify Premium" while paused), it opens from a
``spotify:`` link, and it obeys the media keys. So:

  now_playing()        -> Status(running, playing, artist, title, ready)  (read-only;
                       only the player window's title counts -- see _status_from)
  launch(uri=None)     open the app on a saved playlist link, or plain
                       "spotify:"; no app installed -> open.spotify.com in
                       the browser. Returns "app" / "web" / None.
  media(action)        "play_pause" / "next" / "prev" as a global media key
  app_command(action)  the same, posted straight to the Spotify window
                       (WM_APPCOMMAND), so a paused browser video can't grab it
  parse_link(text)     a pasted open.spotify.com/... or spotify: link -> URI
  clipboard_text()     the clipboard (P in the record player)

``REMOTE`` does all of that on ONE daemon thread, so launching and polling never
block a frame: the game queues commands (``send``), says whether it wants the
status polled (``want``; ~every 1.5 s, only while a record player is on or its
screen is open) and just reads ``REMOTE.status``.

SAFETY GATE -- with HD_NO_EXTERNAL=1 or SDL_VIDEODRIVER=dummy (the smoke and
online tests) nothing outside the game ever happens: launch / media /
app_command only append to ``CALLS``, now_playing() returns ``FAKE_STATUS`` and
the clipboard is ``FAKE_CLIPBOARD``. Every public function swallows its own
errors, and only ``spotify:`` URIs that pass ``clean_uri`` are ever opened.
On other systems launch() opens the web player; media / now_playing are no-ops.
"""
import os
import re
import sys
import threading
import time
import webbrowser

CALLS = []                  # gated calls, newest last: ("launch", uri) / ("media", action)
FAKE_STATUS = None          # gated now_playing() result (tests, screenshots)
FAKE_CLIPBOARD = ""         # gated clipboard_text() result

POLL_EVERY = 1.5            # seconds between status polls
LAUNCH_WAIT = 12.0          # give a cold-starting app this long to show its window
AUTOPLAY_SETTLE = 1.2       # then let it finish loading before pressing play
VERIFY_WAIT = 2.5           # a targeted press that changed nothing -> global key
FAST_POLL = 0.4             # poll rate while waiting on a launch / a press check
AFTER_CMD = 0.3             # poll this soon after a command (show its result quickly)
LINGER = 0.6                # the thread outlives its last command / want this long
                            # (a command is usually queued a moment before want())

IDLE_TITLES = {"spotify", "spotify free", "spotify premium"}
# Spotify.exe owns more top-level windows than the player: hidden helpers
# (IME, DDE, GDI+, notify icons) and sometimes a Miniplayer. Their titles
# never say what plays, so they are never taken for the status.
_JUNK_TITLES = {"default ime", "msctfime ui", "dde server window", "gdi+ window",
                "cspnotify notify window", "miniplayer", "spotify miniplayer",
                "media", "chrome legacy window"}
_JUNK_PREFIX = ("gdi+ window", "dde server", "msctfime", "default ime")
# the player window's class: "Chrome_WidgetWin_0" (current CEF builds),
# "SpotifyMainWindow" (older builds)
MAIN_CLASSES = {"Chrome_WidgetWin_0", "SpotifyMainWindow"}
_VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1}
_APPCMD = {"play_pause": 14, "next": 11, "prev": 12}
_KINDS = ("playlist", "album", "artist", "track", "show", "episode")
_URI_RE = re.compile(r"^spotify(:[A-Za-z0-9._\-]+)*:?$")
_WEB_RE = re.compile(r"^(?:https?://)?open\.spotify\.com/(?:intl-[a-z]{2}(?:-[a-z]{2})?/)?"
                     r"(?:embed/)?(playlist|album|artist|track|show|episode)/"
                     r"([A-Za-z0-9]{6,40})(?:[/?#].*)?$", re.I)
_APP_RE = re.compile(r"^spotify:(?:user:[\w.\-]+:)?(playlist|album|artist|track|show|episode)"
                     r":([A-Za-z0-9]{6,40})$", re.I)
_LIKED_RE = re.compile(r"^(?:(?:https?://)?open\.spotify\.com/collection/tracks/?(?:[?#].*)?"
                       r"|spotify:collection(?::tracks)?|spotify:user:[\w.\-]+:collection)$", re.I)


def gated():
    """True while nothing external may happen (tests / headless runs)."""
    return (os.environ.get("HD_NO_EXTERNAL") == "1"
            or os.environ.get("SDL_VIDEODRIVER") == "dummy")


def _record(*call):
    CALLS.append(call)
    del CALLS[:-200]


# ------------------------------------------------------------------ status
class Status:
    """What Spotify is doing right now (immutable; the poller swaps it whole).

    ``ready``: the player window itself was found (default: = running). The
    process can be up with only its helper windows (starting up): running,
    not playing, not ready -- nothing is pressed until the window is there."""
    __slots__ = ("running", "playing", "artist", "title", "ready")

    def __init__(self, running=False, playing=False, artist="", title="", ready=None):
        self.running = bool(running)
        self.playing = bool(playing)
        self.artist = str(artist or "")
        self.title = str(title or "")
        self.ready = self.running if ready is None else bool(ready) and self.running

    @property
    def song(self):
        """(artist, title) while something is playing, else None."""
        return (self.artist, self.title) if self.playing and self.title else None

    def __eq__(self, o):
        return isinstance(o, Status) and all(getattr(self, k) == getattr(o, k)
                                             for k in self.__slots__)

    def __repr__(self):
        extra = "" if self.ready == self.running else f", ready={self.ready}"
        return (f"Status(running={self.running}, playing={self.playing}, "
                f"artist={self.artist!r}, title={self.title!r}{extra})")


NOT_RUNNING = Status()


def _norm(title):
    return " ".join(str(title or "").split())


def _junk(title):
    """A Spotify.exe helper window's title (never the player's)."""
    low = _norm(title).lower()
    return low in _JUNK_TITLES or low.startswith(_JUNK_PREFIX)


def _idle_title(title):
    low = _norm(title).lower()
    return low in IDLE_TITLES or (low.startswith("spotify") and " - " not in low)


def parse_title(title):
    """The Spotify window title -> Status (the app is running)."""
    t = _norm(title)
    if not t or _idle_title(t) or _junk(t):
        return Status(True, False)
    if " - " in t:                                   # "Artist - Song - Remastered"
        artist, song = t.split(" - ", 1)
        return Status(True, True, artist.strip(), song.strip())
    return Status(True, True, "", t)                 # an ad / a title without artist


# ------------------------------------------------------------------ links
def clean_uri(uri):
    """``uri`` if it is a harmless spotify: URI, else None (never shell-open
    anything else: the link comes from the clipboard / a save file)."""
    if not isinstance(uri, str):
        return None
    uri = uri.strip()
    if len(uri) > 200 or not _URI_RE.match(uri):
        return None
    return uri


def parse_link(text):
    """A pasted Spotify link -> app URI ("spotify:playlist:ID"), else None.
    Accepts open.spotify.com/<kind>/<id> (any ?si= tail, intl- prefix),
    spotify:<kind>:<id> and Liked Songs."""
    s = str(text or "").strip().strip("<>\"' ")
    if not s or len(s) > 400:
        return None
    if _LIKED_RE.match(s):
        return "spotify:collection:tracks"
    m = _APP_RE.match(s) or _WEB_RE.match(s)
    if m:
        return f"spotify:{m.group(1).lower()}:{m.group(2)}"
    return None


def link_kind(uri):
    """'Playlist' / 'Album' / ... / 'Liked Songs' for a URI from parse_link."""
    u = str(uri or "")
    if u.startswith("spotify:collection"):
        return "Liked Songs"
    for k in _KINDS:
        if u.startswith(f"spotify:{k}:"):
            return k.title()
    return "Link"


def web_url(uri):
    """The open.spotify.com page for an app URI (the browser fallback)."""
    u = clean_uri(uri) or "spotify:"
    if u.startswith("spotify:collection"):
        return "https://open.spotify.com/collection/tracks"
    parts = u.split(":")
    for i, p in enumerate(parts[:-1]):
        if p in _KINDS and parts[i + 1]:
            return f"https://open.spotify.com/{p}/{parts[i + 1]}"
    return "https://open.spotify.com/"


# ------------------------------------------------------------------ Windows glue
_W = None
_EXE = {}                   # pid -> (image name, when looked up)
_MAIN = [None]              # hwnd of the main Spotify window (last poll)


def _win():
    """ctypes handles with proper signatures (own WinDLL objects, so the
    shared ``ctypes.windll`` other code may use is left untouched)."""
    global _W
    if _W is None:
        import ctypes
        from ctypes import wintypes as T

        class _NS:
            pass
        w = _NS()
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        w.ctypes, w.T = ctypes, T
        w.WNDENUMPROC = ctypes.WINFUNCTYPE(T.BOOL, T.HWND, T.LPARAM)
        w.EnumWindows = u.EnumWindows
        w.EnumWindows.argtypes = [w.WNDENUMPROC, T.LPARAM]
        w.EnumWindows.restype = T.BOOL
        w.GetWindowThreadProcessId = u.GetWindowThreadProcessId
        w.GetWindowThreadProcessId.argtypes = [T.HWND, ctypes.POINTER(T.DWORD)]
        w.GetWindowThreadProcessId.restype = T.DWORD
        w.GetWindowTextLengthW = u.GetWindowTextLengthW
        w.GetWindowTextLengthW.argtypes = [T.HWND]
        w.GetWindowTextLengthW.restype = ctypes.c_int
        w.GetWindowTextW = u.GetWindowTextW
        w.GetWindowTextW.argtypes = [T.HWND, T.LPWSTR, ctypes.c_int]
        w.GetWindowTextW.restype = ctypes.c_int
        w.IsWindowVisible = u.IsWindowVisible
        w.IsWindowVisible.argtypes = [T.HWND]
        w.IsWindowVisible.restype = T.BOOL
        w.GetClassNameW = u.GetClassNameW
        w.GetClassNameW.argtypes = [T.HWND, T.LPWSTR, ctypes.c_int]
        w.GetClassNameW.restype = ctypes.c_int
        w.PostMessageW = u.PostMessageW
        w.PostMessageW.argtypes = [T.HWND, T.UINT, T.WPARAM, T.LPARAM]
        w.PostMessageW.restype = T.BOOL
        w.keybd_event = u.keybd_event
        w.keybd_event.argtypes = [T.BYTE, T.BYTE, T.DWORD, ctypes.c_size_t]
        w.keybd_event.restype = None
        w.OpenProcess = k.OpenProcess
        w.OpenProcess.argtypes = [T.DWORD, T.BOOL, T.DWORD]
        w.OpenProcess.restype = T.HANDLE
        w.QueryFullProcessImageNameW = k.QueryFullProcessImageNameW
        w.QueryFullProcessImageNameW.argtypes = [T.HANDLE, T.DWORD, T.LPWSTR,
                                                 ctypes.POINTER(T.DWORD)]
        w.QueryFullProcessImageNameW.restype = T.BOOL
        w.CloseHandle = k.CloseHandle
        w.CloseHandle.argtypes = [T.HANDLE]
        w.CloseHandle.restype = T.BOOL
        _W = w
    return _W


def _exe_name(pid):
    """Lower-case image name of process ``pid`` ("" if unknown), cached 30 s
    (a recycled pid can't pin a wrong name for long)."""
    now = time.monotonic()
    hit = _EXE.get(pid)
    if hit and now - hit[1] < 30.0:
        return hit[0]
    if len(_EXE) > 1024:
        _EXE.clear()
    name = ""
    w = _win()
    h = w.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        try:
            buf = w.ctypes.create_unicode_buffer(1024)
            n = w.T.DWORD(1024)
            if w.QueryFullProcessImageNameW(h, 0, buf, w.ctypes.byref(n)):
                name = os.path.basename(buf.value).lower()
        finally:
            w.CloseHandle(h)
    _EXE[pid] = (name, now)
    return name


def _spotify_windows():
    """[(hwnd, title, visible, class name)] for every top-level window of
    Spotify.exe."""
    w = _win()
    found = []

    def cb(hwnd, _lp):
        try:
            pid = w.T.DWORD(0)
            w.GetWindowThreadProcessId(hwnd, w.ctypes.byref(pid))
            if pid.value and _exe_name(pid.value) == "spotify.exe":
                n = w.GetWindowTextLengthW(hwnd)
                title = ""
                if n > 0:
                    buf = w.ctypes.create_unicode_buffer(n + 1)
                    w.GetWindowTextW(hwnd, buf, n + 1)
                    title = buf.value
                cbuf = w.ctypes.create_unicode_buffer(256)
                cls = cbuf.value if w.GetClassNameW(hwnd, cbuf, 256) > 0 else ""
                found.append((hwnd, title, bool(w.IsWindowVisible(hwnd)), cls))
        except Exception:
            pass
        return True
    w.EnumWindows(w.WNDENUMPROC(cb), 0)
    return found


def _status_from(wins):
    """Spotify's windows [(hwnd, title, visible[, class])] -> Status.

    Only the player window tells what plays. Helper windows (junk titles, or
    any other window whose title is neither "Artist - Song" nor an idle
    "Spotify ..." one) are skipped; of the rest the player's class wins, then
    visible before hidden (closed to the tray it still reports its song),
    then a readable title. Only helpers: the app is running (starting up)
    but not ready -- nothing plays and nothing may be pressed yet."""
    best, best_key, any_win = None, None, False
    for row in wins:
        hwnd, title, visible = row[0], _norm(row[1]), bool(row[2])
        main = len(row) > 3 and row[3] in MAIN_CLASSES
        any_win = True
        if not title or _junk(title):
            continue
        readable = " - " in title or _idle_title(title)
        if not (readable or main):
            continue                                 # an unknown helper window
        key = (main, visible, readable, " - " in title)
        if best_key is None or key > best_key:
            best, best_key = (hwnd, title), key
    if best is None:
        _MAIN[0] = None
        return Status(True, False, ready=False) if any_win else NOT_RUNNING
    _MAIN[0] = best[0]
    return parse_title(best[1])


def _registered():
    """Is a spotify: URL handler installed (desktop or Microsoft Store app)?"""
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "spotify"))
        return True
    except Exception:
        return False


# the four ways out of the game -- kept tiny so tests can swap them for spies
def _startfile(uri):
    os.startfile(uri)                                # type: ignore[attr-defined]


def _open_web(url):
    webbrowser.open(url)


def _key(vk):
    w = _win()
    w.keybd_event(vk, 0, 0x1, 0)                     # KEYEVENTF_EXTENDEDKEY
    w.keybd_event(vk, 0, 0x1 | 0x2, 0)               # ... | KEYEVENTF_KEYUP


def _post(hwnd, code):
    return bool(_win().PostMessageW(hwnd, 0x0319, hwnd, code << 16))   # WM_APPCOMMAND


# ------------------------------------------------------------------ public API
def now_playing():
    """Status of the Spotify desktop app on this PC. Never raises."""
    if gated():
        st = FAKE_STATUS
        return st if isinstance(st, Status) else NOT_RUNNING
    if sys.platform != "win32":
        return NOT_RUNNING
    try:
        return _status_from(_spotify_windows())
    except Exception:
        return NOT_RUNNING


def launch(uri=None):
    """Open Spotify (on ``uri`` when it's a valid spotify: link). "app" when
    the app was asked to open, "web" for the browser fallback, None on failure."""
    uri = clean_uri(uri) or "spotify:"
    if gated():
        _record("launch", uri)
        return "app"
    try:
        if sys.platform == "win32" and _registered():
            _startfile(uri)
            return "app"
    except Exception:
        pass
    try:
        _open_web(web_url(uri))
        return "web"
    except Exception:
        return None


def media(action):
    """Press a global media key ("play_pause" / "next" / "prev")."""
    vk = _VK.get(action)
    if vk is None:
        return False
    if gated():
        _record("media", action)
        return True
    if sys.platform != "win32":
        return False
    try:
        _key(vk)
        return True
    except Exception:
        return False


def app_command(action):
    """Send ``action`` to the Spotify window only (False: no window / failed)."""
    code = _APPCMD.get(action)
    if code is None:
        return False
    if gated():
        _record("app", action)
        return True
    if sys.platform != "win32":
        return False
    try:
        hwnd = _MAIN[0]
        if not hwnd:
            now_playing()
            hwnd = _MAIN[0]
        return bool(hwnd) and _post(hwnd, code)
    except Exception:
        return False


def clipboard_text():
    """Text on the clipboard ("" if none / unreadable)."""
    if gated():
        return str(FAKE_CLIPBOARD or "")
    try:
        import pygame
        if pygame.display.get_init() and hasattr(pygame.scrap, "get_text"):
            t = pygame.scrap.get_text()
            if t:
                return str(t)
    except Exception:
        pass
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes as T
        u = ctypes.WinDLL("user32")
        k = ctypes.WinDLL("kernel32")
        u.OpenClipboard.argtypes = [T.HWND]
        u.GetClipboardData.argtypes = [T.UINT]
        u.GetClipboardData.restype = T.HANDLE
        k.GlobalLock.argtypes = [T.HGLOBAL]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [T.HGLOBAL]
        if not u.OpenClipboard(None):
            return ""
        try:
            h = u.GetClipboardData(13)               # CF_UNICODETEXT
            if not h:
                return ""
            p = k.GlobalLock(h)
            if not p:
                return ""
            try:
                return ctypes.wstring_at(p)[:2000]
            finally:
                k.GlobalUnlock(h)
        finally:
            u.CloseClipboard()
    except Exception:
        return ""


# ------------------------------------------------------------------ the remote
class Remote:
    """One daemon thread that runs Spotify commands and polls the status.

    ``send(cmd, uri)`` queues: "start" (record player switched on: open the app
    if needed, then make it play; in browser mode it reopens the web player),
    "toggle" (play/pause; opens it if closed), "next", "prev", "open" (bring
    the app up on ``uri``), "pause" (switching off: pause only if playing).
    ``want(owner, on)``: poll while ANY owner wants it; the thread exits by
    itself once nobody does, the queue is empty and no pause is unconfirmed.

    Presses go to the Spotify window first; play/pause and next are then
    checked against the window title and repeated as the global media key if
    nothing changed within VERIFY_WAIT.
    """

    def __init__(self):
        self.status = NOT_RUNNING
        self.last_song = None          # (artist, title) last heard playing
        self.web = False               # the last launch fell back to the browser
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._q = []
        self._wants = set()
        self._thread = None
        self._busy = False
        self._next_poll = 0.0
        self._autoplay = None          # launch time while waiting to press play
        self._seen = None              # when the launched app's window showed up
        self._verify = None            # (action, was_playing, was_song, deadline)
        self._halt = None              # deadline: pause if a cancelled play still lands
        self._ignored = False          # a targeted press was ignored this session

    # ---- game side ----
    @property
    def alive(self):
        t = self._thread
        return t is not None and t.is_alive()

    @property
    def launching(self):
        """True while a launched app is starting up (-> "Opening Spotify...")."""
        return self._autoplay is not None

    def want(self, owner, on):
        with self._lock:
            if on:
                self._wants.add(owner)
            else:
                self._wants.discard(owner)
            run = bool(self._wants)
        if run:
            self._ensure()

    def send(self, cmd, uri=None):
        with self._lock:
            self._q.append((cmd, uri))
        self._ensure()
        self._wake.set()

    def poke(self):
        """Poll again right away instead of waiting for the next tick."""
        self._next_poll = 0.0
        self._wake.set()

    def flush(self, timeout=1.0):
        """Wait until every queued command ran (tests). True when idle."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                idle = not self._q and not self._busy
            if idle:
                return True
            time.sleep(0.005)
        return False

    def join(self, timeout=1.0):
        """Wait for the thread to exit (tests). True when it has."""
        t = self._thread
        if t is not None:
            t.join(timeout)
        return not self.alive

    def _pausing(self):
        """A pause is still being checked, or a cancelled play may still land
        (the thread must see it through, even once nobody wants the status:
        switching off must really stop the music)."""
        v = self._verify
        return (v is not None and v[0] == "play_pause" and v[1]) or self._halt is not None

    def _ensure(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._next_poll = 0.0
            self._thread = threading.Thread(target=self._run, name="spotify-remote",
                                            daemon=True)
            self._thread.start()

    # ---- worker ----
    def _run(self):
        idle = time.monotonic()
        while True:
            with self._lock:
                now = time.monotonic()
                if self._wants or self._q or self._pausing():
                    idle = now
                elif now - idle > LINGER:
                    self._thread = None        # nobody listening: stop polling
                    self._autoplay = self._verify = self._halt = None
                    return
                job = self._q.pop(0) if self._q else None
                self._busy = job is not None
            try:
                if job is not None:
                    self._do(*job)
                if time.monotonic() >= self._next_poll:
                    self._poll()
            except Exception:
                pass
            finally:
                with self._lock:
                    self._busy = False
            if job is None:
                self._wake.wait(0.1)
                self._wake.clear()

    def _poll(self):
        now = time.monotonic()
        st = now_playing()
        self.status = st
        if st.running:
            self.web = False
        if st.song:
            self.last_song = st.song
        if self._autoplay is not None:               # waiting for a launched app
            if st.playing:
                self._autoplay = None
            elif st.ready:                           # its player window is up
                if self._seen is None:
                    self._seen = now
                if now - self._seen >= AUTOPLAY_SETTLE:
                    self._autoplay = None
                    self._press("play_pause", st)
            elif now - self._autoplay > LAUNCH_WAIT:
                self._autoplay = None
        if self._halt is not None:                   # switched off right after a play
            if st.playing:
                self._halt = None
                self._verify = None
                self._press("play_pause", st)        # it started anyway: pause it
            elif now >= self._halt or not st.running:
                self._halt = None
        v = self._verify
        if v is not None:                            # did the window take the press?
            action, was_playing, was_song, deadline = v
            landed = (st.playing != was_playing if action == "play_pause"
                      else st.song != was_song)
            if landed or not st.running:
                self._verify = None
            elif now >= deadline:
                self._verify = None
                self._ignored = True
                media(action)                        # fall back to the global key
        fast = self._autoplay is not None or self._verify is not None or self._halt is not None
        self._next_poll = now + (FAST_POLL if fast else POLL_EVERY)

    def _do(self, cmd, uri=None):
        st = now_playing()
        self.status = st
        if cmd != "pause":
            self._halt = None                        # switched on again: let it play
        if cmd in ("start", "toggle"):
            if st.ready:
                if cmd == "toggle" or not st.playing:
                    self._press("play_pause", st)
            elif self.web and cmd == "toggle" and not st.running:
                media("play_pause")                  # the browser player
            elif self._autoplay is None:             # (browser: switching on reopens it;
                self._launch(uri, autoplay=True)     #  helpers only: bring the window up)
        elif cmd == "open":
            self._launch(uri, autoplay=not st.ready)
        elif cmd in ("next", "prev"):
            if st.running:
                self._press(cmd, st)
            elif self.web:
                media(cmd)
        elif cmd == "pause":
            self._autoplay = None
            if not self._pausing():
                # an unconfirmed play / skip must not fire its fallback key
                # later (that could start the music again); a pause already
                # on its way is left alone (pressing twice would resume)
                v, self._verify = self._verify, None
                if st.running and st.playing:
                    self._press("play_pause", st)
                elif v is not None and v[0] == "play_pause" and not v[1]:
                    # a play press the title doesn't show yet: if it still
                    # lands within VERIFY_WAIT, pause it then (once)
                    self._halt = time.monotonic() + VERIFY_WAIT
        self._next_poll = time.monotonic() + AFTER_CMD

    def _launch(self, uri, autoplay):
        how = launch(uri)
        self.web = how == "web"
        if how == "app" and autoplay:
            self._autoplay, self._seen = time.monotonic(), None

    def _press(self, action, st):
        if gated() or sys.platform != "win32":
            media(action)
            return
        if action == "prev" and self._ignored:
            media(action)                            # the window ignores us: global key
            return
        if app_command(action):
            # Check that the window took it (the title changes) and fall back
            # to the global key if not. Never for "prev": more than ~3 s into
            # a song Spotify restarts it (same title), which a check would take
            # for a miss -> a second, unwanted skip back.
            if action == "play_pause" or (action == "next" and st.song):
                self._verify = (action, st.playing, st.song,
                                time.monotonic() + VERIFY_WAIT)
        else:
            media(action)


REMOTE = Remote()
