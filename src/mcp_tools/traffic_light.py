import traci
from typing import Dict, List
from utils.connection import connection_manager


def get_tls_ids() -> List[str]:
    """Get the list of all traffic light IDs in the network."""
    if not connection_manager.is_connected():
        return []
    return list(traci.trafficlight.getIDList())


def get_phase(tls_id: str) -> Dict[str, object]:
    """Get the current phase index, remaining duration, and signal state string for a traffic light."""
    if not connection_manager.is_connected():
        raise RuntimeError("Not connected to SUMO.")
    phase_index = int(traci.trafficlight.getPhase(tls_id))
    state = str(traci.trafficlight.getRedYellowGreenState(tls_id))
    next_switch = float(traci.trafficlight.getNextSwitch(tls_id))
    current_time = float(traci.simulation.getTime())
    return {
        "tls_id": tls_id,
        "phase_index": phase_index,
        "state": state,
        "seconds_until_switch": round(next_switch - current_time, 2),
    }


def get_queue_lengths(tls_id: str) -> Dict[str, object]:
    """
    Get queue length (halted vehicle count) and accumulated waiting time
    for every incoming lane that controls the given traffic light.
    """
    if not connection_manager.is_connected():
        raise RuntimeError("Not connected to SUMO.")

    controlled_lanes = list(dict.fromkeys(traci.trafficlight.getControlledLanes(tls_id)))

    lanes_info = []
    total_queue = 0
    for lane_id in controlled_lanes:
        halted = int(traci.lane.getLastStepHaltingNumber(lane_id))
        waiting_time = float(traci.lane.getWaitingTime(lane_id))
        vehicle_count = int(traci.lane.getLastStepVehicleNumber(lane_id))
        lanes_info.append({
            "lane_id": lane_id,
            "halted_vehicles": halted,
            "waiting_time_s": round(waiting_time, 2),
            "vehicle_count": vehicle_count,
        })
        total_queue += halted

    return {
        "tls_id": tls_id,
        "total_halted_vehicles": total_queue,
        "lanes": lanes_info,
    }


def set_phase_duration(tls_id: str, duration: float) -> str:
    """
    Set the duration (in seconds) of the CURRENT phase for a traffic light.
    Does not change which phase is active, only how long it lasts from now.
    """
    if not connection_manager.is_connected():
        raise RuntimeError("Not connected to SUMO.")
    traci.trafficlight.setPhaseDuration(tls_id, float(duration))
    return f"Phase duration for '{tls_id}' set to {duration}s."
