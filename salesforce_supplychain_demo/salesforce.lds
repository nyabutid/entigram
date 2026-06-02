
ENTITY: SF_Product
ATTRIBUTES:
  . id (TEXT)
  - name (TEXT)
  - product_code (TEXT)

ENTITY: SF_OpportunityLineItem
ATTRIBUTES:
  . id (TEXT)
  - product_id (TEXT)
  - quantity (INTEGER)

RELATIONSHIP: SF_Product (1) [MUST] --- [MAY] (MANY) SF_OpportunityLineItem
