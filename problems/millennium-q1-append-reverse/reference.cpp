// Millennium Q1 — append-and-reverse, maximise final b. VERIFIED (exhaustive to n=14).
// Judged output: the unique rearrangement s of the input that yields the maximum b.
// (The transform is a bijection on positions, so exactly one arrangement produces the max b,
//  which makes this output unique and token-comparable.)
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    string s;
    if (!(cin >> s)) return 0;
    int n = s.size();
    int ones = count(s.begin(), s.end(), '1');
    string best = string(ones, '1') + string(n - ones, '0');   // maximum achievable b

    vector<int> p;                       // position j of b is drawn from s[p[j]]
    for (int i = n - 1; i >= 0; i -= 2) p.push_back(i);
    for (int i = n % 2; i < n; i += 2)  p.push_back(i);

    string mutated(n, '?');
    for (int j = 0; j < n; ++j) mutated[p[j]] = best[j];        // invert the permutation
    cout << mutated << '\n';
    return 0;
}
