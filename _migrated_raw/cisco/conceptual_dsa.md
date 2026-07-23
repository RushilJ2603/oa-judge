# CISCO OA — Conceptual "read & reason about the code" sets (DSA)

These are **written-answer** questions (rich-text editor, no code execution). Each set shows one piece of
language-neutral pseudocode and a shared scenario, then asks **four variants** that change only the
"Question" line. They test whether you can *read* code, find the bug precisely, and reason about paths,
boundaries, and complexity — the exact skills the coding questions also lean on. Transcribed by hand.

---

## Set A — "does any root-to-leaf path add up to N?" accepts a non-leaf path

### Shared pseudocode (verbatim)
```
function hasPathSum(node, target):
    if node is null:
        return false
    if node.value == target:
        return true
    return hasPathSum(node.left,  target - node.value)
        or hasPathSum(node.right, target - node.value)
```
Intent: return true **iff** there is a **root-to-leaf** path whose node values sum exactly to `target`.
A binary-tree node has `node.value`, `node.left`, `node.right`; a missing child is `null`. A leaf is a
node whose left and right are both null. `or` is short-circuiting (if the left operand is true, the right
is not evaluated).

Sample tree used for the traces:
```
        (5)
       /   \
     (3)    (8)
     /
   (2)
```
Root 5 has children 3 and 8; node 3 has a single left child 2; nodes 2 and 8 are leaves. The two
root-to-leaf paths are `5→3→2` (sum 10) and `5→8` (sum 13).

### The four Question variants (verbatim intent)
- **Q1 (fix - 4):** Rewrite the routine so it only succeeds at a leaf, and re-trace case (a) to confirm it
  now returns false. Then explain why using `if node is null: return target == 0` at the completion test
  (instead of checking both children are null) would be incorrect for a node with a single child, using
  node 3 as your example.
- **Q2 (fix - 3):** Reading the code, at which nodes can the check `node.value == target` cause a true
  return — only at leaves, or at any node? And what does the routine return when `node` is null?
- **Q3 (fix - 2):** Explain the bug. Then characterize the error precisely: can this routine return a
  wrong `true`, a wrong `false`, or both? State the exact condition (in terms of paths in the tree) under
  which the routine's answer differs from the intended one.
- **Q4 (fix - 1):** Trace and give the return value for (a) `hasPathSum(root, 8)` and (b)
  `hasPathSum(root, 13)`. For each, state the correct answer and whether the code matches. For (a), name
  the node at which the code returns true.

### Model answers
**The bug.** The success test `node.value == target` does **not** require `node` to be a **leaf**. So the
routine returns `true` at an *internal* node whenever the running remainder equals that node's value — i.e.
it accepts a path that ends **before** a leaf. (The `target` passed down is the remaining sum needed.)

**Wrong-true only.** It can only produce a **wrong `true`**, never a wrong `false`: a genuine root-to-leaf
path that sums to `target` is still discovered (at its leaf, `node.value == remaining` holds). The error
fires exactly when **some non-leaf node's value equals the remaining target along a partial path** — that
partial (non-leaf-terminating) path is wrongly accepted.

**Trace (Q4).**
- `hasPathSum(root, 8)` — correct answer is **false** (paths sum to 10 and 13). The code: `5 ≠ 8`, recurse
  left `hasPathSum(3, 3)`; `3 == 3` → **returns true at node 3** (a non-leaf!). Buggy → `true`. **Mismatch.**
- `hasPathSum(root, 13)` — correct answer is **true** (`5→8`). The code: `5 ≠ 13`; left `hasPathSum(3, 8)`
  → `3 ≠ 8` → `hasPathSum(2, 5)` → `2 ≠ 5` → both null children false → false; right `hasPathSum(8, 8)` →
  `8 == 8`, and node 8 **is** a leaf → true. Buggy → `true`. **Coincidentally correct.**

**Nodes that can trigger true (Q2):** `node.value == target` can return true at **any** node, leaf or
internal — that is the whole defect. When `node` is null the routine returns **false**.

