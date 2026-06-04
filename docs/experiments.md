# AegisStream Experiment Suite

## Running Experiments

```bash
# Run all experiments
make benchmark

# Run individual experiments
docker compose exec api python scripts/run_experiments.py --experiment throughput
docker compose exec api python scripts/run_experiments.py --experiment latency
docker compose exec api python scripts/run_experiments.py --experiment failure
docker compose exec api python scripts/run_experiments.py --experiment models
docker compose exec api python scripts/run_experiments.py --experiment ablation

# Save results
docker compose exec api python scripts/run_experiments.py --output /data/results.json
```

All experiments run in-process (no Kafka required). They use the same evaluators and scoring engine as the live streaming pipeline.

---

## Experiment 1: Throughput Benchmark

**Goal**: Measure how many events/sec the evaluator pipeline can process on a single machine.

**Method**: Generate N events using `SyntheticGenerator`, run all 12 evaluators, measure wall-clock time.

**Configurations**:
- 500 events
- 2,000 events
- 5,000 events

**Metrics reported**: `throughput_eps`, `elapsed_sec`, `avg_risk_score`, `review_rate_pct`

**Expected result**: >1,000 events/sec on a modern laptop (evaluators are pure Python, no I/O).

---

## Experiment 2: Evaluator Latency Breakdown

**Goal**: Identify which evaluators contribute the most overhead.

**Method**: Run each evaluator individually on 200 events and measure mean latency.

**Metrics reported**: Per-evaluator `avg_ms` and `total_ms`

**Expected result**: Most evaluators < 0.1ms; regex-heavy evaluators (SensitiveData) may be slightly slower.

---

## Experiment 3: Failure Mode Simulation

**Goal**: Measure how system metrics respond to injected adversarial traffic.

**Configurations**:

| Scenario | injection_rate | hallucination_rate |
|---|---|---|
| baseline | 2% | 5% |
| high_injection | 20% | 5% |
| high_hallucination | 2% | 25% |
| combined_high | 15% | 20% |

**Metrics reported**: `avg_risk_score`, `review_rate_pct`, `blocking_rate_pct`, `top_failure_modes`

**Research question**: Does the risk score scale linearly with injected failure rates? Are some failure modes more visible than others?

---

## Experiment 4: Model Comparison

**Goal**: Compare synthetic model behaviors on reliability, safety, cost, and latency dimensions.

**Method**: Generate 200 events per model using model-specific weights in `SyntheticGenerator`. All events use the same failure-mode distribution.

**Models**: gpt-4o, claude-3-sonnet, llama-3-70b, mistral-7b, gemma-7b

**Metrics reported**: `avg_risk_score`, `avg_reliability_score`, `avg_safety_score`, `review_rate_pct`, `blocking_rate_pct`, `top_failure_modes`

**Note**: In the synthetic setting, differences between models reflect cost/latency variations from the rate tables, not actual model behavior. To study real behavioral differences, replace the producer with real API calls (see `.env.example` for API key configuration).

---

## Experiment 5: Guardrail Ablation Study

**Goal**: Quantify how much missed risk increases when individual evaluators are removed.

**Method**: Run 300 events with elevated adversarial rates (injection=10%, rag_ungrounded=10%) under four evaluator configurations:

| Configuration | Evaluators removed |
|---|---|
| all_evaluators | none (baseline) |
| no_groundedness | GroundednessEvaluator |
| no_injection_eval | PromptInjectionEvaluator |
| no_refusal_eval | RefusalQualityEvaluator |

**Metrics reported**: `review_rate_pct` (proxy for detection rate), `blocking_rate_pct`

**Research interpretation**: A decrease in `review_rate_pct` when an evaluator is removed indicates that evaluator was contributing unique signal. If review_rate doesn't change, the evaluator's signals are redundant with others.

---

## Interpreting Results

### Review Rate as a Proxy for Precision
In the absence of ground truth labels, `review_rate_pct` measures how aggressively the system flags events. It is a **recall proxy** (high recall → high review rate) but not a precision measure — human review is needed to distinguish true positives from false alarms.

### Deployment Blocking Rate
`blocking_rate_pct` measures the fraction of events that would block a deployment gate. This should be low in clean traffic and spike with adversarial injection. A useful target: <5% blocking rate on clean traffic, >80% on heavy-adversarial traffic.

### Throughput Overhead
The evaluator pipeline adds ~10–50ms of processing overhead per event (dominated by DB writes, not evaluator logic). This overhead is acceptable for async offline evaluation but would require optimization for synchronous inline use.
