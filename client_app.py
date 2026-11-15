import os
import sys
import threading

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass

import webview

from agent_umimiy import config, discovery

LOADING_HTML = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>RMS AI — Ofis Mijozi</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; font-family: "Segoe UI", system-ui, sans-serif; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: radial-gradient(circle at top, #182235, #0b101b 70%);
    color: #e6edf7;
  }
  .card {
    width: min(460px, 92vw); padding: 28px; border-radius: 18px;
    background: rgba(20, 29, 46, 0.92); border: 1px solid rgba(148, 163, 184, 0.22);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
  }
  h1 { margin: 0 0 8px; font-size: 20px; font-weight: 650; }
  p { margin: 0 0 18px; color: #9fb0c7; font-size: 14px; line-height: 1.5; }
  .row { display: flex; gap: 10px; align-items: center; }
  .spinner {
    width: 18px; height: 18px; border-radius: 50%;
    border: 2.5px solid rgba(96, 165, 250, 0.25); border-top-color: #60a5fa;
    animation: spin 0.8s linear infinite; flex: none;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hidden { display: none; }
  input {
    flex: 1; padding: 10px 12px; border-radius: 10px; font-size: 14px;
    border: 1px solid rgba(148, 163, 184, 0.3); background: #0d1422; color: #fff;
  }
  button {
    padding: 10px 16px; border-radius: 10px; border: 0; cursor: pointer;
    background: #2563eb; color: #fff; font-weight: 600; font-size: 14px;
  }
  button:hover { background: #1d4ed8; }
  .err { color: #fca5a5; font-size: 13px; margin-top: 10px; min-height: 18px; }
  .mt { margin-top: 14px; }
</style>
</head>
<body>
  <div class="card">
    <h1>RMS AI</h1>
    <div id="searching" class="row">
      <div class="spinner"></div>
      <p style="margin:0">Ofis serveri avtomatik qidirilmoqda...</p>
    </div>
    <div id="offline" class="hidden">
      <p>Ofis tarmog‘ida <b>RMS AI</b> serveri topilmadi. Asosiy kompyuterda dastur yoqilganini va tarmoq rejimi ochiqligini tekshiring.</p>
      <div class="row">
        <button onclick="retry()">Qayta qidirish</button>
      </div>
      <div class="row mt">
        <input id="manualUrl" placeholder="http://192.168.1.50:8080" />
        <button onclick="connectManual()">Ulanish</button>
      </div>
      <div id="err" class="err"></div>
    </div>
  </div>
  <script>
    function showSearching() {
      document.getElementById("searching").classList.remove("hidden");
      document.getElementById("offline").classList.add("hidden");
      document.getElementById("err").textContent = "";
    }
    function showOffline(msg) {
      document.getElementById("searching").classList.add("hidden");
      document.getElementById("offline").classList.remove("hidden");
      if (msg) document.getElementById("err").textContent = msg;
    }
    async function retry() {
      showSearching();
      const ok = await window.pywebview.api.retry();
      if (!ok) showOffline("Server javob bermadi.");
    }
    async function connectManual() {
      const val = document.getElementById("manualUrl").value.trim();
      if (!val) return;
      showSearching();
      const res = await window.pywebview.api.connect_manual(val);
      if (!res.ok) showOffline(res.error || "Ulanib bo‘lmadi.");
    }
  </script>
</body>
</html>"""


class ClientApi:
    def __init__(self) -> None:
        self.window = None

    def _connect_found(self, info: dict | None) -> bool:
        if not info or not self.window:
            return False
        url = info["url"]
        key = str(info.get("client_key", "")).strip()
        if key:
            url = url.rstrip("/") + f"/client-enter?key={key}"
        self.window.load_url(url)
        return True

    def auto_connect(self) -> None:
        info = discovery.resolve_server(timeout=2.0)
        if not self._connect_found(info) and self.window:
            self.window.evaluate_js("showOffline('')")

    def retry(self) -> bool:
        info = discovery.resolve_server(timeout=2.0)
        return self._connect_found(info)

    def connect_manual(self, raw_url: str) -> dict:
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        if not url.endswith("/"):
            url += "/"
        if discovery.probe_url(url, timeout=1.5):
            info = {"url": url, "ip": "", "port": 8080, "host": ""}
            discovery.save_cached_server(info)
            self._connect_found(info)
            return {"ok": True}
        return {"ok": False, "error": f"{url} manziliga ulanib bo‘lmadi."}


def main() -> None:
    api = ClientApi()
    storage = config.user_dir() / "client-webview"
    storage.mkdir(parents=True, exist_ok=True)
    window = webview.create_window(
        "RMS AI — Ofis Mijozi",
        html=LOADING_HTML,
        width=1280,
        height=820,
        js_api=api,
    )
    api.window = window

    def on_loaded() -> None:
        threading.Thread(target=api.auto_connect, daemon=True).start()

    webview.start(on_loaded, private_mode=False, storage_path=str(storage))


if __name__ == "__main__":
    main()
