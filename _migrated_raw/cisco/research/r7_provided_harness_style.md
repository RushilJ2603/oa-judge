# Research: The "Provided-Harness" Style Coding OA

## 1. What is the "Provided-Harness" Style?
In many enterprise Online Assessments (OAs), candidates are not asked to write code completely from scratch, nor are they given a clean, hidden test runner like LeetCode's `class Solution`. Instead, they are presented with a **provided harness** (or test scaffolding) right in the code editor.

This harness typically includes:
- A `struct` (or class) defining the parsed input data (e.g., `InputData`).
- A `parse_input()` function that reads from standard input (`stdin`) and populates the struct.
- A `format_output()` function that prints the results in the exact format the autograder expects.
- A `main()` function that glues these together.
- A **`solve()`** function with a rigid signature, which is the *only* part the candidate is supposed to fill out.

The goal of this architectural pattern is to separate input/output concerns from the algorithmic logic while explicitly testing the candidate's ability to interface with pre-existing, structured codebases.

## 2. Who Uses This Style?
**Platforms:**
- **HackerRank**: HackerRank's enterprise assessments frequently generate this boilerplate for C, C++, and Java.
- **Mettl & CoderByte**: Occasionally use a slightly modified visible-harness format for advanced back-end coding tests.

**Companies:**
- **Cisco**: Highly notorious for this exact style, particularly in their networking/hardware-oriented roles.
- **Goldman Sachs & JP Morgan**: Frequently use HackerRank instances with heavy, visible struct-based harnesses for C++ or Java developers.
- **Jane Street / Citadel**: Sometimes provide custom local harnesses in zip files that follow this exact pattern for take-home projects.

## 3. How Candidates Should Approach It
To succeed in a provided-harness OA, candidates must shift from a "LeetCode" mindset to a "Code Integration" mindset:

1. **Locate the "TODO":** Look for comments like `// TODO: Implement your solution here`. This is inside the `solve()` function.
2. **Read the Struct, Not Just the Problem Statement:** The `InputData` struct is the source of truth for your variables. If the problem mentions a graph, look at how the harness stores it in the struct (is it an adjacency matrix `vector<vector<int>>` or an edge list `vector<pair<int, int>>`?).
3. **Never Touch `main()` or `parse_input()`:** Unless explicitly instructed, modifying the parser or the `main()` function will immediately break the hidden test runner, resulting in an automatic 0.
4. **Leverage the Harness Types:** Use the exact types defined in the harness. If the harness uses `long long`, do not downcast to `int`.

## 4. Common Mistakes
1. **Changing the Function Signature:** Altering the signature of `solve()` (e.g., adding parameters or changing the return type) will break the compilation when `main()` tries to call it.
2. **Ignoring Struct Fields:** Candidates often try to declare global variables or read from `cin` again inside `solve()`. The data has *already* been read and stored in the struct. Reading from `cin` will consume EOF or hang the program.
3. **Returning the Wrong Type:** If `solve()` expects a `vector<int>`, returning a single `int` or printing directly to `cout` will fail the autograder.
4. **Failing to Return a Value:** Especially in C++, forgetting the `return` statement at the end of `solve()` can lead to undefined behavior or segmentation faults in the harness's `format_output()`.

## 5. The C-Language Variant
The C-language variant of this harness is notoriously difficult for candidates used to modern languages because it involves manual memory management and pointer semantics.

- **Out-Parameters Instead of Return Values:** C lacks tuples or `std::vector`, so returning multiple arrays is impossible via standard return types. Instead, the harness passes pre-allocated arrays or uninitialized pointers to `solve()` as **out-parameters**. The candidate must mutate these arrays.
- **Manual Memory Management (`malloc`/`free`):** The harness usually `malloc`s the 2D arrays or strings before calling `solve()`, and `free`s them in `main()`. Candidates must understand that they do not need to free the input data, but they *do* need to understand pointer arithmetic to access it.
- **`scanf` / `printf` Dependencies:** The harness will heavily rely on format specifiers. Candidates must understand the difference between `%d` (int) and `%lld` (long long) if they need to debug print.

## 6. Actual Example Harnesses

### Example 1: C++ Harness (Pathfinding)
```cpp
#include <iostream>
#include <vector>

using namespace std;

struct InputData {
    int N, M;
    vector<vector<int>> grid;
    int start_x, start_y;
};

static bool parse_input(InputData &D) {
    if (!(cin >> D.N >> D.M)) return false;
    D.grid.assign(D.N, vector<int>(D.M, 0));
    for (int i = 0; i < D.N; ++i) {
        for (int j = 0; j < D.M; ++j) cin >> D.grid[i][j];
    }
    cin >> D.start_x >> D.start_y;
    return true;
}

static void format_output(int result) {
    cout << result << "\n";
}

static int solve(const InputData &D) {
    // TODO: Implement logic using D.grid, D.N, D.M, etc.
    return 0; 
}

int main() {
    InputData D;
    if (!parse_input(D)) return 0;
    format_output(solve(D));
    return 0;
}
```

### Example 2: C Harness with Out-Parameters
```c
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int num_items;
    long long *weights;
} InputData;

static int parse_input(InputData *D) {
    if (scanf("%d", &D->num_items) != 1) return 0;
    D->weights = (long long *)malloc(sizeof(long long) * D->num_items);
    for (int i = 0; i < D->num_items; ++i) {
        scanf("%lld", &D->weights[i]);
    }
    return 1;
}

static void format_output(int *results, int len) {
    for (int i = 0; i < len; ++i) {
        printf("%d ", results[i]);
    }
    printf("\n");
}

/* solve receives 'results' array pre-allocated by main */
static void solve(const InputData *D, int *results) {
    // TODO: Write to the results array
    for (int i = 0; i < D->num_items; i++) {
        results[i] = 1; /* Example modification */
    }
}

int main(void) {
    InputData D;
    if (!parse_input(&D)) return 0;
    
    int *results = (int *)malloc(sizeof(int) * D.num_items);
    solve(&D, results);
    format_output(results, D.num_items);
    
    free(results);
    free(D.weights);
    return 0;
}
```

## Sources & Citations
- **GeeksForGeeks / Testsigma**: Define test harnesses as scaffolding that provides automated execution and input parsing, separating candidate logic from grading logic.
- **HackerRank Engineering Blog / User Guides**: Documents the usage of boilerplate code where candidates only fill the logic block to streamline evaluation.
- **University Resources (e.g. UoL)**: Describe "provided harness" patterns for testing C/C++ memory management efficiently by isolating the `solve` unit tests.
