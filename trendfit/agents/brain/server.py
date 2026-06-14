"""Buffett Brain como microsserviço HTTP (opcional, stdlib).

Expõe o contrato estável do Brain por HTTP, pra quando ele rodar desacoplado do
cockpit (a visão de 'second brain microsserviço' do Bruno). O uso embedded
(import direto) segue sendo o default; este servidor é a porta de rede.

Endpoints:
  GET  /health              -> {"status": "ok"}
  POST /recall  {"query"}   -> BrainResult.to_dict()  (princípios + literatura + teses)

Uso: python -m trendfit.agents.brain.server [porta]   (default 8765)

LINHA VERMELHA: o Brain INFORMA julgamento. Nunca aciona sinal nem alimenta o engine.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from trendfit.agents.brain import BuffettBrain

_BRAIN: BuffettBrain | None = None


def get_brain() -> BuffettBrain:
    """Instancia o Brain uma vez (lazy) — indexa o RAG na 1ª chamada."""
    global _BRAIN
    if _BRAIN is None:
        _BRAIN = BuffettBrain()
    return _BRAIN


def _handle_recall(body: bytes) -> tuple[int, dict]:
    """Lógica pura do /recall (testável sem socket). Retorna (status, payload)."""
    try:
        data = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return 400, {"error": "JSON inválido"}
    query = (data.get("query") or "").strip() if isinstance(data, dict) else ""
    if not query:
        return 400, {"error": "campo 'query' obrigatório"}
    try:
        return 200, get_brain().recall(query).to_dict()
    except Exception as exc:  # nunca derruba o servidor por causa de uma consulta
        return 500, {"error": f"falha no recall: {exc}"}


class BrainHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "rota não encontrada"})

    def do_POST(self) -> None:
        if self.path != "/recall":
            self._send(404, {"error": "rota não encontrada"})
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        status, payload = _handle_recall(self.rfile.read(length))
        self._send(status, payload)

    def log_message(self, *args) -> None:  # silencia o log padrão (ruidoso)
        pass


def serve(port: int = 8765) -> None:
    server = HTTPServer(("127.0.0.1", port), BrainHandler)
    print(f"[brain] microsserviço em http://127.0.0.1:{port} (POST /recall, GET /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
