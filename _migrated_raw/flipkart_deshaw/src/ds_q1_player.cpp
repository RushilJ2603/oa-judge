// DE Shaw Q1 — music player: move-before + positional lookup.
// Sqrt decomposition over a bucketed sequence. All ops O(sqrt n) amortised.
#include <bits/stdc++.h>
using namespace std;

struct Playlist {
    int n, B;                       // B = target bucket size
    vector<vector<int>> buck;       // the sequence, split into buckets
    vector<int> owner;              // owner[track] = index of the bucket holding it

    explicit Playlist(const vector<int> &a) {
        n = (int)a.size();
        B = max(1, (int)sqrt((double)n) + 1);
        owner.assign(n + 1, 0);
        rebuild(a);
    }

    void rebuild(const vector<int> &flat) {
        buck.clear();
        for (int i = 0; i < (int)flat.size(); i += B)
            buck.emplace_back(flat.begin() + i,
                              flat.begin() + min((int)flat.size(), i + B));
        if (buck.empty()) buck.emplace_back();
        reindex();
    }

    void reindex() {
        for (int b = 0; b < (int)buck.size(); ++b)
            for (int x : buck[b]) owner[x] = b;
    }

    vector<int> flatten() const {
        vector<int> out;
        out.reserve(n);
        for (const auto &v : buck) out.insert(out.end(), v.begin(), v.end());
        return out;
    }

    // Erase track u from wherever it currently sits.
    void erase(int u) {
        auto &v = buck[owner[u]];
        v.erase(find(v.begin(), v.end(), u));
    }

    // Insert track u immediately before track v.
    void insertBefore(int u, int v) {
        int b = owner[v];
        auto &vec = buck[b];
        vec.insert(find(vec.begin(), vec.end(), v), u);
        owner[u] = b;
        if ((int)vec.size() > 2 * B) rebuild(flatten());   // amortised O(n/B) per op
    }

    void move(int u, int v) {
        if (u == v) return;
        erase(u);
        insertBefore(u, v);
    }

    // Track at 1-indexed position k.
    int at(int k) const {
        for (const auto &v : buck) {
            if (k <= (int)v.size()) return v[k - 1];
            k -= (int)v.size();
        }
        return -1;                  // unreachable for valid k
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, q;
    if (!(cin >> n >> q)) return 0;
    vector<int> a(n);
    for (int &x : a) cin >> x;

    Playlist pl(a);
    while (q--) {
        int type;
        cin >> type;
        if (type == 1) {
            int u, v;
            cin >> u >> v;
            pl.move(u, v);
        } else {
            int k;
            cin >> k;
            cout << pl.at(k) << '\n';
        }
    }
    return 0;
}
