"""OA Judge — Flask server. Serves the static UI and the JSON API defined in API.md."""
import datetime
import json
import os
import secrets
import sys

from flask import Flask, g, jsonify, request, send_from_directory, session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auth  # noqa: E402  (GitHub OAuth; no-op when AUTH is not configured)
import config  # noqa: E402
import cp  # noqa: E402  (CP + System Design sheets: fetchers + deterministic tracker)
import db  # noqa: E402
import mockoa  # noqa: E402  (timed multi-problem OA papers: catalogue, time model, composition)
import sharing  # noqa: E402  (Phase 5: git sync + problem authoring/publish)
import store  # noqa: E402  (v2 SQLite persistence; replaces runner.history)
from runner import execute, md, problems, stress  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = Flask(__name__, static_folder=None)

# Session signing key. In hosted mode it must be stable (set OAJ_SECRET_KEY) so logins survive a
# restart; locally an ephemeral key is fine because login is unused.
app.secret_key = config.SECRET_KEY or secrets.token_hex(32)
app.permanent_session_lifetime = datetime.timedelta(days=30)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.register_blueprint(auth.bp)

# In hosted mode every personal query is scoped to the logged-in user; locally it stays the
# implicit local user. This one line is what makes the whole app multi-tenant.
store.set_user_provider(auth.current_user_id)

# Endpoints reachable without a login (everything else requires one when AUTH is on).
_PUBLIC_PATHS = {"/", "/api/health", "/api/me"}
# The worker authenticates with X-Worker-Token, not a user session, so these two bypass the login
# guard and do their own check (_worker_authed). They are the only such endpoints.
_WORKER_PATHS = {"/api/interview/worker/lease", "/api/interview/worker/result"}


# Presence: throttle last_seen writes to at most once per user per this many seconds, so a burst of
# requests (autosave, facets, problems) is a single cheap UPDATE, not one per call.
_TOUCH_EVERY_S = 45
_last_touch: dict[int, float] = {}


def _touch_presence(user_id):
    import time
    now = time.time()
    if now - _last_touch.get(user_id, 0) < _TOUCH_EVERY_S:
        return
    _last_touch[user_id] = now
    try:
        store.touch_user(user_id)
    except Exception:
        pass


@app.before_request
def _resolve_user():
    if not config.AUTH_ENABLED:
        return None
    g.user_id = session.get("user_id")
    p = request.path
    if g.user_id and p.startswith("/api/"):
        _touch_presence(g.user_id)   # piggyback presence on real traffic; no heartbeat
    if p in _PUBLIC_PATHS or p in _WORKER_PATHS or p.startswith("/static/") or p.startswith("/auth/"):
        return None
    if not g.user_id:
        # API calls get a clean 401 (the frontend shows the login screen); anything else
        # bounces to the login page.
        if p.startswith("/api/"):
            return jsonify({"error": "login required", "login_url": "/auth/login"}), 401
        from flask import redirect
        return redirect("/auth/login")
    return None


# ----------------------------------------------------------------- static UI
@app.after_request
def _no_cache(resp):
    # Local dev tool: never let the browser serve stale index.html/app.js/style.css.
    # (A cached editor is exactly why a CSS fix can look like "still broken" after reload.)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


# ----------------------------------------------------------------- problem list / detail
def _ensure_index():
    """Build the search index if it's empty (first run / fresh DB). Cheap no-op once populated."""
    try:
        if store.index_count() == 0:
            store.reindex_problems(problems.all_meta())
    except Exception:
        pass


@app.route("/api/problems")
def api_problems():
    """Paginated, filtered search over the problem index — scales to thousands. Query params:
    source, company, difficulty, topic, q, solved (solved|unsolved), sort (title|recent),
    page, page_size."""
    _ensure_index()
    a = request.args
    def _int(name, default):
        try:
            return max(1, int(a.get(name, default)))
        except (TypeError, ValueError):
            return default
    return jsonify(store.search_problems(
        source=a.get("source") or None, company=a.get("company") or None,
        difficulty=a.get("difficulty") or None, topic=a.get("topic") or None,
        q=a.get("q") or None, solved=a.get("solved") or None,
        sort=a.get("sort") or "title",
        page=_int("page", 1), page_size=min(_int("page_size", 50), 200)))


@app.route("/api/facets")
def api_facets():
    """Sidebar grouping + filter counts (per source / company / difficulty)."""
    _ensure_index()
    return jsonify(store.problem_facets())


@app.route("/api/reindex", methods=["POST"])
def api_reindex():
    """Force a rebuild of the search index from disk (used after authoring a problem locally)."""
    n = store.reindex_problems(problems.all_meta())
    return jsonify({"ok": True, "indexed": n})


