/* 
   Entigram Engine Self-Model
   Mental model of the Entigram project structure as of Phase 3 (Macro Deployment).
   STATUS: Phase 3 Federated Routing and Multi-Partner Alignment VERIFIED.
*/

ENTITY: Entigram_Project
ATTRIBUTES:
  - .id (UUID)
  - name (String, MUST)
  - path (String, MUST, UNIQUE)
  - version (String)
  - current_phase (String) # Phase 3: Macro Deployment

/* Verified Phase 3 Domains */

ENTITY: Idea
ATTRIBUTES:
  - .id (UUID)
  - name (String)

ENTITY: SF_Product
ATTRIBUTES:
  - .id (UUID)
  - product_code (String)

ENTITY: SF_OpportunityLineItem
ATTRIBUTES:
  - .id (UUID)
  - quantity (Decimal)

ENTITY: Entigram_Package
ATTRIBUTES:
  - .id (UUID)
  - name (String, MUST, UNIQUE)
  - description (String)
  - type (String) # Infrastructure, SaaS, Clinical, Governance, PartnerLink

ENTITY: Entigram_Agent
ATTRIBUTES:
  - .id (UUID)
  - role (String, MUST)
  - constraints (Text)
  - directives (Text)
  - handoff_policy (Text)
  - default_proof_policy (Text)
  - proof_capabilities (Text) # comma-separated: test_run, command_output, human_review, artifact_review
  - package (String) [EXTERNAL: Entigram_Package.name]

ENTITY: Entigram_Conflict
ATTRIBUTES:
  - .id (UUID)
  - conflict_id (String, UNIQUE)
  - entity_type (String)
  - proposed_states (JSON)
  - source_agents (JSON)
  - timestamp (DateTime)

ENTITY: Entigram_Resolution
ATTRIBUTES:
  - .id (UUID)
  - conflict_id (String)
  - entity_type (String)
  - resolved_state (JSON)
  - rationale (Text)
  - version (Integer)
  - timestamp (DateTime)

ENTITY: Entigram_Alignment
ATTRIBUTES:
  - .id (UUID)
  - source_domain (String)
  - target_domain (String)
  - source_concept (String)
  - target_concept (String)
  - relation (String) # e.g., skos:exactMatch
  - confidence (Float)
  - lifecycle_status (String) # Proposed, Reviewed, Verified, Deprecated, Rejected
  - evidence_type (String) # schema_match, sample_data_match, human_review, integration_test
  - source_artifact (String)
  - semantic_confidence (Float)
  - schema_confidence (Float)
  - data_confidence (Float)
  - human_review_confidence (Float)
  - runtime_observation_confidence (Float)
  - rationale (Text)
  - verified (Boolean) # Set to true only after trusted evidence review
  - verified_by (String)
  - verified_at (DateTime)

ENTITY: Ontology_Concept
ATTRIBUTES:
  - .id (UUID)
  - domain (String, MUST)
  - name (String, MUST)
  - concept_type (String) # Entity, Attribute, Relationship, Alignment
  - lifecycle_status (String) # Proposed, Reviewed, Verified, Deprecated, Rejected
  - source (String)
  - owner (String)
  - verified_by (String)
  - verified_at (DateTime)

ENTITY: Entigram_Agent_Proposal
ATTRIBUTES:
  - .id (UUID)
  - agent_id (String)
  - affected_domain (String)
  - proposed_change (JSON)
  - rationale (Text)
  - supporting_evidence (JSON)
  - expected_benefit (Text)
  - rollback_plan (Text)
  - lifecycle_status (String) # Proposed, Reviewed, Verified, Deprecated, Rejected
  - timestamp (DateTime)

ENTITY: Entigram_Expectation
ATTRIBUTES:
  - .id (UUID)
  - name (String, MUST, UNIQUE)
  - owner (String)
  - developer_expectation (Text, MUST)
  - implementation_rule (Text, MUST)
  - validation_check (String, MUST)
  - priority (String) # Critical, High, Medium, Low
  - lifecycle_status (String) # Proposed, Active, Satisfied, Blocked, Superseded, Deprecated
  - created_at (DateTime)
  - updated_at (DateTime)

ENTITY: Entigram_Delivery_Evidence
ATTRIBUTES:
  - .id (UUID)
  - evidence_type (String) # test_run, command_output, artifact_review, human_review, runtime_observation
  - artifact_ref (String, MUST)
  - command (String)
  - result_summary (Text)
  - passed (Boolean)
  - observed_at (DateTime)

