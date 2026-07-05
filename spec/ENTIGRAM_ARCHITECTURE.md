# Project Entigram: Architectural Context & History

## Origin
Entigram is a federated agent system for enforcing schema-first semantic governance across isolated domains.

## Core Philosophy: Semantic Governance
Entigram does not believe in a single, unified enterprise ontology. It enforces semantic governance across isolated domains:
1.  **Modular Monoliths:** External systems (Salesforce, banking APIs) are treated as black boxes with localized, decoupled ontologies.
2.  **Federated Orchestration:** Edge-agents translate vendor configurations into local domain models. Global agents coordinate across domains but do not merge them.
3.  **Deterministic State:** Unsupported operational concepts and cross-domain contradictions are blocked, proposed, or resolved through an auditable SQLite decision ledger (`entigram_state.db`).
4.  **Verified Alignments:** Discovered mappings are proposals by default. They become operational only after explicit authorization with trusted evidence.

## Data Modeling: The Carlis Methodology
Entigram utilizes the data modeling philosophy of the late John Carlis.
* Before any OWL/RDF ontology is written, the system must be mapped as a plain-text Entigram Schema.
* For "Blank Canvas" domains, the agent must interview the human expert iteratively (one specific cardinality/boundary question at a time) to discover the Schema.

## Architecture Scope
Entigram focuses on closed-world routing, verified semantic alignments, and deterministic conflict handling for agent workflows. Workspaces can model single domains, vendor boundaries, or multi-domain federations while preserving local authority over each schema.

## Competitive Role
Entigram is not intended to replace agent frameworks, MCP, knowledge graphs, or enterprise IAM platforms. It complements them as a semantic governance layer:

```text
Agent framework
  -> Entigram semantic governance
  -> MCP/tools/connectors/databases
  -> enterprise systems
```

Entigram owns the question of semantic validity: which concepts exist, which fields are allowed, which mappings are verified, what state is authoritative, and what happens when domains disagree.
