"""
Facebook Graph + TikTok OAuth helpers for account linking and friend discovery.

Facebook: `/me/friends` only returns friends who also use the same Facebook app
(and granted `user_friends`). See Meta's documentation for limitations.

TikTok: public APIs do not expose a "friends list" for third-party apps.
We only persist `open_id` after OAuth for identity linking; suggestions are not
available from TikTok.
"""

from __future__ import annotations

import logging
from typing import Any
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _get(url: str, **kwargs) -> requests.Response:
    return requests.get(url, timeout=20, **kwargs)


def _post_form(url: str, data: dict[str, str]) -> requests.Response:
    return requests.post(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )


def verify_facebook_token(access_token: str) -> dict[str, Any] | None:
    """
    Validate the user access token and return { id, name } or None.
    When FACEBOOK_APP_ID + FACEBOOK_APP_SECRET are set, uses debug_token.
    Otherwise (e.g. local dev) only checks GET /me with the token.
    """
    app_id = (getattr(settings, "FACEBOOK_APP_ID", "") or "").strip()
    app_secret = (getattr(settings, "FACEBOOK_APP_SECRET", "") or "").strip()

    if app_id and app_secret:
        dbg = _get(
            f"{GRAPH_BASE}/debug_token",
            params={
                "input_token": access_token,
                "access_token": f"{app_id}|{app_secret}",
            },
        )
        if dbg.status_code != 200:
            logger.warning("Facebook debug_token failed: %s", dbg.text[:200])
            return None
        dbg_json = dbg.json()
        data = dbg_json.get("data") or {}
        if not data.get("is_valid"):
            return None
        if str(data.get("app_id")) != str(app_id):
            return None

    r = _get(
        f"{GRAPH_BASE}/me",
        params={"fields": "id,name", "access_token": access_token},
    )
    if r.status_code != 200:
        logger.warning("Facebook /me failed: %s", r.text[:200])
        return None
    return r.json()


def fetch_facebook_friend_ids(access_token: str) -> list[str]:
    """Paginate Facebook `me/friends` (friends who use this app)."""
    ids: list[str] = []
    url: str | None = f"{GRAPH_BASE}/me/friends"
    params: dict[str, Any] = {"access_token": access_token, "limit": 500}
    first = True
    while url:
        r = _get(url, params=params if first else None)
        first = False
        if r.status_code != 200:
            logger.warning("Facebook /me/friends failed: %s", r.text[:200])
            break
        body = r.json()
        for row in body.get("data") or []:
            fid = row.get("id")
            if fid:
                ids.append(str(fid))
        paging = body.get("paging") or {}
        url = paging.get("next")
    return ids


def extract_tiktok_open_id(payload: dict[str, Any]) -> str | None:
    """Parse open_id from TikTok token JSON (shape varies slightly by API version)."""
    if not isinstance(payload, dict):
        return None
    oid = payload.get("open_id")
    if oid:
        return str(oid)
    inner = payload.get("data")
    if isinstance(inner, dict) and inner.get("open_id"):
        return str(inner["open_id"])
    return None


def exchange_tiktok_oauth_code(
    code: str,
    redirect_uri: str,
) -> dict[str, Any] | None:
    """
    Exchange authorization code for tokens. Returns dict with open_id, access_token, etc.
    """
    client_key = (getattr(settings, "TIKTOK_CLIENT_KEY", "") or "").strip()
    client_secret = (getattr(settings, "TIKTOK_CLIENT_SECRET", "") or "").strip()
    if not client_key or not client_secret:
        return None

    # TikTok Login Kit — OAuth token endpoint (v2)
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    r = _post_form(
        url,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    if r.status_code != 200:
        logger.warning("TikTok token exchange failed: %s", r.text[:200])
        return None
    try:
        return r.json()
    except ValueError:
        return None
