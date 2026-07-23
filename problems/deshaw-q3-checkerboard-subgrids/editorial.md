# Checkerboard Subgrids — editorial

The number of valid subgrids could exceed the limit of a 32-bit integer, so **`long long` is required** for the answer.

A rectangle is a checkerboard if and only if every row-adjacent pair differs and every column-adjacent pair differs. We can transform the grid such that checking for a "checkerboard" becomes checking for a "constant value".
Specifically, we can create a new matrix `B` where `B[i][j] = (grid[i][j] - '0') XOR ((i + j) & 1)`. A subgrid in the original grid is a perfect checkerboard if and only if the corresponding subgrid in `B` consists of identical values.

With this transformation, the problem reduces to: given a matrix of values, count the number of submatrices that have all equal elements.

This reduced problem can be solved in O(n × m) time using dynamic programming and a monotonic stack. We can maintain the height of consecutive equal elements extending upwards from each cell. Then, for each row, we sweep from left to right using a monotonic stack to efficiently calculate the number of valid submatrices ending at the current cell.
