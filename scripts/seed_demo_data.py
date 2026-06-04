"""
Seed the AegisStream database with synthetic events for demo purposes.
Runs evaluators directly (no Kafka required).
"""
import sys, os, sqlite3, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set DB path for local scripts
os.environ.setdefault("DATABASE_URL", "/data/aegisstream.db")

from services.api.app.database import init_db, get_db_path
from services.producer.app.synthetic_generator import SyntheticGenerator
from services.evaluator.app.evaluators import ALL_EVALUATORS
from services.evaluator.app.scoring import compute_scores

N_EVENTS = int(os.getenv("SEED_EVENTS", "500"))


def seed():
    init_db()
    generator = SyntheticGenerator(
        injection_rate=0.06,
        hallucination_rate=0.10,
        drift_enabled=True,
        drift_start_event=300,
    )

    db_path = get_db_path()
    print(f"Seeding {N_EVENTS} events to {db_path}...")

    for i in range(N_EVENTS):
        event = generator.generate()
        results = [ev.evaluate(event) for ev in ALL_EVALUATORS]
        evaluated = compute_scores(event, results)

        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO raw_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                event.event_id, event.trace_id, event.session_id, event.user_id_hash,
                event.timestamp.isoformat(), event.app_name, event.route_name,
                event.environment, event.model_name, event.model_family, event.provider,
                event.prompt[:500], event.response[:1000],
                event.input_tokens, event.output_tokens, event.latency_ms,
                event.estimated_cost_usd, event.temperature,
                event.retrieved_context[:500] if event.retrieved_context else None,
                json.dumps(event.metadata),
            ))
            conn.execute("""
                INSERT OR REPLACE INTO evaluated_events VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                event.event_id, evaluated.risk_score, evaluated.reliability_score,
                evaluated.usefulness_score, evaluated.safety_score,
                evaluated.groundedness_score, evaluated.review_required,
                evaluated.deployment_blocking, evaluated.primary_failure_mode,
                evaluated.evaluated_at.isoformat(),
            ))
            if evaluated.review_required:
                conn.execute("""
                    INSERT OR IGNORE INTO review_queue VALUES (?,?,?,'pending',NULL,NULL)
                """, (event.event_id, evaluated.risk_score, evaluated.primary_failure_mode))

            for r in evaluated.evaluator_results:
                conn.execute("""
                    INSERT INTO evaluator_results VALUES (NULL,?,?,?,?,?,?,?,?,?)
                """, (
                    event.event_id, r.evaluator_name, r.passed, r.severity,
                    r.score_delta, r.label, r.explanation[:300], r.evidence[:200],
                    r.confidence,
                ))
            conn.commit()

        if (i + 1) % 100 == 0:
            print(f"  Seeded {i+1}/{N_EVENTS} events...")

    print(f"\n✅ Seeded {N_EVENTS} events successfully.")
    print(f"   Database: {db_path}")

    # Summary
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0]
        avg_risk = conn.execute("SELECT AVG(risk_score) FROM evaluated_events").fetchone()[0]
        print(f"\n📊 Summary:")
        print(f"   Total events: {total}")
        print(f"   Review queue: {reviews}")
        print(f"   Avg risk score: {avg_risk:.1f}")


if __name__ == "__main__":
    seed()
