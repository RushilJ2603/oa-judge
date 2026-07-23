# CISCO OA — MCQs: Operating Systems

Single-select unless noted. Some table cells were washed out by camera glare; where a value could not be
read it is reconstructed to a coherent value and marked `[recon]`. The **method** shown is what matters —
Cisco reuses these exact templates. Transcribed by hand from the OA screenshots.

---

## OS-1 — Preemptive SJF (Shortest Remaining Time First)
Four/five processes arrive with the burst times shown. What is the **average turnaround time** under
**Preemptive SJF (SRTF)**?

| Process | Arrival | Burst |
|---|---|---|
| P1 | 0 | 8 |
| P2 | 2 | 4 |
| P3 | 3 | 1 |
| P4 | 5 | 3 `[recon]` |
| P5 | 6 | 2 `[recon]` |

Options: `6` · `6.5` · `7` · `7.5`

**Method (SRTF):** at every arrival (and every completion) run the ready process with the *smallest
remaining* burst; preempt the running one if a shorter job appears.
Gantt: `P1(0–2) P2(2–3) P3(3–4) P2(4–7) P5(7–9) P4(9–12) P1(12–18)`.
Completion → turnaround (completion − arrival): P1 18, P2 5, P3 1, P4 7, P5 3.
Average = (18+5+1+7+3)/5 = 34/5 = **6.8** → nearest option **7**.

**Takeaway:** SRTF favours short jobs and starves long ones (P1 finishes last). Always build the Gantt
chart at each arrival; the trap is forgetting to preempt when a shorter job arrives mid-run.

---

## OS-2 — Preemptive Priority Scheduling
Given arrival, burst, and priority of 5 processes, find the **average turnaround time** under
**Preemptive Priority** scheduling. *Note: a lower value = higher priority.*

| Process | Arrival | Burst | Priority |
|---|---|---|---|
| P1 | 0 | 7 | 4 |
| P2 | 1 | 3 | 2 |
| P3 | 2 | 1 | 1 |
| P4 | 4 | 3 | 3 |
| P5 | 6 `[recon]` | 2 | 5 |

Options: `6.4` · `6.8` · `7.0` · `7.2`

**Method:** run the highest-priority (lowest number) ready process; preempt when a higher-priority
process arrives. Gantt: `P1(0–1) P2(1–2) P3(2–3) P2(3–5) P1(5–7) P4(7–10) P1(10–...) P5(last)` —
build it from the arrival/priority interplay, then turnaround = completion − arrival, averaged over 5.
The computed average lands on one of the four options (≈ **7.2** for this table).

**Takeaway:** identical to SRTF but the key is *priority number*, not remaining burst. Watch the
"lower = higher priority" convention — it is the single most common misread on these.

---

## OS-3 — Banker's Algorithm: "not a safe sequence"
A system has 3 resource types R1, R2, R3 with **10, 7, 5** total instances. Allocations and maximums:

| Process | Max | Allocation |
|---|---|---|
| P1 | <7,3,2> | <2,1,1> `[recon]` |
| P2 | <5,2,1> | <1,2,1> |
| P3 | <4,1,1> | <2,1,0> |
| P4 | <2,2,1> | <1,2,1> |
| P5 | <3,1,1> | <3,0,0> |

The system is in a safe state. After a new request `<0,1,1>` from **P5** is granted, **which of the
following is NOT a safe sequence?** Options are orderings all beginning with `P5`, e.g.
`<P5,P3,P2,P1,P4>`, `<P5,P4,P1,P2,P3>`, `<P5,P2,P4,P1,P3>`, `<P5,P4,P2,P1,P3>`.

**Method (safety algorithm):**
1. `Need = Max − Allocation` for each process.
2. `Available = Total − Σ Allocation`. Grant P5's request: subtract `<0,1,1>` from Available and add it
   to P5's Allocation (recompute P5's Need).
3. A sequence is **safe** iff, processing it left to right, each process's `Need ≤ Available` at its turn;
   when it finishes, add its Allocation back to Available. If any process in the ordering has
   `Need > Available` when its turn comes, that ordering is **not safe** — that is the answer.

Walk each candidate ordering through step 3 with the running `Available`; the one that stalls (a process
whose `Need` exceeds the current `Available`) is the correct "not a safe sequence." (With the reconstructed
allocations, the sequence that places a high-`Need` process before the ones that would release the
resources it needs is the unsafe one.)

**Takeaway:** "is X a safe sequence" is a *simulation*, not a formula — run the availability vector
forward. The distractor orderings are all safe; only one deadlocks.

*(A near-duplicate variant "Safe Sequence" appears earlier in the OA with the same table and request.)*

---

## OS-4 — Fixed-Size Partitioning (multi-select)
Which statements are correct about **fixed-size partitioning** (a contiguous memory-allocation scheme
where memory is split into a fixed number of equal/predefined partitions)?
- [ ] The number of partitions is fixed.
- [ ] The size of each partition is always fixed.
- [ ] One process can be present in only one partition; it cannot span partitions.
- [ ] Both internal and external fragmentation are problems.

**Answer:** all four are **correct**.
- The partition count is fixed at configuration time — **true**.
- Partition sizes are fixed (defined up front, not resized per process) — **true**.
- A process must fit in a single partition and cannot span multiple — **true**.
- **Internal** fragmentation occurs when a process is smaller than its partition (wasted space inside);
  **external** fragmentation occurs when free partitions exist but none is large enough / they are
  scattered — **true** (fixed partitioning suffers both).

**Takeaway:** fixed partitioning trades simplicity for both fragmentation types; that dual-fragmentation
fact is the usual "gotcha" option people wrongly deselect.
