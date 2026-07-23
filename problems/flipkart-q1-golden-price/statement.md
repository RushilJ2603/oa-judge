# Golden Price

A megastore runs an offer: if a customer can identify a product whose price is a **golden price** `G`,
that product is free. A number `G` is a golden price when the difference between the **sum of all its
digits** and its **highest digit** equals its highest digit — equivalently, `digitSum(G) == 2 ×
maxDigit(G)`.

Examples of golden prices: `352` (digit sum `10`, highest digit `5`, and `10 − 5 = 5`); `3003`;
`32812` (digit sum `16`, highest digit `8`, and `16 − 8 = 8`).

Narendra buys one product priced anywhere in the range between `X` and `Y` inclusive. Compute the
total amount he would save by taking every golden price in that range — that is, the **sum of all
golden prices** between `X` and `Y` inclusive.

## Input

A single line with two integers `X` and `Y`.

## Output

A single integer: the sum of all golden prices in the inclusive range between `X` and `Y`.

## Constraints

```
1 < X, Y < 100000
```
The order of `X` and `Y` is not guaranteed.

## Example 1

Input:
```
10 100
```
Output:
```
495
```
The golden prices between 10 and 100 are 11, 22, 33, 44, 55, 66, 77, 88, 99, and they sum to 495.

## Example 2

Input:
```
10 1000
```
Output:
```
63270
```
