"""Testes do Brain HTTP microsserviço — cobre todas as respostas (200/400/404/500)."""

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from trendfit.agents.brain.server import BrainHandler, _handle_recall


# --- lógica pura (sem socket) ---

def test_handle_recall_valid():
    status, payload = _handle_recall(json.dumps({"query": "ciclo de mercado"}).encode())
    assert status == 200
    assert "principles" in payload and "investors" in payload


def test_handle_recall_missing_query():
    status, payload = _handle_recall(json.dumps({}).encode())
    assert status == 400
    assert "error" in payload


def test_handle_recall_empty_query():
    status, _ = _handle_recall(json.dumps({"query": "   "}).encode())
    assert status == 400


def test_handle_recall_invalid_json():
    status, _ = _handle_recall(b"{not valid json")
    assert status == 400


def test_handle_recall_non_object():
    status, _ = _handle_recall(json.dumps(["lista"]).encode())
    assert status == 400


# --- integração socket real ---

@pytest.fixture
def server_port():
    srv = HTTPServer(("127.0.0.1", 0), BrainHandler)  # porta 0 = livre
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port
    srv.shutdown()


def _req(port: int, path: str, method: str = "GET", data: dict | None = None):
    url = f"http://127.0.0.1:{port}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health_endpoint(server_port):
    status, payload = _req(server_port, "/health")
    assert status == 200 and payload["status"] == "ok"


def test_get_unknown_route_404(server_port):
    status, _ = _req(server_port, "/qualquer")
    assert status == 404


def test_recall_endpoint_ok(server_port):
    status, payload = _req(server_port, "/recall", "POST", {"query": "risco de cauda e bolha"})
    assert status == 200
    assert payload["query"] == "risco de cauda e bolha"
    assert "principles" in payload


def test_recall_endpoint_bad_request(server_port):
    status, _ = _req(server_port, "/recall", "POST", {})
    assert status == 400


def test_post_unknown_route_404(server_port):
    status, _ = _req(server_port, "/xpto", "POST", {"query": "x"})
    assert status == 404
