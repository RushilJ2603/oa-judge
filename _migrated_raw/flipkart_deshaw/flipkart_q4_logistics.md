# Flipkart OA — Q4: Shipment Delay-Risk Analysis (the "big spec" problem)

Transcribed from the OA photos (HirePro). This is the long-form, rule-heavy question type: no
algorithmic trick at all, but a **specification you must implement exactly**. Every scoring rule,
validity rule and tie-break below is verbatim from the statement.

The provided stub is **Python 3** (the language selector showed Python; the other questions used
C++). A C++ port of the harness plus a full solution is in the solutions file.

---

## Statement

A logistics company wants to identify shipments that are at risk of delayed delivery.

The company stores shipment details, route profiles, tracking events, weather alerts, and warehouse
processing logs. Your task is to analyse these records and print shipments whose delay risk level is
HIGH or MEDIUM.

The delay risk must be calculated using tracking activity, delay events, route weather impact,
warehouse processing time, route-level comparison, and expected delivery time.

Read input from STDIN and print output to STDOUT. Do not print arbitrary strings anywhere in the
program, as these contribute to standard output and test cases will fail.

## Data Structures

**Shipments Table**

| Field | Description |
|---|---|
| shipmentId | Unique identifier of the shipment |
| shipmentName | Name or reference of the shipment |
| routeId | Route assigned to the shipment |
| dispatchDay | Day on which the shipment was dispatched |

Every routeId in the Shipments table has exactly one matching entry in the Route Profiles table.

**Route Profiles Table**

| Field | Description |
|---|---|
| routeId | Unique identifier of the route |
| standardTransitDays | Standard number of days required to complete the route |
| maxWarehouseProcessingHours | Maximum allowed total warehouse-processing hours for a shipment on that route |

**Tracking Events Table**

| Field | Description |
|---|---|
| eventId | Unique identifier of the tracking event |
| shipmentId | Shipment to which the event belongs |
| eventDay | Day on which the event was recorded |
| status | IN_TRANSIT, DELAYED, or DELIVERED |

**Weather Alerts Table**

| Field | Description |
|---|---|
| alertId | Unique identifier of the weather alert |
| routeId | Route affected by the alert |
| alertDay | Day on which the alert was recorded |
| severity | LOW, MEDIUM, or HIGH |

**Warehouse Processing Logs Table**

| Field | Description |
|---|---|
| processId | Unique identifier of the processing log |
| shipmentId | Shipment processed at the warehouse |
| processDay | Day on which processing was recorded |
| processingHours | Number of processing hours recorded |

## Valid Record Rules

A **tracking event** is valid only when all conditions are satisfied:
1. Its shipmentId exists in the Shipments table.
2. Its eventDay is between the shipment's dispatchDay and referenceDay, inclusive.
3. Its status is IN_TRANSIT, DELAYED, or DELIVERED.

A **weather alert** is valid only when all conditions are satisfied:
1. Its routeId exists in the Route Profiles table.
2. Its alertDay is between 1 and referenceDay, inclusive.
3. Its severity is LOW, MEDIUM, or HIGH.

A **warehouse processing log** is valid only when all conditions are satisfied:
1. Its shipmentId exists in the Shipments table.
2. Its processDay is between the shipment's dispatchDay and referenceDay, inclusive.
3. Its processingHours is greater than or equal to 0.

Invalid records must be ignored completely.

Every input record must be processed independently. If identical records appear more than once, each
occurrence must be counted separately.

## Features to Calculate

For every shipment, calculate the following values using only valid records.

1. **validTrackingEventCount** — Count the number of valid tracking events for the shipment.
2. **latestTrackingDay** — Find the latest eventDay among valid tracking events.
3. **daysWithoutUpdate** — `daysWithoutUpdate = referenceDay - latestTrackingDay`.
   If validTrackingEventCount is 0: `daysWithoutUpdate = referenceDay + 1`.
4. **delayEventCount** — Count valid tracking events whose status is DELAYED.
5. **isDelivered** — true if at least one valid tracking event has status DELIVERED; otherwise false.
6. **totalWarehouseProcessingHours** — Sum of processingHours from all valid warehouse-processing
   logs for the shipment.
