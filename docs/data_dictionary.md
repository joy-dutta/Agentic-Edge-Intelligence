# Data Dictionary

## Run Summary

Each `artifacts/raw/<phase>/<run_id>/summary.json` is one independent paired-seed
run. Important fields are:

| Field | Unit / denominator | Meaning |
|---|---|---|
| `mean_time_loss_s` | seconds/trip | Mean SUMO time loss for completed trips |
| `p95_time_loss_s` | seconds/trip | Run-level 95th percentile trip time loss |
| `p95_trip_time_s` | seconds/trip | Run-level 95th percentile trip duration |
| `completed_trips` | vehicles/run | Vehicles with a completed trip record |
| `loaded_vehicles` | vehicles/run | Vehicles loaded from the identical paired route demand |
| `inserted_vehicles` | vehicles/run | Vehicles successfully inserted into SUMO |
| `running_vehicles_at_end` | vehicles/run | Inserted vehicles still active after one hour |
| `teleports_*` | events/run | Total and jam/yield/wrong-lane teleport causes |
| `emergency_trip_time_s` | seconds | Injected emergency vehicle trip duration |
| `maximum_approach_wait_s` | seconds | Maximum observed incoming-lane waiting time |
| `approach_wait_fairness_jain` | 0-1 | Jain index over per-lane mean waits |
| `ssm_conflicts` | conflicts/run | SUMO SSM conflicts on edges adjoining the eight controlled junctions |
| `min_ttc_s` | seconds | Minimum valid time-to-collision value in controlled-junction SSM output |
| `min_pet_s` | seconds | Minimum valid post-encroachment time in controlled-junction SSM output |
| `max_drac_mps2` | m/s^2 | Maximum valid deceleration-rate-to-avoid-crash value in controlled-junction SSM output |
| `ssm_unavailable_values` | values/run | SSM conflict fields reported as unavailable by SUMO |
| `proposed_unsafe_actions` | actions/run | Proposals violating at least one frozen rule |
| `blocked_unsafe_actions` | actions/run | Unsafe proposals rejected by the shield |
| `executed_unsafe_actions` | actions/run | Unsafe proposals accepted for execution |
| `unsafe_actions_per_1000_decisions` | per 1,000 | Executed unsafe / total policy decisions |
| `fallback_rate` | fraction | All fallback events / explicit fallback opportunities |
| `local_fallback_control_rate` | fraction | Local fallback steps / agent control opportunities |
| `api_latency_p95_s` | seconds/call | Host-observed Responses API call latency |
| `intent_age_p95_s` | seconds/action | Observation-to-execution age |
| `policy_check_p95_ms` | ms/check | Deterministic shield execution latency |
| `cloud_wan` | bytes/messages | Raw cloud-controller telemetry and action traffic |
| `peer_network` | bytes/messages | Compact edge peer-summary traffic |
| `api_*_application_bytes` | bytes/run | Serialized OpenAI request and response bodies |
| `audit_log_bytes` | bytes/run | Local decision, policy, and API audit files |
| `local_process_cpu_s` | CPU seconds | User plus system CPU consumed by the runner |
| `local_process_rss_bytes` | bytes | Resident set size sampled at run completion |

Post-five-minute fields repeat the trip metrics after excluding the first 300
seconds. No vehicle-level value is used as an independent statistical replicate.
All vehicles are eligible for SSM instrumentation, but SSM conflicts are measured
only on edges adjoining the eight controlled junctions declared in
`configs/ssm_controlled_junctions.txt`.

## Decision Logs

`decisions.jsonl` records observation time, proposed or fallback intent, action
delivery, and executed phase. `policy_decisions.jsonl` records the proposal,
frozen-rule result, rejection reasons, and fallback. `api_calls.jsonl` records a
redacted canonical payload, payload hash, pinned model, latency, status, attempts,
token usage, and structured output. Credentials are never recorded.
