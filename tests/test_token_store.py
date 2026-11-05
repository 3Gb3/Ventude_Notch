import sys

import pytest

from ventude.assistant.token_store import TokenStore


class XorProtector:
    def protect(self, data: bytes) -> bytes:
        return bytes(b ^ 0x5A for b in data)

    def unprotect(self, data: bytes) -> bytes:
        return bytes(b ^ 0x5A for b in data)


def test_roundtrip_not_plaintext(tmp_path):
    store = TokenStore(tmp_path / "c.bin", XorProtector())
    store.set("chatgpt", {"access_token": "SECRET-TOKEN"})
    assert b"SECRET-TOKEN" not in (tmp_path / "c.bin").read_bytes()
    assert TokenStore(tmp_path / "c.bin", XorProtector()).get("chatgpt")["access_token"] == (
        "SECRET-TOKEN"
    )
    store.delete("chatgpt")
    assert store.get("chatgpt") is None


def test_host_id_stable(tmp_path):
    store = TokenStore(tmp_path / "c.bin", XorProtector())
    hid = store.host_id()
    assert hid.startswith("urn:uuid:") and store.host_id() == hid


def test_corrupt_file_is_empty(tmp_path):
    (tmp_path / "c.bin").write_bytes(b"\x00garbage")
    assert TokenStore(tmp_path / "c.bin", XorProtector()).get("x") is None


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só no Windows")
def test_real_dpapi(tmp_path):
    store = TokenStore(tmp_path / "c.bin")
    store.set("k", "valor-secreto")
    assert b"valor-secreto" not in (tmp_path / "c.bin").read_bytes()
    assert TokenStore(tmp_path / "c.bin").get("k") == "valor-secreto"