@app.route("/api/problem/<pid>")
def api_problem(pid):
    p = problems.load(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    m = p["meta"]
    return jsonify({
        "id": m["id"], "title": m.get("title", m["id"]),
        "company": m.get("company", ""), "difficulty": m.get("difficulty", ""),
        "tags": m.get("tags", []),
        "statement_html": md.render(p["statement_md"]),
        "editorial_html": md.render(p["editorial_md"]) if p["editorial_md"] else "",
        "languages": m["languages"], "runnable": m["runnable"], "links": m["links"],
        "limits": m["limits"], "stubs": p["stubs"],
        "samples": [{"index": t["index"], "input": t["input"], "output": t["output"]}
                    for t in p["samples"]],
        "hidden_count": len(p["hidden"]),
    })


# ----------------------------------------------------------------- run (custom input)
@app.route("/api/run", methods=["POST"])
def api_run():
    body = request.get_json(force=True)
    p = problems.load(body["problem_id"])
    if p is None:
        return jsonify({"error": "not found"}), 404
    lang, source = body["language"], body["source"]
    stdin_data = body.get("stdin", "")
    if lang not in p["meta"]["languages"]:
        return jsonify({"error": f"language {lang} not enabled for this problem"}), 400

    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        store.record_run(p["meta"]["id"], lang, source, stdin_data, "",
                         compiled.compile_output, verdict="CE")
        return jsonify({"verdict": "CE", "compile_output": compiled.compile_output,
                        "stdout": "", "stderr": "", "exit_code": None, "signal": None,
                        "time_ms": 0, "memory_kb": 0})
    res = execute.run_once(lang, compiled, stdin_data,
                           time_ms=p["meta"]["limits"]["time_ms"],
                           memory_mb=p["meta"]["limits"]["memory_mb"])
    execute.cleanup(compiled)
    from runner import judge
    v = judge.verdict_for_run(res, memory_mb=p["meta"]["limits"]["memory_mb"]) or "OK"
    # v1 did not log runs at all — you could never look back at what you tried.
    store.record_run(p["meta"]["id"], lang, source, stdin_data, res.stdout, res.stderr,
                     exit_code=res.exit_code, signal=res.signal_name,
                     runtime_ms=res.time_ms, verdict=v)
    return jsonify({
        "verdict": v, "compile_output": "", "stdout": res.stdout, "stderr": res.stderr,
        "exit_code": res.exit_code, "signal": res.signal_name,
        "time_ms": res.time_ms, "memory_kb": res.memory_kb,
    })


# ----------------------------------------------------------------- submit (judge)
@app.route("/api/submit", methods=["POST"])
def api_submit():
    body = request.get_json(force=True)
    p = problems.load(body["problem_id"])
    if p is None:
        return jsonify({"error": "not found"}), 404
    lang, source = body["language"], body["source"]
    mode = body.get("mode", "lc")
    if lang not in p["meta"]["languages"]:
        return jsonify({"error": f"language {lang} not enabled for this problem"}), 400

    # Snapshot the exact code being judged before anything can overwrite it.
    store.snapshot_draft(p["meta"]["id"], lang, source, reason="pre-submit")

    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        attempt_id = store.record_attempt(
            p["meta"]["id"], lang, mode, "CE", 0, 0,
            source_code=source,
            compile_output=compiled.compile_output,
            duration_s=body.get("duration_s"))
        return jsonify({"verdict": "CE", "compile_output": compiled.compile_output,
                        "passed": 0, "total": 0, "time_ms_max": 0, "tests": [],
                        "attempt_id": attempt_id})

    limits, compare = p["meta"]["limits"], p["meta"]["compare"]
    cases = ([("sample", t) for t in p["samples"]] +
             [("hidden", t) for t in p["hidden"]])
    results, passed, tmax, overall = [], 0, 0, "AC"
    first_fail_idx = None
    fail_got = fail_stderr = None
    for idx, (group, t) in enumerate(cases, start=1):
        v, got, stderr, tms = execute.judge_case(
            lang, compiled, t["input"], t["output"],
            time_ms=limits["time_ms"], memory_mb=limits["memory_mb"], compare=compare)
        tmax = max(tmax, tms)
        if v == "AC":
            passed += 1
        elif overall == "AC":
            overall = v                       # first failing verdict becomes the overall verdict
            first_fail_idx = idx
            fail_got, fail_stderr = got, stderr   # kept for the attempt record, not the response
        visible = (group == "sample") or (mode == "lc")
        row = {"index": idx, "group": group, "verdict": v, "time_ms": tms, "visible": visible}
        if visible:
            row.update({"input": t["input"], "expected": t["output"],
                        "got": got, "stderr": stderr})
        results.append(row)
        # OA mode stops the solver from learning more than "test k failed": keep judging so the
        # index is right, but never leak I/O. (We still run every test for an honest pass count.)

    execute.cleanup(compiled)
    total = len(cases)
    if total == 0:
        overall = "AC"
    attempt_id = store.record_attempt(
        p["meta"]["id"], lang, mode, overall, passed, total,
        source_code=source, duration_s=body.get("duration_s"), runtime_ms=tmax,
        first_fail_idx=first_fail_idx,
        stdout_snippet=fail_got, stderr_snippet=fail_stderr)

    # Problem of the Day: an AC on today's POTD (on the day itself) extends the user's streak.
    if overall == "AC":
        pm = _potd_meta()
        if pm and pm.get("id") == p["meta"]["id"]:
            store.potd_mark_solved(_ist_today().isoformat(), pm["id"])

    # Close an OA session if the frontend opened one, so time-per-problem is real data
    # rather than the NULL every v1 row carried.
    sid = body.get("oa_session_id")
    if sid:
        store.end_oa_session(int(sid), duration_s=body.get("duration_s"), result=overall)

    return jsonify({"verdict": overall, "compile_output": "", "passed": passed,
                    "total": total, "time_ms_max": tmax, "tests": results,
                    "attempt_id": attempt_id})


# ----------------------------------------------------------------- stress
@app.route("/api/stress", methods=["POST"])
def api_stress():
    body = request.get_json(force=True)
    p = problems.load(body["problem_id"])
    if p is None:
        return jsonify({"error": "not found"}), 404
    lang, source = body["language"], body["source"]
    if lang not in p["meta"]["languages"]:
        return jsonify({"error": f"language {lang} not enabled"}), 400
    iters = int(body.get("iterations", 300))
    return jsonify(stress.run(p, lang, source, iterations=iters))


# ----------------------------------------------------------------- history
@app.route("/api/history")
def api_history():
    return jsonify({"attempts": store.attempts(),
                    "revisit": store.revisit_list(problems.list_ids())})


@app.route("/api/history/<pid>")
def api_history_one(pid):
    return jsonify({"attempts": store.attempts(pid),
                    "revisit": store.revisit_list(problems.list_ids())})


# ----------------------------------------------------------------- attempts (with code)
@app.route("/api/attempt/<int:attempt_id>")
def api_attempt(attempt_id):
    """Full attempt including the source that was judged — the code viewer and diff use this."""
    a = store.attempt(attempt_id)
    if a is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(a)


# ----------------------------------------------------------------- drafts (autosave)
@app.route("/api/draft/<pid>/<lang>", methods=["GET"])
def api_get_draft(pid, lang):
    return jsonify(store.get_draft(pid, lang) or {})


@app.route("/api/draft/<pid>/<lang>", methods=["PUT"])
def api_put_draft(pid, lang):
    """Debounced autosave target. Replaces browser localStorage, which was per-origin
    (so the 5000 -> 5137 port move stranded it) and kept no history."""
    body = request.get_json(force=True)
    store.save_draft(pid, lang, body.get("source", ""), body.get("cursor_pos"))
    return jsonify({"ok": True})


@app.route("/api/drafts")
def api_all_drafts():
    return jsonify({"drafts": store.all_drafts()})


# ----------------------------------------------------------------- snapshots (time travel)
@app.route("/api/snapshots/<pid>")
def api_snapshots(pid):
    return jsonify({"snapshots": store.snapshots(pid, request.args.get("lang"))})


@app.route("/api/snapshot/<int:snapshot_id>")
def api_snapshot(snapshot_id):
    s = store.snapshot(snapshot_id)
    if s is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(s)


@app.route("/api/snapshot", methods=["POST"])
def api_make_snapshot():
    body = request.get_json(force=True)
    sid = store.snapshot_draft(body["problem_id"], body["language"],
                               body.get("source", ""), body.get("reason", "periodic"))
    return jsonify({"ok": True, "snapshot_id": sid})   # sid is null when unchanged


# ----------------------------------------------------------------- bug reports
@app.route("/api/report", methods=["POST"])
def api_report():
    """One-click issue report from the problem view. Low friction: just a problem id + message."""
    body = request.get_json(force=True)
    pid = (body.get("problem_id") or "").strip()
    msg = (body.get("message") or "").strip()
    if not pid or not msg:
        return jsonify({"error": "problem_id and message are required"}), 400
    rid = store.add_bug_report(pid, msg[:2000])
    return jsonify({"ok": True, "report_id": rid})


@app.route("/api/reports")
def api_reports():
    """Owner review of submitted reports. On a personal deployment any logged-in user may list them;
    when OAJ_OWNER_GITHUB_ID is set, only that user may."""
    owner = os.environ.get("OAJ_OWNER_GITHUB_ID")
    if owner:
        me = store.get_user(getattr(g, "user_id", None) or 0) or {}
        if str(me.get("github_id")) != str(owner):
            return jsonify({"error": "forbidden"}), 403
    return jsonify({"reports": store.bug_reports(status=request.args.get("status"))})


# ----------------------------------------------------------------- runs
@app.route("/api/runs/<pid>")
def api_runs(pid):
    return jsonify({"runs": store.runs(pid)})


# ----------------------------------------------------------------- OA sessions
@app.route("/api/oa-session", methods=["POST"])
def api_start_oa_session():
    body = request.get_json(force=True)
    return jsonify({"session_id": store.start_oa_session(body["problem_id"])})


@app.route("/api/oa-session/<int:session_id>", methods=["DELETE"])
def api_abandon_oa_session(session_id):
    store.end_oa_session(session_id, abandoned=True)
    return jsonify({"ok": True})


# ----------------------------------------------------------------- notes / flags
@app.route("/api/note/<pid>", methods=["GET", "PUT"])
def api_note(pid):
    if request.method == "PUT":
        store.save_note(pid, request.get_json(force=True).get("body", ""))
        return jsonify({"ok": True})
    return jsonify({"body": store.get_note(pid)})


@app.route("/api/flags/<pid>", methods=["GET", "PUT"])
def api_flags(pid):
    if request.method == "PUT":
        b = request.get_json(force=True)
        store.save_flags(pid, b.get("starred"), b.get("revisit"), b.get("confidence"))
        return jsonify({"ok": True})
    return jsonify(store.get_flags(pid))


# ----------------------------------------------------------------- stats / health
@app.route("/api/stats")
def api_stats():
    return jsonify(store.stats())


@app.route("/api/export")
def api_export():
    """Everything you've produced as a downloadable zip: the raw DB plus a readable tree of
    your submitted code and notes as plain files. Your data is never locked inside this app."""
    import io
    import zipfile
    from datetime import datetime

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # The database itself, so an export is a complete backup.
        if os.path.exists(db.DB_PATH):
            z.write(db.DB_PATH, "judge.db")
        # Human-readable copies: latest attempt code + notes per problem.
        ext = {"cpp": "cpp", "py": "py"}
        for a in store.attempts(limit=100000):
            if not a.get("has_code"):
                continue
            full = store.attempt(a["id"])
            if not full or not full.get("source_code"):
                continue
            e = ext.get(full["language"], "txt")
            path = f"code/{a['problem_id']}/attempt-{a['id']}-{full['verdict']}.{e}"
            z.writestr(path, full["source_code"])
        for pid in problems.list_ids():
            note = store.get_note(pid)
            if note.strip():
                z.writestr(f"notes/{pid}.md", note)
    buf.seek(0)
    from flask import send_file
    stamp = datetime.now().strftime("%Y%m%d")
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"oa-judge-export-{stamp}.zip")


