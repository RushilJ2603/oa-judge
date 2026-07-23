# CISCO OA — Conceptual "reason about the design" sets (Systems / OS)

Two written-answer sets. Same format as the DSA conceptual sets: one shared scenario, four Question
variants. These probe **worst-case vs amortized cost**, **memory/overflow behavior**, and **OS I/O
mechanisms** — the systems-fluency Cisco leans on. Transcribed by hand.

---

## Set D — Two-Stack Amortized Queue vs Fixed-Capacity Ring Buffer (bounded task queue)

### Shared scenario (verbatim intent)
You need a **FIFO queue** for a bounded pool of at most **1000 tasks**. Two implementations are on the table:
- **A. Two-stack queue.** Keep an `inbox` stack and an `outbox` stack. `enqueue(x)` pushes onto `inbox`.
  `dequeue()` pops from `outbox`; if `outbox` is empty, first pour every element of `inbox` into `outbox`
  (which reverses them into FIFO order), then pop. Elements live in heap-allocated stack nodes and the
  queue grows as needed.
- **B. Ring buffer.** A fixed array of 1000 slots with `head` and `tail` indices. `enqueue(x)` writes at
  `tail` and advances `tail = (tail + 1) % 1000`. `dequeue()` reads at `head` and advances
  `head = (head + 1) % 1000`. The array is allocated once up front.

Constraints given: "Worst case" means a **single** operation, not the average. Do not change the
comparison. Assume the ring buffer **rejects** (does not overwrite) when full unless you state otherwise.
FIFO ordering is required.

### The four Question variants (verbatim intent)
- **Q1:** For each implementation, give the **worst-case** time cost of a single `enqueue` and a single
  `dequeue`, and in one sentence describe the mechanism behind that cost.
- **Q2:** Implementation A is described as "amortized O(1)." Explain what amortized O(1) means here: why any
  individual `dequeue` can be O(n), yet the average cost per operation is still O(1). Refer to how many
  times each element is moved.
- **Q3:** Compare the two on **memory and overflow** for the 1000-task bound. Address (a) up-front vs
  per-element allocation, and (b) what happens when a 1001st task arrives — how does each signal/handle it?
- **Q4:** The queue sits on a **latency-sensitive** path; every `dequeue` must finish within a tight,
  predictable deadline, and an occasional slow operation is worse than a slightly higher average. Which
  implementation do you choose and why? Name the specific **failure mode** of the other one.

### Model answers
**Worst-case costs (Q1).**
| Op | A: two-stack | B: ring buffer |
|---|---|---|
| `enqueue` | **O(1)** — push onto `inbox` | **O(1)** — write at `tail`, advance index |
| `dequeue` | **O(n)** worst case — if `outbox` is empty it must transfer all `n` elements from `inbox` first | **O(1)** always — read at `head`, advance index mod N |

**Amortized O(1) (Q2).** Over its lifetime each element is touched a constant number of times: pushed onto
`inbox` once, moved to `outbox` once, popped once — **3 moves total**. A single `dequeue` that triggers a
transfer pays for *all* those moves at once, so it is O(n) in isolation; but across any sequence of `m`
operations the total work is O(m) (each element's 3 moves are charged once), so the **average per operation
is O(1)**. "Amortized" describes the average over a sequence — it is explicitly **not** a worst-case bound.

**Memory & overflow (Q3).** (a) B allocates all 1000 slots **once**, a fixed, cache-friendly footprint with
no per-op allocation; A allocates a **heap node per element**, so it has allocator overhead and pointer
memory that grows and shrinks with the queue. (b) On a 1001st task: B detects "full" (`(tail+1)%N == head`,
or a size counter) and **rejects** the enqueue (returns an error); A, being dynamically grown, just
**allocates another node** — it does not enforce the 1000 bound unless you add an explicit size check.

**Latency-sensitive choice (Q4).** Choose **B, the ring buffer**. Its per-operation cost is O(1)
**worst-case** and therefore predictable — every `dequeue` finishes in constant time. A's failure mode is
the periodic **O(n) transfer spike**: a single `dequeue` that happens to hit an empty `outbox` pours the
whole `inbox` across, blowing the deadline. That tail-latency spike is exactly what a latency-sensitive
path cannot tolerate, even though A's *average* is fine.

---

## Set E — Polling vs Interrupt-Driven I/O Under Two Event Rates

### Shared scenario (verbatim intent)
An operating system must handle events from a device. Two classic mechanisms exist:
- **Polling:** the CPU repeatedly reads the device's status register in a loop to check whether it has work.
- **Interrupt-driven:** the device raises an interrupt when it has work; the CPU does other things (or
  sleeps) until then, and an interrupt handler runs on each event.

Each interrupt costs roughly a fixed **~2 µs** of overhead (save/restore context, dispatch the handler, and
the pipeline/cache disruption it causes). A poll costs only a few **nanoseconds** but does nothing useful
when the device is idle. Two regimes: **Case A — 100 Gbps NIC, ~10 M packets/s**; **Case B — door sensor,
~1 event/min**.

Constraints given: reasoning must reference **CPU waste and/or per-event overhead**, not vague "speed";
your answer must describe a **switching mechanism**, not just "use both."

### The four Question variants (verbatim intent)
- **Q1:** In one or two sentences each, state the core CPU-cost difference: when does each mechanism waste
  CPU and/or incur cost?
- **Q2:** High-rate case (100 Gbps NIC, ~10 M pkt/s): which mechanism, and why? Address what happens to
  interrupt overhead at this rate.
- **Q3:** Sparse case (door sensor, ~1 event/min): which mechanism, and why? Address what polling costs here.
- **Q4:** Describe an **adaptive hybrid** that behaves well across both regimes, and explain the mechanism
  that makes it switch.

### Model answers
**Core cost difference (Q1).** **Polling** wastes CPU when the device is **idle** — it burns cycles spinning
on a status register that has nothing new. **Interrupts** cost a fixed **~2 µs per event** (context
save/restore + handler dispatch + cache/pipeline disruption); that is negligible when events are rare but
becomes the dominant cost when events are frequent.

**High rate (Q2).** At ~10 M packets/s, one interrupt per packet would cost `10^7 × 2 µs = 20 s` of CPU per
**second** — impossible; the machine would spend all its time in interrupt entry/exit and make no forward
progress (**"interrupt livelock"**). Choose **polling**: once packets are arriving back-to-back, a tight
poll loop processes each with a few-ns status check and **zero per-packet interrupt overhead**.

**Sparse (Q3).** At ~1 event/min, choose **interrupts**. Polling a door sensor means the CPU spins (or is
pinned) essentially 100% of the time to catch one event every 60 seconds — an enormous waste of cycles and
power. An interrupt lets the CPU **sleep** and wake only when the door actually fires; ~2 µs once a minute
is nothing.

**Adaptive hybrid (Q4).** Take the **first interrupt** to notice that work has arrived, then **switch to
polling** while the device stays busy — draining the queue with cheap polls and amortizing away per-packet
interrupt cost — and **re-arm interrupts** once a poll finds the queue empty (the device went idle), so you
don't spin on an idle device. The **switch is driven by whether each poll still finds work**. This is
exactly Linux **NAPI** in NIC drivers: interrupt-on-first-packet → poll-while-busy → re-enable-interrupts-
when-drained.
