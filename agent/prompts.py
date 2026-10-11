SYSTEM_PROMPT = """You are a traffic signal coordination agent for a cluster of 8 real
signalized junctions in Lucknow, India, all close together near Hazratganj Chauraha.

Your job: every decision cycle, you will be shown the current queue lengths and waiting
times for EACH of the 8 traffic lights. You must decide a green phase duration, in
seconds, for EACH signal.

Because these signals are physically close together, they interact: giving one signal
a very long green time can starve traffic trying to reach or leave a neighboring
signal, making overall congestion worse even if that one signal looks fine in
isolation. Balance green time across all 8 signals based on where the queues and
waiting times are worst, rather than maximizing green time everywhere.

Rules:
- Respond with ONLY a JSON array, nothing else. No explanation, no markdown formatting.
- The JSON must be a list with exactly one object per signal, in this shape:
  [{"tls_id": "<id>", "green_seconds": <number>}, ...]
- Include ALL signals given to you, using their exact tls_id.
- Typical green times range between 10 and 40 seconds. Prefer shorter, more frequent
  cycles over very long green times, since long green on one signal usually blocks
  traffic feeding into another signal in this same cluster.
- Give more green time only to signals with genuinely high queues/waiting time
  relative to the others; keep low-queue signals short so the cluster cycles quickly.

Example response:
[{"tls_id": "602511661", "green_seconds": 25}, {"tls_id": "2196599314", "green_seconds": 35}]
"""


def format_state_for_prompt(tls_id: str, phase_info: dict, queue_info: dict) -> str:
    """
    (Kept for backward compatibility with the single-signal version.)
    Turn raw queue/phase data into a short, readable text block for the LLM.
    """
    lines = [
        f"Traffic light: {tls_id}",
        f"Current phase index: {phase_info['phase_index']}",
        f"Current signal state: {phase_info['state']}",
        f"Seconds until this phase would normally switch: {phase_info['seconds_until_switch']}",
        "",
        "Lane queues:",
    ]
    for lane in queue_info["lanes"]:
        lines.append(
            f"  - Lane {lane['lane_id']}: "
            f"{lane['halted_vehicles']} vehicles halted, "
            f"{lane['waiting_time_s']}s accumulated waiting time, "
            f"{lane['vehicle_count']} vehicles present"
        )
    lines.append("")
    lines.append(f"Total halted vehicles across all lanes: {queue_info['total_halted_vehicles']}")
    lines.append("")
    lines.append("Decide the green_seconds for the current phase now.")
    return "\n".join(lines)


def format_multi_state_for_prompt(signals_data: list) -> str:
    """
    signals_data: list of dicts, each {"tls_id": str, "phase_info": dict, "queue_info": dict}
    Turn all signals' state into one combined text block for the LLM.
    """
    lines = ["Current state of all 8 signals in the cluster:", ""]
    for entry in signals_data:
        tls_id = entry["tls_id"]
        phase_info = entry["phase_info"]
        queue_info = entry["queue_info"]
        lines.append(f"--- Signal {tls_id} ---")
        lines.append(f"  Current phase: {phase_info['phase_index']} (state {phase_info['state']})")
        for lane in queue_info["lanes"]:
            lines.append(
                f"  Lane {lane['lane_id']}: {lane['halted_vehicles']} halted, "
                f"{lane['waiting_time_s']}s waiting, {lane['vehicle_count']} present"
            )
        lines.append(f"  Total halted at this signal: {queue_info['total_halted_vehicles']}")
        lines.append("")

    lines.append("Decide green_seconds for EACH of the 8 signals now, as a JSON array.")
    return "\n".join(lines)