@app.route("/api/health")
def api_health():
    """Used by the launcher to detect an already-running instance instead of colliding."""
    import shutil
    return jsonify({"ok": True, "version": 2,
                    "db": db.DB_PATH,
                    "gpp": bool(shutil.which("g++")),
                    "problems": len(problems.list_ids())})


@app.route("/api/presence")
def api_presence():
    """Best-effort "who's online": users who made a request in the last few minutes. Free — it reads
    last_seen (bumped by real traffic) and never triggers a heartbeat, so it can't keep the machine
    awake. In single-user local mode there's no roster to show."""
    if not config.AUTH_ENABLED:
        return jsonify({"enabled": False, "users": [], "recent": []})
    me = getattr(g, "user_id", None)
    users = store.online_users(within_seconds=300)
    recent = store.presence_recent(within_seconds=30 * 86400, limit=60)
    for u in users:
        u["is_me"] = (u["id"] == me)
    for u in recent:
        u["is_me"] = (u["id"] == me)
    return jsonify({"enabled": True, "users": users, "recent": recent, "me": me})


# ----------------------------------------------------------------- problem of the day
_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _ist_today():
    return datetime.datetime.now(_IST).date()


def _potd_meta(day=None):
    """The deterministic POTD meta for `day` (default today, IST): index = ordinal mod N over the
    id-sorted bank. Same for everyone, no storage."""
    metas = sorted(problems.all_meta(), key=lambda m: m.get("id", ""))
    if not metas:
        return None
    d = day or _ist_today()
    return metas[d.toordinal() % len(metas)]


def _potd_streak(days: set, today) -> int:
    """Consecutive-day streak ending today or (if today isn't solved yet) yesterday — GitHub-style,
    so an unsolved-but-still-open today doesn't zero a live streak."""
    one = datetime.timedelta(days=1)
    if today.isoformat() in days:
        anchor = today
    elif (today - one).isoformat() in days:
        anchor = today - one
    else:
        return 0
    n, d = 0, anchor
    while d.isoformat() in days:
        n += 1
        d -= one
    return n


def _potd_best(days: set) -> int:
    if not days:
        return 0
    ds = sorted(datetime.date.fromisoformat(x) for x in days)
    best = run = 1
    for i in range(1, len(ds)):
        run = run + 1 if (ds[i] - ds[i - 1]).days == 1 else 1
        best = max(best, run)
    return best


@app.route("/api/potd")
def api_potd():
    m = _potd_meta()
    if not m:
        return jsonify({"ok": False})
    today = _ist_today()
    days = store.potd_solved_days()
    return jsonify({"ok": True, "date": today.isoformat(), "id": m.get("id"),
                    "title": m.get("title"), "difficulty": m.get("difficulty"),
                    "company": store.canon_company(m.get("company", "")), "topic": m.get("topic"),
                    "solved": today.isoformat() in days,
                    "streak": _potd_streak(days, today), "best": _potd_best(days)})


# ----------------------------------------------------------------- sharing (Phase 5)
@app.route("/api/bank/status")
def api_bank_status():
    return jsonify(sharing.status())


@app.route("/api/bank/sync", methods=["POST"])
def api_bank_sync():
    """git pull the problems bank, then rebuild the search index so new problems show up in the
    grouped sidebar immediately."""
    result = sharing.sync()
    if result.get("ok"):
        try:
            store.reindex_problems(problems.all_meta())
        except Exception:
            pass
    return jsonify(result)


