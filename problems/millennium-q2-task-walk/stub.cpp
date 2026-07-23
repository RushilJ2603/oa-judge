#include <iostream>
#include <vector>

using namespace std;

int solve(int n, const vector<pair<int,int>>& edges, int start, int end_, const vector<int>& tasks) {
    // WRITE YOUR CODE HERE
    return -1;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<pair<int,int>> edges(m);
    for (int i = 0; i < m; ++i) {
        cin >> edges[i].first >> edges[i].second;
    }
    int start, end_, k;
    cin >> start >> end_ >> k;
    vector<int> tasks(k);
    for (int i = 0; i < k; ++i) {
        cin >> tasks[i];
    }
    cout << solve(n, edges, start, end_, tasks) << "\n";
    return 0;
}
