# Max Flips — editorial

A naive approach testing all 2ⁿ sign assignments is too slow.

This problem can be efficiently solved using a greedy algorithm with "regret", often implemented with a priority queue (max-heap).
We can iterate through the elements from left to right, optimistically flipping each element to negative and maintaining a running prefix sum. 

When a prefix sum drops to zero or below (becomes non-positive), our optimistic choices have failed. To fix this, we should undo the flip of the largest element we've flipped so far, as that will recover the maximum possible sum for our prefix with only one retraction. We can use a max-heap to keep track of the flipped elements and retrieve the maximum efficiently.

Since `a_i` can be up to 10⁹ and `n` up to 2·10⁵, the prefix sum can reach 2·10¹⁴, which exceeds the limit of a 32-bit integer. **`long long` is mandatory** for the running sum to prevent overflow.
