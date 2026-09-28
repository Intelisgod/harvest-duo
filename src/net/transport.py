"""Threaded, non-blocking TCP transport for a single host <-> single client link.

Both ``Host`` and ``Client`` run their socket I/O on a background daemon thread
and expose the same tiny game-loop API:

    poll()        -> list of decoded messages received since the last poll
    send(obj)     -> queue/transmit a message (best-effort, never blocks the loop)
    connected     -> bool, flips True once the link is up, False if it drops
    error         -> last error string (None if healthy)
    close()       -> tear everything down

The game loop just calls poll() and send() each frame; the thread handles
accept/connect/recv. Designed for LAN where one peer hosts and one joins.
"""
import collections
import socket
import threading
import time

from .protocol import pack, Reader

PORT = 50573                      # default LAN port for Harvest Duo

# Outbound backlog policy. send() never touches the socket: frames go onto a
# per-link queue that a sender thread drains, so a peer that stops reading
# (laptop asleep, Wi-Fi gone without a FIN, a long GC / window-drag stall) can
# never block the game loop.
_BACKLOG_MAX = 256 * 1024         # past this, stale 'snap' / older 'world' frames are dropped
_STALL_S = 5.0                    # backlog not draining this long -> drop the link
_TICK = 0.25                      # socket timeout: how often the I/O threads re-check state
_INBOX_MAX = 600                  # inbound cap if the game loop stops polling
# only the newest of these matters -- older queued copies are safe to drop
_LATEST_ONLY = ("snap", "world")


class _Link:
    """Shared receive-buffer + outbound send logic for both ends."""

    def __init__(self):
        self._reader = Reader()
        self._inbox = []
        self._lock = threading.Lock()
        self._conn = None             # the active connected socket
        self.connected = False
        self.error = None
        self._run = True
        self._out = collections.deque()      # [(kind, bytes)] not yet started
        self._out_bytes = 0
        self._out_cv = threading.Condition()
        self._busy = False                   # the sender is mid-frame
        self._progress_t = time.monotonic()  # last time bytes left (or queue idle)

    # ---- background recv loop (runs on the worker thread) ----
    def _pump(self, conn):
        with self._out_cv:
            self._out.clear()
            self._out_bytes = 0
            self._busy = False
            self._progress_t = time.monotonic()
        self._conn = conn
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        try:
            conn.settimeout(_TICK)    # both threads wake up to re-check state
        except Exception:
            pass
        self.connected = True
        threading.Thread(target=self._send_loop, args=(conn,), daemon=True).start()
        try:
            while self._run:
                if self._stalled():
                    self.error = "peer not responding"
                    break
                try:
                    data = conn.recv(262144)
                except socket.timeout:
                    continue
                if not data:
                    break             # peer closed
                self._reader.feed(data)
                msgs = self._reader.messages()
                if msgs:
                    with self._lock:
                        self._inbox.extend(msgs)
                        if len(self._inbox) > _INBOX_MAX:
                            self._inbox = _trim_inbox(self._inbox)
        except Exception as e:
            if self._run and self.error != "peer not responding":
                self.error = str(e)
        finally:
            self.connected = False
            with self._out_cv:
                self._out.clear()
                self._out_bytes = 0
                self._out_cv.notify_all()

    def _stalled(self):
        with self._out_cv:
            pending = self._busy or bool(self._out)
            return pending and time.monotonic() - self._progress_t > _STALL_S

    # ---- background send loop (one per connection) ----
    def _send_loop(self, conn):
        while self._run and self._conn is conn and self.connected:
            with self._out_cv:
                if not self._out:
                    self._progress_t = time.monotonic()      # idle is not a stall
                    self._out_cv.wait(_TICK)
                    continue
                _kind, data = self._out.popleft()
                self._out_bytes -= len(data)
                self._busy = True
            mv = memoryview(data)
            try:
                while mv and self._run and self._conn is conn and self.connected:
                    try:
                        n = conn.send(mv)
                    except socket.timeout:
                        continue           # buffer full: _pump decides when to give up
                    if n:
                        mv = mv[n:]
                        with self._out_cv:
                            self._progress_t = time.monotonic()
            except Exception as e:
                if self._run and self._conn is conn:
                    self.error = self.error or str(e)
                    self.connected = False
                    try:
                        conn.shutdown(socket.SHUT_RDWR)      # wake the recv loop
                    except Exception:
                        pass
                return
            finally:
                with self._out_cv:
                    self._busy = False

    # ---- game-loop API ----
    def poll(self):
        with self._lock:
            if not self._inbox:
                return []
            msgs = self._inbox
            self._inbox = []
        return msgs

    def send(self, obj):
        """Queue one message; never blocks the game loop."""
        if self._conn is None or not self.connected:
            return
        try:
            data = pack(obj)
        except Exception as e:
            self.error = str(e)
            return
        kind = obj.get("t") if isinstance(obj, dict) else None
        with self._out_cv:
            if self._out_bytes + len(data) > _BACKLOG_MAX:
                self._drop_stale(kind)
                if kind == "snap" and self._out_bytes + len(data) > _BACKLOG_MAX:
                    return                 # a newer snapshot follows in 1/30 s
            self._out.append((kind, data))
            self._out_bytes += len(data)
            self._out_cv.notify()

    def _drop_stale(self, incoming):
        """Backlog full: drop queued frames a newer copy supersedes (every
        'snap'; every 'world' but the newest). Toasts, inputs and menu ops are
        always kept."""
        worlds = sum(1 for k, _ in self._out if k == "world") + (incoming == "world")
        keep = collections.deque()
        size = 0
        for k, d in self._out:
            if k == "snap":
                continue
            if k == "world" and worlds > 1:
                worlds -= 1
                continue
            keep.append((k, d))
            size += len(d)
        self._out = keep
        self._out_bytes = size

    def backlog(self):
        """Bytes queued but not yet handed to the socket (for tests / HUD)."""
        with self._out_cv:
            return self._out_bytes

    def close(self):
        self._run = False
        self.connected = False
        for s in (self._conn, getattr(self, "_listen", None)):
            try:
                if s:
                    s.close()
            except Exception:
                pass
        with self._out_cv:
            self._out.clear()
            self._out_bytes = 0
            self._out_cv.notify_all()


