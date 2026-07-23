// Millennium Q1, placement form — the "count the characters and place them" idea, completed.
// No permutation array, no simulation. Two runs, and the spill from one into the other.
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    if (!(cin >> s)) return 0;
    int n = s.size();
    int zeros = count(s.begin(), s.end(), '0');

    int f = (n + 1) / 2;              // head run: parity of n-1, read DESCENDING from n-1
    int t = n / 2;                    // tail run: parity of n,   read ASCENDING from n%2

    string out(n, '1');
    for (int j = 0; j < zeros; ++j) {
        int pos;
        if (j < t) pos = n - 2 - 2 * j;             // fill the tail run from its far end backwards
        else       pos = (n + 1 - 2 * f) + 2 * (j - t);  // spill: head run, from its LOW end upwards
        out[pos] = '0';
    }
    cout << out << '\n';
    return 0;
}
