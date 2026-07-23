#include <iostream>
#include <vector>
#include <string>

using namespace std;

// ===== WRITE YOUR CODE HERE =====

long long solve(int n, int m, const vector<string>& grid) {
    // Write your logic here
    return 0;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<string> grid(n);
    for (int i = 0; i < n; ++i) {
        cin >> grid[i];
    }
    cout << solve(n, m, grid) << "\n";
    return 0;
}
