#!/usr/bin/env python3
"""Phase 0 — one-shot rescue of editor drafts stranded in browser localStorage.

localStorage is partitioned by ORIGIN (scheme + host + port), so drafts written while the
judge served 127.0.0.1:5000 are invisible to the judge now serving 127.0.0.1:5137. This
script serves the same tiny page on BOTH ports at once; visiting each one lets the browser
hand back that origin's storage.

    python3 rescue_drafts.py            # serves 5000 + 5137
    python3 rescue_drafts.py 5000 5137 8080

Everything captured is merged into app/data/rescued_drafts.json, keyed by origin. Re-running
is safe: existing entries are only overwritten by a LONGER version of the same key, so a
second visit can never shrink what you already rescued.

Throwaway tool. Delete once Phase 1 has imported the JSON.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "app", "data", "rescued_drafts.json")
_lock = threading.Lock()

PAGE = """<!doctype html>
<meta charset="utf-8"><title>OA Judge — Draft Rescue</title>
<style>
  :root { color-scheme: dark; }
  body { background:#16171d; color:#e6e6ec; font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;
         margin:0; display:flex; align-items:center; justify-content:center; min-height:100vh; padding:24px; }
  .card { background:#1e2029; border:1px solid #31344a; border-radius:14px; padding:28px 32px;
          max-width:620px; width:100%; box-shadow:0 12px 40px #0008; }
  h1 { margin:0 0 4px; font-size:19px; }
  .origin { font-family:ui-monospace,Consolas,monospace; color:#8be9fd; font-size:13px; margin-bottom:18px; }
  button { background:#6272e0; color:#fff; border:0; border-radius:9px; padding:11px 20px;
           font-size:15px; font-weight:600; cursor:pointer; }
  button:hover { background:#7181ef; }
  button:disabled { background:#3a3d4e; cursor:default; }
  #out { margin-top:18px; font-size:13.5px; }
  .ok { color:#50fa7b; } .warn { color:#ffb86c; } .err { color:#ff5555; }
  ul { margin:10px 0 0; padding-left:20px; max-height:230px; overflow:auto; }
  li { font-family:ui-monospace,Consolas,monospace; font-size:12.5px; color:#c8c9d4; }
  .hint { margin-top:16px; font-size:13px; color:#9296a8; border-top:1px solid #31344a; padding-top:14px; }
</style>
<div class="card">
  <h1>Draft Rescue</h1>
  <div class="origin" id="origin"></div>
  <button id="go">Rescue drafts from this origin</button>
  <div id="out"></div>
  <div class="hint">Visit this page once on <b>every</b> port the judge has ever used
    (5000 and 5137), then close both tabs.</div>
</div>
<script>
document.getElementById('origin').textContent = location.origin;
document.getElementById('go').onclick = async function () {
  var btn = this, out = document.getElementById('out');
  btn.disabled = true;
  var items = {};
  for (var i = 0; i < localStorage.length; i++) {
    var k = localStorage.key(i);
    items[k] = localStorage.getItem(k);
  }
  var n = Object.keys(items).length;
  if (n === 0) {
    out.innerHTML = '<span class="warn">No localStorage on this origin — nothing to rescue here. '
                  + 'That is expected if you never used the judge on this port.</span>';
    btn.disabled = false;
    return;
  }
  try {
    var res = await fetch('/rescue-save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin: location.origin, items: items })
    });
    var j = await res.json();
    var list = Object.keys(items).sort().map(function (k) {
      return '<li>' + k.replace(/[<>&]/g, '') + '  —  ' + (items[k] || '').length + ' chars</li>';
    }).join('');
    out.innerHTML = '<span class="ok">Saved ' + n + ' key(s) ('
                  + j.total_chars + ' chars) to app/data/rescued_drafts.json</span><ul>' + list + '</ul>';
  } catch (e) {
    out.innerHTML = '<span class="err">Failed: ' + e + '</span>';
    btn.disabled = false;
  }
};
</script>
"""


def _merge(origin: str, items: dict) -> int:
    """Merge into the JSON on disk. A key is only replaced by a LONGER value, so re-running
    (or visiting after an accidental Reset) can never destroy a bigger rescued draft."""
    with _lock:
        data = {}
        if os.path.exists(OUT_PATH):
            try:
                with open(OUT_PATH, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}
        bucket = data.setdefault(origin, {})
        for k, v in items.items():
            old = bucket.get(k)
            if old is None or len(v or "") >= len(old or ""):
                bucket[k] = v
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        tmp = OUT_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, OUT_PATH)  # atomic
        return sum(len(v or "") for v in bucket.values())


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._send(200, PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/rescue-save":
            self._send(404, "{}", "application/json")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            origin = payload.get("origin") or "unknown"
            items = payload.get("items") or {}
            total = _merge(origin, items)
            print(f"  [rescued] {origin}: {len(items)} key(s), {total} chars total")
            self._send(200, json.dumps({"ok": True, "total_chars": total}), "application/json")
        except Exception as e:  # noqa: BLE001 - throwaway tool, report and keep serving
            print(f"  [error] {e}")
            self._send(500, json.dumps({"ok": False, "error": str(e)}), "application/json")

    def log_message(self, *args):
        pass  # quiet; we print our own lines


def serve(port: int):
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except OSError as e:
        print(f"  !! port {port} unavailable ({e}) — is the judge still running on it?")


if __name__ == "__main__":
    ports = [int(a) for a in sys.argv[1:]] or [5000, 5137]
    print("OA Judge — draft rescue. Open EACH of these in the browser you code in:\n")
    for p in ports:
        print(f"    http://127.0.0.1:{p}/")
        threading.Thread(target=serve, args=(p,), daemon=True).start()
    print(f"\nClick the button on each page. Results merge into:\n    {OUT_PATH}")
    print("\nCtrl+C here when both are done.\n")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopped.")
