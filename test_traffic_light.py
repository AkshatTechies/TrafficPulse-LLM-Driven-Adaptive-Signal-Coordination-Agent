import sys
sys.path.insert(0, "src")

from utils.connection import connection_manager
from mcp_tools.traffic_light import get_tls_ids, get_queue_lengths

connection_manager.connect(config_file="scenario/config.sumocfg", gui=False)

for _ in range(100):
    connection_manager.simulation_step(0)

all_ids = get_tls_ids()
print("Checking all junctions...\n")

for tls_id in all_ids:
    info = get_queue_lengths(tls_id)
    num_lanes = len(info["lanes"])
    total_halted = info["total_halted_vehicles"]
    print(f"ID: {tls_id:15} | lanes: {num_lanes} | halted vehicles: {total_halted}")

connection_manager.disconnect()
print("\nDone.")
