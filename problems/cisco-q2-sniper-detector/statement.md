# Online Auction Sniper Detector

*Statement-only for now — no runnable reference wired yet. The intended solution is a two-pointer
sliding window over bids sorted by time, with per-user counts and a set of currently-sniping user
ids.*

Bids arrive in strictly increasing timestamp order. A user is **sniping** at the moment of bid `i` if
that user has placed at least `K` bids within the closed time window `[t_i − W, t_i]`. For each bid,
output whether the bidding user is sniping, and the smallest user id currently sniping.

## Input

```
N W K
N lines: timestamp userId      (timestamps strictly increasing)
```

## Output

For each bid `i` in order, output two values: `flag` (1 if that bid's user is sniping at time `t_i`,
else 0) and `smallest_sniper` (the smallest user id with at least `K` bids in the window ending at
`t_i`, or `-1` if none).

## Constraints

```
1 <= N <= 200000
1 <= W <= 1e9
2 <= K <= N
1 <= timestamp, userId <= 1e9
```
