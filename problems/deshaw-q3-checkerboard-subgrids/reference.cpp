// DE Shaw Q3 — count axis-aligned subgrids that are perfect checkerboards.
// Key move: XOR out the parity mask, turning "checkerboard" into "constant",
// then count constant-value submatrices with the classic histogram/monotonic-stack sweep.
#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<string> g(n);
    for (auto &row : g) cin >> row;

    // b[i][j] = g[i][j] XOR ((i+j) & 1).
    // A rectangle is a checkerboard  <=>  b is constant on it.
    vector<vector<int>> b(n, vector<int>(m));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < m; ++j)
            b[i][j] = (g[i][j] - '0') ^ ((i + j) & 1);

    long long total = 0;
    vector<int> h(m, 0);            // h[j] = run of equal b upward in column j, ending at row i
    vector<int> stk(m), width(m);   // monotonic stack of (height, accumulated width)

    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < m; ++j)
            h[j] = (i > 0 && b[i][j] == b[i - 1][j]) ? h[j] + 1 : 1;

        // Sweep row i left to right; reset the stack at every b-boundary, because a
        // rectangle may not straddle a colour change within its bottom row.
        int top = 0;                // stack size
        long long sumMin = 0;       // sum of min-height over all subarrays ending at j
        for (int j = 0; j < m; ++j) {
            if (j > 0 && b[i][j] != b[i][j - 1]) { top = 0; sumMin = 0; }
            int w = 1;
            while (top > 0 && stk[top - 1] >= h[j]) {
                --top;
                w += width[top];
                sumMin -= (long long)stk[top] * width[top];
            }
            stk[top] = h[j];
            width[top] = w;
            ++top;
            sumMin += (long long)h[j] * w;
            total += sumMin;        // all rectangles whose bottom-right corner is (i,j)
        }
    }
    cout << total << '\n';
    return 0;
}
