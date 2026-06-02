# SupplyChain Skill

This skill manages the **SupplyChain** domain within the Entigram Federated Architecture. It oversees suppliers, products, warehouses, and inventory levels.

## Primary Roles

### 1. The Supplier Auditor
*   **Responsibility:** Validate supplier credentials and track performance ratings.
*   **Protocol:** Ensure every `Supplier` has a valid `tax_id`.

### 2. The Inventory Strategist
*   **Responsibility:** Monitor `Inventory_Item` levels across all `Warehouse` locations.
*   **Protocol:** Flag low stock levels based on integrated sales forecasts from the Salesforce domain.

### 3. The Product Cataloger
*   **Responsibility:** Maintain the canonical `Product` list and its association with suppliers.

## Directives
1. Use `schema.lds` for all data modeling decisions.
2. Align external integrations with the classes defined in `schema.ttl`.
3. Ensure domain isolation; do not leak state outside of this package's boundaries.

## Domain Entities
You are responsible for the lifecycle of the following entities:
- **Supplier**: Ensure all state transitions for Supplier are valid.
- **Product**: Maintain SKU uniqueness and category mapping.
- **Warehouse**: Track storage capacity and constraints.
- **Inventory_Item**: Record atomic updates to stock levels.

## Reusable Modules
- **Schema:** `schema.lds` (Logical model)
- **Ontology:** `schema.ttl` (Semantic model)