**The fix (Q1)** — test the leaf condition before comparing:
```
function hasPathSum(node, target):
    if node is null:
        return false
    if node.left is null and node.right is null:   # leaf
        return node.value == target
    return hasPathSum(node.left,  target - node.value)
        or hasPathSum(node.right, target - node.value)
```
Re-trace `hasPathSum(root, 8)`: `5` is not a leaf → recurse `hasPathSum(3, 3)`; `3` is not a leaf (it has
left child 2) → recurse `hasPathSum(2, 0)`; `2` is a leaf → `2 == 0`? false; right child null → false →
node 3 returns false; node 8 leaf → `8 == 8`? no (target 3) → false. Overall **false**. Correct.

**Why `if node is null: return target == 0` is wrong (Q1).** Consider node 3, which has a single (left)
child. Its **null right child** is visited with `target = 3 - 3 = 0`, so `return target == 0` returns
**true** — falsely reporting a path that "ends" at node 3's *missing* child. That treats a non-leaf
(node 3) as if it were an endpoint. The correct completion test, "both children null," makes node 3 fail
the leaf check, so no phantom path is counted.

### Verified C++ of the corrected routine
```cpp
#include <bits/stdc++.h>
using namespace std;
struct Node { int value; Node *left = nullptr, *right = nullptr; Node(int v):value(v){} };

bool hasPathSum(Node* node, long long target) {
    if (!node) return false;
    if (!node->left && !node->right) return node->value == target;  // leaf only
    return hasPathSum(node->left,  target - node->value)
        || hasPathSum(node->right, target - node->value);
}
// tree 5(3(2),8): hasPathSum(root,8)=false, hasPathSum(root,10)=true, hasPathSum(root,13)=true
```

---

## Set B — a merge of two sorted lists silently loses elements

### Shared pseudocode (verbatim)
```
function merge(A, B):
    i = 0
    j = 0
    out = empty list
    while i < length(A) and j < length(B):
        if A[i] <= B[j]:
            append A[i] to out
            i = i + 1
        else:
            append B[j] to out
            j = j + 1
    while i < length(A):
        append A[i] to out
        i = i + 1
    return out
```
Intent: return a single sorted list containing **all** elements of A and B. Both inputs are sorted
non-decreasing; indices are 0-based. It "sometimes returns fewer elements than it should."

### The four Question variants (verbatim intent)
- **Q1 (find when - 1):** Reading the code, after the main compare-heads loop finishes, describe the copy
  step(s) that run before `return` — which input's leftover elements get appended, and which input's do not?
- **Q2 (find when - 2):** Trace and give the exact returned list for (a) `merge([1,2],[3,4,5])` and (b)
  `merge([1,4,6],[2,3])`. For each, state the correct merged result.
- **Q3 (find when - 3):** Identify the bug, and characterize exactly when it causes wrong output vs. when
  the routine happens to be correct. Note whether the elements it *does* return are still in sorted order.
- **Q4 (find when - 4):** Fix the routine with the smallest addition. Explain why the first `while` loop
  always ends with at least one input not fully consumed, and why after your fix at most one of the two
  "drain" loops actually runs.

### Model answers
**The bug (Q1/Q3).** After the main loop there is only **one** drain loop — `while i < length(A)` — so the
leftover tail of **A** is copied but the leftover tail of **B** is **silently dropped**. The routine loses
elements exactly when **B is the input still holding elements** when the main loop exits (i.e., A is
exhausted first). When B is exhausted first (or both at once), the missing loop would have copied nothing,
so the output is correct. The elements it does return are **always in sorted order** — it only truncates a
suffix, never misorders.

**Traces (Q2).**
- `merge([1,2],[3,4,5])`: main loop appends `1,2` (A exhausted, `i=2`), drain-A copies nothing → returns
  **`[1,2]`**. Correct is `[1,2,3,4,5]` → it loses `3,4,5`. **Wrong.**
- `merge([1,4,6],[2,3])`: `1≤2`→1; `4≤2`? no →2; `4≤3`? no →3 (B exhausted, `j=2`); loop ends; drain-A
  copies `4,6` → returns **`[1,2,3,4,6]`**. Correct is `[1,2,3,4,6]`. **Right** (B had no leftover).

**The fix (Q4)** — add the symmetric drain for B:
```
    while j < length(B):
        append B[j] to out
        j = j + 1
    return out
```
The main loop's condition is `i < len(A) AND j < len(B)`, so it stops the instant **either** index reaches
its end — hence at least one input still has elements (unless both ended together). After the fix, the two
drain loops are mutually exclusive: whichever input was exhausted first has an empty drain, so **exactly
one** drain loop does real work.

