### Method

The operation allows us to complement a contiguous substring of `s` at most once.

A flip of a block `[i, j]` is equivalent to taking the XOR of the string with a mask that has `1`s exactly in the range `[i, j]`.
Distinct blocks give distinct masks. Distinct masks applied via XOR to a string give distinct result strings. Also, no non-empty mask can leave the original string `s` unchanged.

Therefore, the number of distinct strings that can be formed is `1` (for no flip, which leaves `s` unchanged) plus the number of all possible contiguous substrings.
For a string of length $n$, the number of contiguous substrings is $\frac{n(n+1)}{2}$.

The answer is simply $1 + \frac{n(n+1)}{2}$, which is completely independent of the contents of the binary string `s`.

Be careful with data types: for $n = 10^6$, $\frac{n(n+1)}{2} \approx 5 \times 10^{11}$, which exceeds the range of a 32-bit integer. A 64-bit integer (`long long`) must be used for $n$ before the multiplication.
