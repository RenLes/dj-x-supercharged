from __future__ import annotations

import base64
import time
import urllib.parse

import httpx

from djx.auth._oauth_common import PKCEPair, capture_via_loopback, manual_paste, vercel_fallback
from djx.auth.token_store import TokenSet, TokenStore

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = [
    "user-top-read",
    "user-read-recently-played",
    "playlist-modify-private",
    "playlist-modify-public",
]


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


async def authorize(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    store: TokenStore,
    vercel_fallback_url: str = "",
) -> TokenSet:
    pkce = PKCEPair.generate()
    state = pkce.challenge[:16]
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": pkce.challenge,
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    captured = capture_via_loopback(redirect_uri, auth_url)
    if captured and captured.get("code"):
        code = captured["code"]
    elif vercel_fallback_url:
        code = vercel_fallback(auth_url, vercel_fallback_url)
    else:
        code = manual_paste(auth_url)
    if not code:
        raise RuntimeError("Spotify OAuth did not return a code.")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(client_id, client_secret),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": pkce.verifier,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
    tokens = TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_at=time.time() + int(payload.get("expires_in", 3600)),
        scope=payload.get("scope", ""),
        token_type=payload.get("token_type", "Bearer"),
    )
    store.set("spotify", tokens)
    return tokens


async def refresh(
    *, client_id: str, client_secret: str, store: TokenStore
) -> TokenSet:
    current = store.get("spotify")
    if not current or not current.refresh_token:
        raise RuntimeError("No Spotify refresh token. Run `djx auth spotify`.")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(client_id, client_secret),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": current.refresh_token},
        )
        resp.raise_for_status()
        payload = resp.json()
    tokens = TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token") or current.refresh_token,
        expires_at=time.time() + int(payload.get("expires_in", 3600)),
        scope=payload.get("scope", current.scope),
        token_type=payload.get("token_type", "Bearer"),
    )
    store.set("spotify", tokens)
    return tokens