### Verified C++ of the corrected routine
```cpp
#include <bits/stdc++.h>
using namespace std;
vector<int> merge_sorted(const vector<int>& A, const vector<int>& B) {
    vector<int> out; size_t i = 0, j = 0;
    while (i < A.size() && j < B.size()) {
        if (A[i] <= B[j]) out.push_back(A[i++]);
        else              out.push_back(B[j++]);
    }
    while (i < A.size()) out.push_back(A[i++]);
    while (j < B.size()) out.push_back(B[j++]);   // the missing drain
    return out;
}
// merge_sorted({1,2},{3,4,5}) == {1,2,3,4,5}
```

---

## Set C — Designing a Time-Versioned Key-Value Store

### Shared scenario (verbatim intent)
Design an in-memory **time-versioned key-value store** with two operations:
- `set(key, value, timestamp)` — record that `key` had `value` at time `timestamp`.
- `get(key, timestamp)` — return the value whose stored timestamp is the **greatest timestamp ≤ the query
  timestamp**. If no such version exists, return a not-found sentinel.

The store holds many keys, each independently versioned; timestamps are integers. (This is exactly
LeetCode 981, *Time Based Key-Value Store*, posed as a design/reasoning question — no full code required.)

### The four Question variants (verbatim intent)
- **Q1 (store - 1):** Define the exact behavior of `get(key, timestamp)` for two edge cases: (a) the key was
  never written at all, and (b) the key exists but its earliest stored timestamp is greater than the query.
  Explain, in terms of your search, why the correct result in both cases is the not-found sentinel and not
  the earliest value. ("return null" alone is not full credit without the search-based reason.)
- **Q2 (store - 2):** Propose the data structure. Describe the top-level container and the per-key structure,
  and sketch how `set` and `get` use them.
- **Q3 (store - 3):** How does memory scale with the workload? Give a strategy to bound memory when only
  recent history matters, and state the trade-off your strategy introduces.
- **Q4 (store - 4):** Assume that for each key, `set` is always called with strictly increasing timestamps.
  Give the time complexity of `set` and `get` under this assumption, and justify each. Then state precisely
  what changes if that assumption is dropped and `set` can arrive out of order.

### Model answers
**Data structure (Q2).** Top level: a hash map `unordered_map<Key, vector<pair<int,Value>>>` — key →
a list of `(timestamp, value)` kept **sorted by timestamp**. `set` appends the new `(ts, value)` to that
key's list. `get(key, ts)` does a **predecessor search**: binary-search for the last entry with
`timestamp ≤ ts` (`upper_bound` on `ts`, then step back one); return its value, or the sentinel if the
search lands before the first entry.

**Edge cases (Q1).** (a) Key never written → the per-key list is absent/empty → **not-found**. (b) Query is
earlier than the key's first stored timestamp → the predecessor search finds **no** element `≤ ts` →
**not-found**. Returning the earliest value would be wrong because `get`'s contract is "greatest timestamp
`≤ query`"; the earliest version has `timestamp > query`, so it is *not* a valid answer. The reason is the
**search finds nothing ≤ query**, not merely "there was nothing."

**Memory (Q3).** Memory is `O(total number of set calls)` — every version is retained forever. To bound it
when only recent history matters: cap each key's list to the **last H versions** (a ring buffer) or evict
versions older than a **retention horizon** `T`. Trade-off: `get` for timestamps older than what you kept
now returns not-found (or a coarser answer) — you trade historical accuracy for bounded memory.

**Complexity (Q4).** With strictly increasing `set` timestamps: `set` is **O(1)** amortized — the new entry
belongs at the tail, so a plain append keeps the list sorted. `get` is **O(log m)** where `m` is that key's
version count — binary search over the sorted list. If `set` can arrive **out of order**, the new entry may
belong in the middle, so keeping a sorted array makes `set` **O(m)** (shift to insert); to restore
`O(log m)` inserts you switch the per-key container to a balanced BST / `std::map<int,Value>` (higher
constants). `get` stays **O(log m)** either way.
