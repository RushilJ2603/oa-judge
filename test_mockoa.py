#!/usr/bin/env python3
"""Invariants for the Mock OA — the timed multi-problem paper.

Run:  python3 test_mockoa.py       (exits non-zero on failure)

What is worth pinning here, in rough order of how much it would hurt to get wrong:

  1. THE CLOCK IS THE SERVER'S. A paper that can be extended by reloading, closing the tab, or
     submitting after the deadline is not a mock OA, it is a problem list with a stopwatch on it.
  2. THE CURATED PAPERS ARE REAL. Every hand-picked question must exist, be runnable, and appear in
     exactly one paper; the ramp must not go backwards. These 15 are the feature — a typo in an id
     turns a "hand-picked Amazon paper" into a 404 halfway through someone's timed hour.
  3. NOTHING NAMES THE TECHNIQUE. The problem list deliberately hides tags and topics so as not to
     hand over the approach. A mock OA card that says "binary search on the answer" would undo that
     in the one place it matters most, so both the API payload and the hand-written blurbs are
     checked.
  4. SCORING MATCHES WHAT HAPPENED. Partial credit, multiple submissions, and the window boundaries.
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app")
sys.path.insert(0, APP)

_tmpdb = os.path.join(tempfile.mkdtemp(prefix="oaj-mock-"), "t.db")
os.environ["OAJ_DB"] = _tmpdb

import db          # noqa: E402
import mockoa      # noqa: E402
import server      # noqa: E402
import store       # noqa: E402
from runner import problems  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"   {detail}" if not cond and detail else ""))
    if not cond:
        FAILS.append(name)


def section(t):
    print(f"\n{t}")


def reset_papers():
    conn = db.connect()
    conn.execute("DELETE FROM mock_oa_attempt")
    conn.execute("DELETE FROM attempt")
    conn.commit()


def shift(attempt_id, started_min_ago, ends_min_from_now):
    """Move a paper's window, to test deadlines without waiting for them."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    conn = db.connect()
    conn.execute("UPDATE mock_oa_attempt SET started_at = ?, ends_at = ? WHERE id = ?",
                 ((now - timedelta(minutes=started_min_ago)).isoformat(timespec="seconds"),
                  (now + timedelta(minutes=ends_min_from_now)).isoformat(timespec="seconds"),
                  attempt_id))
    conn.commit()


