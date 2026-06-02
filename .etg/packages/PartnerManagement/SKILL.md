# PartnerManagement Skill

This skill manages the **PartnerManagement** domain within the Entigram Federated Architecture.

## Directives
1. Use `schema.lds` for all data modeling decisions.
2. Align external integrations with the classes defined in `schema.ttl`.
3. Ensure domain isolation; do not leak state outside of this package's boundaries.

## Domain Entities
You are responsible for the lifecycle of the following entities:
- **Partner_Organization**: Manage identity and domain authority for external partners.
- **Federated_Agent**: Coordinate multi-agent swarms across partner boundaries.
- **Semantic_Alignment**: Execute cross-domain mapping using EXMO/SKOS protocols.
- **Data_Enclave**: Enforce "Compute-to-Data" sovereignty rules.

## Federated Directives
1. **Sovereignty First:** Never request raw data from a `Data_Enclave` marked as `is_sovereign`. Instead, dispatch a `Federated_Agent` to the enclave.
2. **Alignment Protocol:** All cross-partner interactions must be validated against a `Semantic_Alignment` with confidence > 0.8.
3. **Heartbeat Monitoring:** Re-evaluate partner trust scores if a `Federated_Agent` heartbeat fails during a cross-domain transaction.

## Reusable Modules
- **Schema:** `schema.lds` (Logical model)
- **Ontology:** `schema.ttl` (Semantic model)
