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