7. **routeWeatherAlertScore** — For each route, add the following weights for all valid weather
   alerts recorded for that route:

   | Severity | Weight |
   |---|---|
   | LOW | 1 |
   | MEDIUM | 2 |
   | HIGH | 3 |

   The total is the routeWeatherAlertScore for every shipment on that route.
8. **routeAverageDelayEventCount** — For each route, calculate:
   `routeAverageDelayEventCount = total delayEventCount of all shipments on that route // number of
   shipments on that route` (integer division).
   All shipments on the route must be considered, including delivered shipments and shipments with
   no tracking events.
9. **aboveRouteDelayBaseline** — A shipment is above the route delay baseline when:
   `delayEventCount > routeAverageDelayEventCount`.
10. **expectedDeliveryDay** — `expectedDeliveryDay = dispatchDay + standardTransitDays`.

## Delay Risk Score

Calculate the delay risk score for every shipment.

| Condition | Score Added |
|---|---|
| If daysWithoutUpdate >= 5 | 4 |
| If validTrackingEventCount = 0 | 3 |
| If delayEventCount >= 2 | 3 |
| If routeWeatherAlertScore >= 4 | 2 |
| If totalWarehouseProcessingHours > maxWarehouseProcessingHours | 3 |
| If the shipment is above the route delay baseline | 2 |
| If referenceDay > expectedDeliveryDay and isDelivered is false | 4 |

The final score is:
`riskScore = staleUpdateScore + noTrackingScore + delayEventScore + weatherScore + warehouseScore +
routeBaselineScore + overdueScore`

## Delay Risk Level

| Risk Score | Risk Level |
|---|---|
| 10 or more | HIGH |
| 6 to 9 | MEDIUM |
| Less than 6 | LOW |

A delivered shipment must never be printed, even if its calculated risk score is HIGH or MEDIUM.

Only non-delivered shipments with HIGH or MEDIUM risk must be printed.

## Constraints

```
I.    2 <= numberOfShipments      <= 100000
II.   1 <= numberOfRouteProfiles  <= 100
III.  0 <= numberOfTrackingEvents <= 200000
IV.   0 <= numberOfWeatherAlerts  <= 200000
V.    0 <= numberOfWarehouseLogs  <= 200000
VI.   1 <= referenceDay           <= 1000000
VII.  1 <= dispatchDay <= referenceDay
VIII. -1000000 <= eventDay, alertDay, processDay <= 1000000
IX.   -1000000000 <= processingHours <= 1000000000
```
All IDs, names, route IDs, statuses, and severity values contain no spaces.

## Input Format

- The first line contains an integer referenceDay, representing the fixed analysis day.
- The second line contains the number of records in the Shipments table.
- The third line contains the number of records in the Route Profiles table.
- The fourth line contains the number of records in the Tracking Events table.
- The fifth line contains the number of records in the Weather Alerts table.
- The sixth line contains the number of records in the Warehouse Processing Logs table.
- The next records are provided in this order:
  1. Shipments table: `text shipmentId shipmentName routeId dispatchDay`
  2. Route Profiles table: `text routeId standardTransitDays maxWarehouseProcessingHours`
  3. Tracking Events table: `text eventId shipmentId eventDay status`
  4. Weather Alerts table: `text alertId routeId alertDay severity`
  5. Warehouse Processing Logs table: `text processId shipmentId processDay processingHours`

## Output Format

Print all eligible shipments in the following format:
```
<shipmentName>-<riskLevel>-<riskScore>-<daysWithoutUpdate>
```
If multiple shipments must be displayed, separate them with a hash symbol (`#`).

Sort the output in the following sequence:
1. HIGH risk shipments before MEDIUM risk shipments.
2. Higher riskScore first.
3. Higher daysWithoutUpdate first.
4. Original input sequence of the Shipments table when all previous values are equal.

Apply the next sorting condition only when the previous condition results in a tie.
Print `NA` if no shipment qualifies.