@app.route("/api/bank/author", methods=["POST"])
def api_bank_author():
    """Scaffold → generate hidden tests → verify. Only a green package is left on disk ready to
    publish; a failing one is reported so the author can fix the reference or samples."""
    spec = request.get_json(force=True)
    made = sharing.scaffold(spec)
    if not made.get("ok"):
        return jsonify(made), 400
    pid = made["id"]
    hid = sharing.make_hidden(pid)
    ver = sharing.verify_one(pid)
    return jsonify({"ok": ver.get("ok", False), "id": pid,
                    "hidden": hid, "verify": ver})


@app.route("/api/bank/publish", methods=["POST"])
def api_bank_publish():
    body = request.get_json(force=True)
    pid = body.get("id")
    if not pid:
        return jsonify({"ok": False, "error": "id required"}), 400
    # Re-verify before publishing so a package edited after authoring can't ship broken.
    ver = sharing.verify_one(pid)
    if not ver.get("ok"):
        return jsonify({"ok": False, "error": "verification failed — not publishing",
                        "verify": ver}), 400
    return jsonify(sharing.publish(pid, body.get("message", "")))


# ============================================================ CP + System Design sheets
_STATS_TTL = 6 * 3600      # refresh a linked site's stats at most this often
_CONTEST_TTL = 3600        # refresh the upcoming-contest feed hourly


@app.route("/api/sheets")
def api_sheets():
    return jsonify({"sheets": cp.list_sheets()})


@app.route("/api/sheet/<sid>")
def api_sheet(sid):
    sheet = cp.load_sheet(sid)
    if not sheet:
        return jsonify({"error": "no such sheet"}), 404
    prog = store.sheet_progress()
    ids = cp.all_item_ids(sheet)
    done = sum(1 for i in ids if prog.get(i) == "done")
    return jsonify({"sheet": sheet, "progress": prog,
                    "counts": {"total": len(ids), "done": done}})


@app.route("/api/sheet-item", methods=["POST"])
def api_sheet_item():
    b = request.get_json(force=True)
    item_id = b.get("item_id")
    if not item_id:
        return jsonify({"ok": False, "error": "item_id required"}), 400
    if b.get("clear"):
        store.clear_sheet_item(item_id)
    else:
        store.set_sheet_item(item_id, b.get("status", "done"))
    return jsonify({"ok": True})


@app.route("/api/sheet-code", methods=["GET"])
def api_sheet_code_get():
    item_id = request.args.get("item", "")
    if not item_id:
        return jsonify({"ok": False, "error": "item required"}), 400
    return jsonify({"ok": True, **store.sheet_code_get(item_id)})


@app.route("/api/sheet-code", methods=["POST"])
def api_sheet_code_set():
    b = request.get_json(force=True)
    item_id = b.get("item_id")
    if not item_id:
        return jsonify({"ok": False, "error": "item_id required"}), 400
    # Cap at 64 KB — a scratchpad, not a repo; keeps a runaway paste from bloating the DB.
    code = (b.get("code") or "")[:65536]
    lang = (b.get("lang") or "cpp")[:16]
    store.set_sheet_code(item_id, lang, code)
    return jsonify({"ok": True})


# ============================================================ Mock OA (timed papers)
# Problem cards here carry title / difficulty / company and NOTHING else — no tags, no topic —
# because that is the rule the problem list already follows: naming the technique is telling the
# candidate the answer, and a mock OA is the one place that matters most.
def _paper_cards(problem_ids: list[str]) -> list[dict]:
    solved = store.solved_ids()
    out = []
    for pid in problem_ids:
        m = problems.meta_only(pid)
        out.append({
            "id": pid,
            "title": (m or {}).get("title", pid),
            "difficulty": (m or {}).get("difficulty", ""),
            "company": (m or {}).get("company", ""),
            "runnable": bool((m or {}).get("runnable", False)),
            "missing": m is None,
            "solved_ever": pid in solved,
        })
    return out


def _paper_state(att: dict) -> dict:
    """A running paper as the browser needs it: the frozen questions, live per-question status, and
    the seconds left — computed from the stored deadline, never from a client clock."""
    import datetime as _dt
    now = store._now()
    until = min(now, att["ends_at"])
    rows = store.mock_window_attempts(att["problems"], att["started_at"], until)
    live = mockoa.score_paper(att["problems"], rows)
    ends = _dt.datetime.fromisoformat(att["ends_at"])
    left = (ends - _dt.datetime.now(_dt.timezone.utc)).total_seconds()
    return {**att, "cards": _paper_cards(att["problems"]), "live": live,
            "seconds_left": max(0, int(left)), "expired": left <= 0}


@app.route("/api/mock-oa")
def api_mock_oa():
    """Catalogue + history. The curated sets are enriched with their questions so a card can show
    the ramp (2 Medium + 1 Hard) before you commit three hours to it."""
    sets = []
    for s in mockoa.curated():
        cards = _paper_cards(s["problems"])
        sets.append({
            "id": s["id"], "title": s["title"], "company": s.get("company", ""),
            "minutes": s["minutes"], "blurb": s.get("blurb", ""),
            "themed": bool(s.get("themed")),
            "questions": len(s["problems"]),
            "difficulties": [c["difficulty"] for c in cards],
            "estimate": mockoa.estimate(c["difficulty"] for c in cards),
            "cards": cards,
        })
    running = store.mock_running()
    return jsonify({
        "sets": sets,
        "durations": mockoa.DURATIONS,
        "cost_min": mockoa.COST_MIN,
        "running": _paper_state(running) if running else None,
        "history": [h for h in store.mock_history(60) if h["status"] != "running"],
    })


@app.route("/api/mock-oa/random", methods=["POST"])
def api_mock_oa_random():
    """Compose a random paper WITHOUT starting it, so the shuffle button costs nothing and the
    candidate can see what they are agreeing to."""
    b = request.get_json(force=True) or {}
    minutes = max(30, min(300, int(b.get("minutes") or 120)))
    pool = store.indexed_rows()
    solved = store.solved_ids()
    picked = mockoa.compose(pool, minutes, solved=solved, seed=b.get("seed"))
    if not picked:
        return jsonify({"ok": False, "error": "the bank cannot fill a paper this long"}), 409
    ids = [p["id"] for p in picked]
    cards = _paper_cards(ids)
    return jsonify({"ok": True, "minutes": minutes, "problems": ids, "cards": cards,
                    "estimate": mockoa.estimate(c["difficulty"] for c in cards)})


