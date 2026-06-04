"""Servidor local do painel TrendFit — http://localhost:5000/dashboard

Serve reports/dashboard.html (mantido fresco pelo agendador 9h/21h). Rotas:
  /  ou /dashboard  -> o painel
  /refresh          -> regenera o painel sob demanda (roda scripts/dashboard.py) e volta
  /health           -> 'ok' (pro launchd/checagem)

Sem dependência externa (http.server da stdlib). Porta via env TRENDFIT_PORT (default 5000).
"""

from __future__ import annotations

import http.server
import os
import socketserver
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "reports" / "dashboard.html"
GEN = ROOT / "scripts" / "dashboard.py"
PORT = int(os.environ.get("TRENDFIT_PORT", "5000"))


def regenerate() -> None:
    try:
        subprocess.run([sys.executable, str(GEN)], cwd=str(ROOT), timeout=600, check=False)
    except Exception:  # noqa: BLE001
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes = b"", ctype: str = "text/html; charset=utf-8",
              headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in ("/", "/dashboard"):
            if not HTML.exists():
                regenerate()
            body = HTML.read_bytes() if HTML.exists() else b"<h1>Gerando painel... recarregue em instantes.</h1>"
            self._send(200, body)
        elif path == "/refresh":
            regenerate()
            self._send(302, headers={"Location": "/dashboard"})
        elif path == "/health":
            self._send(200, b"ok", "text/plain; charset=utf-8")
        else:
            self._send(404, b"404 - use /dashboard", "text/plain; charset=utf-8")

    def log_message(self, *args):  # silencioso
        return


def main() -> int:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        print(f"[serve] porta {PORT} ocupada ({exc}). Rode com TRENDFIT_PORT=8787, por ex.")
        return 1
    print(f"[serve] painel em http://localhost:{PORT}/dashboard  (/refresh pra atualizar)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
