from __future__ import annotations

import time
import urllib.parse

import httpx

from djx.auth._oauth_common import PKCEPair, capture_via_loopback, manual_paste, vercel_fallback
from djx.auth.token_store import TokenSet, TokenStore

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
SCOPES = ["tweet.read", "users.read", "like.read", "offline.access"]


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
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
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
        raise RuntimeError("X OAuth did not return a code.")

    async with httpx.AsyncClient(timeout=30) as client:
        kwargs: dict = {
            "data": {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": pkce.verifier,
                "client_id": client_id,
            },
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        }
        if client_secret:
            kwargs["auth"] = httpx.BasicAuth(client_id, client_secret)
        resp = await client.post(TOKEN_URL, **kwargs)
        resp.raise_for_status()
        payload = resp.json()
    tokens = TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_at=time.time() + int(payload.get("expires_in", 7200)),
        scope=payload.get("scope", " ".join(SCOPES)),
        token_type=payload.get("token_type", "Bearer"),
    )
    store.set("x", tokens)
    return tokens


async def refresh(
    *, client_id: str, client_secret: str, store: TokenStore
) -> TokenSet:
    current = store.get("x")
    if not current or not current.refresh_token:
        raise RuntimeError("No X refresh token. Run `djx auth x`.")
    async with httpx.AsyncClient(timeout=30) as client:
        kwargs: dict = {
            "data": {
                "grant_type": "refresh_token",
                "refresh_token": current.refresh_token,
                "client_id": client_id,
            },
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        }
        if client_secret:
            kwargs["auth"] = httpx.BasicAuth(client_id, client_secret)
        resp = await client.post(TOKEN_URL, **kwargs)
        resp.raise_for_status()
        payload = resp.json()
    tokens = TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token") or current.refresh_token,
        expires_at=time.time() + int(payload.get("expires_in", 7200)),
        scope=payload.get("scope", current.scope),
        token_type=payload.get("token_type", "Bearer"),
    )
    store.set("x", tokens)
    return tokens
