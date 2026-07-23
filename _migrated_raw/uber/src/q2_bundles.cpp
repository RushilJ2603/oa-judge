// Uber Q2 — for how many "min-pick counts" x can the target be formed?
// {1..2n} split into n pairs; from each pick min or max; picks must equal target T (|T|=n).
// Reduce: match each target t to a distinct non-target c; pick is a MIN iff c>t.
// The achievable x = #{c>t} is exactly the contiguous range [xmin, xmax], endpoints by greedy.
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    if (!(cin >> n)) return 0;                  // n = |target|,  universe is 1..2n
    vector<int> T(n);
    vector<char> inT(2 * n + 1, 0);
    for (int &t : T) { cin >> t; inT[t] = 1; }
    sort(T.begin(), T.end());

    vector<int> C;                              // complement, ascending
    for (int v = 1; v <= 2 * n; ++v) if (!inT[v]) C.push_back(v);

    // xmax = max pairs with c > t : for each c ascending, satisfy the smallest unmet t < c.
    int xmax = 0;
    for (int i = 0, ci = 0; ci < (int)C.size(); ++ci)
        if (i < n && T[i] < C[ci]) { ++xmax; ++i; }

    // max pairs with c < t : for each t ascending, consume the smallest unused c < t.
    int below = 0;
    for (int j = 0, ti = 0; ti < n; ++ti)
        if (j < (int)C.size() && C[j] < T[ti]) { ++below; ++j; }
    int xmin = n - below;

    cout << xmin << ' ' << xmax << '\n';        // every x in [xmin, xmax] is achievable
    return 0;
}