> **[recon]** The exact output field layout is not stated in prose anywhere in the photos — it is
> inferred from the two sample outputs, which are consistently
> `Name-LEVEL-riskScore-daysWithoutUpdate` (e.g. `Parcel_A-HIGH-18-20`, `Alpha-HIGH-16-51`). Both
> samples confirm the pattern, so the inference is safe.

## Sample Input 1
```
100
3
2
4
3
3
S1 Parcel_A R1 10
S2 Parcel_B R1 10
S3 Parcel_C R2 80
R1 20 10
R2 30 8
E1 S1 70 DELAYED
E2 S1 80 DELAYED
E3 S2 99 IN_TRANSIT
E4 S3 90 IN_TRANSIT
W1 R1 30 HIGH
W2 R1 50 MEDIUM
W3 R2 85 LOW
P1 S1 60 15
P2 S2 20 5
P3 S3 85 9
```
## Sample Output 1
```
Parcel_A-HIGH-18-20#Parcel_C-MEDIUM-7-10#Parcel_B-MEDIUM-6-1
```
## Explanation 1

For Parcel_A:
```
daysWithoutUpdate = 100 - 80 = 20
delayEventCount = 2
routeWeatherAlertScore for R1 = 3 + 2 = 5
totalWarehouseProcessingHours = 15
routeAverageDelayEventCount for R1 = (2 + 0) // 2 = 1
expectedDeliveryDay = 10 + 20 = 30
```
Parcel_A is above the route delay baseline and is overdue.
`riskScore = 4 + 0 + 3 + 2 + 3 + 2 + 4 = 18`

For Parcel_C:
```
daysWithoutUpdate = 100 - 90 = 10
totalWarehouseProcessingHours = 9
maxWarehouseProcessingHours for R2 = 8
riskScore = 4 + 3 = 7
```

For Parcel_B:
```
daysWithoutUpdate = 100 - 99 = 1
routeWeatherAlertScore for R1 = 5
expectedDeliveryDay = 30
riskScore = 2 + 4 = 6
```

Parcel_A is printed first because it has HIGH risk. Parcel_C is printed before Parcel_B because both
have MEDIUM risk but Parcel_C has a higher risk score.

## Sample Input 2
```
50
4
2
6
6
5
S1 Alpha R1 10
S2 Beta R1 10
S3 Gamma R2 20
S4 Delta R2 20
R1 20 5
R2 15 8
E1 S1 51 DELAYED
E2 S2 30 DELIVERED
E3 S3 25 UNKNOWN
E4 X9 30 DELAYED
E5 S4 40 DELAYED
E6 S4 41 DELAYED
W1 R1 5 HIGH
W2 R1 20 HIGH
W3 R1 30 MEDIUM
W4 R2 30 HIGH
W5 X9 30 HIGH
W6 R2 51 HIGH
P1 S1 20 6
P2 S2 51 10
P3 S3 30 -1
P4 S4 30 9
P5 X9 25 10
```
## Sample Output 2
```
Alpha-HIGH-16-51#Delta-HIGH-16-9#Gamma-HIGH-11-51
```
## Explanation 2

The tracking event for Alpha on day 51 is invalid because it is later than referenceDay 50.
The shipment Beta has a valid DELIVERED event and is never printed.
The tracking event of Gamma is invalid because UNKNOWN is not a valid status. Its warehouse log is
also invalid because its processingHours value is negative.

For Alpha:
```
validTrackingEventCount = 0
daysWithoutUpdate = 50 + 1 = 51
routeWeatherAlertScore for R1 = 3 + 2 = 5
totalWarehouseProcessingHours = 6
expectedDeliveryDay = 10 + 20 = 30
riskScore = 4 + 3 + 2 + 3 + 4 = 16
```

For Delta:
```
daysWithoutUpdate = 50 - 41 = 9
delayEventCount = 2
totalWarehouseProcessingHours = 9
routeAverageDelayEventCount for R2 = (0 + 2) // 2 = 1
expectedDeliveryDay = 20 + 15 = 35
riskScore = 4 + 3 + 3 + 2 + 4 = 16
```

