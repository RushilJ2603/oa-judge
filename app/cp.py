"""CP sheets — sheet loading, external stat fetchers, contest feed, and the deterministic tracker.

Everything here is either (a) reading committed sheet JSON, or (b) fetching public data from the
competitive-programming sites the user links, or (c) pure arithmetic over that data. No AI, no
secrets except an optional clist.by key (env OAJ_CLIST_KEY / _USER). All network calls are
best-effort with short timeouts and degrade to cached / last-known data — a slow or down site can
never break the page or keep the scale-to-zero machine busy.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, date

HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS_DIR = os.path.join(HERE, "sheets")
UA = "oa-judge/1.0 (+https://oa123.fly.dev)"
TIMEOUT = 6

# --------------------------------------------------------------------------- sheet content
def _sheet_path(sid: str) -> str:
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", sid or ""):
        return ""
    return os.path.join(SHEETS_DIR, f"{sid}.json")


def load_sheet(sid: str) -> dict | None:
    p = _sheet_path(sid)
    if not p or not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def list_sheets() -> list[dict]:
    """Lightweight catalogue: id, title, subtitle, and item/section counts for each sheet."""
    out = []
    if not os.path.isdir(SHEETS_DIR):
        return out
    for name in sorted(os.listdir(SHEETS_DIR)):
        if not name.endswith(".json"):
            continue
        try:
            s = json.load(open(os.path.join(SHEETS_DIR, name), encoding="utf-8"))
        except Exception:
            continue
        secs = s.get("sections", [])
        out.append({"id": s["id"], "title": s.get("title"), "subtitle": s.get("subtitle"),
                    "sections": len(secs),
                    "items": sum(len(sec.get("items", [])) for sec in secs)})
    return out


def all_item_ids(sheet: dict) -> list[str]:
    return [it["id"] for sec in sheet.get("sections", []) for it in sec.get("items", [])]


# --------------------------------------------------------------------------- http helper
def _get_json(url: str, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------- stat fetchers
# Each returns {"ok": True, ...fields} or {"ok": False, "error": "..."}. Fields are normalized:
# rating, max_rating, rank, solved, plus (for codeforces/atcoder) a rating history list of
# {t: ISO-date, r: newRating} used by the tracker.

def fetch_codeforces(handle: str) -> dict:
    try:
        info = _get_json(f"https://codeforces.com/api/user.info?handles={urllib.parse.quote(handle)}")
        if info.get("status") != "OK":
            return {"ok": False, "error": info.get("comment", "codeforces error")}
        u = info["result"][0]
        hist = []
        try:
            rr = _get_json(f"https://codeforces.com/api/user.rating?handle={urllib.parse.quote(handle)}")
            if rr.get("status") == "OK":
                hist = [{"t": datetime.fromtimestamp(x["ratingUpdateTimeSeconds"], timezone.utc)
                         .date().isoformat(), "r": x["newRating"]} for x in rr["result"]]
        except Exception:
            pass
        return {"ok": True, "rating": u.get("rating"), "max_rating": u.get("maxRating"),
                "rank": u.get("rank"), "max_rank": u.get("maxRank"), "history": hist,
                "url": f"https://codeforces.com/profile/{handle}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_atcoder(handle: str) -> dict:
    try:
        hist_raw = _get_json(f"https://atcoder.jp/users/{urllib.parse.quote(handle)}/history/json")
        rated = [h for h in hist_raw if h.get("IsRated")]
        hist = [{"t": h["EndTime"][:10], "r": h["NewRating"]} for h in rated if h.get("EndTime")]
        cur = rated[-1]["NewRating"] if rated else None
        mx = max((h["NewRating"] for h in rated), default=None)
        return {"ok": True, "rating": cur, "max_rating": mx, "history": hist,
                "url": f"https://atcoder.jp/users/{handle}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_LC_QUERY = ("query($u:String!){matchedUser(username:$u){profile{ranking}"
             "submitStatsGlobal{acSubmissionNum{difficulty count}}}"
             "userContestRanking(username:$u){rating attendedContestsCount topPercentage}}")


def fetch_leetcode(handle: str) -> dict:
    try:
        body = json.dumps({"query": _LC_QUERY, "variables": {"u": handle}}).encode()
        d = _get_json("https://leetcode.com/graphql", data=body,
                      headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"})
        m = (d.get("data") or {}).get("matchedUser")
        if not m:
            return {"ok": False, "error": "user not found"}
        solved = {x["difficulty"]: x["count"] for x in m["submitStatsGlobal"]["acSubmissionNum"]}
        cr = (d.get("data") or {}).get("userContestRanking") or {}
        return {"ok": True, "solved": solved.get("All"), "solved_breakdown": solved,
                "rating": round(cr["rating"]) if cr.get("rating") else None,
                "contests": cr.get("attendedContestsCount"),
                "url": f"https://leetcode.com/u/{handle}/"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_codechef(handle: str) -> dict:
    # No official API; scrape the public profile. Fragile by nature -> always wrapped, degrades to
    # last-known via the cache. We only pull current rating + stars.
    try:
        html = _get_text(f"https://www.codechef.com/users/{urllib.parse.quote(handle)}")
        rm = re.search(r'"rating"\s*:\s*(\d{3,4})', html) or re.search(r'rating-number[^>]*>(\d{3,4})', html)
        star = re.search(r'rating-star[^>]*>(?:[^<]*★)+', html)
        return {"ok": bool(rm), "rating": int(rm.group(1)) if rm else None,
                "stars": (star.group(0).count("★") if star else None),
                "url": f"https://www.codechef.com/users/{handle}",
                "error": None if rm else "could not parse profile"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


FETCHERS = {"codeforces": fetch_codeforces, "atcoder": fetch_atcoder,
            "leetcode": fetch_leetcode, "codechef": fetch_codechef}


# --------------------------------------------------------------------------- contests
# Each site fetched from its own public endpoint so the multi-site feed works with NO key. clist.by
# (one call, all judges) is used only when a key is configured. Every fetcher is best-effort and
# returns [] on any failure, so one flaky site never blanks the others.

def _contests_codeforces() -> list[dict]:
    out = []
    d = _get_json("https://codeforces.com/api/contest.list?gym=false")
    if d.get("status") == "OK":
        for c in d["result"]:
            if c.get("phase") != "BEFORE" or not c.get("startTimeSeconds"):
                continue
            out.append({"site": "codeforces.com", "name": c["name"],
                        "url": f"https://codeforces.com/contest/{c['id']}",
                        "start_at": datetime.fromtimestamp(c["startTimeSeconds"], timezone.utc).isoformat(),
                        "duration_min": (c.get("durationSeconds") or 0) // 60})
    return out


def _contests_codechef() -> list[dict]:
    out = []
    d = _get_json("https://www.codechef.com/api/list/contests/all")
    for c in d.get("future_contests", []):
        start = c.get("contest_start_date_iso") or c.get("contest_start_date")
        out.append({"site": "codechef.com", "name": c.get("contest_name", ""),
                    "url": f"https://www.codechef.com/{c.get('contest_code', '')}",
                    "start_at": start, "duration_min": int(c.get("contest_duration") or 0) or None})
    return out


def _contests_atcoder() -> list[dict]:
    out = []
    html = _get_text("https://atcoder.jp/contests/")
    m = re.search(r'id="contest-table-upcoming".*?</table>', html, re.S)
    if not m:
        return out
    for row in re.findall(r'<tr>.*?</tr>', m.group(0), re.S):
        tt = re.search(r'>(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)([+\-]\d{4})<', row)
        am = re.search(r'href="(/contests/[^"]+)"[^>]*>([^<]+)</a>', row)
        if tt and am:
            off = tt.group(2)[:3] + ":" + tt.group(2)[3:]        # +0900 -> +09:00 (JS-parseable)
            out.append({"site": "atcoder.jp", "name": am.group(2).strip(),
                        "url": "https://atcoder.jp" + am.group(1),
                        "start_at": tt.group(1).replace(" ", "T") + off, "duration_min": None})
    return out


def _contests_leetcode() -> list[dict]:
    # The REST /contest/api/list/ endpoint 403s bots; the GraphQL upcomingContests field does not.
    out = []
    body = json.dumps({"query": "query{upcomingContests{title titleSlug startTime duration}}"}).encode()
    d = _get_json("https://leetcode.com/graphql", data=body,
                  headers={"Content-Type": "application/json", "Referer": "https://leetcode.com/contest/"})
    for c in (d.get("data") or {}).get("upcomingContests") or []:
        st = c.get("startTime")
        if not st:
            continue
        out.append({"site": "leetcode.com", "name": c.get("title", ""),
                    "url": f"https://leetcode.com/contest/{c.get('titleSlug', '')}",
                    "start_at": datetime.fromtimestamp(st, timezone.utc).isoformat(),
                    "duration_min": (c.get("duration") or 0) // 60})
    return out


def fetch_contests() -> list[dict]:
    """Upcoming contests across all four judges. With a clist.by key -> one aggregated call; without
    -> each site's own public endpoint, merged. Deduped by URL, sorted by start, capped at 50."""
    key, user = os.environ.get("OAJ_CLIST_KEY"), os.environ.get("OAJ_CLIST_USER")
    rows: list[dict] = []
    if key and user:
        try:
            q = urllib.parse.urlencode({
                "username": user, "api_key": key, "upcoming": "true", "order_by": "start", "limit": 50,
                "resource": "codeforces.com,atcoder.jp,codechef.com,leetcode.com"})
            d = _get_json(f"https://clist.by/api/v4/contest/?{q}")
            for c in d.get("objects", []):
                st = c.get("start", "")
                rows.append({"site": c.get("resource", ""), "name": c.get("event", ""),
                             "url": c.get("href", ""),
                             "start_at": st + "Z" if st and not st.endswith("Z") else st,
                             "duration_min": int(c.get("duration", 0)) // 60 if c.get("duration") else None})
        except Exception:
            rows = []
    if not rows:
        for fn in (_contests_codeforces, _contests_atcoder, _contests_codechef, _contests_leetcode):
            try:
                rows += fn()
            except Exception:
                pass
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r.get("start_at") or "z"):
        u = r.get("url")
        if not r.get("start_at") or not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
    return out[:50]


# --------------------------------------------------------------------------- tracker (pure math)
def _parse_day(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return None


def tracker(goal: dict, primary: dict | None) -> dict:
    """Deterministic on-track verdict. `primary` = the codeforces stats payload (rating + history).
    Target trajectory is the straight line (start_at, start_rating) -> (deadline, target_rating);
    'expected today' is the point on that line; the verdict compares real rating to it. Cadence
    counts rated contests in the trailing 4 weeks against a 2/week target."""
    target = goal.get("target_rating") or 1900
    deadline = _parse_day(goal.get("deadline")) or date(2027, 5, 31)
    start_r = goal.get("start_rating")
    start_d = _parse_day(goal.get("start_at"))
    cur = (primary or {}).get("rating")
    hist = (primary or {}).get("history") or []

    # Calibration falls back to earliest history point / current rating if not set explicitly.
    if start_r is None and hist:
        start_r, start_d = hist[0]["r"], _parse_day(hist[0]["t"])
    if start_r is None:
        start_r, start_d = cur, date.today()

    today = date.today()
    out = {"target": target, "deadline": deadline.isoformat(), "current": cur,
           "start_rating": start_r, "start_at": start_d.isoformat() if start_d else None,
           "have_data": cur is not None and start_r is not None and start_d is not None}
    if not out["have_data"]:
        out["verdict"] = "no-data"
        return out

    span = (deadline - start_d).days or 1
    frac = min(max((today - start_d).days / span, 0.0), 1.0)
    expected = round(start_r + (target - start_r) * frac)
    gap = cur - expected
    days_left = (deadline - today).days
    verdict = "ahead" if gap >= 40 else ("behind" if gap <= -40 else "on-track")
    if cur >= target:
        verdict = "reached"

    # cadence: rated contests in the trailing 28 days
    recent = sum(1 for h in hist if (today - (_parse_day(h["t"]) or today)).days <= 28)
    out.update({"expected": expected, "gap": gap, "days_left": days_left,
                "verdict": verdict, "contests_28d": recent, "cadence_per_week": round(recent / 4, 1),
                "cadence_target": 2, "history": hist})
    return out
