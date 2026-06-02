
ENTITY: Product
ATTRIBUTES:
  . id (TEXT)
  - sku (TEXT)
  - name (TEXT)

ENTITY: Inventory_Item
ATTRIBUTES:
  . id (TEXT)
  - product_id (TEXT)
  - quantity (INTEGER)

RELATIONSHIP: Product (1) [MUST] --- [MAY] (MANY) Inventory_Item