ENTITY: Entigram_Delivery_Evaluation
ATTRIBUTES:
  - .id (UUID)
  - status (String) # Accepted, Needs_Work, Blocked, Rejected
  - score (Float)
  - findings (JSON)
  - residual_risk (Text)
  - evaluated_by (String)
  - evaluated_at (DateTime)

ENTITY: Entigram_Improvement_Proposal
ATTRIBUTES:
  - .id (UUID)
  - title (String, MUST)
  - affected_model (String, MUST)
  - proposed_change (JSON, MUST)
  - rationale (Text, MUST)
  - expected_benefit (Text)
  - lifecycle_status (String) # Proposed, Reviewed, Implemented, Rejected, Deprecated
  - created_by (String)
  - created_at (DateTime)

ENTITY: Entigram_Learning
ATTRIBUTES:
  - .id (UUID)
  - source_task (String)
  - lesson (Text, MUST)
  - reusable_rule (Text)
  - confidence (Float)
  - lifecycle_status (String) # Proposed, Active, Superseded, Deprecated
  - observed_at (DateTime)

ENTITY: Entigram_Grounding_Rule
ATTRIBUTES:
  - .id (UUID)
  - domain (String)
  - rule_type (String) # closed_world, require_verified_alignment, quarantine_unknown_field
  - severity (String) # Advisory, Warning, Blocking
  - enabled (Boolean)
  - rationale (Text)

ENTITY: Entigram_Negative_Constraint
ATTRIBUTES:
  - .id (UUID)
  - source_concept (String)
  - target_concept (String)
  - relation (String) # e.g., skos:notExactMatch
  - condition (Text)
  - rationale (Text)
  - lifecycle_status (String)
  - verified_by (String)
  - verified_at (DateTime)

ENTITY: Entigram_Synonym
ATTRIBUTES:
  - .id (UUID)
  - term (String)
  - synonym (String)
  - confidence (Float)

ENTITY: Partner_Organization
ATTRIBUTES:
  - .id (UUID)
  - name (String, MUST, UNIQUE)
  - remote_endpoint (String)
  - trust_level (String)
  - status (String) # Active, Pending, Terminated

ENTITY: Vulnerability_Finding
ATTRIBUTES:
  - .id (UUID, PK)
  - vulnerability_id (String)
  - severity (String)
  - description (String)
  - detected_at (DateTime)

ENTITY: Security_Bypass
ATTRIBUTES:
  - .id (UUID, PK)
  - vulnerability_id (String)
  - rationale (String)
  - authorized_by (String)
  - authorized_at (DateTime)

ENTITY: Migration
ATTRIBUTES:
  - .id (UUID, PK)
  - filename (String)
  - executed_at (DateTime)

/* Federated Domain Mappings (Phase 3) */

ENTITY: Salesforce_Integration
ATTRIBUTES:
  - .id (UUID)
  - sf_org_id (String)
  - sync_status (String)
  - last_forecast_date (DateTime)

ENTITY: Inventory_Forecast
ATTRIBUTES:
  - .id (UUID)
  - product_sku (String)
  - forecasted_demand (Integer)
  - confidence_interval (Float)

ENTITY: Entigram_Delivery_Snapshot
ATTRIBUTES:
  - .id (UUID)
  - snapshot_id (String, MUST, UNIQUE)
  - expectation_count (Integer)
  - missing_proof_count (Integer)
  - schema_hash (String) # First 16 chars of SHA-256 for drift detection
  - agent_id (String)
  - warden_status (String) # intact, tampered
  - evidence_ids (JSON) # list of delivery_evidence row IDs covered
  - artifact_ids (JSON) # list of Entigram_Artifact ledger row IDs covered
  - metadata (JSON)
  - snapped_at (DateTime)

ENTITY: Entigram_Artifact
ATTRIBUTES:
  - .id (UUID)
  - path (String, MUST)
  - artifact_role (String) # schema_contract, ontology_contract, delivery_artifact, evidence_artifact, local_artifact, external_reference
  - sha256 (String)
  - size_bytes (Integer)
  - content_type (String)
  - source_ref (String) # optional URI, local path, or external system reference
  - captured_at (DateTime)

ENTITY: Entigram_Delivery_Drift
ATTRIBUTES:
  - .id (UUID)
  - snapshot_id (String, MUST)
  - artifact_path (String)
  - drift_status (String) # current, changed, missing, unanchored, missing_record
  - previous_sha256 (String)
  - current_sha256 (String)
  - recommendation (String)
  - observed_at (DateTime)