@app.route("/api/mock-oa/start", methods=["POST"])
def api_mock_oa_start():
    b = request.get_json(force=True) or {}
    set_id = b.get("set_id")
    if set_id:
        s = mockoa.get_set(set_id)
        if not s:
            return jsonify({"ok": False, "error": "no such set"}), 404
        title, minutes, ids = s["title"], s["minutes"], list(s["problems"])
    else:
        minutes = max(30, min(300, int(b.get("minutes") or 120)))
        ids = [str(x) for x in (b.get("problems") or [])]
        if not (mockoa.MIN_QUESTIONS <= len(ids) <= mockoa.MAX_QUESTIONS):
            return jsonify({"ok": False, "error": "a paper is 2 to 4 questions"}), 400
        if len(set(ids)) != len(ids):
            return jsonify({"ok": False, "error": "duplicate question"}), 400
        for pid in ids:
            m = problems.meta_only(pid)
            if not m or not m.get("runnable"):
                return jsonify({"ok": False, "error": f"not a runnable problem: {pid}"}), 400
        set_id, title = "random", f"Random paper · {minutes} min"
    return jsonify({"ok": True, "attempt": _paper_state(store.mock_start(set_id, title, minutes, ids))})


@app.route("/api/mock-oa/active")
def api_mock_oa_active():
    """Polled by the running-paper bar. When the deadline has passed the paper is closed HERE,
    server-side, so a closed laptop still ends the OA at the right time and with the right score."""
    att = store.mock_running()
    if not att:
        return jsonify({"running": None})
    state = _paper_state(att)
    if state["expired"]:
        # Carries `cards` because this IS the report the browser is about to draw — the client
        # cannot re-fetch what it needs mid-render, and a report with no questions on it is worse
        # than no report.
        done = store.mock_finish(att["id"])
        return jsonify({"running": None,
                        "just_finished": {**done, "cards": _paper_cards(done["problems"])}})
    return jsonify({"running": state})


@app.route("/api/mock-oa/finish", methods=["POST"])
def api_mock_oa_finish():
    b = request.get_json(force=True) or {}
    att = store.mock_running()
    aid = int(b.get("attempt_id") or (att or {}).get("id") or 0)
    if not aid:
        return jsonify({"ok": False, "error": "no running paper"}), 404
    done = store.mock_finish(aid, status=b.get("status") or "finished")
    if not done:
        return jsonify({"ok": False, "error": "no such paper"}), 404
    return jsonify({"ok": True, "attempt": {**done, "cards": _paper_cards(done["problems"])}})


@app.route("/api/mock-oa/attempt/<int:aid>")
def api_mock_oa_attempt(aid):
    att = store.mock_get(aid)
    if not att:
        return jsonify({"error": "not found"}), 404
    return jsonify({"attempt": {**att, "cards": _paper_cards(att["problems"])}})


@app.route("/api/mock-oa/attempt/<int:aid>", methods=["DELETE"])
def api_mock_oa_delete(aid):
    return jsonify({"ok": store.mock_delete(aid)})


# Generic compile-and-run: a gcc/ideone-style playground, not tied to any problem. Runs untrusted
# code in the exact same sandbox as the judge (see runner/sandbox.py), so it adds no new risk
# surface — just fixed, generous limits and no expected-output comparison.
_SCRATCH_LANGS = {"cpp": "cpp", "c": "cpp", "py": "py", "python": "py", "py3": "py", "pypy": "py"}
_SCRATCH_TIME_MS = 5000
_SCRATCH_MEM_MB = 256
_VIZ_TIME_MS = 8000          # Python tracer budget
_VIZ_CPP_TIME_MS = 12000     # gdb is slower per step
_VIZ_TEMPLATES = {}


def _viz_template(name):
    """Load a tracer template file once (kept as a file so it reads like normal Python)."""
    if name not in _VIZ_TEMPLATES:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name),
                  encoding="utf-8") as f:
            _VIZ_TEMPLATES[name] = f.read()
    return _VIZ_TEMPLATES[name]


def _visualize_py(source, stdin_data):
    program = ("USER_SRC = " + json.dumps(source) + "\nSTDIN_DATA = " + json.dumps(stdin_data)
               + "\n" + _viz_template("_viz_tracer.pyt"))
    compiled = execute.compile_for("py", program)
    if not compiled.ok:
        execute.cleanup(compiled)
        return {"ok": False, "error": "Could not stage the tracer."}
    res = execute.run_once("py", compiled, "", time_ms=_VIZ_TIME_MS, memory_mb=_SCRATCH_MEM_MB)
    execute.cleanup(compiled)
    try:
        return json.loads(res.stdout or "")
    except (ValueError, TypeError):
        tail = (res.stderr or "").strip().splitlines()
        return {"ok": False, "error": tail[-1][:300] if tail else
                "The program didn't finish in time or produced no trace (infinite loop / too many steps?)."}


def _visualize_cpp(source, stdin_data):
    """Compile with -g -O0, then drive gdb to single-step, staying in the user's code (STL/library is
    skipped). gdb writes the same-shape trace JSON to trace.json in the workspace."""
    from runner import run_cpp, sandbox
    wd = sandbox.workspace()
    try:
        src = os.path.join(wd, "sol.cpp")
        binp = os.path.join(wd, "sol")
        with open(src, "w", encoding="utf-8") as f:
            f.write(source)
        with open(os.path.join(wd, "prog_in.txt"), "w", encoding="utf-8") as f:
            f.write(stdin_data)
        with open(os.path.join(wd, "viz_gdb.py"), "w", encoding="utf-8") as f:
            f.write(_viz_template("_viz_gdb.pyt"))
        rc, out = sandbox.compile_argv(
            [run_cpp.GXX, run_cpp.STD, "-g", "-O0", "-w", "-o", binp, src], cwd=wd, timeout=25)
        if rc != 0:
            return {"ok": False, "error": (out or "compilation failed")[:1500], "compile": True}
        res = sandbox.run(["gdb", "-q", "-batch", "-nx", "-x", "viz_gdb.py", "--args", "./sol"],
                          "", time_ms=_VIZ_CPP_TIME_MS, memory_mb=512, cwd=wd)
        try:
            with open(os.path.join(wd, "trace.json"), encoding="utf-8") as f:
                return json.loads(f.read())
        except (OSError, ValueError):
            tail = (res.stderr or res.stdout or "").strip().splitlines()
            if any("ptrace" in t.lower() or "operation not permitted" in t.lower() for t in tail):
                return {"ok": False, "error": "The host doesn't permit gdb tracing here."}
            return {"ok": False, "error": tail[-1][:300] if tail else
                    "gdb produced no trace (the program may not have reached main, or timed out)."}
    finally:
        execute.cleanup(type("C", (), {"workdir": wd})())


