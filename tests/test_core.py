"""Unit tests for the pure helpers (no network required)."""

from __future__ import annotations

from notegpt_harvester.email_provider import extract_link
from notegpt_harvester.harvester import Checkpoint
from notegpt_harvester.models import Account
from notegpt_harvester.notegpt import NoteGPTClient, token_from_link


def test_generate_password_policy():
    for _ in range(25):
        pwd = NoteGPTClient.generate_password(12)
        assert 8 <= len(pwd) <= 16
        assert any(c.islower() for c in pwd)
        assert any(c.isupper() for c in pwd)
        assert any(c.isdigit() for c in pwd)


def test_token_from_link():
    link = "https://notegpt.io/auth/register-confirm?token=abc.def.ghi&email=a%40b.dev"
    assert token_from_link(link) == "abc.def.ghi"
    assert token_from_link("https://x.dev/no-token") == ""


def test_extract_link_prefers_verify():
    body = '<a href="https://notegpt.io/home">Home</a><a href="https://notegpt.io/auth/register-confirm?token=T1">Verify</a>'
    assert "token=T1" in extract_link(body)


def test_account_ok_and_serialization():
    acc = Account(email="a@b.dev", password="x", x_token="tok")
    assert acc.ok
    assert acc.openai_api_key() == "tok"
    assert "a@b.dev" in acc.to_dict()["email"]
    bad = Account(email="a@b.dev", password="x", error="boom")
    assert not bad.ok


def test_checkpoint_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    cp = Checkpoint(path)
    cp.mark(Account(email="a@b.dev", password="x", x_token="t"))
    again = Checkpoint(path)
    assert "a@b.dev" in again.done
    again.clear()
    assert Checkpoint(path).done == set()
