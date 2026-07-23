// Uber Q3 — distinct strings from complementing at most one contiguous substring.
// A flip of block [i,j] is XOR with a unique mask; distinct blocks give distinct results,
// none equal to the original. So the count is 1 + (number of substrings) = 1 + n(n+1)/2,
// INDEPENDENT of the string's contents.
#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    if (!(cin >> s)) return 0;
    long long n = s.size();
    cout << 1 + n * (n + 1) / 2 << '\n';
    return 0;
}
