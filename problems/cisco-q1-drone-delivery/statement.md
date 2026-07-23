# Drone Delivery with Battery Swap Stations

*Statement-only for now — no runnable reference wired yet. The intended solution is a 0-1 BFS /
Dijkstra over the state `(row, col, batteryLeft, vouchersLeft)`.*

An autonomous delivery drone must fly from a depot to a customer over a dense urban grid, but its
battery cannot last the full distance. The city has a sparse network of rooftop battery-swap kiosks:
passing over a kiosk lets the drone instantly refill to full charge — **but only if it spends one of
its scarce, global swap vouchers**. Plan when to swap and when to push through on remaining charge.

Find the **minimum number of moves** to fly from the depot `(sr, sc)` to the customer `(er, ec)`,
given battery capacity `B` (in moves, starting full), a set of `M` swap-kiosk cells, and a global
budget of `K` swap vouchers. Report `-1` if no feasible delivery exists. Moves are 4-directional into
open cells; each move costs 1 battery; a kiosk cell may optionally consume one voucher to refill to
`B`.

## Input

```
rows cols
grid (rows lines of cols chars: 0 = open, 1 = no-fly)
sr sc
er ec
B
M
M lines: station_r station_c
K
```

## Output

A single integer: the minimum number of moves to reach `(er, ec)`, or `-1` if infeasible.

## Constraints

```
1 <= rows, cols <= 50
1 <= B <= 50
0 <= K <= 10
0 <= M <= rows * cols
```
