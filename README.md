# Entigram: The Semantic Governance Layer for Enterprise Agents

**Entigram** is a schema-first control plane for enterprise agents that grounds agent behavior in verified domain models, approved semantic alignments, and auditable state transitions.

It provides the infrastructure to build **constrained autonomy**, ensuring that agents operate across fragmented enterprise systems without inventing fields, joins, entities, or state transitions.

## 🎯 The Entigram Thesis

Enterprise agent adoption fails when agents lack trustworthy domain context and enforceable schema boundaries. Entigram addresses this by sitting between your agents and your enterprise state.

> **Defensible Grounding:** Entigram prevents unsupported concepts and unverified mappings from entering operational agent workflows.

## 🛠️ Key Capabilities

- **Domain Boundaries (Schema):** Force agents to operate against explicit Entigram Schemas rather than vague natural-language context.
- **Closed-World Reasoning:** Automatically reject or quarantine unknown entities, attributes, and relationships.
- **Verified Semantic Alignments:** Enable cross-domain data federation using approved mappings instead of fuzzy LLM guesses.
- **Deterministic Conflict Handling:** Transform contradictory agent states into auditable ledger entries for human or policy-driven resolution.
- **Agent Hydration:** Boot agents with exact project state, schemas, alignments, and settled decisions.
- **Auditability:** Store every alignment and decision in a local SQLite ledger for full provenance and governance.

## 🚀 Quickstart

### 1. Initialize a Governance Workspace
```bash
python3 -m entigram.cli_runner.etg_cli init --dir my-governed-agent
cd my-governed-agent
```

### 2. Define your Schema Contracts (Schema)
Create a `schema.lds` to define the entities and relationships your agents are allowed to "know."
```bash
ENTITY: Supplier
ATTRIBUTES:
  - .id (UUID)
  - name (String)
  - tax_id (String)
```

### 3. Hydrate and Launch
Align your agent's state vector with your local domain models:
```bash
python3 -m entigram.cli_runner.etg_cli agent --engine Antigravity
```

## 🏗️ How it Fits

Entigram is not an orchestration framework, MCP replacement, graph database, or IAM product. It is the **semantic governance layer** that complements those systems by providing:

1. **Schema Discipline:** Validating agent inputs/outputs against a strict Schema.
2. **Alignment Gates:** Ensuring cross-system joins (e.g., Salesforce Opportunity to Warehouse SKU) use verified mappings.
3. **Decision Ledger:** Providing a persistent, auditable record of state transitions.

```text
Agent framework
  -> Entigram semantic governance
  -> MCP/tools/connectors/databases
  -> enterprise systems
```

| Existing Layer | Examples | Entigram's Role |
| --- | --- | --- |
| Agent orchestration | LangGraph, CrewAI, OpenAI Agents SDK, Microsoft Agent Framework | Validate domain state, mappings, payloads, and handoffs before agents act |
| Tool and data access | MCP, API tools, enterprise connectors | Govern tool schemas and block unsupported concepts or unverified mappings |
| Knowledge and context | RAG, GraphRAG, Neo4j, Stardog, data.world, LlamaIndex | Operationalize only verified concepts, relationships, and alignments |
| Runtime governance | RunAgents, Okta, policy engines, approval systems | Supply semantic policy signals and provenance for tool/action decisions |
| Observability | Tracing, OpenTelemetry, agent logs | Add semantic provenance: schema, alignment, evidence, conflict, and decision IDs |

## 🔒 Operational Principle

Discovery creates proposals, not operational facts.

Agents and routers may suggest alignments from schema similarity, partner data, or field names, but those proposals do not drive cross-domain joins until they are explicitly authorized with trusted evidence.

## 📈 Best-Fit Use Cases

- **Partner Reconciliation:** Normalizing and aligning external supplier data with internal systems.
- **Cross-Domain Integration:** Linking CRM data (Salesforce) to supply-chain or inventory forecasting.
- **Regulated Data Extraction:** Clinical/EHR extraction with strict validation and conflict gates.
- **Governance for Multi-Agent Ops:** Auditing the "handoff" state between different specialized agents.

## ⚖️ License

Entigram Core is Open Source under the Apache License 2.0.

---
*Entigram: Grounding agentic autonomy in enterprise reality.*