Both Alpha and Delta have the same HIGH risk score. Alpha is printed first because Alpha has more
daysWithoutUpdate (51) than Delta (9).

> **[recon — resolved by implementation]** Alpha's `routeWeatherAlertScore for R1 = 3 + 2 = 5` as
> written in the explanation counts only two of R1's three valid alerts (W1 HIGH=3, W2 HIGH=3,
> W3 MEDIUM=2 give **8**). The photo is legible here — the statement's own arithmetic is simply
> inconsistent with its own data. A literal implementation of the *rule* (sum all valid alerts on
> the route) computes 8 and **reproduces both sample outputs exactly**, because the condition is
> `>= 4` and both readings clear it. So the rule text is trustworthy and the worked explanation
> contains an arithmetic slip. Implement the rule, not the explanation's number.
>
> This is worth internalising: OA statements contain errors, and the sample explanations are
> hand-written prose that is *not* generated from the reference solution. When explanation and rule
> disagree, the rule plus the sample **output** is the ground truth — the explanation's intermediate
> values are the least reliable thing in the document.

## Provided harness (Python 3, verbatim)

```python
import sys

def solve(reference_day, shipments, route_profiles, tracking_events, weather_alerts, warehouse_logs):
    """
    reference_day:
        Fixed analysis day.

    shipments:
        List of tuples:
            (shipment_id, shipment_name, route_id, dispatch_day, input_index)

    route_profiles:
        List of tuples:
            (route_id, standard_transit_days, max_warehouse_hours)

    tracking_events:
        List of tuples:
            (event_id, shipment_id, event_day, status)

    weather_alerts:
        List of tuples:
            (alert_id, route_id, alert_day, severity)

    warehouse_logs:
        List of tuples:
            (process_id, shipment_id, process_day, processing_hours)

    Return:
        Final output string in the required format.
        Return "NA" if no shipment qualifies.
    """

    final_output = "NONE"

    # WRITE YOUR CODE HERE

    return final_output

def main():
    input_data = sys.stdin.readline

    reference_day = int(input_data())

    shipment_count = int(input_data())
    route_count = int(input_data())
    tracking_count = int(input_data())
    weather_count = int(input_data())
    warehouse_count = int(input_data())

    shipments = []
    for input_index in range(shipment_count):
        shipment_id, shipment_name, route_id, dispatch_day = input_data().split()
        shipments.append((shipment_id, shipment_name, route_id, int(dispatch_day), input_index))

    route_profiles = []
    for _ in range(route_count):
        route_id, standard_transit_days, max_warehouse_hours = input_data().split()
        route_profiles.append((route_id, int(standard_transit_days), int(max_warehouse_hours)))

    tracking_events = []
    for _ in range(tracking_count):
        event_id, shipment_id, event_day, status = input_data().split()
        tracking_events.append((event_id, shipment_id, int(event_day), status))

    weather_alerts = []
    for _ in range(weather_count):
        alert_id, route_id, alert_day, severity = input_data().split()
        weather_alerts.append((alert_id, route_id, int(alert_day), severity))

    warehouse_logs = []
    for _ in range(warehouse_count):
        process_id, shipment_id, process_day, processing_hours = input_data().split()
        warehouse_logs.append((process_id, shipment_id, int(process_day), int(processing_hours)))

    result = solve(reference_day, shipments, route_profiles, tracking_events,
                   weather_alerts, warehouse_logs)

    print(result)

if __name__ == "__main__":
    main()
```
**[recon]** The right edge of the code pane is cut off in every frame, so the tail of the long
`… = input_data().split()` lines and the `int(...)` conversions inside each `append` were
reconstructed from the visible left portion plus the docstring's declared tuple shapes. The structure
is unambiguous (each loop reads one line, splits it, appends a tuple with the numeric fields cast);
the exact wrapping is not.

Note `final_output = "NONE"` in the stub versus the docstring's instruction to return `"NA"` — the
stub's placeholder is a decoy, the spec says NA.