@app.route("/api/visualize", methods=["POST"])
def api_visualize():
    """Step-through execution trace (Python Tutor style) for the user's code. Python uses sys.settrace;
    C++ is driven through gdb. Both run in the same sandbox as the judge and emit one JSON step log:
    {ok, lang, steps:[{line, func, stack:[{func,line,locals:{name:{t,v}}}], o}], stdout, truncated}."""
    b = request.get_json(force=True)
    lang = _SCRATCH_LANGS.get((b.get("lang") or "py").lower())
    if lang not in ("py", "cpp"):
        return jsonify({"ok": False, "error": "The visualizer supports Python and C++."}), 400
    source = (b.get("source") or "")[:100000]
    stdin_data = (b.get("stdin") or "")[:100000]
    if not source.strip():
        return jsonify({"ok": False, "error": "Nothing to visualize — the editor is empty."}), 400
    data = _visualize_py(source, stdin_data) if lang == "py" else _visualize_cpp(source, stdin_data)
    return jsonify(data)


@app.route("/api/scratch-run", methods=["POST"])
def api_scratch_run():
    b = request.get_json(force=True)
    lang = _SCRATCH_LANGS.get((b.get("lang") or "cpp").lower())
    if lang is None:
        return jsonify({"ok": False, "error": "Run supports C++ and Python only."}), 400
    source = (b.get("source") or "")[:200000]
    stdin_data = (b.get("stdin") or "")[:200000]
    if not source.strip():
        return jsonify({"ok": False, "error": "Nothing to compile — the editor is empty."}), 400
    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        return jsonify({"ok": True, "verdict": "CE", "compile_output": compiled.compile_output,
                        "stdout": "", "stderr": "", "exit_code": None, "signal": None,
                        "time_ms": 0, "memory_kb": 0})
    res = execute.run_once(lang, compiled, stdin_data,
                           time_ms=_SCRATCH_TIME_MS, memory_mb=_SCRATCH_MEM_MB)
    execute.cleanup(compiled)
    from runner import judge
    verdict = judge.verdict_for_run(res, memory_mb=_SCRATCH_MEM_MB) or "OK"
    return jsonify({"ok": True, "verdict": verdict, "compile_output": "",
                    "stdout": res.stdout, "stderr": res.stderr, "exit_code": res.exit_code,
                    "signal": res.signal_name, "time_ms": res.time_ms, "memory_kb": res.memory_kb})


_TOOLCHAIN = None


def _toolchain():
    """The real compiler/interpreter the playground uses, probed once and cached. Reported to the UI
    so a user sees exactly what their code runs on (e.g. 'GNU g++ 13.3.0 · C++17')."""
    global _TOOLCHAIN
    if _TOOLCHAIN is not None:
        return _TOOLCHAIN
    import subprocess
    import sys as _sys
    from runner import run_cpp
    first, ver = run_cpp.GXX, ""
    try:
        r = subprocess.run([run_cpp.GXX, "--version"], capture_output=True, text=True, timeout=5)
        line = (r.stdout.splitlines() or [""])[0].strip()
        if line:
            first, ver = line, line.split()[-1]
    except Exception:  # noqa: BLE001
        pass
    std = run_cpp.STD.replace("-std=", "").replace("c++", "C++").replace("gnu++", "GNU++")
    _TOOLCHAIN = {
        "cpp": {"label": f"GNU g++ {ver}".strip(), "std": std, "full": first},
        "py": {"label": "CPython " + _sys.version.split()[0], "std": "",
               "full": "Python " + _sys.version.split()[0]},
    }
    return _TOOLCHAIN


@app.route("/api/scratch-env")
def api_scratch_env():
    return jsonify(_toolchain())


def _stats_age(iso):
    try:
        return (datetime.datetime.now(datetime.timezone.utc)
                - datetime.datetime.fromisoformat(iso)).total_seconds()
    except Exception:
        return None


def _calibrate_goal():
    """The first time we ever see a Codeforces rating, pin it as the tracker's start point."""
    if store.cp_goal().get("start_rating") is not None:
        return
    p = (store.cp_stats_cache_get("codeforces") or {}).get("payload") or {}
    if not p.get("ok"):
        return
    hist = p.get("history") or []
    if hist:
        store.set_cp_goal(start_rating=hist[0]["r"], start_at=hist[0]["t"])
    elif p.get("rating") is not None:
        store.set_cp_goal(start_rating=p["rating"],
                          start_at=datetime.datetime.now(datetime.timezone.utc).date().isoformat())


def _refresh_cp_stats(handles):
    for site, handle in handles.items():
        fn = cp.FETCHERS.get(site)
        if fn and handle:
            res = fn(handle)
            store.cp_stats_cache_put(site, res, ok=bool(res.get("ok")))
    _calibrate_goal()


def _cp_payload():
    stats = {}
    for site in ("codeforces", "atcoder", "leetcode", "codechef"):
        c = store.cp_stats_cache_get(site)
        if c:
            stats[site] = {"data": c["payload"], "ok": c["ok"], "fetched_at": c["fetched_at"]}
    cf = store.cp_stats_cache_get("codeforces")
    trk = cp.tracker(store.cp_goal(), (cf or {}).get("payload") if cf else None)
    return {"handles": store.cp_handles(), "stats": stats, "tracker": trk, "goal": store.cp_goal()}


@app.route("/api/cp/handles", methods=["GET", "POST"])
def api_cp_handles():
    if request.method == "POST":
        b = request.get_json(force=True)
        for site in ("codeforces", "atcoder", "leetcode", "codechef"):
            if site in b:
                store.set_cp_handle(site, (b.get(site) or "").strip())
        return jsonify({"ok": True, "handles": store.cp_handles()})
    return jsonify({"handles": store.cp_handles()})


@app.route("/api/cp/sync", methods=["POST"])
def api_cp_sync():
    """Force-refresh every linked site now (the 'Refresh' button)."""
    _refresh_cp_stats(store.cp_handles())
    return jsonify(_cp_payload())


@app.route("/api/cp/stats")
def api_cp_stats():
    handles = store.cp_handles()
    if handles:
        stale = any(
            (store.cp_stats_cache_get(s) is None) or
            ((_stats_age(store.cp_stats_cache_get(s)["fetched_at"]) or 1e9) > _STATS_TTL)
            for s in handles)
        if stale:
            _refresh_cp_stats(handles)
    return jsonify(_cp_payload())


@app.route("/api/cp/contests")
def api_cp_contests():
    age = store.contests_age_seconds()
    if age is None or age > _CONTEST_TTL:
        rows = cp.fetch_contests()
        if rows:
            store.contests_replace(rows)
    return jsonify({"contests": store.contests_get()})


