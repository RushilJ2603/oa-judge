import sys

VALID_STATUS = {"IN_TRANSIT", "DELAYED", "DELIVERED"}
SEVERITY_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def solve(reference_day, shipments, route_profiles, tracking_events, weather_alerts, warehouse_logs):
    # --- index the two lookup tables -------------------------------------------------
    route = {r[0]: (r[1], r[2]) for r in route_profiles}          # routeId -> (transit, maxHours)
    ship = {s[0]: s for s in shipments}                           # shipmentId -> full tuple

    # --- per-shipment accumulators ----------------------------------------------------
    event_count = {s[0]: 0 for s in shipments}
    latest_day = {}                                               # only set when an event is valid
    delay_count = {s[0]: 0 for s in shipments}
    delivered = {s[0]: False for s in shipments}
    warehouse_hours = {s[0]: 0 for s in shipments}

    # Rule 2 of each validity block is relative to that shipment's own dispatchDay.
    for _eid, sid, day, status in tracking_events:
        s = ship.get(sid)
        if s is None or status not in VALID_STATUS:
            continue
        if not (s[3] <= day <= reference_day):
            continue
        event_count[sid] += 1
        if sid not in latest_day or day > latest_day[sid]:
            latest_day[sid] = day
        if status == "DELAYED":
            delay_count[sid] += 1
        elif status == "DELIVERED":
            delivered[sid] = True

    for _pid, sid, day, hours in warehouse_logs:
        s = ship.get(sid)
        if s is None or hours < 0:
            continue
        if not (s[3] <= day <= reference_day):
            continue
        warehouse_hours[sid] += hours

    # --- per-route aggregates ---------------------------------------------------------
    weather_score = {rid: 0 for rid in route}
    for _aid, rid, day, severity in weather_alerts:
        if rid not in route or severity not in SEVERITY_WEIGHT:
            continue
        if not (1 <= day <= reference_day):
            continue
        weather_score[rid] += SEVERITY_WEIGHT[severity]

    route_delay_total = {rid: 0 for rid in route}
    route_ship_total = {rid: 0 for rid in route}
    for s in shipments:                       # every shipment counts, delivered or not
        route_delay_total[s[2]] += delay_count[s[0]]
        route_ship_total[s[2]] += 1
    route_avg_delay = {rid: (route_delay_total[rid] // route_ship_total[rid]
                             if route_ship_total[rid] else 0)
                       for rid in route}

    # --- score every shipment ---------------------------------------------------------
    rows = []
    for sid, name, rid, dispatch_day, input_index in shipments:
        transit, max_hours = route[rid]

        count = event_count[sid]
        days_without_update = (reference_day + 1) if count == 0 else reference_day - latest_day[sid]
        expected_delivery_day = dispatch_day + transit

        score = 0
        if days_without_update >= 5:                      score += 4
        if count == 0:                                    score += 3
        if delay_count[sid] >= 2:                         score += 3
        if weather_score[rid] >= 4:                       score += 2
        if warehouse_hours[sid] > max_hours:              score += 3
        if delay_count[sid] > route_avg_delay[rid]:       score += 2
        if reference_day > expected_delivery_day and not delivered[sid]:
            score += 4

        if delivered[sid]:                                # never printed, whatever the score
            continue
        if score >= 10:
            level, rank = "HIGH", 0
        elif score >= 6:
            level, rank = "MEDIUM", 1
        else:
            continue                                      # LOW is not printed

        rows.append((rank, -score, -days_without_update, input_index,
                     f"{name}-{level}-{score}-{days_without_update}"))

    rows.sort()
    return "#".join(r[4] for r in rows) if rows else "NA"


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
