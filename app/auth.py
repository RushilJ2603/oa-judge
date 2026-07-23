"""GitHub OAuth for the hosted, multi-user deployment.

Dual-mode by design:
  * config.AUTH_ENABLED is False (no OAuth app configured) -> single-user, no login. The store's
    default provider returns the local user, so the app behaves exactly as it does on your machine.
  * AUTH_ENABLED is True -> everyone signs in with GitHub; each request is scoped to that user.

No third-party OAuth library — the flow is three small HTTP calls over stdlib urllib, and the
session is Flask's signed cookie. Keeps the app dependency-light and easy to audit.
"""
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

from flask import Blueprint, g, jsonify, redirect, request, session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import store  # noqa: E402

bp = Blueprint("auth", __name__)

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"


def _callback_url() -> str:
    # Prefer the configured public URL; fall back to the request host (fine for local testing).
    base = config.BASE_URL or request.host_url.rstrip("/")
    return f"{base}/auth/callback"


def _post_json(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"{}")


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "oa-judge",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"{}")


@bp.route("/auth/login")
def login():
    if not config.AUTH_ENABLED:
        return redirect("/")
    # CSRF: a random state echoed back by GitHub and checked in the callback.
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = urllib.parse.urlencode({
        "client_id": config.GITHUB_CLIENT_ID,
        "redirect_uri": _callback_url(),
        "scope": "read:user",
        "state": state,
    })
    return redirect(f"{GITHUB_AUTHORIZE}?{params}")


@bp.route("/auth/callback")
def callback():
    if not config.AUTH_ENABLED:
        return redirect("/")
    if request.args.get("state") != session.pop("oauth_state", None):
        return "state mismatch — please try signing in again", 400
    code = request.args.get("code")
    if not code:
        return "no code from GitHub", 400
    try:
        tok = _post_json(GITHUB_TOKEN, {
            "client_id": config.GITHUB_CLIENT_ID,
            "client_secret": config.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": _callback_url(),
        })
        access = tok.get("access_token")
        if not access:
            return "GitHub did not return a token", 400
        gh = _get_json(GITHUB_USER, access)
    except Exception as e:  # noqa: BLE001 - surface a clean message rather than a 500
        return f"sign-in failed: {e}", 502

    login = gh.get("login") or f"user{gh['id']}"
    if config.GITHUB_ALLOWED and login.lower() not in config.GITHUB_ALLOWED:
        return (f"Sorry, @{login} isn't on this judge's allow-list. "
                "Ask the owner to add you."), 403
    uid = store.upsert_github_user(
        github_id=gh["id"], login=login,
        name=gh.get("name"), avatar_url=gh.get("avatar_url"))
    session.permanent = True
    session["user_id"] = uid
    return redirect("/")


@bp.route("/auth/logout", methods=["POST", "GET"])
def logout():
    session.pop("user_id", None)
    return redirect("/")


@bp.route("/api/me")
def me():
    """Who am I? Drives the frontend's login state."""
    if not config.AUTH_ENABLED:
        return jsonify({"auth": False})   # single-user; no login concept
    uid = session.get("user_id")
    if not uid:
        return jsonify({"auth": True, "logged_in": False})
    u = store.get_user(uid)
    if not u:
        session.pop("user_id", None)
        return jsonify({"auth": True, "logged_in": False})
    return jsonify({"auth": True, "logged_in": True, "user": {
        "login": u["login"], "name": u["name"], "avatar_url": u["avatar_url"]}})


def current_user_id():
    """The store's user provider in hosted mode. Reads the session-established id off `g`
    (set by the server's before_request); falls back to the local user."""
    return getattr(g, "user_id", store.LOCAL_USER_ID)