RELATIONSHIPS:
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Package
- Entigram_Package (1) [MUST] --- [MAY] (MANY) Entigram_Agent
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Conflict
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Resolution
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Alignment
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Synonym
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Ontology_Concept
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Agent_Proposal
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Expectation
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Learning
- Entigram_Agent (1) [MUST] --- [MAY] (MANY) Entigram_Delivery_Evidence
- Entigram_Expectation (1) [MUST] --- [MAY] (MANY) Entigram_Delivery_Evidence
- Entigram_Expectation (1) [MUST] --- [MAY] (MANY) Entigram_Delivery_Evaluation
- Entigram_Expectation (1) [MUST] --- [MAY] (MANY) Entigram_Improvement_Proposal
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Grounding_Rule
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Negative_Constraint
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Partner_Organization
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Migration
- Entigram_Package (1) [MUST] --- [MAY] (MANY) Vulnerability_Finding
- Entigram_Package (1) [MUST] --- [MAY] (MANY) Security_Bypass
- Partner_Organization (1) [MUST] --- [MAY] (MANY) Entigram_Alignment
- Salesforce_Integration (1) [MUST] --- [MAY] (MANY) Inventory_Forecast
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Delivery_Snapshot
- Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Artifact
- Entigram_Delivery_Snapshot (1) [MUST] --- [MAY] (MANY) Entigram_Artifact
- Entigram_Delivery_Snapshot (1) [MUST] --- [MAY] (MANY) Entigram_Delivery_Drift

/* Phase 3 Macro Chain (Federated) */
- Idea (1) --- (1) Partner_Organization [ALIGN: Idea.id == Partner_Organization.id]
- Partner_Organization (1) --- (1) Supplier [ALIGN: Partner_Organization.id == Supplier.id]
- Product (1) --- (1) SF_Product [ALIGN: Product.sku == SF_Product.product_code]
- SF_Product (1) --- (MANY) SF_OpportunityLineItem

ENTITY: Warehouse
ATTRIBUTES:
  - .id (UUID)
  - location_name (String)
  - capacity (Integer)

ENTITY: Inventory_Item
ATTRIBUTES:
  - .id (UUID)
  - quantity (Integer)
  - last_updated (DateTime)

ENTITY: Supplier
ATTRIBUTES:
  - .id (UUID, PK)
  - name (String)
  - tax_id (String)
  - rating (Decimal)

ENTITY: Product
ATTRIBUTES:
  - .id (UUID, PK)
  - sku (String, UNIQUE)
  - name (String)
  - category (String)
  - supplier_id (UUID) [EXTERNAL: Supplier.id]

RELATIONSHIPS:
- Warehouse (1) [MUST] --- [MAY] (MANY) Inventory_Item
- Product (1) [MUST] --- [MAY] (MANY) Inventory_Item
- Supplier (1) [MUST] --- [MAY] (MANY) Product

EXPECTATION: Entigram Self-Improvement Loop {
  developer_expectation: Entigram should use its own model to make Entigram stronger, more useful, and easier for agents to deliver against.
  implementation_rule: Changes to Entigram behavior, governance, or schema must preserve a modeled expectation, evidence path, evaluation result, or improvement proposal.
  validation_check: python -m unittest tests.test_entigram_self_improvement_model
  proof: python -m unittest tests.test_entigram_self_improvement_model
}

EXPECTATION: Agent Delivery Proof {
  developer_expectation: Agents should hand off only after the requested outcome, validation evidence, and residual risks are visible.
  implementation_rule: Every material agent delivery should be traceable to Entigram_Expectation and Entigram_Delivery_Evidence, with Entigram_Delivery_Evaluation used when quality or risk must be judged.
  validation_check: python -m unittest tests.test_entigram_self_improvement_model
  proof: python -m unittest tests.test_entigram_self_improvement_model
}

/* Updated: 2026-05-20 Headless Antigravity engine execution via stdin piping support added */
/* Updated: 2026-06-04 Entigram self-improvement loop modeled with expectations, evidence, evaluations, proposals, and learnings */
/* Updated: 2026-06-04 Commissioner companion features: Entigram_Delivery_Snapshot, Blocked lifecycle, proof_capabilities, improvement proposals */
/* Updated: 2026-06-04 Artifact-centered delivery snapshots for source-control-neutral workspaces */
/* Updated: 2026-06-04 Delivery drift status modeled as a read-only recommission signal */
