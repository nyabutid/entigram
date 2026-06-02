/* 
 * SupplyChain Entigram Schema 
 * Managed by Entigram Federated Architecture
 */

ENTITY: Supplier
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - tax_id (String)
  - rating (Decimal)

ENTITY: Product
ATTRIBUTES:
  - id (UUID, PK)
  - sku (String, UNIQUE)
  - name (String)
  - category (String)

ENTITY: Warehouse
ATTRIBUTES:
  - id (UUID, PK)
  - location_name (String)
  - capacity (Integer)

ENTITY: Inventory_Item
ATTRIBUTES:
  - id (UUID, PK)
  - quantity (Integer)
  - last_updated (DateTime)

RELATIONSHIP: Supplier (1) [MUST] --- [MAY] (MANY) Product
RELATIONSHIP: Warehouse (1) [MUST] --- [MAY] (MANY) Inventory_Item
RELATIONSHIP: Product (1) [MUST] --- [MAY] (MANY) Inventory_Item
