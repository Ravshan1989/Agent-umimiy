from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DISCOVERY_PORT = 48080
DISCOVERY_MAGIC = b"RMS_AI_DISCOVER_V1"


def _client_cache_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "RMSAIClient" / "server.json"


def load_cached_server(cache_path: Path | None = None) -> dict | None:
    p = cache_path or _client_cache_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("url"):
            return data
    except Exception:
        pass
    return None


def save_cached_server(info: dict, cache_path: Path | None = None) -> None:
    p = cache_path or _client_cache_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def probe_url(url: str, timeout: float = 0.9) -> bool:
    """Return True if an RMS AI HTTP server responds at url."""
    target = url.rstrip("/") + "/"
    try:
        req = urllib.request.Request(target, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except urllib.error.HTTPError as exc:
        return 200 <= exc.code < 500
    except Exception:
        return False


class DiscoveryResponder:
    """UDP LAN responder so office clients find the server IP automatically."""

    def __init__(self, http_port: int, discovery_port: int = DISCOVERY_PORT, client_key: str = ""):
        self.http_port = int(http_port)
        self.discovery_port = int(discovery_port)
        self.client_key = client_key
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", self.discovery_port))
        sock.settimeout(0.4)
        self._sock = sock
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        import hashlib
        server_id = hashlib.sha256(
            f"{socket.gethostname()}:{self.http_port}".encode()
        ).hexdigest()[:16]
        payload = json.dumps(
            {
                "service": "rms-ai",
                "port": self.http_port,
                "host": socket.gethostname(),
                "server_id": server_id,
            }
        ).encode("utf-8")
        while not self._stop.is_set() and self._sock:
            try:
                data, addr = self._sock.recvfrom(1024)
            except TimeoutError:
                continue
            except OSError:
                break
            if data.strip() == DISCOVERY_MAGIC:
                try:
                    self._sock.sendto(payload, addr)
                except OSError:
                    pass

    def stop(self) -> None:
        self._stop.set()
        sock, self._sock = self._sock, None
        if sock:
            try:
                sock.close()
            except OSError:
                pass


def discover_server(timeout: float = 1.8, discovery_port: int = DISCOVERY_PORT) -> dict | None:
    """Broadcast a discovery packet and return the first responding RMS AI server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", 0))
        targets = ["255.255.255.255", "127.0.0.1"]
        for target in targets:
            try:
                sock.sendto(DISCOVERY_MAGIC, (target, discovery_port))
            except OSError:
                pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            sock.settimeout(min(0.4, remaining))
            try:
                raw, addr = sock.recvfrom(2048)
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                info = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if isinstance(info, dict) and info.get("service") == "rms-ai" and info.get("port"):
                ip = addr[0]
                port = int(info["port"])
                return {
                    "ip": ip,
                    "port": port,
                    "host": str(info.get("host", "")),
                    "url": f"http://{ip}:{port}/",
                    "server_id": str(info.get("server_id", "")),
                }
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return None


def resolve_server(
    timeout: float = 1.8,
    discovery_port: int = DISCOVERY_PORT,
    cache_path: Path | None = None,
) -> dict | None:
    """Discover the office server via UDP broadcast, falling back to cached host/URL."""
    found = discover_server(timeout=timeout, discovery_port=discovery_port)
    cached = load_cached_server(cache_path=cache_path)
    if found:
        if cached and cached.get("server_id") and found.get("server_id") and cached["server_id"] != found["server_id"]:
            return {**found, "mismatch": True}
        if cached and cached.get("client_key"):
            found["client_key"] = cached["client_key"]
        save_cached_server(found, cache_path=cache_path)
        return found

    if not cached:
        return None

    host = str(cached.get("host", "")).strip()
    port = int(cached.get("port", 8080) or 8080)
    if host:
        try:
            ip = socket.gethostbyname(host)
            url = f"http://{ip}:{port}/"
            if probe_url(url):
                updated = {"ip": ip, "port": port, "host": host, "url": url}
                save_cached_server(updated, cache_path=cache_path)
                return updated
        except OSError:
            pass

    url = str(cached.get("url", "")).strip()
    if url and probe_url(url):
        return cached
    return None
