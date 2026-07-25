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

> **Mandatory (enforced):** every runnable problem ships **at least 5 curated edge cases** and they
> must include a **max-scale** case. `audit.py` hard-fails a runnable problem with no sample or fewer
> than 2 edges, and **warns** below 5. Weak test suites are how a wrong or slow solution sneaks a
> green — this bar is not optional for new problems.

Every reference is also cross-checked against an **independent brute force** on small random inputs
before shipping (see §Verification discipline). A passing `verify_all` alone is not enough — it only
proves the reference agrees with its *own* generated outputs.

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

### 4.1 Test STRENGTH is measured, not assumed — mutation testing (binding)

The `≥5 edges` rule is a proxy; the **binding measure of suite strength is the mutation score** from
`mutation_test.py`. A suite that a bugged submission can pass (Goldman *unstable-tasks* passed 17/18)
is a defect regardless of edge count. The gate deliberately breaks the verified reference one edit at
a time (flip `<`/`<=`, `+`/`-`, `&&`/`||`, `min`/`max`; delete a statement — an ineffective/removed
update is exactly the unstable-tasks bug) and **requires the tests to catch 100% of the killable
mutants**. When a mutant survives, the gate fires random generator inputs at it: if one distinguishes
it, that input is the **exact missing edge** (auto-added with `--fix`); if none do, it is a provable
**equivalent** and excluded from the score. So `100%` means "no wrong solution of these shapes can
pass," measured — not hoped.

```bash
python3 mutation_test.py <id>          # one problem: score + any GAP (with distinguishing input)
python3 mutation_test.py <id> --fix    # write each gap's distinguishing input as a curated edge
python3 mutation_test.py --all         # whole-bank sweep (run WITHOUT --quick for the true result;
                                       # --quick drops max-scale tests and over-reports gaps)
```

Optional **planted wrongs**: drop a known-wrong solution in `problems/<id>/wrong/*.{cpp,py}` and the
gate requires the suite to kill it — locks a specific trap (e.g. the sort-a-copy bug) against regress.

A **committed independent `brute.{cpp,py}`** (a different, obviously-correct algorithm) is required
for new problems: `gate_candidate.py` runs reference-vs-brute on all provided tests + hundreds of
random inputs. The reference is only trusted once brute agrees AND it reproduces the source's own
`provided_tests`.

### 4.2 Difficulty rubric (a single loop is not "Medium")

Label by the hardest idea the intended solution *requires*, calibrated to LeetCode:
- **Easy** — one pass / running min-max / prefix sum / direct library call / one monotonic stack with
  no twist. (LC-Easy like "final prices", or `max(0, p[i]-min_so_far)` are Easy — never Medium.)
- **Medium** — needs a non-obvious idea: DP with a real state, binary-search-on-answer, greedy with
  an exchange argument, graph traversal with bookkeeping, combinatorics/number theory.
- **Hard** — multiple layered ideas, heavy DP (bitmask/interval/digit), advanced graph, or a proof-
  heavy greedy. Mislabeling easy-as-medium is a gate reject, not a warning.

### Verification discipline (non-negotiable)

Every reference and every hand-derived example is **cross-checked against an independent brute force
before shipping** — run the code, don't reason about what it "should" print. When a problem's rules
are ambiguous and not disambiguated by its examples (e.g. Array Burst's removal order, which turned
out **not** to be confluent), we **do not ship a guessed judge** — the problem is deferred until the
rule is pinned down. A wrong judge is worse than a missing one.

## 5. The gates (the safety net)

Run these from the repo root before publishing anything:

```bash
python3 verify_all.py                       # correctness: every reference ACs its own tests
python3 audit.py                            # structure: stub rule, required metadata, references
python3 mutation_test.py <id>               # test STRENGTH: 100% mutation score (§4.1)
python3 gate_candidate.py <dir> --scraped <slug.json>   # ONE-COMMAND full gate for a new package
```

`audit.py` prints **WARNINGS (allowed)** then **HARD FAILURES**; it exits non-zero only on a hard
failure. The stub regression is a hard failure — this is the specific guard that keeps it from
recurring.

`gate_candidate.py` is the **single gate every candidate (incl. Grok-authored) must pass** before it
merges: it composes structure + compile + **anchor** (reference reproduces every scraped
`provided_test`) + **brute** agreement + samples + **100% mutation**. `GATE: PASS` is the only thing
that authorizes a merge. Author identity is irrelevant — the gate is run by Claude in a clean state
and never trusts a self-reported pass.

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

**Presence ("who's online") is best-effort by design, for the same $0 reason.** Each user's
`last_seen` is bumped from their *real* API traffic (throttled to once per 45s) — there is **no
background heartbeat**, because a recurring heartbeat would keep the scale-to-zero machine awake and
cost money. "Online" = made a request in the last 5 minutes; the roster refreshes on genuine moments
(load, tab focus, submit, sync), never on a timer. The honest tradeoff: someone with an idle tab open
and no activity ages out of the roster — detecting them would require the very heartbeat we avoid.

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
