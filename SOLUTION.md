# OA Judge — Solution & Authoring Reference

The single source of truth for **what we've built** and **how we add questions**. If you read one
file before touching this project, read this one. It exists because a batch of stubs once regressed
(solving inside `main()` instead of exposing a solution function); the rules and the automated gates
below make that class of mistake fail loudly instead of shipping.

Two gates back everything here:
- **`python3 verify_all.py`** — every reference solution ACs its own tests (*correctness*).
- **`python3 audit.py`** — every package is *shaped right*: the stub rule, required metadata,
  references present (*structure* — the checks a wrong answer can't catch).

**A package is publishable only when both are green.** Never skip either.

---

## 1. What it is

A self-hosted LeetCode/HackerRank-style judge for practising OA (online-assessment) problems. You
write C++/Python in a Monaco editor, Submit against hidden tests, and everything — attempts,
half-written drafts, stats — is stored per-user in SQLite. Friends sign in with GitHub; anyone can
add a problem and, after a Sync, everyone sees it.

## 2. Architecture (two repos)

| Repo | Role |
|------|------|
| **oa-judge** | The app: Flask backend + vanilla-JS/Monaco frontend, the SQLite DB, the sandbox, the gates, deploy config. |
| **oa-problems** | The **problem bank** — one folder per problem. Cloned into `oa-judge/problems/` (gitignored there). The app only *reads* it, so the two repos update independently. |

Key components (all under `app/`):
- **`config.py`** — every setting resolves env (`OAJ_*`) → `config.local.json` → default. `PROBLEMS_DIR`
  is the bank location; `PROBLEMS_SEED` is the hosted volume-seed (see §7).
- **`db.py`** — per-thread SQLite connections, WAL, numbered migrations in `app/migrations/*.sql`.
- **`store.py`** — all persistence, **scoped per user** (`_uid()`), plus the search layer:
  `reindex_problems`, `search_problems`, `problem_facets`. `SOURCE_LABELS` / `SOURCE_ORDER` define the
  three top-level groups.
- **`runner/problems.py`** — loads packages from disk (`load`, `meta_only`, `all_meta`).
- **`runner/sandbox.py`** — runs untrusted code: `local` (subprocess + rlimits) or `docker`
  (network-less, read-only, `--cap-drop ALL`, `nobody`) per `EXEC_BACKEND`.
- **`sharing.py`** — git over the bank (`sync`, `status`), authoring (`scaffold`/`verify`/`publish`),
  and `ensure_seeded` (§7).
- **`server.py`** — routes + auth gating. Search served from `problem_index` (rebuilt on
  startup + after Sync) so the sidebar scales to thousands without loading everything.
- **`auth.py`** — GitHub OAuth. Unconfigured → single-user no-login (local). Configured → login
  required, per-user data, optional allow-list.

## 3. How a question is packaged — **the format**

Every problem is a folder `problems/<id>/`, `<id>` = kebab-case `company-qN-slug`. Canonical example
to clone: **`problems/flipkart-q1-golden-price/`**. Full field-level spec lives in
`problems/FORMAT.md`; this section is the load-bearing summary.

```
problems/<id>/
  problem.json      required   metadata (schema below)
  statement.md      required   solver-facing statement (prose, Input, Output, Constraints, Example)
  editorial.md      optional   solution writeup (shown after solving)
  stub.cpp/.py      required per language   starter code the solver edits
  reference.cpp/.py Claude owns   verified-correct solution; its output defines expected answers
  generator.py      wanted     prints ONE random valid input (powers stress + hidden tests)
  tests/
    sample/  NN.in NN.out   visible; mirror the statement's examples verbatim
    edge/    NN.in          curated LC/OA-grade edge inputs (INPUTS only; .out computed)
    hidden/  built by make_hidden.py = solved edge/ + random generator
```

**`problem.json`** required keys: `id`, `title`, `difficulty` (Easy|Medium|Hard), `source`
(`tuf` | `oa-helper` | `gyan`), `runnable`. Plus `company`, `tags`, `languages`, `topic`, `origin`,
`links`, `limits`, `compare`. `source` drives the top-level sidebar group; `company` drives the
nested dropdown under it.

### 3.1 THE STUB RULE (do not violate)

> The stub separates **I/O plumbing** from the **solution**. `main()` only parses stdin, calls a
> **named solution function**, and prints the result. The solver's `// WRITE YOUR CODE HERE` marker
> lives **inside that function**, never loose inside `main()`.

Right (C++):
```cpp
// Return the length of the longest palindromic subsequence of s.
int longestPalindromicSubsequence(const string& s) {
    // WRITE YOUR CODE HERE
    return 0;
}
int main() {
    string s;
    if (cin >> s) cout << longestPalindromicSubsequence(s) << "\n";
    return 0;
}
```

Wrong (the regression — never do this):
```cpp
int main() {
    string s; cin >> s;
    // Return the length of the longest palindromic subsequence of s.
    // your code here   <-- solving inside main(), no function
    return 0;
}
```

Why: it mirrors the real OA/LC harness (fill a function body, not I/O), isolates the algorithm,
and makes the stub reusable. `audit.py` **fails hard** on any runnable C++/Python stub that has no
solution function separate from `main()`. The stub must also **compile/parse as-is** (it may print a
wrong answer, but the first Run must never error on the solver's behalf).

### 3.2 The direct-LeetCode rule (scale without redundancy)

If a problem is a **one-to-one LeetCode question** (same algorithm, just re-worded), don't re-judge
it: set `runnable: false`, keep the OA **story wrapper** in `statement.md` (OAs wrap a plain LC task
in a narrative — preserve that), and put the LeetCode URL in `links[]`. No reference, no tests.
Only build a full judged package when the problem is an OA original or meaningfully diverges from LC.
(Statement-only problems with genuinely no LC twin — e.g. a SQL question — may omit the link; that's
the one allowed audit *warning*.)

## 4. Test-case standard

`make_hidden.py` builds `tests/hidden/` with **outputs computed by running the verified reference**,
never hand-written. Two layers:

1. **Curated edge cases** (`tests/edge/*.in`, hand-written INPUTS) — required for every runnable
   problem. Cover: bounds (min n=1/empty, max sizes, constraint-limit values); degenerate/structural
   (all-equal, all-distinct, sorted, reverse-sorted, single element, no-valid-answer, all-valid);
   adversarial (overflow → forces 64-bit, strict-vs-nonstrict boundary, unordered input, decoy
   records to ignore); and **scale** (≥1 max-size input to separate correct from TLE).
2. **Random cases** from `generator.py` across a spread of sizes including the max.

`tests/edge/` is durable: rerunning `make_hidden.py` recomputes `.out` from the reference but never
deletes curated inputs.

### Verification discipline (non-negotiable)

Every reference and every hand-derived example is **cross-checked against an independent brute force
before shipping** — run the code, don't reason about what it "should" print. When a problem's rules
are ambiguous and not disambiguated by its examples (e.g. Array Burst's removal order, which turned
out **not** to be confluent), we **do not ship a guessed judge** — the problem is deferred until the
rule is pinned down. A wrong judge is worse than a missing one.

## 5. The gates (the safety net)

Run both from the repo root before publishing anything:

```bash
python3 verify_all.py   # correctness: every reference ACs its own tests
python3 audit.py        # structure: stub rule, required metadata, references present
```

`audit.py` prints **WARNINGS (allowed)** then **HARD FAILURES**; it exits non-zero only on a hard
failure. The stub regression is a hard failure — this is the specific guard that keeps it from
recurring.

## 6. Adding a new question — end to end

1. **Decide judged vs. link-only** (§3.2). Direct-LC → statement-only + link, stop.
2. **Transcribe** the statement into `statement.md` (drop authoring meta; commit to one reading of any
   ambiguity, as *the* rule). Fill `problem.json` (`source`, `company`, `difficulty`, `tags`, …).
3. **Write the stub** obeying the stub rule (§3.1). Confirm it compiles/parses as-is.
4. **Write a verified reference** (Claude owns `reference.*`). Cross-check against a brute force.
5. **Author edge inputs** (§4) and a `generator.py`; run `make_hidden.py` to build hidden tests.
6. **Gate:** `verify_all.py` green *and* `audit.py` clean.
7. **Publish:** commit + push to **oa-problems**. Everyone gets it after a **Sync**.

When adding from **screenshots/transcripts**, you must author OA/LC-grade test cases yourself where
none are given — the reference plus curated edges plus generator are what make it a real judge, not
just a statement.

## 7. Deployment & the Sync model

Hosted on Fly.io (app `oa123`, single `shared-cpu-1x` machine, **scale-to-zero** → ~$0/month). The
DB lives on a persistent volume at `/data`. Login via GitHub OAuth; each friend sees only their data.

**The bank is on the volume.** `OAJ_PROBLEMS_DIR=/data/problems` (persistent), seeded once on first
boot from the image-baked `OAJ_PROBLEMS_SEED=/problems` via `sharing.ensure_seeded()`. This is
deliberate: scale-to-zero discards the container's ephemeral filesystem on every sleep, so a bank
baked only into the image would revert on each cold start and a Sync's `git pull` wouldn't stick —
the "I have to click Sync several times" bug. With the bank on the volume, **one Sync sticks
permanently** until the next push. Locally `PROBLEMS_SEED` is unset, so seeding is a no-op and the
bank is just `oa-judge/problems/`.

Flow when a friend adds a problem: they push to **oa-problems** → anyone clicks **⟳ Sync** in the app
→ the server `git pull`s into `/data/problems` and rebuilds the search index → the problem appears in
its `source ▸ company` group. Costs stay $0 because the machine only wakes to serve a request and
sleeps again after; keeping a tab open or editing code never wakes it.

## 8. Current state (self-audit)

- **24 packages**: 22 runnable (21 C++, 1 Python), 2 statement-only.
- Sources: **OA-Helper** (5, all Goldman Sachs), **Iris — Personal** (19, across Flipkart / DE Shaw /
  Uber / Cisco / Millennium / Rippling / “Unknown OA”). **TUF+** empty pending the scraper.
- `verify_all.py`: **green**. `audit.py`: **clean** (1 allowed warning — the SQL statement-only
  problem with no LC twin).
- Deferred (correctly, per §4): **Array Burst** (removal order not confluent), **Optimal
  Reconstruction** (unreadable sample tree edges).

---

*Change this project's authoring behaviour? Update this file and `audit.py` together, so the gate
always encodes the current rules.*
