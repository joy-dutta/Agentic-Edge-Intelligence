# Experiment Design

## Objective

The experiment evaluates a governed agentic edge architecture under a physical-process workload. Traffic-signal control was selected because it combines strict timing, distributed sensing, neighboring-node interaction, abnormal events, and visible consequences when a control action is unsuitable.

The LLM is deliberately kept outside the hard real-time loop. Its role is to convert bounded context into a structured supervisory intent. Signal actuation, minimum timing, fairness overrides, policy checks, stale-intent rejection, and fallback remain deterministic and local.

## Timing and Authority

| Function | Interval | Authority |
|---|---:|---|
| SUMO vehicle update | 1 s | Microscopic traffic simulation |
| Local signal-control loop | 5 s | Deterministic controller |
| Scheduled LLM supervision | 120 s | Bounded intent only |
| Event-triggered supervision | At most once per 10 s | Bounded intent only |
| Maximum accepted intent age | 10 s | Enforced locally |
| Policy shield | Before every intent execution | Deterministic allow/block decision |

An LLM response cannot directly set an arbitrary signal state. It can only propose an intent admitted by the strict response schema. The local executor remains responsible for translating accepted intents into legal phase changes.

## Networks and Simulation

- **Cologne-8:** eight controlled signalized junctions used for the confirmatory evaluation.
- **Cologne-3:** a smaller three-signal arterial corridor used as a cross-network check in the exploratory follow-up.
- **Source:** public RESCO benchmark at commit `f1ed9a174f8de41fc9d8689373b836bc882570dc`.
- **Simulator:** SUMO 1.27.1.
- **Demand period:** 07:00 to 08:00 from the TAPAS Cologne morning demand.
- **Resolution:** one simulated second.

The setup retains real-road topology, routes, signal programs, and activity-based demand from the benchmark. Incidents, sensing faults, communication impairments, and trust events are injected in a controlled and repeatable way.

## Controller Configurations

Seven configurations are used so that controller placement, LLM supervision, governance, and peer context can be examined separately.

| Controller | Purpose |
|---|---|
| Fixed timing | Uses the benchmark signal plan without adapting to observed traffic. |
| Local MaxWave | Serves the phase with the largest observed incoming queue; strong, responsive, deterministic edge baseline. |
| Coordinated max-pressure | Uses upstream and downstream queues to avoid moving traffic into an already congested exit; runs locally. |
| Cloud max-pressure | Passes observations and actions through the emulated WAN to represent cloud-dependent control. |
| Agentic, unguarded | Applies bounded LLM intents without the deterministic policy shield. |
| Agentic, governed | Uses the same model and observations, but every intent is checked before execution. |
| Agentic, governed without peers | Matches governed control but withholds neighboring-agent summaries, isolating the effect of peer context. |

A separately trained, frozen RESCO IDQN is retained as an additional placement sensitivity study. It is not counted in the 520-run confirmatory matrix.

## Confirmatory Scenarios

| Case | Purpose | Conditions | Paired seeds |
|---|---|---|---:|
| S0 | Routine operation | Normal morning traffic with no injected incident or system fault. | 20 |
| S1 | High demand | Traffic demand increased by 20%, representing a busier morning period. | 10 |
| S2 | Physical incident | One lane closed for 600 s and an emergency vehicle introduced during the closure. | 20 |
| S3 | Impaired incident | S2 plus 5% sensor-count error, 5% sensor loss, a 30-s detector outage, stressed WAN conditions, a 10-s remote-service outage, and stale peer state. | 20 |
| S4 | Trust stress | Incident and impaired sensing/communication plus stale, replayed, and unauthenticated peer messages representing a faulty or compromised neighbor. | 10 |

The confirmatory matrix contains 80 scenario-seed combinations:

- Four deterministic or conventional controllers across all 80 combinations: 320 runs.
- Governed and unguarded agentic controllers across all 80 combinations: 160 runs.
- Governed no-peer ablation in S0 and S2: 40 runs.
- **Total: 520 runs.**

Controllers sharing a scenario and seed receive the same demand realization. This paired design reduces variation unrelated to the controller.

## Exploratory Follow-up

The follow-up is kept separate from the confirmatory matrix. It uses four controllers, 10 new seeds, and two networks under 1.3-times demand and a 900-s corridor lane closure. Its 80 runs test whether peer context becomes more useful when queues interact over a longer disturbance.

The follow-up cannot retroactively change the confirmatory protocol or its statistical decision rules.

## LLM Configuration

- Primary model snapshot: `gpt-5.4-nano-2026-03-17`.
- Validation model snapshot: `gpt-5.4-mini-2026-03-17`.
- OpenAI Python SDK: 3.6.0.
- Reasoning effort: `none`.
- Maximum output: 500 tokens.
- Storage: disabled with `store: false`.
- Response contract: strict structured output for all eight intersection agents in one batched request.
- Prompt: [`configs/prompts/supervisor_v1.txt`](../configs/prompts/supervisor_v1.txt).

Model calls are batched to control cost and communication. The primary controller receives one scheduled request every 120 simulated seconds plus bounded event requests.

## Governance and Failure Handling

The local shield checks declared signal-timing, intent-age, sensing-completeness, emergency-verification, spillback, peer-freshness, authentication, replay, and action-rate rules. A rejected proposal is logged and local control continues. The same fallback path is used for invalid structured output, timeout, service error, simulated API outage, or an intent that arrives too late.

The shield demonstrates compliance with the declared rules. It is not a proof of universal physical safety.

## Measurements

Traffic measures include mean and P95 vehicle time loss, trip completion, queues, waiting time, fairness, and emergency-vehicle trip time. System measures include WAN and peer traffic, API and intent latency, structured-output validity, fallback and recovery, policy proposals, blocked proposals, executed policy violations, process resource use, collisions, and teleports.

Each complete simulation run is one independent statistical observation. Vehicles within the same run are not treated as independent samples.

## Statistical Procedure

- Paired bootstrap 95% confidence intervals for controller differences.
- Wilcoxon signed-rank tests for paired comparisons.
- Holm correction within each metric family.
- Paired effect sizes.
- Fixed random seeds for bootstrap generation and run ordering.

The frozen values are in [`configs/experiment.yaml`](../configs/experiment.yaml). Protocol corrections made before the affected runs are recorded as versioned amendment files under [`configs`](../configs).

