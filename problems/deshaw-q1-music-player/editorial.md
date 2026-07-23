# Music Player — editorial

A naive vector implementation takes O(n) time per move operation, which is too slow for q = 2·10⁵. A naive linked list allows O(1) moves but requires O(n) for positional queries, which is also too slow.

To achieve sub-linear time per operation, we need an advanced data structure like an order-statistic tree, a balanced binary search tree (like a Treap or Splay tree) augmented with subtree sizes, or a block decomposition approach.

In a block decomposition (or square root decomposition) approach, we can maintain the elements in chunks of size roughly √n. Moving an element involves removing it from its chunk and inserting it into another. Positional queries can skip whole blocks by summing their sizes, completing both operations in amortised O(√n) time.
