#!/usr/bin/env python3
"""Validate the paired Single profiling runs and summarize sampled phase times."""

import sys

from summarize_double_profile import SAMPLE_INTERVAL, profile_main, projected, search_time


BASE = ("single_st", "single_et1", "single_et2")
PHASES = ("gate", "terminal", "fallback", "matching", "generate", "commit", "output")
WORK = ("et_attempt", "et_hit", "et_degree2_hit")


def check_pair(control, sampled):
    if any(control[key] != sampled[key] for key in WORK):
        raise ValueError("profiling changed terminal counters")
    if control["single_profile_interval"] or int(sampled["single_profile_interval"]) != SAMPLE_INTERVAL:
        raise ValueError("unexpected profile sampling configuration")

    gates, gate_samples, samples, fallbacks, outputs, output_samples = (
        int(sampled["single_" + key]) for key in
        ("gate_calls", "gate_samples", "terminal_samples", "fallbacks", "output_calls", "output_samples")
    )
    calls, hits = (int(sampled[key]) for key in WORK[:2])
    profiled_time = search_time(sampled)
    if (not 0 <= gate_samples <= gates or not 0 <= samples <= calls <= gates or not 0 <= hits <= calls
            or fallbacks != calls - hits or not 0 <= output_samples <= outputs
            or outputs < int(sampled["count"]) or (control["mode"] == BASE[0] and gates)):
        raise ValueError("invalid profiler call or sample counts")

    times = {phase: int(sampled[f"single_{phase}_ns"]) for phase in PHASES}
    stages = times["matching"] + times["generate"] + times["commit"]
    # The runner's published search time is rounded. Terminal subphases nest
    # inside attempts, while reporting covers later callbacks across the run.
    if (min(times.values()) < 0 or stages > times["terminal"] or times["fallback"] > times["terminal"]
            or sum(times[phase] for phase in ("gate", "terminal", "output")) > profiled_time * 1.00001e9 + 1000
            or (not gate_samples and times["gate"]) or (not output_samples and times["output"])
            or (not samples and any(times[phase] for phase in PHASES[1:-1]))
            or (control["mode"] == BASE[1] and (times["generate"] or times["commit"]))
            or (control["mode"] == BASE[2] and times["matching"])):
        raise ValueError("invalid sampled phase times")

    times["preparation_and_other"] = times["terminal"] - stages
    measured = {phase: nanoseconds / 1e6 for phase, nanoseconds in times.items()}
    estimates = {phase: projected(value, calls, samples) for phase, value in measured.items()}
    estimates["gate"] = projected(measured["gate"], gates, gate_samples)
    estimates["output"] = projected(measured["output"], outputs, output_samples)
    # A failed attempt can include generation work. Keep that overlapping
    # timer in the raw estimates and partition only the known disjoint regions.
    exclusive = {"eligibility": estimates["gate"], "matching_with_tree_updates": estimates["matching"],
                 "mis_generation": estimates["generate"], "result_tree_integration": estimates["commit"],
                 "terminal_preparation_and_other": estimates["preparation_and_other"],
                 "final_output_callback": estimates["output"]}
    if control["mode"] == BASE[1]:
        exclusive["mis_generation"] = exclusive["result_tree_integration"] = 0.0
    elif control["mode"] == BASE[2]:
        exclusive["matching_with_tree_updates"] = 0.0
    control_time = search_time(control)
    return {"control_search_ms": 1000 * control_time, "profiled_search_ms": 1000 * profiled_time,
            "profile_to_control_time_ratio": profiled_time / control_time,
            "eligibility_calls": gates, "eligibility_samples": gate_samples,
            "terminal_calls": calls, "terminal_samples": samples, "terminal_fallbacks": fallbacks,
            "output_calls": outputs, "output_samples": output_samples,
            "measured_ms": measured, "estimated_ms": estimates, "exclusive_estimated_ms": exclusive}


if __name__ == "__main__":
    sys.exit(profile_main(__doc__, "single", BASE, check_pair))
