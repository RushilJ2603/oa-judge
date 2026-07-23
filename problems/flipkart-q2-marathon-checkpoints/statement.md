A marathon is being organised in the hilly terrains of Ladakh. Since the region is sparsely populated, care must be taken to ensure that no runner gets lost along the route. There are multiple checkpoints along the route, and each checkpoint must connect to only one downstream checkpoint. However, since there were multiple teams working on setting up the connections, there have been some mistakes, and there are some checkpoints which are connecting to more than one downstream checkpoints.

The checkpoint details are given, with each checkpoint represented by a random integer. Write a program to identify the checkpoints which are connecting to more than one downstream checkpoints, and print their sum as the output.

The route details are given as a list of relations between the Starting point and the checkpoints. The relations are indicated as L, R, LL, LR… and so on, where the checkpoint is to the left (L), or left-left (LL) or right-left (RL) to the Starting point.

Read the input from STDIN and print the output to STDOUT. Do not print arbitrary strings anywhere in the program, as these contribute to the output and test cases will fail.

**Constraint:** `3 <= Number of checkpoints <= 100`

**Input Format:**
- The first line of input contains an integer, N, the number of checkpoints in the route, including the Starting point.
- The second line of input contains an integer, which is the Starting point of the route.
- The next N−1 lines of input contain a string, S and an integer, X separated by a single white space, where X is a checkpoint along the route and S is the relation between the Starting point and X.

**Output Format:** The output contains an integer which is the sum of all checkpoints connecting to more than one downstream checkpoint.

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
We can see that checkpoint 65 is connecting to two downstream checkpoints, 60 and 68, instead of one. Since this is the only checkpoint which does so, output is printed as 65.

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
We can see that two checkpoints, 30 and 28, are connecting to two downstream checkpoints. Sum of checkpoints is 30+28 = 58. Hence output is 58.
