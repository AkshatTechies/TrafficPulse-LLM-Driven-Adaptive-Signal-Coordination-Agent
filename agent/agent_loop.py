import sys
import os
import time
import logging
import argparse

sys.path.insert(0, "src")

from google import genai

from utils.connection import connection_manager
from mcp_tools.traffic_light import get_tls_ids, get_phase, get_queue_lengths, set_phase_duration

from agent.prompts import SYSTEM_PROMPT, format_multi_state_for_prompt
from agent.safety import apply_safety_check_multi

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("agent.loop")

DECISION_INTERVAL_STEPS = 30  # ask the LLM for a new decision every N simulated seconds

# Gemini free tier rate limit safety gap between calls.
MIN_SECONDS_BETWEEN_CALLS = 13.0


def run_agent(config_file: str, total_steps: int, output_log: str, model_name: str) -> None:
    client = genai.Client()

    connection_manager.connect(config_file=config_file, gui=False)
    logger.info(f"Connected to SUMO using {config_file}")

    all_tls_ids = get_tls_ids()
    logger.info(f"Controlling {len(all_tls_ids)} signals: {all_tls_ids}")

    fallback_count = 0
    clamp_count = 0
    decision_cycles = 0

    header = "step,tls_id,green_seconds,was_clamped,was_fallback,total_halted,reason"
    with open(output_log, "w") as f:
        f.write(header + "\n")

    last_call_time = 0.0
    step = 0

    try:
        while step < total_steps:
            connection_manager.simulation_step(0)
            step += 1

            if step % DECISION_INTERVAL_STEPS == 0:
                signals_data = []
                halted_by_id = {}
                for tls_id in all_tls_ids:
                    phase_info = get_phase(tls_id)
                    queue_info = get_queue_lengths(tls_id)
                    signals_data.append({
                        "tls_id": tls_id,
                        "phase_info": phase_info,
                        "queue_info": queue_info,
                    })
                    halted_by_id[tls_id] = queue_info["total_halted_vehicles"]

                prompt_text = format_multi_state_for_prompt(signals_data)

                elapsed = time.time() - last_call_time
                if elapsed < MIN_SECONDS_BETWEEN_CALLS:
                    wait_time = MIN_SECONDS_BETWEEN_CALLS - elapsed
                    logger.info(f"Waiting {wait_time:.1f}s to respect API rate limit...")
                    time.sleep(wait_time)

                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                        config={"system_instruction": SYSTEM_PROMPT},
                    )
                    raw_text = response.text
                except Exception as e:
                    logger.warning(f"LLM call failed at step {step}: {e}")
                    raw_text = ""
                finally:
                    last_call_time = time.time()

                results = apply_safety_check_multi(raw_text, all_tls_ids)

                decision_cycles += 1
                for tls_id, result in results.items():
                    set_phase_duration(tls_id, result.green_seconds)

                    if result.was_fallback:
                        fallback_count += 1
                    if result.was_clamped:
                        clamp_count += 1

                    line = (
                        f"{step},{tls_id},{result.green_seconds},{result.was_clamped},"
                        f"{result.was_fallback},{halted_by_id[tls_id]},\"{result.reason}\""
                    )
                    with open(output_log, "a") as f:
                        f.write(line + "\n")

                total_halted_all = sum(halted_by_id.values())
                logger.info(
                    f"[step {step}] applied {len(results)} signal decisions | "
                    f"total halted across cluster: {total_halted_all}"
                )

    finally:
        connection_manager.disconnect()
        logger.info("=== Agent run complete (or interrupted) ===")
        logger.info(f"Steps completed: {step}/{total_steps}")
        logger.info(f"Decision cycles: {decision_cycles}")
        logger.info(f"Total per-signal fallbacks: {fallback_count}")
        logger.info(f"Total per-signal clamps: {clamp_count}")
        logger.info(f"Log written to: {output_log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="scenario/config.sumocfg")
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--output", default="agent/agent_decisions.csv")
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Error: GEMINI_API_KEY environment variable is not set.")

    run_agent(args.config, args.steps, args.output, args.model)
