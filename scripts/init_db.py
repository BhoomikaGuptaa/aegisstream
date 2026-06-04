"""Initialize the AegisStream SQLite database."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, "/app")

from services.api.app.database import init_db

if __name__ == "__main__":
    print("Initializing AegisStream database...")
    init_db()
    print("Database initialized successfully.")
