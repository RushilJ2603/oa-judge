#include <iostream>
#include <vector>

using namespace std;

// WRITE YOUR CODE HERE
void solve(int n, vector<int>& T) {
    cout << 0 << " " << 0 << "\n";
}

int main() {
    int n;
    if (cin >> n) {
        vector<int> T(n);
        for (int i = 0; i < n; i++) {
            cin >> T[i];
        }
        solve(n, T);
    }
    return 0;
}
