import random
import sys

def generate(seed, size_hint):
    random.seed(seed)
    
    is_small = (size_hint != "LARGE")
    num_shipments = random.randint(2, 5) if is_small else random.randint(10, 50)
    num_routes = random.randint(1, 3) if is_small else random.randint(3, 10)
    num_tracking = random.randint(0, 10) if is_small else random.randint(20, 100)
    num_weather = random.randint(0, 5) if is_small else random.randint(10, 50)
    num_warehouse = random.randint(0, 5) if is_small else random.randint(10, 50)
    
    reference_day = random.randint(50, 100)
    
    routes = []
    for i in range(num_routes):
        routes.append(f"R{i+1}")
        
    shipments = []
    for i in range(num_shipments):
        shipments.append(f"S{i+1}")
        
    print(reference_day)
    print(num_shipments)
    print(num_routes)
    print(num_tracking)
    print(num_weather)
    print(num_warehouse)
    
    # Shipments: shipmentId shipmentName routeId dispatchDay
    dispatch_days = {}
    for i in range(num_shipments):
        s_id = shipments[i]
        s_name = f"Parcel_{i+1}"
        r_id = random.choice(routes)
        d_day = random.randint(1, reference_day)
        dispatch_days[s_id] = d_day
        print(f"{s_id} {s_name} {r_id} {d_day}")
        
    # Route Profiles: routeId standardTransitDays maxWarehouseProcessingHours
    for r_id in routes:
        std_transit = random.randint(5, 30)
        max_wh = random.randint(5, 20)
        print(f"{r_id} {std_transit} {max_wh}")
        
    # Tracking Events: eventId shipmentId eventDay status
    statuses = ["IN_TRANSIT", "DELAYED", "DELIVERED", "UNKNOWN"]
    for i in range(num_tracking):
        e_id = f"E{i+1}"
        s_id = random.choice(shipments)
        e_day = random.randint(dispatch_days[s_id] - 5, reference_day + 10) # mix valid and invalid bounds
        status = random.choice(statuses)
        print(f"{e_id} {s_id} {e_day} {status}")
        
    # Weather Alerts: alertId routeId alertDay severity
    severities = ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
    for i in range(num_weather):
        a_id = f"W{i+1}"
        r_id = random.choice(routes)
        a_day = random.randint(-5, reference_day + 5)
        sev = random.choice(severities)
        print(f"{a_id} {r_id} {a_day} {sev}")
        
    # Warehouse logs: processId shipmentId processDay processingHours
    for i in range(num_warehouse):
        p_id = f"P{i+1}"
        s_id = random.choice(shipments)
        p_day = random.randint(dispatch_days[s_id] - 5, reference_day + 10)
        p_hours = random.randint(-5, 15)
        print(f"{p_id} {s_id} {p_day} {p_hours}")

if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    size_hint = sys.argv[2] if len(sys.argv) > 2 else "SMALL"
    generate(seed, size_hint)