def _trim_inbox(msgs):
    """Inbound cap: keep only the newest 'snap' / 'world' (older copies are
    superseded) and every other message; hard cap the rest, oldest first."""
    last = {}
    for i, m in enumerate(msgs):
        k = m.get("t") if isinstance(m, dict) else None
        if k in _LATEST_ONLY:
            last[k] = i
    out = [m for i, m in enumerate(msgs)
           if not (isinstance(m, dict) and m.get("t") in _LATEST_ONLY)
           or last.get(m.get("t")) == i]
    return out[-_INBOX_MAX:]


class Host(_Link):
    """Listens for one client and serves it. Non-blocking to the game loop."""

    def __init__(self, port=PORT):
        super().__init__()
        self.port = port
        self._listen = None
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        try:
            ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            ls.bind(("0.0.0.0", self.port))
            ls.listen(1)
            self._listen = ls
            # serve clients one after another: after a drop (game closed, Wi-Fi
            # hiccup) the partner can simply join again
            while self._run:
                conn, _addr = ls.accept()      # blocks until the client joins
                self._reader = Reader()        # never splice two streams together
                self.error = None
                try:
                    self._pump(conn)
                finally:
                    self._conn = None
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception as e:
            if self._run:
                self.error = str(e)
            self.connected = False


class Client(_Link):
    """Connects out to a host's IP:port."""

    def __init__(self, ip, port=PORT, timeout=8.0):
        super().__init__()
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((self.ip, self.port))
            s.settimeout(None)
            self._pump(s)
            if self._run and not self.error:
                self.error = "the host closed the connection"
        except Exception as e:
            if self._run:
                self.error = str(e)
            self.connected = False
        finally:
            if s is not None and self._run:
                try:
                    s.close()             # a dropped link never lingers half-open
                except Exception:
                    pass


def local_ip():
    """Best-effort LAN IP of this machine (for the host to show the joiner)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))            # no packets actually sent
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
