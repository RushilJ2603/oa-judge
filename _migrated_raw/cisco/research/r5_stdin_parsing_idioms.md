# C++ Stdin Parsing Idioms for Competitive Programming

## 1. Read N then N ints
Reads an integer `N` followed by `N` integers into an array/vector.

**Input:**
```
5
10 20 30 40 50
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <vector>

using namespace std;

int main() {
    int n;
    if (cin >> n) {
        vector<int> arr(n);
        for (int i = 0; i < n; i++) {
            cin >> arr[i];
        }
    }
    return 0;
}
```

## 2. Read a 2D grid R x C
Reads rows and columns count, then the elements of the grid.

**Input:**
```
2 3
1 2 3
4 5 6
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <vector>

using namespace std;

int main() {
    int r, c;
    if (cin >> r >> c) {
        vector<vector<int>> grid(r, vector<int>(c));
        for (int i = 0; i < r; i++) {
            for (int j = 0; j < c; j++) {
                cin >> grid[i][j];
            }
        }
    }
    return 0;
}
```

## 3. Read a graph given M edges into an adjacency list
Reads `N` vertices and `M` edges, then each edge `u`, `v`.

**Input:**
```
4 4
0 1
1 2
2 3
3 0
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <vector>

using namespace std;

int main() {
    int n, m;
    if (cin >> n >> m) {
        vector<vector<int>> adj(n);
        for (int i = 0; i < m; i++) {
            int u, v;
            cin >> u >> v;
            // Undirected graph
            adj[u].push_back(v);
            adj[v].push_back(u); 
        }
    }
    return 0;
}
```

## 4. Read T test cases
Reads the number of test cases and processes each sequentially.

**Input:**
```
2
3
1 2 3
2
10 20
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <vector>

using namespace std;

void solve() {
    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; i++) cin >> a[i];
    // process
}

int main() {
    int t;
    if (cin >> t) {
        while (t--) {
            solve();
        }
    }
    return 0;
}
```

## 5. Read pairs
Reads `N` pairs of values.

**Input:**
```
3
1 10
2 20
3 30
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <vector>

using namespace std;

int main() {
    int n;
    if (cin >> n) {
        vector<pair<int, int>> pairs(n);
        for (int i = 0; i < n; i++) {
            cin >> pairs[i].first >> pairs[i].second;
        }
    }
    return 0;
}
```

## 6. Read until EOF
Useful when the input length is unspecified and you just read until no more data.

**Input:**
```
1 2 3 4 5
6 7 8
```

**C++ Snippet:**
```cpp
#include <iostream>

using namespace std;

int main() {
    int x;
    while (cin >> x) {
        // process x
    }
    return 0;
}
```

## 7. Read a whole line with `getline`
Reads an entire line, including spaces.

**Input:**
```
Hello world from C++
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <string>

using namespace std;

int main() {
    string line;
    if (getline(cin, line)) {
        // process line
    }
    return 0;
}
```

## 8. Classic bug of mixing `cin >>` and `getline`, and its fix with `cin.ignore()`
`cin >> n` leaves the newline character in the stream. If `getline` is called immediately after, it reads an empty string up to the newline. Use `cin.ignore()` to flush it.

**Input:**
```
42
This is the second line
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <string>
#include <limits>

using namespace std;

int main() {
    int n;
    cin >> n; // Reads 42, leaves '\n'
    
    // FIX: ignore the leftover newline
    cin.ignore(numeric_limits<streamsize>::max(), '\n');
    
    string s;
    getline(cin, s); // Reads "This is the second line"
    return 0;
}
```

## 9. Tokenizing a line with `stringstream`
Reading an entire line and extracting tokens separated by whitespace.

**Input:**
```
apple banana orange grape
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <string>
#include <sstream>
#include <vector>

using namespace std;

int main() {
    string line;
    if (getline(cin, line)) {
        stringstream ss(line);
        string token;
        vector<string> tokens;
        while (ss >> token) {
            tokens.push_back(token);
        }
    }
    return 0;
}
```

## 10. Reading comma-separated values
Using `getline` with a delimiter to read comma-separated tokens.

**Input:**
```
10,20,30,40
```

**C++ Snippet:**
```cpp
#include <iostream>
#include <string>
#include <sstream>
#include <vector>

using namespace std;

int main() {
    string line;
    if (getline(cin, line)) {
        stringstream ss(line);
        string token;
        vector<int> values;
        while (getline(ss, token, ',')) {
            values.push_back(stoi(token));
        }
    }
    return 0;
}
```
