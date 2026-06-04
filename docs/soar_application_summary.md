# SOAR Application Summary

## AegisStream: Real-Time Behavioral Evaluation and Reliability Observatory for Open-Source LLMs

**Application Statement for the Summer of Open AI Research Program (EleutherAI)**

---

Existing LLM evaluation practice is dominated by static benchmarks: fixed datasets, controlled prompts, and offline scoring. While benchmarks like MMLU, HumanEval, and MT-Bench provide useful capability signals, they cannot capture the behavioral dynamics that emerge during real deployment — adversarial prompt distributions, retrieval-augmented context failures, model drift triggered by fine-tuning or provider updates, or the cost and latency tradeoffs that shape real-world reliability. AegisStream addresses this gap by treating a live stream of LLM prompt-response events as a first-class source of behavioral evidence.

The project makes three concrete research contributions. First, it introduces a composable online evaluation framework consisting of twelve lightweight evaluators — covering injection, jailbreak, sensitive data, hallucination, groundedness, refusal quality, toxicity, format compliance, latency SLA, cost anomaly, drift, and route regression — each returning a structured result with a severity label, score delta, explanation, and evidence string. These evaluators are intentionally stateless and heuristic-based, prioritizing interpretability and speed (sub-millisecond per evaluator) over recall, and their precision-recall tradeoffs are studied directly in the guardrail ablation experiment. Second, the project defines a composite scoring schema — combining risk, reliability, safety, usefulness, and groundedness dimensions — that converts heterogeneous evaluator signals into a single deployment decision. Third, it ships a reproducible experimental suite studying how these signals behave under varying failure-mode injection rates, model comparisons across five open-source model families, and guardrail configurations with individual evaluators ablated.

The system is built on a production-credible stack (Python, FastAPI, Kafka/Redpanda, Streamlit, SQLite, Docker Compose) and can process over 1,000 events per minute on a standard laptop. It includes a CI/CD deployment gate script that integrates directly into model release pipelines. All components are open-source, documented, and designed to be extended by researchers adding new evaluators, model providers, or scoring strategies.

The broader scientific question — whether online behavioral telemetry can meaningfully complement offline benchmarks for deployment readiness assessment — remains under-studied. AegisStream provides a concrete, reproducible artifact for investigating it.

---

## Resume Bullets

- **Built AegisStream**, an open-source streaming LLM evaluation framework processing 1,000+ events/min with <200ms end-to-end latency; implemented 12 behavioral evaluators covering injection, jailbreak, hallucination, groundedness, and cost signals across 5 model families
- **Designed a composite reliability scoring system** (risk, safety, usefulness, groundedness dimensions) that powers a human review queue, CI/CD deployment gate, and drift alerting system running on Kafka/Redpanda + SQLite
- **Ran reproducible AI safety experiments** including throughput benchmarks, failure-mode simulations (2%→20% injection rate), model comparisons, and guardrail ablation studies; packaged as a research framework suitable for open science publication
- **Architected and deployed a 5-service Docker Compose observability stack** (FastAPI, Streamlit, Redpanda, Python consumers) with 20+ API endpoints, 10-page live dashboard, and a model release deployment gate with configurable risk thresholds

---

## GitHub README Badges / Taglines

```
🛡️ AegisStream — Stream first, benchmark later.
⚡ 1,000+ events/min | 12 behavioral evaluators | 5 model families
🔬 Online LLM reliability research, not just a monitoring dashboard
🚀 docker compose up — the entire AI safety observatory on your laptop
📊 From raw tokens to deployment decision in <200ms
```

---

## 30-Second Elevator Pitch

"AegisStream is an open-source research framework that treats live LLM traffic as behavioral evidence. As prompt-response pairs stream through the system, twelve lightweight evaluators check for injection attacks, jailbreaks, hallucinations, grounding failures, over-refusals, and latency and cost violations — computing composite reliability and safety scores in under 200 milliseconds. The result is a streaming reliability observatory: a live dashboard, a human review queue, drift alerts, a model comparison lab, and a CI/CD deployment gate that blocks risky model releases before they reach production. The entire stack runs on your laptop via Docker Compose and includes a research experiment suite studying how these signals behave under adversarial traffic, model drift, and guardrail ablation. It's AI safety research you can actually run."

---

## 2-Minute Technical Explanation

"The core insight is that a prompt-response pair — combined with latency, token count, and retrieval context — contains rich behavioral signal that offline benchmarks discard. AegisStream makes this signal legible.

Events flow into a Redpanda topic. The evaluator service consumes each event and applies twelve evaluators in sequence. Each evaluator returns a structured result: whether it passed, a severity level, a numeric score delta, a human-readable explanation, and an evidence string. These results feed into a scoring engine that computes five composite scores: risk (0–100, sum of deltas), reliability (100 − risk), safety (penalizes injection/jailbreak/toxicity deltas), usefulness (penalizes over-refusals and malformed outputs), and groundedness (derived from context-response token overlap for RAG routes).

Events above the risk threshold enter a human review queue. A separate rolling-window drift detector watches for sustained spikes in average risk score and publishes alerts to a dedicated topic. A FastAPI service exposes all of this over 20+ endpoints that power a 10-page Streamlit dashboard and a CLI deployment gate.

The research layer consists of five reproducible experiments: a throughput benchmark scaling from 500 to 5,000 events, a per-evaluator latency breakdown, a failure-mode simulation where injection and hallucination rates sweep from baseline to 20%, a five-model comparison across GPT-4o, Claude, Llama, Mistral, and Gemma mock providers, and a guardrail ablation study measuring how review precision and missed-risk rates change when individual evaluators are removed.

The design philosophy is intentional: evaluators are heuristic and lightweight because the goal is to study which signals are actually informative from telemetry alone, before introducing heavier LLM-as-judge approaches. AegisStream is the substrate for that research."
