# Flipkart OA — Coding Questions (HirePro platform, transcribed from photos)

Source: 45 phone photos of the OA screen (`inapp.hirepro.ai` screen-share banner visible).
Transcription policy — same as the CISCO pass: orchestrator vision only, no OCR, no subagents.
Text obscured by glare/frame-crop is reconstructed from an overlapping photo where one exists;
anything still uncertain is marked **[recon]**.

Platform notes worth keeping (they drive the debugging section):
- The editor shows a **fixed function signature + a `main()` that does all the I/O for you**. You
  only fill in `// WRITE YOUR CODE HERE`. You cannot see the test cases.
- Both statements carry the warning: *"Do not print arbitrary strings anywhere in the program, as
  these contribute to the output and test cases will fail."* — i.e. **no debug `cout` survives**.
  This is exactly the constraint that makes blind debugging hard.

---

## Q1 — Golden Price (megastore savings)

**Statement.**
The megastore has kept an offer saying that, if the customer can identify a product whose price is
a *golden price* G, then it is absolutely free for them. A golden price is defined as a number G
whose difference between the sum of all the digits and the highest digit is equal to the highest
digit.

Worked examples given in the statement:
- 352 → (3+5+2) − 5 = 5 → the highest digit is 5 → golden.
- 3003, 32812 → (3+2+8+1+2) − 8 = 8 → golden.

Narendra goes to the megamarket and buys one unit of product in the price range of (X, Y). Now he
wants to know the amount he saved by selecting the golden price product from the list.

As you are a friend of Narendra, can you help him calculate the total amount he saved by purchasing
one product in the price ranges of X and Y.

Read the input from STDIN and write the output to STDOUT. You should not write arbitrary strings
while reading the input and while printing as these contribute to the standard output.

**Constraints:** `1 < X, Y < 100000`

**Input Format:** Single line of input contains the price ranges X and Y.

**Output Format:** A single line of output is the total amount that he saved.

**Sample Input 1:**
```
10 100
```
**Sample Output 1:**
```
495
```
**Explanation 1:** Given the price range X and Y is 10 and 100. After checking all the golden prices
of items between 10 and 100 we get 11,22,33,44,55,66,77,88,99. So, after adding
11 + 22 + 33 …+ 99 = 495.

**Sample Input 2:**
```
10 1000
```
**Sample Output 2:**
```
63270
```
**Explanation 2:** After checking all the golden prices of items between 10 and 1000 we get
11,22,33,44,55,66,77,88,99,101,110,112,…,880,891,909,918,927,936,945,954,963,972,981,990.
So, after adding all we get 63270.

**Provided harness (C++, verbatim):**
```cpp
#include <iostream>
using namespace std;

int totalAmount(int x, int y)   // x and y are given input numbers
{
    int count=-1;

    // WRITE YOUR CODE HERE

    return count;
}

int main()
{
    int X,Y;
    cin>>X>>Y;
    cout<<totalAmount(X,Y);
    return 0;
}
```

> **Reading the definition carefully.** "difference between the sum of all the digits and the highest
> digit is equal to the highest digit" means `digitSum(G) - maxDigit(G) == maxDigit(G)`, i.e.
> **`digitSum(G) == 2 * maxDigit(G)`**. Check against the samples: 11 → sum 2, max 1, 2 == 2·1 ✓.
> 352 → sum 10, max 5, 10 == 2·5 ✓. 32812 → sum 16, max 8, 16 == 2·8 ✓. Solution in the solutions file.

---

## Q2 — Marathon Checkpoints (sum of checkpoints with two downstream checkpoints)

*(Labelled QUESTION 3 in the OA sidebar.)*

**Statement.**
A marathon is being organised in the hilly terrains of Ladakh. Since the region is sparsely
populated, care must be taken to ensure that no runner gets lost along the route. There are multiple
checkpoints along the route, and each checkpoint must connect to only one downstream checkpoint.
However, since there were multiple teams working on setting up the connections, there have been some
mistakes, and there are some checkpoints which are connecting to more than one downstream
checkpoints.

The checkpoint details are given, with each checkpoint represented by a random integer. Write a
program to identify the checkpoints which are connecting to more than one downstream checkpoints,
and print their sum as the output.

The route details are given as a list of relations between the Starting point and the checkpoints.
The relations are indicated as L, R, LL, LR… and so on, where the checkpoint is to the left (L), or
left-left (LL) or right-left (RL) to the Starting point.

Read the input from STDIN and print the output to STDOUT. Do not print arbitrary strings anywhere in
the program, as these contribute to the output and test cases will fail.

**Constraint:** `3 <= Number of checkpoints <= 100`

**Input Format:**
- The first line of input contains an integer, N, the number of checkpoints in the route, including
  the Starting point.
- The second line of input contains an integer, which is the Starting point of the route.
- The next N−1 lines of input contain a string, S and an integer, X separated by a single white
  space, where X is a checkpoint along the route and S is the relation between the Starting point
  and X.

**Output Format:** The output contains an integer which is the sum of all checkpoints connecting to
more than one downstream checkpoint.

**Sample Input 1:**
```
6
70
L 50
LR 65
LRL 60
LRR 68
LRRL 69
```
**Sample Output 1:**
```
65
```
**Explanation 1:** The marathon route can be represented as below. Starting point is 70.

```
        70
       /
     50
       \
        65
       /  \
     60    68
          /
        69
```
We can see that checkpoint 65 is connecting to two downstream checkpoints, 60 and 68, instead of
one. Since this is the only checkpoint which does so, output is printed as 65.

**Sample Input 2:**
```
8
24
R 35
RL 30
RLL 28
RLR 34
RLLL 25
RLLR 29
RLRL 33
```
**Sample Output 2:**
```
58
```
**Explanation 2:** The marathon route can be represented as below. Starting point is 24.

```
     24
       \
        35
       /
     30
    /   \
  28     34
 /  \   /
25   29 33
```
We can see that two checkpoints, 30 and 28, are connecting to two downstream checkpoints. Sum of
checkpoints is 30+28 = 58. Hence output is 58.

**Provided harness (C++, verbatim):**
```cpp
#include <bits/stdc++.h>
using namespace std;

int sumCheckPoints(int N, int S, string pos[], int val[])
// N is the number of checkpoints in the route, including the Starting point.
// S is the Starting point of the route.
// pos contains the relation between the Starting point and val.
// val contains the checkpoint at corresponding pos index.
{
    int sum=-1;

    // WRITE YOUR CODE HERE

    return sum;
}

int main()
{
    int N;
    cin>>N;
    int S;
    cin>>S;
    string str[N-1];
    int val[N-1];
    for(int i=0;i<N-1;i++)
    {
        cin>>str[i];
        cin>>val[i];
    }
    cout<<sumCheckPoints(N,S,str,val);
    return 0;
}
```
**[recon — line 1 `#include <bits/stdc++.h>` is glare-obscured in every frame; only the tail
`…s/stdc++.h>` is legible. `using namespace std;` on line 2 is clear.]**

> This is "build a binary tree from root-relative L/R path strings, then count nodes with two
> children" — the path string is literally the sequence of left/right turns from the root. Note the
> harness uses **VLAs** (`string str[N-1]`), a GCC extension, not standard C++. Solution in the
> solutions file.
