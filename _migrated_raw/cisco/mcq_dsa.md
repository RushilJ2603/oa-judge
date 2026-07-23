# CISCO OA — MCQs: DSA / CS fundamentals

Single-select. Answers with working.

---

## DSA-1 — Recursion output (C)
What is the output of the following C program?
```c
int foo(int x) {
    if (x <= 0)
        return 0;
    else
        return foo(x - 2) + x;
}
int main() {
    printf("%d", foo(6));
    return 0;
}
```
Options: `0` · `6` · `10` · **12**

**Answer:** **12.** Unwind the recursion (it steps down by 2 until `x ≤ 0`):
`foo(6) = 6 + foo(4) = 6 + 4 + foo(2) = 6 + 4 + 2 + foo(0) = 6 + 4 + 2 + 0 = 12.`
It sums the even numbers `6 + 4 + 2`. (The trap is stepping by 1, or forgetting the base case returns 0.)

---

## DSA-2 — Uniform hashing statements
A hash table of length **10** stores only positive integers. Which is true about:
- **Statement I:** `h(x) = x^3 mod 10` is a uniform hash function.
- **Statement II:** `h(x) = x mod 10` is a uniform hash function.

Options: Only I · Only II · Both · **None of the statements are correct**

**Answer:** **None** (the intended "trick" answer). Both functions depend **only on the last decimal digit**
of `x`: `x mod 10` is the last digit, and `x^3 mod 10` is a **permutation** of the last digit
(`0→0,1→1,2→8,3→7,4→4,5→5,6→6,7→3,8→2,9→9`) — so it partitions keys into the same 10 last-digit classes and
buckets keys with a common last digit together. A table size of **10 (composite)** with a division-method
hash on base-10 data does **not** spread keys uniformly (low-digit regularities cluster) — neither meets the
"each key equally likely in any slot, independent of others" bar for uniform hashing. *(This is why real hash
tables use a prime table size and/or multiplicative/mixing hashes.)*

**Takeaway:** `x mod m` is uniform **only** if `m` is well-chosen (prime, unrelated to input structure);
cubing first changes nothing because it is a bijection on residues.