def main():
    c = server.app.test_client()
    store.reindex_problems(problems.all_meta())
    meta = {m["id"]: m for m in problems.all_meta()}

    # ---------------------------------------------------------------- curated papers
    section("curated papers")
    sets = mockoa.curated()
    check("15 hand-picked papers exist", len(sets) == 15, str(len(sets)))
    by_dur = {}
    for s in sets:
        by_dur.setdefault(s["minutes"], []).append(s)
    check("five 1-hour papers", len(by_dur.get(60, [])) == 5, str(len(by_dur.get(60, []))))
    check("five 2-hour papers", len(by_dur.get(120, [])) == 5, str(len(by_dur.get(120, []))))
    check("five 3-hour papers", len(by_dur.get(180, [])) == 5, str(len(by_dur.get(180, []))))

    seen, dupes, missing, unrunnable = set(), [], [], []
    for s in sets:
        for pid in s["problems"]:
            if pid in seen:
                dupes.append(pid)
            seen.add(pid)
            m = meta.get(pid)
            if not m:
                missing.append(f"{s['id']}:{pid}")
            elif not m["runnable"]:
                unrunnable.append(f"{s['id']}:{pid}")
    check("every question exists in the bank", not missing, ", ".join(missing[:4]))
    check("every question is auto-judgeable", not unrunnable, ", ".join(unrunnable[:4]))
    check("no question appears in two papers", not dupes, ", ".join(dupes[:4]))
    check("45 distinct questions across the papers", len(seen) == 45, str(len(seen)))

    rank = {"Easy": 0, "Medium": 1, "Hard": 2}
    backwards = [s["id"] for s in sets
                 if any(rank.get(meta[a]["difficulty"], 1) > rank.get(meta[b]["difficulty"], 1)
                        for a, b in zip(s["problems"], s["problems"][1:]))]
    check("papers ramp (never harder then easier)", not backwards, ", ".join(backwards))
    sizes = {len(s["problems"]) for s in sets}
    check("every paper is 2-4 questions", sizes <= {2, 3, 4}, str(sizes))
    ids = [s["id"] for s in sets]
    check("paper ids are unique", len(set(ids)) == len(ids))

    # A hand-picked paper is allowed to be TIGHT — Amazon's intern OA really is two mediums in an
    # hour, and running out of time is part of what it measures. It is not allowed to be absurd, so
    # it obeys the same ceiling a generated paper does.
    over = [f"{s['id']}({mockoa.estimate(meta[p]['difficulty'] for p in s['problems'])}m)"
            for s in sets
            if mockoa.estimate(meta[p]["difficulty"] for p in s["problems"])
            > mockoa.FILL_HI * s["minutes"]]
    check("no paper is over-stuffed for its length", not over, ", ".join(over))

    # ---------------------------------------------------------------- the leak guard
    section("nothing names the technique")
    # The words a solver must NOT be handed. This is the same rule the problem list follows (it
    # hides `topic` for exactly this reason) — a mock OA blurb is the worst place to break it.
    LEAK = ["binary search", "dynamic programming", " dp ", "knapsack", "dijkstra", "bfs", "dfs",
            "union-find", "union find", "segment tree", "fenwick", "trie", "aho", "monotonic",
            "two pointer", "sliding window", "prefix sum", "bitmask", "topological", "memoi",
            "greedy", "heap", "priority queue", "matrix exponentiation", "sqrt decomposition",
            "backtrack", "shortest path", "flow", "combinatoric", "modular", "hashing"]
    leaks = []
    for s in sets:
        if s.get("themed"):
            continue          # themed drills name their family on purpose, in the title
        blob = f" {s.get('blurb', '').lower()} "
        for w in LEAK:
            if w in blob:
                leaks.append(f"{s['id']}: '{w.strip()}'")
    check("no blurb names an algorithm", not leaks, "; ".join(leaks[:5]))

    payload = c.get("/api/mock-oa").get_json()
    card_keys = set()
    for s in payload["sets"]:
        for card in s["cards"]:
            card_keys |= set(card.keys())
    check("cards carry no tags/topic", not (card_keys & {"tags", "topic", "tags_json"}),
          str(sorted(card_keys)))
    check("cards carry what a candidate needs",
          {"id", "title", "difficulty", "company"} <= card_keys, str(sorted(card_keys)))
    check("catalogue lists all 15", len(payload["sets"]) == 15, str(len(payload["sets"])))
    check("catalogue has no running paper on a fresh account", payload["running"] is None)

    # ---------------------------------------------------------------- the time model
    section("time model")
    for minutes in (60, 90, 120, 180):
        sh = mockoa.shapes(minutes)
        check(f"{minutes}m has usable shapes", len(sh) >= 2, str(sh))
        bad_len = [s for s in sh if not (2 <= len(s) <= 4)]
        check(f"{minutes}m shapes are 2-4 questions", not bad_len, str(bad_len))
        bad_fit = [s for s in sh if not (mockoa.FILL_LO * minutes <= mockoa.estimate(s)
                                         <= mockoa.FILL_HI * minutes)]
        check(f"{minutes}m shapes fit the clock", not bad_fit, str(bad_fit))
        bad_ramp = [s for s in sh if any(rank[a] > rank[b] for a, b in zip(s, s[1:]))]
        check(f"{minutes}m shapes ramp", not bad_ramp, str(bad_ramp))
        all_easy = [s for s in sh if all(d == "Easy" for d in s)]
        check(f"{minutes}m has no all-Easy paper", not all_easy, str(all_easy))
    # More time buys more questions — the property the whole "adjust the count to the difficulty"
    # ask rests on.
    check("a 3-hour paper can hold more than a 1-hour one",
          max(len(s) for s in mockoa.shapes(180)) > max(len(s) for s in mockoa.shapes(60)))

    # ---------------------------------------------------------------- random papers
    section("random papers")
    pool = store.indexed_rows()
    for minutes in (60, 90, 120, 180):
        picked = mockoa.compose(pool, minutes, seed=minutes)
        check(f"{minutes}m composes", 2 <= len(picked) <= 4, str(len(picked)))
        check(f"{minutes}m ramps",
              all(rank[a["difficulty"]] <= rank[b["difficulty"]] for a, b in zip(picked, picked[1:])),
              str([p["difficulty"] for p in picked]))
        check(f"{minutes}m has no duplicate question",
              len({p["id"] for p in picked}) == len(picked))
        check(f"{minutes}m only offers judgeable questions", all(p["runnable"] for p in picked))
    a = [p["id"] for p in mockoa.compose(pool, 120, seed=1)]
    b = [p["id"] for p in mockoa.compose(pool, 120, seed=2)]
    same = [p["id"] for p in mockoa.compose(pool, 120, seed=1)]
    check("the same seed gives the same paper", a == same)
    check("different seeds give different papers", a != b, f"{a} vs {b}")

    # Already-solved problems are the least useful thing to put in a mock OA.
    solved = {r["id"] for r in pool if r["difficulty"] == "Medium"}
    p = mockoa.compose(pool, 120, solved=solved, seed=5)
    unseen = [x for x in p if x["id"] not in solved]
    check("unsolved questions are preferred", len(unseen) >= 1, str([x["id"] for x in p]))
    excl = {r["id"] for r in pool[:80]}
    p2 = mockoa.compose(pool, 120, exclude=excl, seed=6)
    check("excluded questions never appear", all(x["id"] not in excl for x in p2))
    check("an impossible length is refused, not faked", mockoa.compose(pool, 400, seed=1) == [])

    # ---------------------------------------------------------------- lifecycle + the clock
    section("the clock belongs to the server")
    reset_papers()
    r = c.post("/api/mock-oa/start", json={"set_id": "ms-screen-60"}).get_json()
    check("a curated paper starts", r.get("ok") is True, json.dumps(r)[:120])
    att = r["attempt"]
    check("its questions are frozen at start", att["problems"] == mockoa.get_set("ms-screen-60")["problems"])
    check("the deadline is an hour out", 3500 <= att["seconds_left"] <= 3600, str(att["seconds_left"]))
    check("it is the running paper", (store.mock_running() or {}).get("id") == att["id"])

    # Reloading must not extend it: `ends_at` is written once and never touched again.
    ends_before = att["ends_at"]
    for _ in range(3):
        c.get("/api/mock-oa/active")
    check("polling does not move the deadline",
          store.mock_get(att["id"])["ends_at"] == ends_before)

    # Starting a second paper closes the first — two live clocks would both claim the same submits.
    r2 = c.post("/api/mock-oa/start", json={"set_id": "uber-rapid-60"}).get_json()
    check("starting another paper abandons the first",
          store.mock_get(att["id"])["status"] == "abandoned"
          and store.mock_running()["id"] == r2["attempt"]["id"])
    running = [x for x in store.mock_history(50) if x["status"] == "running"]
    check("only one paper is ever running", len(running) == 1, str(len(running)))

    # ---------------------------------------------------------------- scoring
    section("scoring")
    reset_papers()
    paper = c.post("/api/mock-oa/start", json={"set_id": "gs-superday-120"}).get_json()["attempt"]
    q1, q2, q3 = paper["problems"]
    store.record_attempt(q1, "cpp", "oa", "WA", 3, 10)
    store.record_attempt(q1, "cpp", "oa", "AC", 10, 10)      # solved on the second try
    store.record_attempt(q2, "cpp", "oa", "WA", 7, 10)       # partial credit only
    live = c.get("/api/mock-oa/active").get_json()["running"]["live"]
    per = {p["problem_id"]: p for p in live["per_problem"]}
    check("an AC is full marks", per[q1]["points"] == 100 and per[q1]["solved"])
    check("both submissions on Q1 are counted", per[q1]["submissions"] == 2, str(per[q1]["submissions"]))
    check("a near-miss earns partial credit", per[q2]["points"] == 70 and not per[q2]["solved"],
          str(per[q2]["points"]))
    check("an untouched question is zero, not blank",
          per[q3]["points"] == 0 and per[q3]["submissions"] == 0)
    check("the paper score is the mean of the questions", live["score"] == 57, str(live["score"]))
    check("solved counts only ACs", live["solved"] == 1 and live["attempted"] == 2)

    # A submission from before the paper started belongs to practice, not to this result.
    reset_papers()
    old_pid = mockoa.get_set("uber-rapid-60")["problems"][0]
    store.record_attempt(old_pid, "cpp", "lc", "AC", 10, 10,
                         created_at="2020-01-01T00:00:00+00:00")
    paper = c.post("/api/mock-oa/start", json={"set_id": "uber-rapid-60"}).get_json()["attempt"]
    live = c.get("/api/mock-oa/active").get_json()["running"]["live"]
    check("solving it yesterday does not score today's paper", live["score"] == 0, str(live["score"]))

    # ---------------------------------------------------------------- the deadline bites
    section("the deadline")
    reset_papers()
    paper = c.post("/api/mock-oa/start", json={"set_id": "amzn-intern-60"}).get_json()["attempt"]
    shift(paper["id"], started_min_ago=65, ends_min_from_now=-5)     # ran out five minutes ago
    store.record_attempt(paper["problems"][0], "cpp", "oa", "AC", 10, 10)   # ... and solved late
    active = c.get("/api/mock-oa/active").get_json()
    check("an expired paper is not still running", active["running"] is None)
    check("expiry closes it server-side",
          active.get("just_finished", {}).get("status") == "finished")
    check("a submission after time is up does not count",
          active["just_finished"]["score"]["score"] == 0,
          str(active["just_finished"]["score"]["score"]))
    check("the recorded end is the deadline, not now",
          active["just_finished"]["ended_at"] == store.mock_get(paper["id"])["ends_at"])

    # Three tabs all noticing the expiry must not rewrite the result.
    again = c.post("/api/mock-oa/finish", json={"attempt_id": paper["id"]}).get_json()
    check("finishing twice is idempotent",
          again["ok"] and again["attempt"]["score"]["score"] == 0
          and again["attempt"]["ended_at"] == active["just_finished"]["ended_at"])

    # Finishing early is the candidate's call and must score what they had at that moment.
    reset_papers()
    paper = c.post("/api/mock-oa/start", json={"set_id": "gs-screen-60"}).get_json()["attempt"]
    store.record_attempt(paper["problems"][0], "cpp", "oa", "AC", 5, 5)
    fin = c.post("/api/mock-oa/finish", json={}).get_json()
    check("finishing early scores what was in", fin["ok"] and fin["attempt"]["score"]["score"] == 50,
          str(fin["attempt"]["score"]["score"]))
    check("nothing is running afterwards", store.mock_running() is None)
    late = store.record_attempt(paper["problems"][1], "cpp", "oa", "AC", 5, 5)
    check("submitting after you hand in changes nothing",
          store.mock_get(paper["id"])["score"]["score"] == 50, str(late))

    # ---------------------------------------------------------------- history + validation
    section("history and bad input")
    hist = c.get("/api/mock-oa").get_json()["history"]
    check("finished papers appear in history", len(hist) >= 1, str(len(hist)))
    check("history never contains a running paper", all(h["status"] != "running" for h in hist))
    hid = hist[0]["id"]
    check("a past paper's report is readable",
          c.get(f"/api/mock-oa/attempt/{hid}").get_json()["attempt"]["id"] == hid)
    check("a past paper can be deleted", c.delete(f"/api/mock-oa/attempt/{hid}").get_json()["ok"])
    check("deleting it removes it", store.mock_get(hid) is None)
    check("a missing paper is a 404", c.get("/api/mock-oa/attempt/999999").status_code == 404)

    check("an unknown set is refused", c.post("/api/mock-oa/start", json={"set_id": "nope"}).status_code == 404)
    one = c.post("/api/mock-oa/start", json={"minutes": 60, "problems": ["flipkart-q1-golden-price"]})
    check("a one-question paper is refused", one.get_json()["ok"] is False)
    five = c.post("/api/mock-oa/start", json={"minutes": 180, "problems": [
        "flipkart-q1-golden-price", "goldman-2048", "goldman-book-cricket",
        "uber-q1-min-penalty-partition", "deshaw-celebrity"]})
    check("a five-question paper is refused", five.get_json()["ok"] is False)
    dup = c.post("/api/mock-oa/start", json={"minutes": 60, "problems": [
        "goldman-2048", "goldman-2048"]})
    check("the same question twice is refused", dup.get_json()["ok"] is False)
    junk = c.post("/api/mock-oa/start", json={"minutes": 60, "problems": ["does-not-exist", "goldman-2048"]})
    check("an unknown question is refused", junk.get_json()["ok"] is False)
    rnd = c.post("/api/mock-oa/random", json={"minutes": 120}).get_json()
    check("the random endpoint returns a startable paper",
          rnd["ok"] and 2 <= len(rnd["problems"]) <= 4)
    check("a random paper does not start itself", store.mock_running() is None)
    check("an unfillable length is a clean refusal",
          c.post("/api/mock-oa/random", json={"minutes": 300}).status_code == 409)

    # ---------------------------------------------------------------- wiring
    section("front-end wiring")
    static = os.path.join(APP, "static")
    html = open(os.path.join(static, "index.html"), encoding="utf-8").read()
    js = open(os.path.join(static, "mockoa.js"), encoding="utf-8").read()
    app_js = open(os.path.join(static, "app.js"), encoding="utf-8").read()
    sheets_js = open(os.path.join(static, "sheets.js"), encoding="utf-8").read()
    css = open(os.path.join(static, "style.css"), encoding="utf-8").read()
    check("the tab exists", 'data-view="mock"' in html)
    check("the view exists", 'id="mock-view"' in html and 'id="mock-inner"' in html)
    check("the running bar is outside every view",
          re.search(r'</header>.*?id="mock-bar".*?<div class="workspace"', html, re.S) is not None)
    check("mockoa.js is loaded", "mockoa.js?v=" in html)
    check("the view switcher knows the tab", "view === 'mock'" in sheets_js and "OAMockOA" in sheets_js)
    check("the deep link works", "h === 'mock'" in sheets_js)
    check("the judge re-enables submit during a paper", "inPaper" in app_js
          and "mode === 'lc' || inPaper" in app_js)
    check("the judge repaints the bar after a submit", "OAMockOA.refresh()" in app_js)
    check("the bar survives a reload", "async function boot()" in js and "/api/mock-oa/active" in js)
    check("the server's clock wins", "S.left = r.running.seconds_left" in js)
    check("the bar is styled", ".mk-bar {" in css and ".mk-clock" in css)
    check("static versions were bumped",
          "style.css?v=43" in html and "app.js?v=18" in html and "sheets.js?v=26" in html)

    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}): {', '.join(FAILS[:10])}")
        return 1
    print("ALL MOCK OA INVARIANTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
