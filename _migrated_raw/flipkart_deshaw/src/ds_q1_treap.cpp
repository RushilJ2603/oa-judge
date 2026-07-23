// DE Shaw Q1 — music player, O(log n) per operation.
// Implicit treap (keyed by subtree size, not by value) + parent pointers.
//
// Two directions of travel are needed and they are NOT symmetric:
//   "track at position k"  -> walk DOWN from the root, steering by subtree size.
//   "position of track u"  -> walk UP from u's node to the root, summing left subtrees.
// The upward walk is what forces parent pointers, and keeping them correct through
// every split and merge is the whole difficulty of this solution.
#include <bits/stdc++.h>
using namespace std;

const int MAXN = 200005;

int lc[MAXN], rc[MAXN], par[MAXN], sz[MAXN];
unsigned pri[MAXN];
int root = 0;                       // node id == track id, so no separate value array

inline int size_(int t) { return t ? sz[t] : 0; }

// Recompute t's size and re-assert ownership of its children.
// Every structural change must be followed by pull() or the parent links rot.
inline void pull(int t) {
    sz[t] = 1 + size_(lc[t]) + size_(rc[t]);
    if (lc[t]) par[lc[t]] = t;
    if (rc[t]) par[rc[t]] = t;
}

// a receives the first k nodes in sequence order, b receives the rest.
void split(int t, int k, int &a, int &b) {
    if (!t) { a = b = 0; return; }
    if (size_(lc[t]) >= k) {
        split(lc[t], k, a, lc[t]);
        pull(t);
        b = t;
    } else {
        split(rc[t], k - size_(lc[t]) - 1, rc[t], b);
        pull(t);
        a = t;
    }
    if (a) par[a] = 0;              // both halves are now roots; ancestors' pull()
    if (b) par[b] = 0;              // will overwrite this for the non-root one
}

int merge(int a, int b) {
    if (!a || !b) {
        int t = a ? a : b;
        if (t) par[t] = 0;
        return t;
    }
    if (pri[a] > pri[b]) {
        rc[a] = merge(rc[a], b);
        pull(a);
        par[a] = 0;
        return a;
    }
    lc[b] = merge(a, lc[b]);
    pull(b);
    par[b] = 0;
    return b;
}

// Walk UP: 1-indexed position of track x.
int position(int x) {
    int r = size_(lc[x]) + 1;
    while (par[x]) {
        int p = par[x];
        if (rc[p] == x) r += size_(lc[p]) + 1;   // whole left subtree + p itself precede x
        x = p;
    }
    return r;
}

// Walk DOWN: track at 1-indexed position k.
int kth(int t, int k) {
    while (t) {
        int leftSize = size_(lc[t]);
        if (k == leftSize + 1) return t;
        if (k <= leftSize) t = lc[t];
        else { k -= leftSize + 1; t = rc[t]; }
    }
    return -1;
}

// Remove u, re-insert immediately before v.
void moveBefore(int u, int v) {
    if (u == v) return;

    int pu = position(u);
    int A, B, U, C;
    split(root, pu - 1, A, B);      // A = [1..pu-1],  B = [pu..n]
    split(B, 1, U, C);              // U = {u},        C = [pu+1..n]
    root = merge(A, C);             // sequence with u removed

    int pv = position(v);           // v's position AFTER the removal — must be recomputed
    split(root, pv - 1, A, B);      // A = [1..pv-1],  B = [pv..] starting at v
    root = merge(merge(A, U), B);   // u lands immediately before v
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, q;
    if (!(cin >> n >> q)) return 0;

    mt19937 rng(12345);
    for (int i = 1; i <= n; ++i) {
        int a;
        cin >> a;
        lc[a] = rc[a] = par[a] = 0;
        sz[a] = 1;
        pri[a] = rng();
        root = merge(root, a);      // append in input order
    }

    while (q--) {
        int type;
        cin >> type;
        if (type == 1) {
            int u, v;
            cin >> u >> v;
            moveBefore(u, v);
        } else {
            int k;
            cin >> k;
            cout << kth(root, k) << '\n';
        }
    }
    return 0;
}
