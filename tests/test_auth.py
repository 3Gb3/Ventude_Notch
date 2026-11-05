import asyncio
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.test_token_store import XorProtector
from ventude.assistant import auth as A
from ventude.assistant.token_store import TokenStore


def pending(client_id=A.DYNAMIC_CLIENT):
    return A.PendingAuth("st", "no", "ver", "http://127.0.0.1:1455/auth/callback", client_id)


def test_authorize_url_new_registration():
    url = A.build_authorize_url(pending(), "chal", "urn:uuid:x", None)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert url.startswith("https://auth.openai.com/api/accounts/authorize?")
    assert q["client_id"] == "dynamic_agent_client" and q["agent_name_hint"] == "Ventude"
    assert q["ext_agent_host_id"] == "urn:uuid:x" and q["code_challenge_method"] == "S256"
    assert "chatgpt.tokens.use.direct" in q["scope"] and q["resource"] == A.RESOURCE


def test_authorize_url_returning_account():
    url = A.build_authorize_url(pending("oaiapp_1"), "c", "h", {"id_token": "t", "email": "e@x"})
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert "agent_name_hint" not in q and q["id_token_hint"] == "t" and q["login_hint"] == "e@x"


def test_parse_callback_rules():
    p = pending()
    assert A.parse_callback("/auth/callback?code=c&state=st&client_id=oaiapp_9", p) == (
        "c",
        "oaiapp_9",
    )
    with pytest.raises(A.AuthError):
        A.parse_callback("/auth/callback?code=c&state=bad&client_id=x", p)
    with pytest.raises(A.AuthError):
        A.parse_callback("/auth/callback?code=c&state=st", p)  # sem client_id
    with pytest.raises(A.AuthError):
        A.parse_callback("/auth/callback?error=access_denied&state=st", p)
    with pytest.raises(A.AuthError):
        A.parse_callback("/auth/callback?code=c&state=st&client_id=other", pending("oaiapp_1"))


def _store(tmp_path, **cred):
    s = TokenStore(tmp_path / "c.bin", XorProtector())
    if cred:
        s.set(A.CRED_KEY, cred)
    return s


def test_refresh_when_expired(tmp_path):
    forms = []

    def handler(req):
        forms.append(parse_qs(req.content.decode()))
        return httpx.Response(
            200,
            json={
                "access_token": "new",
                "refresh_token": "r2",
                "expires_in": 3600,
                "scope": "chatgpt.tokens.use.direct",
            },
        )

    store = _store(
        tmp_path,
        access_token="old",
        refresh_token="r1",
        client_id="oaiapp_1",
        expires_in=3600,
        saved_at=time.time() - 7200,
        scopes=[],
    )
    auth = A.ChatGPTAuth(store, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert asyncio.run(auth.access_token()) == "new"
    assert forms[0]["grant_type"] == ["refresh_token"] and forms[0]["client_id"] == ["oaiapp_1"]
    assert store.get(A.CRED_KEY)["refresh_token"] == "r2"


def test_valid_token_not_refreshed(tmp_path):
    store = _store(
        tmp_path,
        access_token="ok",
        refresh_token="r",
        client_id="c",
        expires_in=3600,
        saved_at=time.time(),
        scopes=[],
    )
    auth = A.ChatGPTAuth(
        store, httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    )
    assert asyncio.run(auth.access_token()) == "ok"


def test_validate_id_token_with_jwks(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "k1"
    token = jwt.encode(
        {
            "iss": A.ISSUER,
            "aud": "oaiapp_1",
            "sub": "u1",
            "nonce": "n",
            "exp": int(time.time()) + 600,
        },
        key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    def handler(req):
        if req.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"jwks_uri": "https://auth.openai.com/jwks"})
        return httpx.Response(200, json={"keys": [jwk]})

    auth = A.ChatGPTAuth(
        _store(tmp_path), httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    assert asyncio.run(auth.validate_id_token(token, "oaiapp_1", "n"))["sub"] == "u1"
    with pytest.raises(A.AuthError):
        asyncio.run(auth.validate_id_token(token, "oaiapp_1", "other-nonce"))
    with pytest.raises(jwt.InvalidAudienceError):
        asyncio.run(auth.validate_id_token(token, "wrong", "n"))


def test_sign_out_revokes_and_keeps_client(tmp_path):
    seen = []

    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json={"revocation_endpoint": "https://auth.openai.com/rev"})
        seen.append(parse_qs(req.content.decode()))
        return httpx.Response(200)

    store = _store(
        tmp_path,
        access_token="a",
        refresh_token="r",
        id_token="i",
        client_id="oaiapp_1",
        expires_in=1,
        saved_at=0,
        scopes=[],
    )
    auth = A.ChatGPTAuth(store, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert asyncio.run(auth.sign_out()) is True
    assert seen[0]["token_type_hint"] == ["refresh_token"]
    cred = store.get(A.CRED_KEY)
    assert "access_token" not in cred and cred["client_id"] == "oaiapp_1"
    assert auth.credentials() is None
