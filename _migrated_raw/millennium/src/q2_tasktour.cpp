// Millennium Q2 — shortest walk from start to end visiting every task node.
// Unit-weight undirected graph, revisits permitted.
//
// Two-stage standard solution:
//   Stage 1: BFS from each of the k+2 "milestone" nodes -> pairwise shortest paths.
//   Stage 2: TSP-style bitmask DP over the k task nodes on that dense distance matrix.
#include <bits/stdc++.h>
using namespace std;

const int INF = 1e9;

vector<int> bfs(int src, const vector<vector<int>> &g) {
    vector<int> d(g.size(), INF);
    d[src] = 0;
    queue<int> q;
    q.push(src);
    while (!q.empty()) {
        int u = q.front(); q.pop();
        for (int v : g[u])
            if (d[v] == INF) { d[v] = d[u] + 1; q.push(v); }
    }
    return d;
}

int solve(int n, const vector<pair<int,int>> &edges, int start, int end_, vector<int> tasks) {
    vector<vector<int>> g(n);
    for (auto &e : edges) {
        g[e.first].push_back(e.second);
        g[e.second].push_back(e.first);      // bidirectional
    }

    // Milestones: index 0..k-1 = tasks, k = start, k+1 = end.
    int k = tasks.size();
    vector<int> node = tasks;
    node.push_back(start);
    node.push_back(end_);

    vector<vector<int>> dist(k + 2);
    for (int i = 0; i < k + 2; ++i) {
        vector<int> d = bfs(node[i], g);
        dist[i].resize(k + 2);
        for (int j = 0; j < k + 2; ++j) dist[i][j] = d[node[j]];
    }

    // Unreachable milestone => no such walk exists.
    for (int j = 0; j < k + 2; ++j)
        if (dist[k][j] >= INF) return -1;

    if (k == 0) return dist[k][k + 1];

    // dp[mask][i] = shortest walk from start covering `mask`, currently standing on task i.
    vector<vector<int>> dp(1 << k, vector<int>(k, INF));
    for (int i = 0; i < k; ++i) dp[1 << i][i] = dist[k][i];

    for (int mask = 1; mask < (1 << k); ++mask)
        for (int i = 0; i < k; ++i) {
            if (dp[mask][i] >= INF || !(mask >> i & 1)) continue;
            for (int j = 0; j < k; ++j) {
                if (mask >> j & 1) continue;
                int nxt = dp[mask][i] + dist[i][j];
                if (nxt < dp[mask | 1 << j][j]) dp[mask | 1 << j][j] = nxt;
            }
        }

    int best = INF;
    for (int i = 0; i < k; ++i)
        if (dp[(1 << k) - 1][i] < INF)
            best = min(best, dp[(1 << k) - 1][i] + dist[i][k + 1]);
    return best >= INF ? -1 : best;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<pair<int,int>> edges(m);
    for (auto &e : edges) cin >> e.first >> e.second;
    int start, end_, k;
    cin >> start >> end_ >> k;
    vector<int> tasks(k);
    for (int &t : tasks) cin >> t;
    cout << solve(n, edges, start, end_, tasks) << '\n';
    return 0;
}
