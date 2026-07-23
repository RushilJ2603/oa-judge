// Millennium Q1 — append-and-reverse, maximise the final string.
//
// The operation is a FIXED permutation of positions, independent of the characters.
// Simulating it naively costs O(n^2) in the reversals; a deque with a direction flag
// does it in O(n). Maximising is then trivial: the reachable set of b is every
// rearrangement of s, so max b = all 1s then all 0s. The work is inverting the
// permutation to report which s produces it.
#include <bits/stdc++.h>
using namespace std;

// O(n) simulation: instead of reversing, alternate which end we append to.
string transform_(const string &s) {
    deque<char> b;
    bool flipped = false;               // true => the logical string is reversed vs. the deque
    for (char c : s) {
        if (flipped) b.push_front(c);   // "append to the end" of a reversed view
        else         b.push_back(c);
        flipped = !flipped;             // the reversal itself is deferred into the flag
    }
    string out(b.begin(), b.end());
    if (flipped) reverse(out.begin(), out.end());
    return out;
}

// Position j of the final b is drawn from s[perm[j]].
vector<int> permOf(int n) {
    vector<int> p;
    p.reserve(n);
    for (int i = n - 1; i >= 0; i -= 2) p.push_back(i);   // parity of n-1, descending
    for (int i = n % 2; i < n; i += 2)  p.push_back(i);   // the other parity, ascending
    return p;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    if (!(cin >> s)) return 0;
    int n = s.size();

    int ones = count(s.begin(), s.end(), '1');
    string best = string(ones, '1') + string(n - ones, '0');   // the maximum b

    // Invert the permutation to recover the s that yields it.
    vector<int> p = permOf(n);
    string mutated(n, '?');
    for (int j = 0; j < n; ++j) mutated[p[j]] = best[j];

    cout << mutated << '\n' << best << '\n';
    return 0;
}