@app.route("/api/cp/goal", methods=["GET", "POST"])
def api_cp_goal():
    if request.method == "POST":
        b = request.get_json(force=True)
        store.set_cp_goal(target_rating=b.get("target_rating"), deadline=b.get("deadline"),
                          pace_per_day=b.get("pace_per_day"))
        return jsonify({"ok": True, "goal": store.cp_goal()})
    return jsonify({"goal": store.cp_goal()})


# ----------------------------------------------------------------- mock interview
# Quality lives in app/interview/: the app owns question choice, hint release, advancement and
# scoring; the model only supplies language and reports rubric point ids.
def _worker_authed() -> bool:
    """Workers authenticate with their own shared secret, never with a user session.

    Two separate identities on purpose: a logged-in friend can never lease jobs (so never sees
    another user's answers), and a worker can never act as a user.
    """
    tok = config.WORKER_TOKEN
    return bool(tok) and secrets.compare_digest(request.headers.get("X-Worker-Token", ""), tok)


@app.route("/api/interview/status")
def api_interview_status():
    """Who can answer a turn right now.

    Two independent paths, reported separately because they fail separately: `cloud` is the server
    calling Gemini itself (always up, but the free tier rate-limits), `host` is the owner's machine
    running agy (slower, but no quota). `online` is just "either" — what the UI gates starting on.
    """
    from interview import cloud, jobs, rubrics
    host, cl = jobs.online(), cloud.healthy()
    return jsonify({"online": host or cl, "cloud": cl, "host": host,
                    "cloud_configured": cloud.gemini.available(),
                    "rubrics": len(rubrics.list_ids()),
                    "used_today": jobs.used_today(g.get("user_id") or 1),
                    "daily_limit": jobs.DAILY_PER_USER})


@app.route("/api/interview/catalog")
def api_interview_catalog():
    """The topic list, plus what THIS user has already covered.

    `summaries()` is shared and cached across users, so per-user progress rides alongside it as a
    separate map rather than being merged into the cached rows.
    """
    from interview import dossier, rubrics
    return jsonify({"items": rubrics.summaries(),
                    "progress": dossier.topic_progress(g.get("user_id") or 1)})


@app.route("/api/interview/shapes")
def api_interview_shapes():
    """Loop shapes for mixed rounds, plus the subject list the custom builder excludes from."""
    from interview import mixed
    uid = g.get("user_id") or 1
    out = [mixed.preview(uid, name) for name in mixed.SHAPES]
    return jsonify({"shapes": [s for s in out if s["segments"]],
                    "subjects": mixed.available_subjects()})


@app.route("/api/interview/preview", methods=["POST"])
def api_interview_preview():
    """Preview a custom loop before committing to it — what would you actually be asked."""
    from interview import mixed
    b = request.get_json(force=True) or {}
    uid = g.get("user_id") or 1
    plan = mixed.compose(uid, "mixed_full", exclude=b.get("exclude") or [],
                         segments=int(b.get("segments") or 4))
    return jsonify({"preview": mixed.describe(plan), "segments": len(plan)})


@app.route("/api/interview/start", methods=["POST"])
def api_interview_start():
    from interview import jobs, mixed
    from interview import session as iv
    b = request.get_json(force=True) or {}
    uid = g.get("user_id") or 1
    # A shape (or a custom exclude list) composes a multi-subject loop weakness-first from the
    # dossier; a rubric_id is a single-subject session. Both land in the same session machinery.
    plan = None
    if b.get("rubric_ids"):
        plan = mixed.from_ids(b["rubric_ids"])          # "drill these exact topics" (weak spots)
    elif b.get("shape") or b.get("exclude") is not None:
        plan = mixed.compose(uid, b.get("shape") or "mixed_full",
                             exclude=b.get("exclude"),
                             segments=int(b["segments"]) if b.get("segments") else None)
    depth = "deep" if str(b.get("depth", "")).lower() == "deep" else "standard"
    s = iv.start(uid, b.get("rubric_id", ""), b.get("problem_id"), plan=plan, depth=depth)
    if not s:
        return jsonify({"error": "unknown rubric"}), 404
    j = jobs.enqueue(uid, s["session_id"], iv.build_payload(uid, s["session_id"]), "turn")
    if "error" in j:
        return jsonify(j), 429
    return jsonify({**s, "job_id": j["job_id"], "online": jobs.online()})


@app.route("/api/interview/answer", methods=["POST"])
def api_interview_answer():
    from interview import jobs
    from interview import session as iv
    b = request.get_json(force=True) or {}
    uid = g.get("user_id") or 1
    sid = int(b.get("session_id") or 0)
    s = iv.get(uid, sid)
    if not s:
        return jsonify({"error": "unknown session"}), 404
    if s["status"] != "active":
        return jsonify({"error": "session already finished"}), 409
    iv.add_turn(sid, uid, "candidate", str(b.get("answer", ""))[:8000], s["current_phase"])
    j = jobs.enqueue(uid, sid, iv.build_payload(uid, sid), "turn")
    if "error" in j:
        return jsonify(j), 429
    return jsonify({"job_id": j["job_id"]})


@app.route("/api/interview/poll/<int:job_id>")
def api_interview_poll(job_id):
    """Browser polls its own job. Model output is folded into session state HERE, server-side, so a
    browser can never submit a hand-crafted 'model response' and score itself."""
    from interview import jobs
    from interview import session as iv
    uid = g.get("user_id") or 1
    owner = jobs.job_owner(job_id)
    if not owner or owner[0] != uid:
        # No owner means the job is gone — its session was deleted mid-turn. Reporting "unknown"
        # stops the client polling rather than letting the apply path dereference a missing owner.
        return jsonify({"status": "unknown"}), 404
    # Already applied by an earlier (possibly still in-flight) poll: replay the stored outcome.
    prev = jobs.applied_result(job_id)
    if prev is not None:
        return jsonify({"status": "done", **prev})
    st = jobs.poll(uid, job_id)
    if st.get("status") != "done" or not st.get("output"):
        return jsonify(st)
    if not jobs.claim_for_apply(job_id):
        # Another request won the claim and is applying right now; report pending and let the
        # client poll again rather than applying the same turn twice.
        prev = jobs.applied_result(job_id)
        return jsonify({"status": "done", **prev} if prev else {"status": "pending"})
    applied = iv.apply_turn(uid, owner[1], st["output"])
    jobs.store_applied(job_id, applied)
    return jsonify({"status": "done", **applied})


@app.route("/api/interview/session/<int:sid>")
def api_interview_session(sid):
    from interview import session as iv
    uid = g.get("user_id") or 1
    s = iv.get(uid, sid)
    if not s:
        return jsonify({"error": "unknown session"}), 404
    return jsonify({"session": s, "turns": iv.turns_for_ui(sid)})


