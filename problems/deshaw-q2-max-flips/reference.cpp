// DE Shaw Q2 — maximum flips keeping every prefix sum strictly positive.
// Greedy with regret: flip optimistically, un-flip the largest when the prefix breaks.
#include <bits/stdc++.h>
using namespace std;

int maxFlips(const vector<long long> &a) {
    priority_queue<long long> flipped;   // magnitudes currently flipped
    long long running = 0;               // prefix sum with current decisions
    int count = 0;

    for (long long x : a) {
        running -= x;                    // flip it optimistically
        flipped.push(x);
        ++count;
        while (running <= 0) {           // infeasible: buy back the most sum per un-flip
            long long big = flipped.top();
            flipped.pop();
            running += 2 * big;          // -big becomes +big
            --count;
        }
    }
    return count;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    if (!(cin >> n)) return 0;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    cout << maxFlips(a) << '\n';
    return 0;
}
