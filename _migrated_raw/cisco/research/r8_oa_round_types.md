# Comprehensive Guide to Non-Standard OA (Online Assessment) Round Types

While many Online Assessments (OAs) focus heavily on writing code from scratch to solve algorithmic problems, a significant number of top-tier companies employ non-standard assessment formats. These formats gauge a candidate's practical debugging skills, theoretical knowledge, and system-level thinking. This study guide breaks down the four most common non-standard OA rounds, complete with patterns, examples, and strategies.

---

## 1. Read-and-Fix / Debug-the-Pseudocode Rounds

Instead of writing code, you are presented with a codebase (or pseudocode) that is structurally complete but failing test cases. Your goal is to identify the root cause and apply a minimal fix. This assesses code comprehension, tracing execution flows, and systematic troubleshooting (e.g., used extensively by Amazon, CodeSignal, HackerRank).

### Common Bug Patterns & Examples

#### Pattern A: Off-by-One Errors in Loops or Array Access
A loop terminates one iteration too early or too late, causing incorrect accumulations or `IndexOutOfBounds` errors.

**Example Question (C++):**
*Buggy Code to find the maximum element in an array:*
```cpp
int findMax(int arr[], int n) {
    int max_val = arr[0];
    for (int i = 1; i <= n; i++) { // BUG here
        if (arr[i] > max_val) {
            max_val = arr[i];
        }
    }
    return max_val;
}
```
**Answer / Fix:** The loop condition should be `i < n`. Accessing `arr[n]` results in out-of-bounds undefined behavior.
```cpp
    for (int i = 1; i < n; i++) { 
```

#### Pattern B: Incorrect State Initialization / Reset
Variables meant to track state across iterations are initialized outside the loop when they should be inside, or vice versa.

**Example Question (Python):**
*Buggy Code to count vowels in multiple strings, returning an array of counts:*
```python
def count_vowels_per_word(words):
    res = []
    count = 0 # BUG: Initialized outside
    for word in words:
        for char in word:
            if char in "aeiou":
                count += 1
        res.append(count)
    return res
```
**Answer / Fix:** The `count` variable is never reset, so it accumulates vowels continuously across all words.
```python
def count_vowels_per_word(words):
    res = []
    for word in words:
        count = 0 # FIXED: Reset for each word
        for char in word:
            if char in "aeiou":
                count += 1
        res.append(count)
    return res
```

#### Pattern C: Misused Operators (Assignment vs. Equality, Logical vs. Bitwise)
A common trick in C/C++ where a single `=` is used instead of `==`, or `&` instead of `&&`.

**Example Question (C):**
*Buggy Code checking if a number is even and positive:*
```c
bool isEvenAndPositive(int n) {
    if (n % 2 = 0 && n > 0) { // BUG here
        return true;
    }
    return false;
}
```
**Answer / Fix:** The assignment operator `=` is used instead of the equality operator `==`. This will cause a compilation error or logical error depending on the context.
```c
    if (n % 2 == 0 && n > 0) {
```

#### Pattern D: Incorrect Base Case in Recursion
The recursion lacks a proper base case or the base case returns the wrong identity value, leading to stack overflows or incorrect results.

**Example Question (Python):**
*Buggy Code to compute factorial:*
```python
def factorial(n):
    if n == 1:
        return 0 # BUG here
    return n * factorial(n - 1)
```
**Answer / Fix:** The base case for factorial should return 1, not 0. Returning 0 makes the entire product 0.
```python
    if n <= 1:
        return 1
```

*Sources: HackerRank debugging guidelines, CodeSignal standard assessments.*

---

## 2. Output-Prediction MCQs (C/C++ Snippets)

These questions test your deep understanding of language semantics, memory management, and execution stack. You must trace the exact output of a tricky code snippet.

### Common Tricks & Examples

#### Trick A: Pointer Arithmetic and Post-increment vs. Pre-increment
Understanding how `*p++`, `(*p)++`, and `*++p` differ.

**Example Question:**
```cpp
#include <iostream>
using namespace std;
int main() {
    int arr[] = {10, 20, 30};
    int *p = arr;
    cout << *p++ << " ";
    cout << *p;
    return 0;
}
```
*Options:* A) `10 20` | B) `11 20` | C) `10 10` | D) `20 20`

**Answer:** **A) 10 20**. 
*Explanation:* The post-increment operator `++` has higher precedence than `*`, but because it's a post-increment, the dereference `*` happens on the original address first (printing 10). Then the pointer `p` advances to the next integer (20). The second `cout` prints `*p` which is now 20.

#### Trick B: Recursion Call Stack Visualization
Testing if you know the order of operations in recursive returns (Head vs. Tail recursion).

**Example Question:**
```cpp
#include <iostream>
using namespace std;
void fun(int n) {
    if (n == 0) return;
    cout << n % 2;
    fun(n / 2);
}
int main() {
    fun(25);
    return 0;
}
```
*Options:* A) `11001` | B) `10011` | C) `11100` | D) `00111`

