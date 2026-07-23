# Big Tech Online Assessment (OA) Formats: Amazon & Microsoft

This digest outlines the input/output (I/O) formats, scaffolding styles, and C++ harness/stub structures used in Amazon and Microsoft Online Assessments (OAs). 

## 1. Amazon (HackerRank & Custom Platforms)

Amazon frequently utilizes HackerRank for its online assessments. The coding environment generally provides a pre-written class or function stub where the candidate implements the core logic, closely mirroring platforms like LeetCode. Occasionally, candidates may encounter a blank editor requiring raw standard input/output processing.

### I/O and Scaffolding Style
- **Class-based Stub (Most Common):** The scaffolding parses the standard input, instantiates a `Solution` class, calls the required method, and prints the return value. Candidates only edit the body of the class method. 
- **Raw Standard I/O (Less Common):** The candidate is provided a blank `main()` function and must manually read from `std::cin` using token-based (`cin >> x`) or line-based (`getline(cin, str)`) parsing.

### Common Input Formats
- **Arrays:** Typically passed as `vector<int>&` or `vector<string>&`.
- **Grids/Matrices:** Passed as `vector<vector<int>>&`.
- **Queries:** Often an array of queries `vector<vector<int>>& queries` where each query is a pair or triplet of integers indicating operations.

### Actual Example C++ Harness/Stub

**Type A: Class Method Stub (LeetCode Style)**
```cpp
#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    long long maximumQuality(vector<int>& packets, int channels) {
        // Your code here
        return 0;
    }
};

// Invisible to candidate, HackerRank scaffolding generally looks like:
/*
int main() {
    int n; cin >> n;
    vector<int> packets(n);
    for(int i = 0; i < n; i++) cin >> packets[i];
    int channels; cin >> channels;
    Solution obj;
    cout << obj.maximumQuality(packets, channels) << endl;
    return 0;
}
*/
```

**Type B: Standard I/O Form**
```cpp
#include <iostream>
#include <vector>
using namespace std;

int main() {
    // Read tokens
    int n, m;
    if (!(cin >> n >> m)) return 0;
    
    vector<vector<int>> grid(n, vector<int>(m));
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < m; ++j) {
            cin >> grid[i][j];
        }
    }
    
    // Process and print
    cout << 0 << "\n";
    return 0;
}
```

## 2. Microsoft (Codility & Custom Platforms)

Microsoft historically and currently relies heavily on Codility for automated initial screens. Codility focuses heavily on correctness and optimal time/space complexity (Big-O).

### I/O and Scaffolding Style
- **Standalone Function:** Unlike HackerRank's class object instantiation, Codility typically expects the candidate to complete a standalone global function named `solution`.
- **Invisible I/O:** The candidate does not parse standard input. Codility provides the parameters directly to the function.
- **Strict Headers:** The environment automatically includes basic standard headers (`<vector>`, `<algorithm>`), but candidates can include others. Codility has a built-in snippet reminding candidates how to log debug messages.

### Common Input Formats
- Arrays are passed by reference to avoid copying overhead (`vector<int> &A`).
- **Strings:** Passed directly (`string &S`).
- Focus is heavy on single integer arrays, prefix sums, strings, and maps.

### Actual Example C++ Harness/Stub

```cpp
// Codility automatically includes some basic headers
#include <vector>
#include <algorithm>
#include <iostream>

// you can write to stdout for debugging purposes, e.g.
// cout << "this is a debug message" << endl;

int solution(vector<int> &A) {
    // Implement your solution here
    
    // Example: finding the minimum missing positive integer
    return 1;
}
```

## Citations & Sources
- **LeetCode Discuss (Amazon OAs):** Candidates regularly confirm the Class Solution stub environment. [LeetCode Discuss: Amazon OA](https://leetcode.com/discuss/interview-question?currentPage=1&orderBy=hot&query=&tag=amazon-oa)
- **HackerRank Candidate Experience:** HackerRank environment documentation outlines the hidden `main()` scaffolding. [HackerRank Support](https://support.hackerrank.com/hc/en-us/articles/115007357428-Coding-Environment)
- **Codility Lessons:** Codility's official lessons utilize the exact `int solution(vector<int> &A)` format. [Codility Developer Training](https://app.codility.com/programmers/lessons/1-iterations/)
- **Glassdoor & Reddit:** Aggregated reports (`r/csMajors`, `r/cscareerquestions`) highlight the emphasis on performance tracking via Codility and standard library usage.
