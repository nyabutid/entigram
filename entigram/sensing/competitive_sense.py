import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime

class CompetitiveSensing:
    """
    Operationalizes the CompetitiveIntelligence package by simulating 
    sensing activities (SEC filings, News, Market signals).
    """
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.db_file = self.target_dir / ".etg" / "states" / "CompetitiveIntelligence.db"
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    def record_signal(self, source: str, description: str, sentiment: str):
        """Records a new intelligence signal."""
        signal_id = f"SIG-{uuid.uuid4()}"
        detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(self.db_file)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO intelligence_signals (id, source_type, description, sentiment, detected_at) VALUES (?, ?, ?, ?, ?)",
                    (signal_id, source, description, sentiment, detected_at)
                )
            print(f"📡 Signal Captured: [{source}] {description[:50]}...")
        finally:
            conn.close()

    def add_competitor(self, name: str, headquarters: str, tier: str):
        """Adds a competitor to the local domain state."""
        comp_id = f"COMP-{name.replace(' ', '-').upper()}"
        
        conn = sqlite3.connect(self.db_file)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO competitors (id, name, headquarters, tier, market_share) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET name=excluded.name, headquarters=excluded.headquarters, tier=excluded.tier",
                    (comp_id, name, headquarters, tier, 0.0)
                )
            print(f"🏢 Competitor Identified: {name}")
        finally:
            conn.close()

if __name__ == "__main__":
    # Example sensing run
    sensor = CompetitiveSensing(".")
    sensor.add_competitor("Enterprise Competitor", "Denver, CO", "Primary")
    sensor.record_signal("SEC Filing", "10-K Filing indicates expansion in commercial Legacy Platform deployments.", "Positive")
    sensor.record_signal("News", "Competitor X launches new federated agent module.", "Neutral")
