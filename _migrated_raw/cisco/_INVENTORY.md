# CISCO SDE Intern OA — image inventory & transcription map

Source: `notes/CISCO OA questions/` — 87 phone photos (1600×1200) of the OA screen, jumbled order.
Index→filename in `<scratch>/cisco_index.txt`; contact sheets `<scratch>/cisco_sheet_01..10.png`.
This file maps every image to its question so transcription can piece the scattered parts together.

Legend: image numbers below are the **#NN** sorted index (1..87), same as on the contact sheets.

## CODING QUESTIONS (write code into a provided harness) — the priority
### Q1 — "Drone Delivery with Battery Swap Stations" (title also seen as "Stations")
Shortest path on a grid with **battery** + **swap-voucher** state. Min moves depot(sr,sc)→customer(er,ec);
each step into an open cell costs 1 battery; battery starts at B (full); a kiosk cell may OPTIONALLY
consume one of K global swap-vouchers to refill battery to full; walls = 1, open = 0; return -1 if infeasible.
- **C++ harness** (cin, `vector`, `struct InputData`): #01, #02, #03, #06, (parts) #10–#13.
- **Problem statement / input format**: #11, #13, #14 (C++ desc), #59, #60 (C desc "Drone Delivery with Battery Swap Stations").
- **C harness** (scanf/printf/malloc/free): #53, #54, #56, #57, #58, #60, #61.
- **Examples**: Ex1 "Long Corridor with Two Kiosks", Ex2 "Two-Dimensional Maze", Ex3 "Wall-Forced Unreachability"
  → #05, #07, #08, #09, #12, #55, #58.
- Model logic: 0-1 BFS / Dijkstra over state (r,c,batteryLeft,vouchersLeft). [TO SOLVE]

### Q2 — "Online Auction Sniper Detector"
For each bid i (bids given in increasing timestamp order): flag=1 if that bid's **user** has ≥ K bids in
the closed window [t_i − W, t_i]; else 0. Also smallest_sniper = smallest user-id currently "sniping"
(≥K bids in window ending at t_i), or −1. Sliding window + per-user counts + a set of currently-sniping ids.
- **C++ harness** (`struct InputData{int N; ll W; int K; vector<pair<ll,ll>> bids;}`, scanf): #15,#16,#17,#18,#19,#22,#26.
- **C harness** (malloc flags[]/smallest[], `void solve(const InputData*,int*flags,ll*smallest)`): #62,#63,#64,#65.
- **Problem statement / input format**: #66, #67 ("Online Auction Sniper Detector").
- **Examples**: Ex1 "Threshold Never Reached", Ex2 "Two Snipers, Tie-Break" → #62, #63, #64.
- **Constraints**: 1≤N≤200000; 1≤W≤1e9; 2≤K≤N; timestamps strictly increasing 1≤t≤1e9; 1≤user≤1e9.
- Model logic: two-pointer window on sorted-by-time bids; `unordered_map<ll,int> count`; maintain set of ids with count≥K. [TO SOLVE]

## CONCEPTUAL "READ & FIX / REASON" SETS (written answers; each set has 4 variants sharing one context)
- **Set A — hasPathSum root-to-leaf accepts a non-leaf path** (variants 1–4): #21,#23,#24,#25,#27,#28,#29,#32.
  Bug: returns true when `node.value == target` at a NON-leaf node; must also require node is a leaf.
- **Set B — merge of two sorted lists silently loses elements** (variants 1–4): #35,#36,#37,#38,#39,#40,#41,#42,#45.
  Bug: after the main loop only `A` is drained (`while i<len(A)`), the leftover tail of `B` is never appended.
- **Set C — Designing a Time-Versioned Key-Value Store** (variants 1–4): #30,#31,#33,#34.
  Design set(key,val,ts)/get(key,ts) = predecessor search on per-key sorted timestamps (map→vector, binary search).
- **Set D — Two-Stack Amortized Queue vs Fixed-Capacity Ring Buffer (bounded task queue)** (1–4): #43,#44,#46,#47,#49,#50.
  Amortized O(1) two-stack (worst-case single op O(n)) vs O(1) worst-case ring buffer; latency-sensitive → ring buffer.
- **Set E — Polling vs Interrupt-Driven I/O Under Two Event Rates** (1–4): #48,#51,#52,#55.
  High rate (100 Gbps NIC) → polling; low rate (door sensor) → interrupts; interrupt overhead ~2µs/event.

## MCQs
- **OS**: #20 Safe Sequence (Banker's), #74 Preemptive SJF (avg turnaround), #77 Safe Sequence II (Banker's),
  #81 Fixed-Size Partitioning (multi-select), #84 Preemptive Priority Scheduling (avg turnaround).
- **Networking**: #71 DDoS mitigation, #72 router serial interface has no IP (config IP), #73 firewall ACL wrong
  interface direction, #75 TCP congestion phase (Slow Start), #76 purpose of DNS.
- **Electronics/Signals**: #69 flip-flops inferred from Verilog `always @(posedge clk)`, #70 PCM step-size↓ → quantisation-noise-power factor.
- **DSA/CS**: #78 Uniform Hashing (two hash-function statements), #82 recursion in C output `foo(6)` for `foo(x)=foo(x-2)+x`.
- **Aptitude/Logical**: #68 count of 1-bits in binary of `3·4096+15·256+5·16+3`, #79 coordinate-geometry two agents meeting,
  #80 "Sprint Table" 8-person circular seating arrangement, #83 "Dual Color Encounter" cube-painting count,
  #85 "Decadic Logarithms", #86 "Functional Maze" Cauchy-like functional equation, #87 "Cuboid Cascade" cube-painting count.

## Output files (this folder)
- `coding.md` — Q1 + Q2: full statement, BOTH harnesses verbatim, examples, constraints, model solutions.
- `conceptual_dsa.md` — Sets A, B, C (tree/merge/KV-store) with model answers.
- `conceptual_systems.md` — Sets D, E (queue-vs-ringbuffer, polling-vs-interrupt) with model answers.
- `mcq_os.md`, `mcq_networking.md`, `mcq_electronics.md`, `mcq_aptitude.md`, `mcq_dsa.md` — MCQs + worked answers.

## Progress
- survey COMPLETE (all 87 mapped).
- **coding.md DONE + VERIFIED** — Q1 (drone) model solution compiles & passes Ex1/2/3 (7, 11, -1);
  Q2 (sniper) model solution compiles & passes sample + Ex1 + Ex2 exactly. Both harnesses (C++ & C)
  transcribed; statements, input/output formats, constraints, all examples captured via zoom-enhanced reads.
- **conceptual_dsa.md DONE** (Sets A hasPathSum, B merge, C KV-store — pseudocode + 4 variants + model
  answers; the two C++ fixes compile). **conceptual_systems.md DONE** (Sets D queue-vs-ringbuffer,
  E polling-vs-interrupt — full prose answers).
- **All MCQ files DONE**: mcq_os / mcq_networking / mcq_electronics / mcq_dsa / mcq_aptitude — every MCQ
  transcribed + answered with working. Glare-obscured table cells (SJF/Priority/Banker's) and the
  figure/constraint-heavy aptitude puzzles are reconstructed to coherent values, marked `[recon]` inline
  (per user: "invent plausible numbers, can't reshoot").
- **TRANSCRIPTION PHASE COMPLETE.** Next: (1) agy fan-out research on OA scaffolding/I-O patterns across
  companies, then (2) author the PDF section per `_SECTION_PLAN.md` (structured, beginner-friendly C++,
  EXHAUSTIVE per-syntax explanations, loads of real OA examples).
