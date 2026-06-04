"""AegisStream evaluator service entrypoint."""
import sys
sys.path.insert(0, "/app")

from services.evaluator.app.consumer import run

if __name__ == "__main__":
    run()
