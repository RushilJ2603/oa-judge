# HackerRank-Style Function-Stub Harnesses

## 1. Concept Overview: The Hidden `main`
Online assessment (OA) platforms like HackerRank hide the I/O boilerplate from candidates. The candidate only sees a "function stub" like `vector<int> solve(vector<int> a)`. Under the hood, a complete C++ source file is constructed. This file includes the candidate's stub logic along with a `main` function that reads from `stdin`, parses the data, calls the function, and writes the result to `stdout` (or a file specified by the environment).

This helps a student who understands data structures (e.g., from LeetCode) but struggles with fast and reliable C++ console I/O, allowing them to just focus on the core algorithmic logic.

## 2. The Exact Structure of the Generated C++ Solution
The platform concatenates the boilerplate around the user's code. In many modern HackerRank challenges, this scaffolding is visible but locked in the editor.
The exact anatomy of the C++ file is:
1. Heavy `#include` directives (often `#include <bits/stdc++.h>`).
2. Forward declarations of string manipulation helper functions (`ltrim`, `rtrim`, `split`).
3. The candidate's **function stub**.
4. The `main()` function, which orchestrates file streams (via `OUTPUT_PATH`), reading inputs using `getline`, parsing inputs, executing the stub, and writing outputs.
5. Implementations of the helper functions.

## 3. Actual Compilable Examples & Input Formats

### Example A: Reading `N`, then an Array
**Input Format:**
```
5
1 2 3 4 5
```

**Compilable Harness:**
```cpp
#include <bits/stdc++.h>
using namespace std;

string ltrim(const string &);
string rtrim(const string &);
vector<string> split(const string &);

/*
 * Complete the 'solveArray' function below.
 *
 * The function is expected to return an INTEGER.
 * The function accepts INTEGER_ARRAY arr as parameter.
 */
int solveArray(vector<int> arr) {
    // CANDIDATE LOGIC GOES HERE
    int sum = 0;
    for (int x : arr) sum += x;
    return sum;
}

int main()
{
    // HackerRank outputs to a file defined by OUTPUT_PATH, or uses a default
    const char* env_p = getenv("OUTPUT_PATH");
    ofstream fout(env_p ? env_p : "output.txt");

    string n_temp;
    // Read N using getline
    getline(cin, n_temp);
    int n = stoi(ltrim(rtrim(n_temp)));

    string arr_temp_temp;
    // Read the array string using getline
    getline(cin, arr_temp_temp);
    vector<string> arr_temp = split(rtrim(arr_temp_temp));

    vector<int> arr(n);
    for (int i = 0; i < n; i++) {
        int arr_item = stoi(arr_temp[i]);
        arr[i] = arr_item;
    }

    // Call the user's function stub
    int result = solveArray(arr);

    fout << result << "\n";
    fout.close();

    return 0;
}

// --- HackerRank String Utility Implementations ---
string ltrim(const string &str) {
    string s(str);
    s.erase(s.begin(), find_if(s.begin(), s.end(), not1(ptr_fun<int, int>(isspace))));
    return s;
}

string rtrim(const string &str) {
    string s(str);
    s.erase(find_if(s.rbegin(), s.rend(), not1(ptr_fun<int, int>(isspace))).base(), s.end());
    return s;
}

vector<string> split(const string &str) {
    vector<string> tokens;
    string::size_type start = 0;
    string::size_type end = 0;
    while ((end = str.find(" ", start)) != string::npos) {
        tokens.push_back(str.substr(start, end - start));
        start = end + 1;
    }
    tokens.push_back(str.substr(start));
    return tokens;
}
```

### Example B: Multiple Test Cases and Matrices
**Input Format:**
```
2       // number of test cases
2 3     // rows cols for test case 1
1 2 3   // row 1
4 5 6   // row 2
1 1     // rows cols for test case 2
9       // row 1
```

**Compilable Harness:**
```cpp
#include <bits/stdc++.h>
using namespace std;

string ltrim(const string &);
string rtrim(const string &);
vector<string> split(const string &);

/*
 * Complete the 'solveMatrix' function below.
 */
int solveMatrix(vector<vector<int>> matrix) {
    // CANDIDATE LOGIC GOES HERE
    return matrix.size() > 0 ? matrix[0][0] : 0;
}

int main()
{
    const char* env_p = getenv("OUTPUT_PATH");
    ofstream fout(env_p ? env_p : "output.txt");

    string t_temp;
    getline(cin, t_temp);
    int t = stoi(ltrim(rtrim(t_temp))); // Read T

    for (int t_itr = 0; t_itr < t; t_itr++) {
        string first_multiple_input_temp;
        getline(cin, first_multiple_input_temp);
        vector<string> first_multiple_input = split(rtrim(first_multiple_input_temp));

        int rows = stoi(first_multiple_input[0]);
        int cols = stoi(first_multiple_input[1]);

        vector<vector<int>> matrix(rows);
        for (int i = 0; i < rows; i++) {
            matrix[i].resize(cols);
            
            string matrix_row_temp_temp;
            getline(cin, matrix_row_temp_temp);
            vector<string> matrix_row_temp = split(rtrim(matrix_row_temp_temp));

            for (int j = 0; j < cols; j++) {
                int matrix_item = stoi(matrix_row_temp[j]);
                matrix[i][j] = matrix_item;
            }
        }

        int result = solveMatrix(matrix);
        fout << result << "\n";
    }

    fout.close();
    return 0;
}

// Utility implementations omitted for brevity (they match Example A)
```

## 4. Edge and Newline Handling
Notice how the templates use `getline(cin, var)` heavily instead of `cin >> var`. 
When candidates write their own I/O, a classic C++ pitfall occurs: `cin >> n` reads a number but leaves the trailing newline `\n` in the input stream. If a subsequent `getline` is called, it immediately consumes that empty string caused by the left-over newline, creating frustrating bugs. 

By exclusively using `getline` across the board, and combining it with string tokenization (`split()`, `ltrim()`, `rtrim()`), the HackerRank harness perfectly sidesteps whitespace/newline misalignment. It reads exactly line-by-line, trims leading/trailing spaces, and parses elements individually.

## Citations
- HackerRank Environment Documentation: https://www.hackerrank.com/environment/
- Example discussion on HackerRank's C++ Boilerplate: https://www.reddit.com/r/learnprogramming/comments/166p1j1/understanding_hackerranks_c_boilerplate/
