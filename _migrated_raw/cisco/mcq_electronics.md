# CISCO OA — MCQs: Electronics / Digital / Signals

Cisco (a hardware-heavy company) mixes core-ECE MCQs into the SDE OA. Single-select. Answers with working.

---

## EL-1 — Flip-flops inferred from Verilog
How many flip-flops are inferred for the following code?
```verilog
output reg q;
input  d;
always @(posedge clk) begin
    while ()          // note: empty/non-terminating loop condition
        q <= d;
end
```
Options: `1` · `2` · `3` · **Hardware inference not possible**

**Answer:** **Hardware inference not possible.** A synthesizable clocked block infers flip-flops from
sequential `<=` assignments, but a `while` loop with a **non-static / empty condition** cannot be unrolled
into fixed hardware, so synthesis fails — no flip-flop count can be inferred.
*(Contrast: `always @(posedge clk) q <= d;` alone infers exactly **1** D flip-flop. The `while` is the trap.)*

---

## EL-2 — PCM quantisation-noise power vs step size
In a **PCM** system the step size is `2 V`. If the step size is reduced to `0.25 V`, by what factor does the
**quantisation noise power** decrease?
Options: `4` · `16` · `32` · **64**

**Answer:** **64.** Quantisation **noise power** = Δ²/12, where Δ is the step size — it scales with the
**square** of the step size.
$$\frac{N_{old}}{N_{new}} = \left(\frac{\Delta_{old}}{\Delta_{new}}\right)^2 = \left(\frac{2}{0.25}\right)^2 = 8^2 = 64.$$
Halving the step size quarters the noise power; here the step shrinks 8×, so noise power drops 64×.
*(Equivalently, SQNR improves; each extra PCM bit halves Δ and cuts noise power by 4× ≈ 6 dB.)*
