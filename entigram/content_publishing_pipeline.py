import sqlite3
import os
from pathlib import Path
from datetime import datetime

class ContentPublishingPipeline:
    """
    Simulates the Content Publishing workflow (e.g. for a Substack newsletter).
    Drafts articles and anchors them in semantic Concept References.
    """
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.db_file = self.target_dir / ".etg" / "states" / "ContentPublishing.db"
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    def define_concept(self, name: str, definition: str):
        concept_id = f"CON-{name.replace(' ', '-').upper()}"
        
        conn = sqlite3.connect(self.db_file)
        try:
            with conn:
                # Update if exists or insert
                conn.execute(
                    "INSERT INTO concept_references (id, concept_name, definition) VALUES (?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET concept_name=excluded.concept_name, definition=excluded.definition",
                    (concept_id, name, definition)
                )
            print(f"🧠 Concept Defined: {name}")
        finally:
            conn.close()
            
        return concept_id

    def draft_article(self, title: str, status: str, concept_ids: list):
        # We ignore concept_ids mapping into the DB for now as the schema doesn't have a Many-to-Many table created yet in this simple example.
        slug = title.lower().replace(' ', '-')
        article_id = f"ART-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        published_date = datetime.now().isoformat() if status == "Published" else None
        
        conn = sqlite3.connect(self.db_file)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO articles (id, title, slug, status, published_date) VALUES (?, ?, ?, ?, ?)",
                    (article_id, title, slug, status, published_date)
                )
            print(f"📝 Article Drafted: '{title}' [{status}]")
        finally:
            conn.close()

if __name__ == "__main__":
    pipeline = ContentPublishingPipeline(".")
    c1 = pipeline.define_concept("Semantic Governance", "The core architectural law emphasizing strict domain isolation and deterministic state bounds.")
    c2 = pipeline.define_concept("Modular Monolith", "A software architecture where application components are modularized but deployed as a single unit, avoiding distributed microservice overhead.")
    pipeline.draft_article("Why Microservices are a Trap for Early Startups", "Published", [c1, c2])
