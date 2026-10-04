"""End-to-end pipeline test with local mock servers (no network).

Spins up:

* a fake NoteGPT API implementing register / confirm / login / userinfo / quota;
* a fake 9Router management API implementing providers + provider-nodes.

Then runs :class:`Harvester` against them and asserts that a token was harvested
and that a 9Router connection was created.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from notegpt_harvester.config import Config
from notegpt_harvester.harvester import Harvester
from notegpt_harvester.router9 import NineRouterConnector

STATE: dict = {"providers": [], "nodes": [], "registered": [], "confirmed": False}


class NoteGPTHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/v1/userinfo"):
            return self._json(200, {"code": 100000, "data": {"user_id": 42, "user_name": "ng"}})
        if self.path.startswith("/api/v2/user/quota"):
            return self._json(200, {"code": 100000, "data": {"ai_chat": {"basic_quota": {"remaining": 5}}}})
        return self._json(404, {"code": 404, "message": "nf"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if self.path.endswith("/auth/email/register"):
            STATE["registered"].append(data["email"])
            return self._json(200, {"code": 100000, "data": {}})
        if self.path.endswith("/auth/email/register/confirm"):
            STATE["confirmed"] = True
            return self._json(200, {"code": 100000, "data": {}})
        if self.path.endswith("/auth/email/login"):
            payload = {"code": 100000, "data": {"access_token": "TOK-abc", "user_id": 42, "user_name": "ng"}}
            return self._json(200, payload)
        return self._json(404, {"code": 404, "message": "nf"})


class RouterHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/providers"):
            return self._json(200, STATE["providers"])
        if self.path.startswith("/api/provider-nodes"):
            return self._json(200, STATE["nodes"])
        return self._json(404, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if self.path.startswith("/api/provider-nodes"):
            STATE["nodes"].append(data)
            return self._json(200, {"ok": True})
        if self.path.startswith("/api/providers"):
            STATE["providers"].append(data)
            return self._json(200, {"ok": True})
        return self._json(404, {})


@pytest.fixture()
def servers():
    STATE.update({"providers": [], "nodes": [], "registered": [], "confirmed": False})
    ng = HTTPServer(("127.0.0.1", 0), NoteGPTHandler)
    rt = HTTPServer(("127.0.0.1", 0), RouterHandler)
    for srv in (ng, rt):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{ng.server_port}", f"http://127.0.0.1:{rt.server_port}"
    ng.shutdown()
    rt.shutdown()


@pytest.mark.asyncio
async def test_full_pipeline(servers, monkeypatch, tmp_path):
    ng_url, rt_url = servers

    # Replace the temp-mail client with a stub that returns a verification link.
    from notegpt_harvester import harvester as hmod
    from notegpt_harvester.email_provider import BaseEmailClient

    class StubMail(BaseEmailClient):
        async def start(self): ...
        async def close(self): ...
        async def create_address(self):
            return "ngtest@example.com"

        async def fetch_messages(self, address):
            from notegpt_harvester.email_provider import EmailMessage

            link = f"{ng_url}/auth/register-confirm?token=TOK-abc"
            return [EmailMessage("Verify Your Email", "no-reply@notegpt.io", f'<a href="{link}">Verify</a>', 1.0, {})]

    monkeypatch.setattr(hmod.TempEmailClient, "create", staticmethod(lambda *a, **k: StubMail(a[0])))

    cfg = Config()
    cfg.notegpt.base_url = ng_url
    cfg.email.provider = "mailtm"
    cfg.run.count = 1
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.run.checkpoint_file = str(tmp_path / "state.json")
    cfg.router9.enabled = True
    cfg.router9.base_url = rt_url
    cfg.router9.create_node = True

    result = await Harvester(cfg).run(count=1)

    assert len(result.succeeded) == 1
    account = result.succeeded[0]
    assert account.x_token == "TOK-abc"
    assert account.verified is True
    assert STATE["confirmed"] is True
    assert STATE["registered"] == ["ngtest@example.com"]

    # token was pushed to the mock 9Router
    assert len(STATE["providers"]) == 1
    conn = STATE["providers"][0]
    assert conn["apiKey"] == "TOK-abc"
    assert conn["provider"] == "notegpt"

    # artifact files written
    assert (tmp_path / "results" / "tokens.txt").read_text().strip() == "TOK-abc"
    assert (tmp_path / "results" / "accounts.json").exists()
    assert (tmp_path / "results" / "accounts.csv").exists()


@pytest.mark.asyncio
async def test_router_duplicate_tolerated(servers, monkeypatch):
    _, rt_url = servers
    from notegpt_harvester.models import Account

    STATE["providers"] = [{"provider": "notegpt", "apiKey": "old"}]
    cfg = Config().router9
    cfg.base_url = rt_url
    conn = NineRouterConnector(cfg)
    try:
        outcome = await conn.import_accounts([Account(email="a@b.dev", password="x", x_token="T")])
        assert outcome.imported == 1
    finally:
        await conn.close()
