#include <iostream>
#include <vector>

using namespace std;

// ===== WRITE YOUR CODE HERE =====

int solve(int n, vector<long long>& a) {
    // Write your logic here
    return 0;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    if (!(cin >> n)) return 0;
    vector<long long> a(n);
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
    }
    cout << solve(n, a) << "\n";
    return 0;
}
