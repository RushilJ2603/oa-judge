#include <iostream>
#include <vector>

using namespace std;

// ===== WRITE YOUR CODE HERE =====
// You may define additional structs/classes or global variables if needed.

void solve() {
    int n, q;
    if (!(cin >> n >> q)) return;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
    }
    
    // Process queries
    for (int i = 0; i < q; ++i) {
        int type;
        cin >> type;
        if (type == 1) {
            int u, v;
            cin >> u >> v;
            // Handle move query
        } else if (type == 2) {
            int k;
            cin >> k;
            // Handle positional query and print the result
        }
    }
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    solve();
    return 0;
}
