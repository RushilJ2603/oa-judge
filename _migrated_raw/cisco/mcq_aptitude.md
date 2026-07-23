# CISCO OA — MCQs: Aptitude / Logical / Quantitative

Single-select. Fully solved where legible; figure/constraint-heavy puzzles give the **method** + a
best-effort answer with reconstructed values marked `[recon]`.

---

## APT-1 — Count of 1-bits in a binary number
Number of `1`s in the binary representation of `3·4096 + 15·256 + 5·16 + 3`.
Options: `8` · `10` · `12` · …

**Answer: 10.** Read the multipliers as nibble (4-bit) positions — `4096 = 2^12`, `256 = 2^8`, `16 = 2^4`,
`1 = 2^0` — and each coefficient (`3, 15, 5, 3`) is `< 16`, so they occupy **separate nibbles** with no
carry:
```
value = 0011 1111 0101 0011   (= 0x3F53 = 16211)
          3    15   5    3
set bits: 2  +  4  + 2 +  2  = 10
```
**Trick:** recognising the "coefficient × power-of-two-per-nibble" structure turns arithmetic into a
`popcount` you can read off directly.

---

## APT-2 — Functional equation ("Functional Maze")
`f : R → R` with `f(x + y) = f(x) + f(y) − 2` for all real `x, y`, and `f(1) = 3` `[recon]`. Find `f(5)`.
Options: `5` · `6` · **`7`** · None of the above

**Answer: 7.** Substitute `g(x) = f(x) − 2`. Then
`g(x+y) + 2 = (g(x)+2) + (g(y)+2) − 2 ⇒ g(x+y) = g(x) + g(y)` — Cauchy's additive equation, so `g(x) = cx`
and `f(x) = cx + 2`. From `f(1) = 3`: `c + 2 = 3 ⇒ c = 1`, hence `f(x) = x + 2` and `f(5) = 7`.
**Method:** shift the constant out to reduce a "+constant" functional equation to the pure additive form.

---

## APT-3 — Painted cube: red AND blue small cubes ("Dual Color Encounter")
A cube of side `18 cm` is painted **red on two opposite faces** and **blue on the other four faces**, then
cut into `729 = 9^3` unit cubes (side `2 cm`). How many small cubes have **at least one red AND at least
one blue** face?
Options: **`64`** · 68 · 72 · 76

**Answer: 64.** Put the red faces on top and bottom. A small cube shows red only if it is in the **top or
bottom layer**; it shows blue only if it lies on one of the **four side faces**. "Red and blue" = a
top/bottom-layer cube that is *also* on the border (side faces). The top face is `9×9`; its border ring is
`9^2 − 7^2 = 81 − 49 = 32` cubes. Same `32` on the bottom. Top and bottom are disjoint ⇒ `32 + 32 = 64`.
**Method:** decompose "condition A and B" into layer membership × border membership and count the border ring.

---

## APT-4 — Nested painted-cuboid cutting ("Cuboid Cascade")  `[recon — 3D, verify]`
A cube has **three mutually-adjacent faces painted blue**. It is cut once vertically and once horizontally
(each fully across) into **4** equal cuboids; each is painted **pink** on all previously-unpainted faces;
each is then cut once more horizontally and vertically → **16** final cuboids. How many final cuboids have
**exactly two pink faces**?
Options: 4 · 6 · **8** `[recon]` · None of the above

**Method (how to attack it):** fix a coordinate frame; track, for each of the 16 final cells, which of its 6
faces were painted blue (original), pink (exposed after the first cut), or bare (interior faces exposed only
by the *second* cut, never repainted). "Exactly two pink" = a cell exposed on exactly two faces during the
*pink* painting step and not later buried. Enumerate the `2×2×...` positions by their (corner/edge/interior)
role at each cut. The count works out to **8** for the symmetric reading of the cuts. *(This is a
visualise-and-count problem; reconstruct the exact cut planes from the figure to confirm the option.)*

---

## APT-5 — Decadic logarithms  `[recon — expression partly illegible]`
Evaluate a base-10 logarithmic expression of the form `log(x^a) + log(x^b) − log(x^c) …` (all logs base 10).
Options: `1` · `10` · `100` · `1000`

**Method:** use the three log laws — `log(x^k) = k·log x`, `log a + log b = log(ab)`,
`log a − log b = log(a/b)`. Collapse the whole expression to `k · log x` (a single coefficient times
`log x`); if the problem fixes `x = 10`, `log₁₀ 10 = 1`, so the value is just the collapsed coefficient `k`,
which the options round to a power of ten (e.g. `1000` if `k = 3` and the terms carry a `10^3`). Pin down the
exact coefficients from the original to select among `1 / 10 / 100 / 1000`.

---

## APT-6 — Two agents meeting on a square track ("Coordinate Sync in a Bounded Grid")  `[recon — needs figure]`
Square `ABCD`, side `90 m`, diagonal `AC` aligned N–S. Rohan starts at `B` (clockwise), Rahul at `C`
(anticlockwise), simultaneously; speeds Rohan `8 km/h`, Rahul `10 km/h`. Where do they meet the **second**
time? (Options are locations like "on `AD`, 30 m from `A`", "on `BC`, 10 m from `B`", …)

**Method (relative speed on a closed loop):** perimeter `P = 4·90 = 360 m`. Moving toward each other, their
**combined** speed is `8 + 10 = 18 km/h = 5 m/s`. They start `90 m` apart (adjacent corners `B, C`).
- **1st meeting:** close the initial `90 m` gap ⇒ combined distance `90 m`.
- **n-th meeting:** combined distance `= 90 + (n−1)·360`. For the **2nd**: `90 + 360 = 450 m`, taking
  `450 / 5 = 90 s`.
- In `90 s`: Rohan travels `8 km/h × 90 s = 200 m`; Rahul `10 km/h × 90 s = 250 m` (check: `200+250=450`).
Walk `200 m` from `B` along Rohan's clockwise path (`= 2` full sides `+ 20 m` into the third side) to read off
the exact side and offset — the specific option depends on the figure's clockwise orientation, so match it
against the labelled square. **Key idea:** the k-th meeting of two bodies moving toward each other on a loop
happens after they jointly cover *initial-gap + (k−1)·perimeter*.

---

## APT-7 — Circular seating with two attributes ("Sprint Table")  `[recon — 10 constraints, partly illegible]`
Eight developers (Alex, Becky, Carl, Diana, Ethan, Farah, Greg, Hina) sit around a circular table, each on
**Frontend** or **Backend** (4 each) and each with a unique sticker colour (Red, Blue, Green, Yellow, Black,
White, Orange, Purple). ~10 clues constrain adjacency, team, and colour; the question asks who sits
**immediately right of Greg** and their sticker colour.

**Method:** this is a constraint-satisfaction (grid-elimination) puzzle — not all 10 clues were legible in
the photo, so the unique seat isn't reconstructable here. Approach: (1) draw 8 seats; (2) place the most
constrained person first (the one named in the most clues); (3) apply "immediately left/right", "opposite",
"between", and team/colour clues to prune; (4) propagate until one arrangement survives; (5) read off Greg's
right neighbour and colour. **Takeaway for OAs:** these long logic-grid puzzles are pure elimination — start
from the tightest clue, never from clue #1, and track team + colour as two parallel attribute grids.
