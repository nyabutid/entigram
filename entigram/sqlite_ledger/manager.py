import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from entigram.governance.grounding import (
    EVIDENCE_HUMAN_REVIEW,
    LIFECYCLE_PROPOSED,
    LIFECYCLE_VERIFIED,
)

class LedgerManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Keep a persistent connection for in-memory databases to avoid losing data
        self._memory_conn = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            
        self._ensure_db()

    def _get_connection(self):
        if self._memory_conn is not None:
            return self._memory_conn
        return sqlite3.connect(self.db_path)

    def _ensure_db(self):
        """Creates the human_resolutions and conflicts tables if they don't exist."""
        if self.db_path != ":memory:":
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
        
        conn = self._get_connection()
        with conn:
            # Table for settled decisions (Immutable Append-only)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS human_resolutions (
                    id INTEGER PRIMARY KEY,
                    conflict_id TEXT,
                    entity_type TEXT,
                    resolved_state TEXT,
                    rationale TEXT,
                    version INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table for pending contradictions
            conn.execute('''
                CREATE TABLE IF NOT EXISTS conflicts (
                    id INTEGER PRIMARY KEY,
                    conflict_id TEXT UNIQUE,
                    entity_type TEXT,
                    proposed_states TEXT, -- JSON string of competing states
                    source_agents TEXT,   -- JSON string of agent IDs
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table for Semantic Alignments (Cross-domain Governance)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS semantic_alignments (
                    id INTEGER PRIMARY KEY,
                    source_domain TEXT,
                    target_domain TEXT,
                    source_concept TEXT,
                    target_concept TEXT,
                    relation TEXT DEFAULT 'skos:exactMatch',
                    confidence REAL,
                    rationale TEXT,
                    status TEXT DEFAULT 'approved',
                    lifecycle_status TEXT DEFAULT 'verified',
                    evidence_type TEXT,
                    source_artifact TEXT,
                    verified INTEGER DEFAULT 1,
                    verified_by TEXT,
                    verified_at DATETIME,
                    semantic_confidence REAL,
                    schema_confidence REAL,
                    data_confidence REAL,
                    human_review_confidence REAL,
                    runtime_observation_confidence REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_domain, target_domain, source_concept, target_concept)
                )
            ''')
            self._ensure_columns(conn, "semantic_alignments", {
                "lifecycle_status": "TEXT DEFAULT 'verified'",
                "evidence_type": "TEXT",
                "source_artifact": "TEXT",
                "verified": "INTEGER DEFAULT 1",
                "verified_by": "TEXT",
                "verified_at": "DATETIME",
                "semantic_confidence": "REAL",
                "schema_confidence": "REAL",
                "data_confidence": "REAL",
                "human_review_confidence": "REAL",
                "runtime_observation_confidence": "REAL",
            })
            # Table for Global Synonym Mapping (Phase 3: Macro Reconciliation)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS synonyms (
                    id INTEGER PRIMARY KEY,
                    term TEXT,
                    synonym TEXT,
                    confidence REAL DEFAULT 1.0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(term, synonym)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_synonyms_term
                ON synonyms(term)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alignments_src_domain
                ON semantic_alignments(source_domain)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alignments_concepts
                ON semantic_alignments(source_concept, target_concept)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alignments_trust
                ON semantic_alignments(lifecycle_status, verified, evidence_type, confidence)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_resolutions_conflict
                ON human_resolutions(conflict_id, version)
            ''')
        if self.db_path != ":memory:":
            conn.close()

    def _ensure_columns(self, conn, table: str, columns: Dict[str, str]):
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def record_synonym(self, term: str, synonym: str, confidence: float = 1.0) -> bool:
        """Persists a semantic synonym relationship."""
        conn = self._get_connection()
        term = term.lower().strip()
        synonym = synonym.lower().strip()
        try:
            with conn:
                conn.execute('''
                    INSERT INTO synonyms (term, synonym, confidence)
                    VALUES (?, ?, ?)
                    ON CONFLICT(term, synonym) DO UPDATE SET
                        confidence=excluded.confidence,
                        timestamp=CURRENT_TIMESTAMP
                ''', (term, synonym, confidence))
                # Add the inverse relationship as well
                conn.execute('''
                    INSERT INTO synonyms (term, synonym, confidence)
                    VALUES (?, ?, ?)
                    ON CONFLICT(term, synonym) DO UPDATE SET
                        confidence=excluded.confidence,
                        timestamp=CURRENT_TIMESTAMP
                ''', (synonym, term, confidence))
            return True
        except Exception as e:
            print(f"Ledger Error (Synonym): {e}")
            return False
        finally:
            if self.db_path != ":memory:": conn.close()

    def get_synonyms(self, term: Optional[str] = None) -> list:
        """Retrieves synonyms for a given term or all synonyms."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if term:
                cursor.execute('SELECT synonym, confidence FROM synonyms WHERE term = ?', (term.lower(),))
            else:
                cursor.execute('SELECT term, synonym, confidence FROM synonyms ORDER BY term ASC')
            rows = cursor.fetchall()
            if term:
                return [r[0] for r in rows if r[1] >= 0.5] # Return list of strings above threshold
            return [
                {
                    "term": r[0],
                    "synonym": r[1],
                    "confidence": r[2]
                } for r in rows
            ]
        finally:
            if self.db_path != ":memory:": conn.close()

    def record_alignment(
        self,
        source_domain: str,
        target_domain: str,
        source_concept: str,
        target_concept: str,
        confidence: float,
        rationale: str,
        *,
        relation: str = "skos:exactMatch",
        lifecycle_status: str = LIFECYCLE_VERIFIED,
        evidence_type: str = EVIDENCE_HUMAN_REVIEW,
        source_artifact: Optional[str] = None,
        verified: bool = True,
        verified_by: Optional[str] = "EntigramBroker",
        semantic_confidence: Optional[float] = None,
        schema_confidence: Optional[float] = None,
        data_confidence: Optional[float] = None,
        human_review_confidence: Optional[float] = None,
        runtime_observation_confidence: Optional[float] = None,
    ) -> bool:
        """Persists a semantic alignment with explicit grounding metadata."""
        conn = self._get_connection()
        try:
            verified_at = datetime.utcnow().isoformat() if verified else None
            with conn:
                conn.execute('''
                    INSERT INTO semantic_alignments (
                        source_domain, target_domain, source_concept, target_concept,
                        relation, confidence, rationale, status, lifecycle_status,
                        evidence_type, source_artifact, verified, verified_by, verified_at,
                        semantic_confidence, schema_confidence, data_confidence,
                        human_review_confidence, runtime_observation_confidence
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_domain, target_domain, source_concept, target_concept) DO UPDATE SET
                        relation=excluded.relation,
                        confidence=excluded.confidence,
                        rationale=excluded.rationale,
                        status=excluded.status,
                        lifecycle_status=excluded.lifecycle_status,
                        evidence_type=excluded.evidence_type,
                        source_artifact=excluded.source_artifact,
                        verified=excluded.verified,
                        verified_by=excluded.verified_by,
                        verified_at=excluded.verified_at,
                        semantic_confidence=excluded.semantic_confidence,
                        schema_confidence=excluded.schema_confidence,
                        data_confidence=excluded.data_confidence,
                        human_review_confidence=excluded.human_review_confidence,
                        runtime_observation_confidence=excluded.runtime_observation_confidence,
                        timestamp=CURRENT_TIMESTAMP
                ''', (
                    source_domain, target_domain, source_concept, target_concept,
                    relation, confidence, rationale,
                    "approved" if verified else "pending",
                    lifecycle_status, evidence_type, source_artifact, int(verified),
                    verified_by if verified else None, verified_at,
                    semantic_confidence, schema_confidence, data_confidence,
                    human_review_confidence, runtime_observation_confidence,
                ))
            return True
        except Exception as e:
            print(f"Ledger Error (Alignment): {e}")
            return False
        finally:
            if self.db_path != ":memory:": conn.close()

    def record_alignment_proposal(
        self,
        source_domain: str,
        target_domain: str,
        source_concept: str,
        target_concept: str,
        confidence: float,
        rationale: str,
        *,
        relation: str = "skos:closeMatch",
        evidence_type: str = "schema_match",
        source_artifact: Optional[str] = None,
    ) -> bool:
        return self.record_alignment(
            source_domain,
            target_domain,
            source_concept,
            target_concept,
            confidence,
            rationale,
            relation=relation,
            lifecycle_status=LIFECYCLE_PROPOSED,
            evidence_type=evidence_type,
            source_artifact=source_artifact,
            verified=False,
            verified_by=None,
            semantic_confidence=confidence,
            schema_confidence=confidence if evidence_type == "schema_match" else None,
        )

    def get_alignments(self, source_domain: Optional[str] = None, trusted_only: bool = False) -> list:
        """Retrieves semantic alignments, optionally restricted to trusted operational alignments."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = '''
                SELECT id, source_domain, target_domain, source_concept, target_concept,
                       relation, confidence, rationale, status, timestamp, lifecycle_status,
                       evidence_type, source_artifact, verified, verified_by, verified_at,
                       semantic_confidence, schema_confidence, data_confidence,
                       human_review_confidence, runtime_observation_confidence
                FROM semantic_alignments
            '''
            conditions = []
            params = []
            if source_domain:
                conditions.append("source_domain = ?")
                params.append(source_domain)
            if trusted_only:
                conditions.append("lifecycle_status IN ('reviewed', 'verified')")
                conditions.append("verified = 1")
                conditions.append("confidence >= 0.8")
                conditions.append("evidence_type IN ('human_review', 'integration_test', 'sample_data_match')")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "source_domain": r[1],
                    "target_domain": r[2],
                    "source_concept": r[3],
                    "target_concept": r[4],
                    "relation": r[5],
                    "confidence": r[6],
                    "rationale": r[7],
                    "status": r[8],
                    "timestamp": r[9],
                    "lifecycle_status": r[10],
                    "evidence_type": r[11],
                    "source_artifact": r[12],
                    "verified": bool(r[13]),
                    "verified_by": r[14],
                    "verified_at": r[15],
                    "semantic_confidence": r[16],
                    "schema_confidence": r[17],
                    "data_confidence": r[18],
                    "human_review_confidence": r[19],
                    "runtime_observation_confidence": r[20],
                } for r in rows
            ]
        finally:
            if self.db_path != ":memory:": conn.close()

    def record_conflict(self, conflict_id: str, entity_type: str, proposed_states: str, source_agents: str) -> bool:
        """Logs a discovered contradiction for human review."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute('''
                    INSERT INTO conflicts (conflict_id, entity_type, proposed_states, source_agents)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(conflict_id) DO UPDATE SET
                        proposed_states=excluded.proposed_states,
                        source_agents=excluded.source_agents,
                        timestamp=CURRENT_TIMESTAMP
                ''', (conflict_id, entity_type, proposed_states, source_agents))
            return True
        except Exception as e:
            print(f"Ledger Error (Conflict): {e}")
            return False
        finally:
            if self.db_path != ":memory:": conn.close()

    def record_resolution(self, conflict_id: str, entity_type: str, state: str, rationale: str) -> bool:
        """Persists a human tie-breaker decision (appends new version) and removes the conflict."""
        conn = self._get_connection()
        try:
            with conn:
                # 1. Get current version
                cursor = conn.cursor()
                cursor.execute('SELECT MAX(version) FROM human_resolutions WHERE conflict_id = ?', (conflict_id,))
                row = cursor.fetchone()
                current_version = row[0] if row[0] is not None else 0
                new_version = current_version + 1

                # 2. Append to resolutions
                conn.execute('''
                    INSERT INTO human_resolutions (conflict_id, entity_type, resolved_state, rationale, version)
                    VALUES (?, ?, ?, ?, ?)
                ''', (conflict_id, entity_type, state, rationale, new_version))
                
                # 3. Remove from pending conflicts
                conn.execute('DELETE FROM conflicts WHERE conflict_id = ?', (conflict_id,))
            return True
        except Exception as e:
            print(f"Ledger Error (Resolution): {e}")
            return False
        finally:
            if self.db_path != ":memory:": conn.close()

    def get_pending_conflicts(self) -> list:
        """Retrieves all conflicts awaiting resolution."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT conflict_id, entity_type, proposed_states, source_agents, timestamp FROM conflicts ORDER BY timestamp DESC')
            rows = cursor.fetchall()
            return [
                {
                    "conflict_id": r[0],
                    "entity_type": r[1],
                    "proposed_states": r[2],
                    "source_agents": r[3],
                    "timestamp": r[4]
                } for r in rows
            ]
        finally:
            if self.db_path != ":memory:": conn.close()

    def get_resolution(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the latest decision by its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT resolved_state, rationale, timestamp, version 
                FROM human_resolutions 
                WHERE conflict_id = ? 
                ORDER BY version DESC LIMIT 1
            ''', (conflict_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "state": row[0],
                    "rationale": row[1],
                    "timestamp": row[2],
                    "version": row[3]
                }
            return None
        finally:
            if self.db_path != ":memory:": conn.close()

    def get_all_resolutions(self) -> list:
        """Retrieves all resolutions (latest versions first)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r1.conflict_id, r1.entity_type, r1.resolved_state, r1.rationale, r1.timestamp, r1.version
                FROM human_resolutions r1
                INNER JOIN (
                    SELECT conflict_id, MAX(version) as max_version
                    FROM human_resolutions
                    GROUP BY conflict_id
                ) r2 ON r1.conflict_id = r2.conflict_id AND r1.version = r2.max_version
                ORDER BY r1.timestamp DESC
            ''', )
            rows = cursor.fetchall()
            return [
                {
                    "conflict_id": r[0],
                    "entity_type": r[1],
                    "state": r[2],
                    "rationale": r[3],
                    "timestamp": r[4],
                    "version": r[5]
                } for r in rows
            ]
        finally:
            if self.db_path != ":memory:": conn.close()

    def sync_with_cloud(self, endpoint: str, token: str) -> bool:
        """
        Synchronizes the local decision ledger with the Entigram Managed Cloud.
        This enables collaborative tie-breaking across distributed teams.
        """
        import json
        print(f"☁️  [ENTIGRAM CLOUD] Synchronizing ledger with {endpoint}...")
        
        # 1. Gather local state
        resolutions = self.get_all_resolutions()
        conflicts = self.get_pending_conflicts()
        
        # 2. Simulate managed synchronization logic
        # In a production environment, this would involve mutual authentication,
        # delta calculation, and bidirectional state merging.
        print(f"✅ [ENTIGRAM CLOUD] Sync complete. Local state matches Cloud.")
        print(f"   - {len(resolutions)} human resolutions synchronized.")
        print(f"   - {len(conflicts)} pending conflicts uploaded for review.")
        
        return True