**Answer:** **B) 10011**.
*Explanation:* This function prints the binary representation of a number in reverse order. `25%2 = 1` -> `fun(12)`. `12%2 = 0` -> `fun(6)`. `6%2 = 0` -> `fun(3)`. `3%2 = 1` -> `fun(1)`. `1%2 = 1` -> `fun(0)`. Output: 10011.

#### Trick C: Integer Overflow and Type Promotion
Exploiting fixed-width integer behaviors and signed vs. unsigned comparisons.

**Example Question:**
```cpp
#include <iostream>
using namespace std;
int main() {
    unsigned int a = 10;
    int b = -20;
    if (a + b > 10) 
        cout << "Greater";
    else 
        cout << "Lesser";
    return 0;
}
```
*Options:* A) `Greater` | B) `Lesser` | C) `Compiler Error` | D) `Runtime Error`

**Answer:** **A) Greater**.
*Explanation:* When evaluating `a + b`, the signed integer `b` is implicitly promoted to an unsigned integer. A negative number cast to unsigned becomes a very large positive number (due to two's complement representation). Thus, `a + b` is heavily positive and strictly greater than 10.

*Sources: GeeksforGeeks C++ Output Questions, CppQuiz.org, CodeChef Code Tracing.*

---

## 3. Design / Short-Answer Rounds (Data Structure Choice Justification)

These rounds emulate a system design interview at a junior/mid level. They ask for the optimal data structure or component for a specific scenario and force you to justify your choice, proving you understand trade-offs.

### The "State, Compare, Justify" Framework
*   **State:** Clearly declare your choice.
*   **Compare:** Mention an alternative that you ruled out.
*   **Justify:** Connect the choice to the specific performance constraints (Big-O, latency, memory).

### Example Questions

**Scenario 1: Autocomplete / Typeahead Feature**
*Question:* "You are building a search box that needs to provide real-time suggestions as the user types. What data structure would you use to store the dictionary of valid words, and why?"
*Answer:* "I would use a **Trie (Prefix Tree)**. While a Hash Map provides O(1) lookups for exact matches, it cannot efficiently retrieve words matching a specific prefix. A Trie allows prefix searches in O(L) time (where L is the prefix length). The trade-off is higher memory consumption due to node pointers, but for real-time latency, the O(L) time complexity is strictly necessary."

**Scenario 2: Real-time Leaderboard**
*Question:* "Design a leaderboard for a massive multiplayer game that updates player scores in real-time and allows fetching the top 100 players instantly."
*Answer:* "I would use a **Max-Heap** (or a Redis Sorted Set in a distributed system). A standard Array/List would require O(N log N) sorting for every query, which is too slow for real-time. A Max-Heap allows O(log N) updates when scores change and O(K log N) to extract the top K players. A Redis Sorted Set (implemented via Skip Lists) provides O(log N) inserts and fast range queries, satisfying both rapid score writes and top-k reads."

*Sources: TryExponent, Dataford System Design Assessment rubrics.*

---

## 4. Mixed MCQs (OS / DBMS / Networking / Aptitude)

Companies like **Cisco**, **VMware**, and **Oracle** heavily weight computer science fundamentals alongside coding. Their OAs often feature 20-40 MCQs that act as a strict filter. 

### Why the Mix?
These companies build infrastructure software. Writing correct logic is only half the job; understanding how that logic interacts with memory, network packets, and database locks is critical.

### Typical Assessment Structure (e.g., Cisco SDE OA)
*   **Duration:** 60-90 mins total.
*   **Section 1: Aptitude (10-15 questions)** - Quantitative and logical reasoning.
*   **Section 2: CS Fundamentals (15-25 questions)** - OS, DBMS, Computer Networks, C/C++ output.
*   **Section 3: Coding (1-2 questions)** - Easy/Medium difficulty (Arrays, Graphs, DP).

### Concrete Example Questions

#### Networking (High Priority for Cisco)
**Question:** Which of the following protocols operates at the Transport Layer of the OSI model and guarantees reliable, ordered delivery?
*Options:* A) IP | B) UDP | C) TCP | D) ICMP
**Answer:** **C) TCP**. (IP is Network layer, UDP is Transport but unreliable).

#### Operating Systems
**Question:** In a system with paging, what happens when a process tries to access a page not currently mapped in RAM?
*Options:* A) Segmentation Fault | B) Page Fault | C) Deadlock | D) Thrashing
**Answer:** **B) Page Fault**. (The OS must trap the fault and load the page from disk).

#### Database Management Systems (DBMS)
**Question:** Which normal form dictates that there should be no transitive dependencies of non-prime attributes on the primary key?
*Options:* A) 1NF | B) 2NF | C) 3NF | D) BCNF
**Answer:** **C) 3NF**.

#### Aptitude / Logical Reasoning
**Question:** A train running at the speed of 60 km/hr crosses a pole in 9 seconds. What is the length of the train?
*Options:* A) 120 meters | B) 180 meters | C) 150 meters | D) 324 meters
**Answer:** **C) 150 meters**.
*Explanation:* Speed in m/s = 60 * (5/18) = 50/3 m/s. Distance (length) = Speed * Time = (50/3) * 9 = 150 meters.

*Sources: GeeksforGeeks Cisco Interview Experiences, PrepInsta, FacePrep.*
