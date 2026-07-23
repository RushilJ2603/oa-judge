### Method

Every bundle consists of one target value and one non-target value.
If you pick the target value, the value you discarded is necessarily a non-target.
Thus, a valid bundling corresponds to a perfect matching between the target set $T$ and the non-target set $C = \{1 \dots 2n\} \setminus T$.

For any matched pair $(t, c)$ where $t \in T$ and $c \in C$:
- You took the **MIN** of that bundle iff $c > t$.
- You took the **MAX** of that bundle iff $c < t$.

The question asks for the possible counts of $x$, the number of bundles where the minimum was picked. This is exactly the number of matched pairs with $c > t$.

The possible values of $x$ form a contiguous range $[xmin, xmax]$. 
- $xmax$ can be found greedily: sort $T$ and $C$, and for each $c$ ascending, pair it with the smallest unmet $t < c$.
- $below$, the maximum number of pairs with $c < t$, can be found greedily: for each $t$ ascending, pair it with the smallest unused $c < t$. Then $xmin = n - below$.

This two-pointer approach runs in $O(n \log n)$ time due to sorting, which easily passes the time limit.
