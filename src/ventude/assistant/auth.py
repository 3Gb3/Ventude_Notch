"""Sign in with ChatGPT para apps open source (fluxo documentado pela OpenAI).

Referência: https://developers.openai.com/siwc/token-sharing-open-source
- Registro dinâmico com client_id=dynamic_agent_client, PKCE S256, state e nonce.
- Callback loopback em http://127.0.0.1:<porta>/auth/callback.
- Troca do código em https://auth.openai.com/api/accounts/oauth/token.
- Validação do ID token pelo JWKS publicado e checagem do escopo chatgpt.tokens.use.direct.
- Refresh e revogação conforme "Accounts and sessions".
O login só começa quando o usuário clica em "Conectar".
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
import webbrowser
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from ventude.assistant.token_store import TokenStore

ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
DYNAMIC_CLIENT = "dynamic_agent_client"
AGENT_NAME = "Ventude"
CALLBACK_PATH = "/auth/callback"
PREFERRED_PORT = 1455
CRED_KEY = "chatgpt"


class AuthError(RuntimeError):
    pass


@dataclass
class PendingAuth:
    state: str
    nonce: str
    verifier: str
    redirect_uri: str
    client_id: str


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def build_authorize_url(
    pending: PendingAuth, challenge: str, host_id: str, saved: dict[str, Any] | None
) -> str:
    params = {
        "client_id": pending.client_id,
        "ext_agent_host_id": host_id,
        "response_type": "code",
        "redirect_uri": pending.redirect_uri,
        "scope": SCOPES,
        "resource": RESOURCE,
        "state": pending.state,
        "nonce": pending.nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    if pending.client_id == DYNAMIC_CLIENT:
        params["agent_name_hint"] = AGENT_NAME
    elif saved:
        if saved.get("id_token"):
            params["id_token_hint"] = saved["id_token"]
        if saved.get("email"):
            params["login_hint"] = saved["email"]
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def parse_callback(target: str, pending: PendingAuth) -> tuple[str, str]:
    """Valida o callback e devolve (code, client_id)."""
    q = {k: v[0] for k, v in parse_qs(urlparse(target).query).items()}
    if q.get("state") != pending.state:
        raise AuthError("state inválido no retorno do login.")
    if q.get("error"):
        if q["error"] == "access_denied":
            raise AuthError("Acesso negado no navegador.")
        raise AuthError(f"Erro no login: {q['error']}")
    code = q.get("code")
    if not code:
        raise AuthError("Retorno sem código de autorização.")
    if pending.client_id == DYNAMIC_CLIENT:
        client_id = q.get("client_id")
        if not client_id:
            raise AuthError("Registro incompleto: o retorno não trouxe client_id.")
    else:
        client_id = q.get("client_id") or pending.client_id
        if client_id != pending.client_id:
            raise AuthError("O retorno trouxe outro client_id; login rejeitado.")
    return code, client_id


async def _wait_callback(port_holder: list[int], timeout: float) -> str:
    """Servidor HTTP mínimo em 127.0.0.1 que captura um único callback."""
    loop = asyncio.get_running_loop()
    result: asyncio.Future[str] = loop.create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        line = (await reader.readline()).decode(errors="replace")
        parts = line.split(" ")
        target = parts[1] if len(parts) > 1 else ""
        ok = target.startswith(CALLBACK_PATH)
        body = ("Login recebido. Pode voltar ao Ventude." if ok else "Not found").encode()
        writer.write(
            f"HTTP/1.1 {'200 OK' if ok else '404 Not Found'}\r\nContent-Type: text/plain; "
            f"charset=utf-8\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()
        if ok and not result.done():
            result.set_result(target)

    try:
        server = await asyncio.start_server(handle, "127.0.0.1", PREFERRED_PORT)
    except OSError:
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port_holder.append(server.sockets[0].getsockname()[1])
    async with server:
        return await asyncio.wait_for(result, timeout)


class ChatGPTAuth:
    def __init__(self, store: TokenStore, http: httpx.AsyncClient | None = None) -> None:
        self.store = store
        self.http = http or httpx.AsyncClient(timeout=30)
        self._refresh_lock = asyncio.Lock()

    # ---------- estado ----------
    def credentials(self) -> dict[str, Any] | None:
        cred = self.store.get(CRED_KEY)
        return cred if isinstance(cred, dict) and cred.get("access_token") else None

    def account_label(self) -> str:
        c = self.credentials()
        return str(c.get("email") or "conta conectada") if c else ""

    # ---------- login ----------
    async def sign_in(self, open_browser: Any = webbrowser.open, timeout: float = 300) -> str:
        host_id = self.store.host_id()
        saved = self.store.get(CRED_KEY) or {}
        client_id = saved.get("client_id") or DYNAMIC_CLIENT
        verifier, challenge = pkce_pair()
        port_holder: list[int] = []
        waiter = asyncio.ensure_future(_wait_callback(port_holder, timeout))
        while not port_holder and not waiter.done():
            await asyncio.sleep(0.01)
        if waiter.done():
            waiter.result()
        pending = PendingAuth(
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            verifier=verifier,
            redirect_uri=f"http://127.0.0.1:{port_holder[0]}{CALLBACK_PATH}",
            client_id=client_id,
        )
        open_browser(build_authorize_url(pending, challenge, host_id, saved))
        target = await waiter
        code, issued = parse_callback(target, pending)
        tokens = await self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": issued,
                "code": code,
                "code_verifier": pending.verifier,
                "redirect_uri": pending.redirect_uri,
                "resource": RESOURCE,
            }
        )
        claims = await self.validate_id_token(tokens.get("id_token", ""), issued, pending.nonce)
        if saved.get("subject") and saved["subject"] != claims.get("sub"):
            raise AuthError("A conta escolhida é diferente da conta salva.")
        scopes = str(tokens.get("scope", "")).split()
        if PLAN_SCOPE not in scopes:
            raise AuthError("O uso do plano do ChatGPT não foi autorizado (escopo ausente).")
        self._save(tokens, issued, claims, host_id, scopes)
        return str(claims.get("email") or "")

    async def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        r = await self.http.post(TOKEN_URL, data=form)
        if r.status_code != 200:
            err = ""
            try:
                err = r.json().get("error", "")
            except ValueError:
                pass
            raise AuthError(f"Falha no token endpoint ({r.status_code} {err}).")
        return r.json()

    async def validate_id_token(self, id_token: str, client_id: str, nonce: str | None) -> dict:
        import jwt

        if not id_token:
            raise AuthError("Resposta sem ID token.")
        conf = (await self.http.get(DISCOVERY_URL)).json()
        jwks = (await self.http.get(conf["jwks_uri"])).json()
        header = jwt.get_unverified_header(id_token)
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
        if key is None:
            raise AuthError("Chave do ID token não encontrada no JWKS.")
        claims = jwt.decode(
            id_token,
            jwt.PyJWK(key).key,
            algorithms=[header.get("alg", "RS256")],
            audience=client_id,
            issuer=ISSUER,
        )
        if nonce is not None and claims.get("nonce") != nonce:
            raise AuthError("nonce do ID token não confere.")
        return claims

    def _save(
        self,
        tokens: dict[str, Any],
        client_id: str,
        claims: dict[str, Any],
        host_id: str,
        scopes: list[str],
    ) -> None:
        self.store.set(
            CRED_KEY,
            {
                "email": claims.get("email", ""),
                "issuer": ISSUER,
                "subject": claims.get("sub", ""),
                "client_id": client_id,
                "ext_agent_host_id": host_id,
                "id_token": tokens.get("id_token", ""),
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", ""),
                "token_type": tokens.get("token_type", "Bearer"),
                "expires_in": int(tokens.get("expires_in", 3600)),
                "scopes": scopes,
                "saved_at": time.time(),
            },
        )

    # ---------- uso ----------
    async def access_token(self) -> str:
        """Token válido; renova perto da expiração (serializado)."""
        async with self._refresh_lock:
            c = self.credentials()
            if not c:
                raise AuthError("Conta do ChatGPT não conectada.")
            if time.time() < c["saved_at"] + c["expires_in"] - 120:
                return str(c["access_token"])
            if not c.get("refresh_token"):
                raise AuthError("Sessão expirada. Clique em Conectar de novo.")
            tokens = await self._token_request(
                {
                    "grant_type": "refresh_token",
                    "client_id": c["client_id"],
                    "refresh_token": c["refresh_token"],
                    "resource": RESOURCE,
                }
            )
            c.update(
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token", c["refresh_token"]),
                expires_in=int(tokens.get("expires_in", 3600)),
                scopes=str(tokens.get("scope", " ".join(c["scopes"]))).split(),
                saved_at=time.time(),
            )
            if tokens.get("id_token"):
                c["id_token"] = tokens["id_token"]
            self.store.set(CRED_KEY, c)
            return str(c["access_token"])

    async def sign_out(self) -> bool:
        """Revoga a sessão renovável e limpa tokens. Retorna se a revogação foi confirmada."""
        c = self.store.get(CRED_KEY) or {}
        confirmed = False
        if c.get("refresh_token"):
            try:
                conf = (await self.http.get(DISCOVERY_URL)).json()
                r = await self.http.post(
                    conf["revocation_endpoint"],
                    data={
                        "token": c["refresh_token"],
                        "token_type_hint": "refresh_token",
                        "client_id": c["client_id"],
                    },
                )
                confirmed = r.status_code == 200
            except (httpx.HTTPError, KeyError, ValueError):
                confirmed = False
        for k in ("access_token", "refresh_token", "id_token"):
            c.pop(k, None)
        self.store.set(CRED_KEY, c)  # mantém client_id/host para próximo login
        return confirmed
