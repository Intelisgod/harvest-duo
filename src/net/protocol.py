"""Wire protocol: each message is a 4-byte big-endian length prefix followed by
a UTF-8 JSON body. Tiny, dependency-free, and easy to debug.

``pack(obj)`` -> bytes ready to send. ``Reader`` accumulates raw bytes from a
stream and yields complete decoded messages, tolerating partial reads (TCP may
split or coalesce sends).
"""
import json
import struct

_HDR = struct.Struct(">I")
MAX_MSG = 8 * 1024 * 1024          # 8 MB sanity cap so a bad length can't OOM us


def pack(obj):
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return _HDR.pack(len(body)) + body


class Reader:
    """Feed it raw bytes; call messages() to drain complete frames."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data

    def messages(self):
        out = []
        while len(self.buf) >= 4:
            n = _HDR.unpack_from(self.buf, 0)[0]
            if n > MAX_MSG:                 # corrupt stream -- drop everything
                self.buf.clear()
                break
            if len(self.buf) < 4 + n:
                break                        # wait for the rest of the body
            body = bytes(self.buf[4:4 + n])
            del self.buf[:4 + n]
            try:
                out.append(json.loads(body.decode("utf-8")))
            except Exception:
                pass                         # skip a single malformed frame
        return out
