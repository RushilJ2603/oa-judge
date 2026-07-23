# Editorial

The final `b` is constructed by pushing characters alternatingly to the ends, depending on whether they have been reversed an odd or even number of times.

The pattern of the final `b` is: **all indices with the same parity as `n−1`, descending**, followed by **all indices of the other parity, ascending**.

Because this is a fixed permutation of positions depending only on `n`, a permutation is a **bijection**. Thus, the maximum achievable `b` is simply **all 1s followed by all 0s**.

The required `s` is found by applying the inverse permutation to this maximum `b`.