@app.route("/api/interview/session/<int:sid>", methods=["DELETE"])
def api_interview_delete(sid):
    """Erase an interview for good, dossier contribution included — see session.delete."""
    from interview import session as iv
    uid = g.get("user_id") or 1
    if not iv.delete(uid, sid):
        return jsonify({"error": "unknown session"}), 404
    return jsonify({"ok": True})


@app.route("/api/interview/weak")
def api_interview_weak():
    """Topics your past interviews say you are weakest at."""
    from interview import dossier
    return jsonify({"topics": dossier.weak_topics(g.get("user_id") or 1)})


@app.route("/api/interview/resume/<int:sid>", methods=["POST"])
def api_interview_resume(sid):
    """Pick an unfinished interview back up where it stopped.

    The worker lives on a laptop and can vanish mid-turn (WSL down, machine asleep), so a session
    can be left with the candidate's answer recorded and no reply. Resuming re-queues that turn
    instead of stranding the session — the transcript, rubric evidence and hint tier are all still
    in SQLite, so it continues rather than restarts.
    """
    from interview import jobs
    from interview import session as iv
    uid = g.get("user_id") or 1
    s = iv.get(uid, sid)
    if not s:
        return jsonify({"error": "unknown session"}), 404
    if s["status"] != "active":
        return jsonify({"error": "this interview is already finished"}), 409
    turns = iv.turns_for_ui(sid)
    out = {"session_id": sid, "title": "", "phase": s["current_phase"],
           "hint_tier": s["hint_tier"], "turns": turns, "resumed": True}
    r = __import__("interview.rubrics", fromlist=["x"]).load(s["rubric_id"])
    if r:
        out["title"] = r.get("title", "")
        out["phases"] = iv._phase_labels(iv._plan(s), r)
        out["type"] = s["kind"]
        out["step"] = iv.step_index(s, r, s["current_phase"])
    # Only re-queue when they are genuinely waiting on the interviewer.
    if turns and turns[-1]["role"] == "candidate":
        j = jobs.enqueue(uid, sid, iv.build_payload(uid, sid), "turn")
        if "error" in j:
            return jsonify({**out, **j}), 429
        out["job_id"] = j["job_id"]
    return jsonify(out)


@app.route("/api/interview/history")
def api_interview_history():
    from interview import session as iv
    return jsonify({"sessions": iv.history(g.get("user_id") or 1)})


@app.route("/api/interview/report/<int:sid>")
def api_interview_report(sid):
    from interview import session as iv
    rep = iv.report(g.get("user_id") or 1, sid)
    return jsonify(rep or {"error": "unknown session"}), (200 if rep else 404)


@app.route("/api/interview/worker/lease", methods=["POST"])
def api_interview_worker_lease():
    if not _worker_authed():
        return jsonify({"error": "bad worker token"}), 401
    from interview import jobs
    b = request.get_json(force=True) or {}
    # `wait` turns this into a long poll: the worker asks once and we hold the request until a turn
    # appears. One held thread per worker, and a worker only runs when the host has switched the
    # interviewer on, so this cannot hold the machine awake unattended.
    try:
        wait = min(float(b.get("wait") or 0), jobs.WAIT_MAX_S)
    except (TypeError, ValueError):
        wait = 0.0
    return jsonify(jobs.lease_waiting(str(b.get("worker_id", ""))[:80],
                                      str(b.get("version", ""))[:20], wait))


@app.route("/api/interview/worker/result", methods=["POST"])
def api_interview_worker_result():
    if not _worker_authed():
        return jsonify({"error": "bad worker token"}), 401
    from interview import jobs
    b = request.get_json(force=True) or {}
    jobs.complete(int(b.get("job_id") or 0), str(b.get("output", "")), str(b.get("error", "")))
    return jsonify({"ok": True})


def _already_running(port: int) -> bool:
    """True if an OA Judge instance is already answering on this port. Double-clicking the
    launcher twice otherwise crashes on 'address already in use' with a confusing traceback."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            import json as _json
            return _json.load(r).get("ok") is True
    except Exception:
        return False


def _start_cloud_interviewer() -> None:
    """Answer interview turns from the server itself when a Gemini key is configured.

    Started here rather than at import so it runs once per process, in the real serving process
    only — not in a `--help` run, a migration, or a test importing the app.
    """
    try:
        from interview import cloud
        if cloud.start(app):
            print(f"  (cloud interviewer on: {cloud.gemini.MODEL}, "
                  f"{cloud.CONCURRENCY} concurrent turns)")
    except Exception as e:                       # never let this stop the site from serving
        print(f"  (cloud interviewer unavailable: {e})")


def _serve(host: str, port: int) -> None:
    """Prefer waitress (a real WSGI server) when it is installed; otherwise fall back to the
    Flask dev server. Both are fine for single-user local use — waitress just handles
    concurrent requests more gracefully (e.g. a long stress run while you browse)."""
    _start_cloud_interviewer()
    try:
        from waitress import serve as waitress_serve
        # Sized for a shared room: an interview client polls every ~2s, so 16 people plus judge
        # traffic is a steady trickle of short DB reads. Threads are cheap here (each is idle
        # waiting on SQLite or a subprocess), and too few is what turns a busy room into timeouts.
        threads = int(os.environ.get("OAJ_HTTP_THREADS", "24"))
        print(f"  (serving via waitress, {threads} threads)")
        waitress_serve(app, host=host, port=port, threads=threads, _quiet=True)
    except ImportError:
        # Not installed, and we deliberately do not force it into an externally-managed
        # Python. `pip install waitress` upgrades this automatically next launch.
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    host, port = config.HOST, config.PORT
    if _already_running(port):
        print(f"\n  OA Judge is already running →  http://127.0.0.1:{port}")
        print("  (Opening a second copy is unnecessary; using the existing one.)\n")
        sys.exit(0)
    # Hosted: seed the live bank onto the persistent volume once, so Sync's pulls survive a
    # scale-to-zero restart instead of reverting to the baked image. No-op locally.
    try:
        seeded = sharing.ensure_seeded()
        if seeded.get("seeded"):
            print(f"  (seeded problem bank onto the volume: {seeded['to']})")
    except Exception as e:  # noqa: BLE001
        print(f"  (warning: could not seed problem bank: {e})")
    # Warm the DB / apply migrations before accepting requests, so the first click is instant
    # and any migration error surfaces here rather than mid-request.
    db.connect()
    # Build the search index from disk at startup (rebuilds on every launch so a freshly deployed
    # image or a git-pulled bank is always reflected).
    try:
        store.reindex_problems(problems.all_meta())
    except Exception as e:  # noqa: BLE001
        print(f"  (warning: could not build problem index: {e})")
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(f"\n  OA Judge running →  http://{shown}:{port}\n")
    _serve(host, port)
