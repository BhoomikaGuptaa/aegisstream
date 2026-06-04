# Ethics

## Intended Use

AegisStream is a research framework for studying online LLM behavioral evaluation. It is intended for:

- Researchers studying LLM reliability, safety, and deployment readiness signals
- Engineers building or evaluating AI safety tooling
- Teams seeking to understand failure mode distributions in their LLM deployments

It is **not** intended as a production-grade safety system and should not be used as the sole safeguard in any high-stakes application.

## Dual-Use Considerations

The synthetic event generator includes realistic prompt injection and jailbreak examples. These are present strictly to enable evaluation of detection systems — the same way a spam filter must be trained on spam. They are not intended to provide attack templates. The examples are drawn from publicly known jailbreak patterns and do not represent novel techniques.

Researchers extending the system with new attack corpora should consider whether those corpora, if leaked, could meaningfully assist bad actors.

## Data Privacy

- No real user data is collected by default
- `user_id_hash` uses SHA-256; hashing is one-way
- Prompt and response fields are truncated to 500/1000 characters in storage
- PII that appears in synthetic prompts is entirely fabricated

In a real deployment, prompts may contain sensitive user data. Operators must:
- Comply with applicable privacy laws before logging prompts
- Apply appropriate access controls to the database
- Consider prompt redaction before storage

## Automated Safety Decisions

The deployment gate and review queue are decision-support tools. Automated evaluators have non-zero false positive and false negative rates (see `docs/limitations.md`). Human review is a first-class feature of AegisStream for this reason. No automated system should make final safety decisions for high-stakes deployments without human oversight.

## Fairness and Representation

The toxicity and hallucination corpora reflect the cultural and linguistic assumptions of their authors. The system will perform differently across:
- Languages other than English
- Domain-specific corpora (medical, legal, financial)
- Cultural contexts where harm definitions differ

Operators deploying AegisStream in multilingual or cross-cultural settings should audit and extend the evaluator corpora accordingly.

## Transparency

All evaluator decisions are logged with full explanations and evidence strings. Users can inspect exactly why any event was flagged. The system is designed to be auditable by default.

## Environmental Impact

All evaluators are heuristic and run in Python without GPU. The system's compute footprint is minimal. Real-model integration (e.g., via Ollama) would add inference cost proportional to traffic volume.
