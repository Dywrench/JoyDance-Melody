import socket
import struct
import threading
import time
import zlib

# (índice del eje DSU, signo) para x, y, z que se entregan al juego.
# Si el movimiento sale mal en el juego, prueba ((0, 1), (1, -1), (2, -1)).
AXIS_MAP = ((0, 1.0), (1, 1.0), (2, 1.0))


def _request_packet():
    body = struct.pack("<I", 0x100002) + bytes([0, 0]) + bytes(6)
    pkt = (b"DSUC" + struct.pack("<HH", 1001, len(body)) + b"\x00" * 4
           + struct.pack("<I", 1234) + body)
    crc = zlib.crc32(pkt) & 0xFFFFFFFF
    return pkt[:8] + struct.pack("<I", crc) + pkt[12:]


class DSUJoyCon:
    """Adaptador de movimiento DSU (Joy2Win) para JoyDance."""

    def __init__(self, is_left=False, host="127.0.0.1", port=26760):
        self._is_left = is_left
        self.serial = "DSU_LEFT" if is_left else "DSU_RIGHT"
        self._addr = (host, port)
        self._latest = (0.0, 0.0, 1.0)
        self._last_out = self._latest
        self._last_update = 0.0
        self._lock = threading.Lock()
        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.settimeout(0.5)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        packet = _request_packet()
        last_req = 0.0
        while self._running:
            now = time.time()
            if now - last_req > 1.0:
                try:
                    self._socket.sendto(packet, self._addr)
                except OSError:
                    pass
                last_req = now
            try:
                data, _ = self._socket.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                if not self._running:
                    break
                time.sleep(0.05)
                continue
            if (len(data) >= 100 and data[:4] == b"DSUS"
                    and struct.unpack_from("<I", data, 16)[0] == 0x100002):
                raw = struct.unpack_from("<3f", data, 76)
                mapped = tuple(raw[i] * s for i, s in AXIS_MAP)
                with self._lock:
                    self._latest = mapped
                    self._last_update = time.time()

    def is_left(self):
        return self._is_left

    def get_accels(self):
        with self._lock:
            target = self._latest
        prev = self._last_out
        self._last_out = target
        return [
            tuple(p + (t - p) * k / 3 for p, t in zip(prev, target))
            for k in (1, 2, 3)
        ]

    def events(self):
        return iter(())

    def get_status(self):
        return {
            "battery": {"charging": False, "level": 4},
            "buttons": {},
            "analog-sticks": {
                "left": {"vertical": 0.0, "horizontal": 0.0},
                "right": {"vertical": 0.0, "horizontal": 0.0},
            },
        }

    def close(self):
        self._running = False
        try:
            self._socket.close()
        except OSError:
            pass