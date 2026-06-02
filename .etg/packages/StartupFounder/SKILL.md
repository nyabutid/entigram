# StartupFounder Skill

This skill manages the **StartupFounder** domain within the Entigram Federated Architecture.

## Directives
1. Use `schema.lds` for all data modeling decisions.
2. Align external integrations with the classes defined in `schema.ttl`.
3. Ensure domain isolation; do not leak state outside of this package's boundaries.

## Domain Entities
You are responsible for the lifecycle of the following entities:
- **Idea**: Ensure all state transitions for Idea are valid.
- **Value_Proposition**: Ensure all state transitions for Value_Proposition are valid.
- **Market_Segment**: Ensure all state transitions for Market_Segment are valid.
- **Competitor**: Ensure all state transitions for Competitor are valid.
- **User_Persona**: Ensure all state transitions for User_Persona are valid.

## Reusable Modules
- **Schema:** `schema.lds` (Logical model)
- **Ontology:** `schema.ttl` (Semantic model)
