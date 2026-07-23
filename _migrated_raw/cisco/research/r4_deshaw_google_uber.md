# D.E. Shaw, Google, and Uber Online Assessments (OAs): I/O & Scaffolding Digest

When tackling Online Assessments (OAs) for top tech companies and quant firms, understanding the platform's input/output format and scaffolding structure is crucial for saving time and avoiding parsing bugs. This document summarizes the I/O conventions and provided harnesses for D.E. Shaw, Google, and Uber.

## 1. D.E. Shaw (Quant/SDE)
**Platform:** HackerRank (mostly) or private portals.
**I/O Format:** Standard Input/Output (`stdin` / `stdout`).

D.E. Shaw often employs a traditional competitive programming style. Depending on the specific HackerRank setup, you might be given a function stub that handles I/O for you, or you might be required to write the full program from scratch, parsing `stdin` manually. 

### Common Input Formats (stdin)
*   **Arrays:** Typically starts with an integer `N` (size of array), followed by `N` space-separated integers on the next line.
*   **Graphs:** Usually given as `V` (vertices) and `E` (edges), followed by `E` lines containing pairs of integers `u v` representing an edge. Occasionally includes edge weights `u v w`.
*   **Queries:** Starts with initial data, followed by an integer `Q` (number of queries), followed by `Q` lines where each line represents a specific query format (e.g., `1 x y` for update, `2 x` for query).

### Example C++ Harness (Manual Parsing)
If the stub code is missing or locked, you will need to write the `main` function and use `cin`/`cout`.

```cpp
#include <iostream>
#include <vector>

using namespace std;

// Your core logic here
void solve() {
    int n;
    // Read array size
    if (!(cin >> n)) return;
    
    vector<int> arr(n);
    for (int i = 0; i < n; ++i) {
        cin >> arr[i];
    }
    
    // Example: Print sum (or logic result)
    long long sum = 0;
    for (int x : arr) sum += x;
    cout << sum << "\n";
}

int main() {
    // Fast I/O
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    int t = 1;
    // cin >> t; // Uncomment if multiple test cases
    while (t--) {
        solve();
    }
    return 0;
}
```
*Source: [HackerRank - Reading Input](https://www.hackerrank.com/)*

---

## 2. Google (Early-Career / SWE)
**Platform:** Custom platforms, HackerRank, or occasionally third-party like HackerEarth.
**I/O Format:** Function Stub (No `stdin` parsing).

Google heavily favors the **function stub** format. You are provided with a class or function signature, and the platform's invisible backend harness handles the serialization, deserialization, and invoking of your code. 

### Scaffolding Style
*   **Hidden Harness:** You don't write the `main` function.
*   **Hidden Test Cases:** Google OAs are notorious for providing only 1 or 2 visible example test cases. You must write your own additional test cases in the environment to verify edge cases. The harness runs your function against many hidden inputs.

### Example C++ Harness (Function Stub)
You just fill in the provided method.

```cpp
#include <vector>
#include <string>
#include <algorithm>

using namespace std;

class Solution {
public:
    // The harness calls this function directly.
    // No cin/cout needed.
    int minimumOperations(vector<int>& arr, string s) {
        // Your logic here
        int result = 0;
        // ...
        return result;
    }
};
```
*Source: [Google Careers / LeetCode Discussion](https://leetcode.com/discuss/interview-question)*

---

## 3. Uber
**Platform:** CodeSignal (most common) or HackerRank.
**I/O Format:** Function Stub.

Uber primarily uses CodeSignal for its General Coding Assessment (GCA). Like Google, this relies entirely on function stubs. You do not need to read from standard input.

### Scaffolding Style
*   **CodeSignal UI:** The interface provides the function signature directly. You return the answer.
*   **Input Types:** CodeSignal passes native data structures (e.g., `std::vector<int>`, `std::vector<std::vector<int>>` for matrices/graphs).

### Example C++ Harness (CodeSignal Style)
```cpp
#include <vector>
#include <unordered_map>

using namespace std;

// CodeSignal provides the function directly, no class wrapper needed
int solution(vector<int> numbers, int target) {
    // Write your code here
    unordered_map<int, int> seen;
    for (int i = 0; i < numbers.size(); ++i) {
        if (seen.count(target - numbers[i])) {
            return 1; // Example logic
        }
        seen[numbers[i]] = i;
    }
    return 0;
}
```
*Source: [CodeSignal General Coding Framework](https://codesignal.com/)*

---

## Summary Cheat Sheet

| Company | Typical Platform | I/O Style | Must I write `main()`? | Key Characteristic |
| :--- | :--- | :--- | :--- | :--- |
| **D.E. Shaw** | HackerRank | `stdin` / `stdout` (often) | Yes (if no stub) | Classic CP style. Fast I/O recommended in C++. |
| **Google** | Custom / HackerRank | Function Stub | No | Minimal visible test cases. Harness is hidden. |
| **Uber** | CodeSignal | Function Stub | No | Native data structures passed directly as arguments. |
