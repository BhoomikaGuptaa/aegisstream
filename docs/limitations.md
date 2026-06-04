# Limitations

## Evaluator Limitations

### Heuristic-Based Detection
All evaluators are heuristic and pattern-based. They are not fine-tuned classifiers. Known limitations include:

- **False positives**: injection patterns may appear in legitimate security research prompts
- **False negatives**: novel jailbreak phrasing will bypass keyword patterns
- **Hallucination detection**: relies on a small corpus of known-wrong facts; will miss novel errors
- **Groundedness**: token overlap is a weak proxy for semantic grounding; short contexts may score artificially high or low

### No Ground Truth
In production settings, ground truth labels are rarely available. The `expected_answer` field supports supervised evaluation but is optional. Most evaluations are unsupervised signals.

### Synthetic Traffic
The synthetic generator is a simplified simulation of real deployment traffic. Real prompt distributions are more varied, culturally complex, and contain long-tail failure modes not captured in this corpus.

### Stateless Evaluators
Most evaluators are stateless and cannot detect multi-turn manipulation (e.g., gradual jailbreak over several turns), user-level behavioral patterns, or prompt evolution over sessions.

### Drift Detection
Rolling-window drift detection compares against a hardcoded baseline. A more rigorous implementation would use control charts, CUSUM, or learned baseline distributions.

## System Limitations

- **SQLite under high load**: at 1000+ events/min, SQLite write contention may become a bottleneck. PostgreSQL support is recommended for production-scale use.
- **Single Kafka partition consumer**: the evaluator service runs a single consumer instance. Horizontal scaling requires consumer group partitioning.
- **No real LLM inference by default**: the system uses synthetic events. Real model integration requires API keys or Ollama.

# Ethics

## Scope
AegisStream is a research framework for studying LLM behavioral signals. It is not a production safety system and should not be deployed as the sole safety mechanism for high-stakes applications.

## Dual-Use Risk
The synthetic generator includes realistic examples of prompt injections and jailbreak attempts. These are included strictly for research purposes — to enable evaluation of detection systems — and are not intended to serve as attack templates.

## Privacy
No real user data is collected or stored by default. The `user_id_hash` field uses SHA-256 hashing of user identifiers. PII appearing in synthetic prompts is entirely fabricated.

## Transparency
All evaluator decisions are logged with `explanation` and `evidence` fields, supporting auditability and human review.

## Limitations of Automated Safety Review
Automated evaluators are imperfect and should augment, not replace, human review. The human review queue is a first-class feature of AegisStream precisely because automated signals require human judgment for high-stakes decisions.

## Fairness
The hallucination and toxicity evaluators use fixed pattern lists that may reflect the cultural assumptions of their authors. These lists should be reviewed and expanded for production use across diverse domains and languages.
