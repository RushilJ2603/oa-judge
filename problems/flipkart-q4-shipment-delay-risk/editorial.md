# Shipment Delay-Risk Analysis — editorial

This is a pure implementation and logic simulation problem. There are no algorithmic tricks required; the challenge lies in carefully digesting a heavy specification, correctly discarding invalid records, maintaining multi-level aggregations (per-shipment and per-route), and correctly applying the sorting criteria.

### Key Rules & Potential Traps

- **Valid vs Invalid Records:** You must filter events bounded strictly by `[dispatchDay, referenceDay]` for tracking/warehouse and `[1, referenceDay]` for weather. Negative processing hours and unknown statuses must also be filtered out.
- **Route Arithmetic (Rule vs Explanation Conflict):** In Sample 2's explanation, the `routeWeatherAlertScore` for R1 is stated as `3 + 2 = 5`. However, R1 has three valid alerts (W1 HIGH=3, W2 HIGH=3, W3 MEDIUM=2) which sum to 8. The literal rule ("add weights for *all* valid weather alerts") gives 8. Both 5 and 8 satisfy the condition `>= 4`, meaning the sample output remains correct, but the explanation's arithmetic is flawed. **Always implement the literal rule, not the hand-written arithmetic of the explanation.**
- **Route Average Delay:** This is calculated by taking the sum of delay events for all shipments on a route and performing an integer division (`//`) by the total number of shipments on that route (delivered or not, even with 0 tracking events).
- **Output formatting:** The final strings must be concatenated with a `#`, formatted strictly as `<shipmentName>-<riskLevel>-<riskScore>-<daysWithoutUpdate>`.
- **Filtering Outputs:** Any shipment that is delivered must never be output, regardless of its score.
- **Tie-breaker Rules:** Python's built-in `sort()` with a tuple of `(rank, -riskScore, -daysWithoutUpdate, original_input_index)` neatly solves the sorting requirements.
