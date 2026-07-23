#include <bits/stdc++.h>
using namespace std;

int sumCheckPoints(int N, int S, string pos[], int val[])
{
    // Path string -> checkpoint value. The root (Starting point) has the empty path.
    unordered_map<string, int> node;
    node[""] = S;
    for (int i = 0; i < N - 1; ++i)
        node[pos[i]] = val[i];

    // A checkpoint is "faulty" iff both of its downstream slots are occupied.
    int sum = 0;
    for (const auto &kv : node)
        if (node.count(kv.first + "L") && node.count(kv.first + "R"))
            sum += kv.second;
    return sum;
}

int main()
{
    int N;
    cin >> N;
    int S;
    cin >> S;
    string str[N - 1];
    int val[N - 1];
    for (int i = 0; i < N - 1; i++)
    {
        cin >> str[i];
        cin >> val[i];
    }
    cout << sumCheckPoints(N, S, str, val);
    return 0;
}
