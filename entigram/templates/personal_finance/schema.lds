/* 
 * Standard Personal Finance Entigram Schema 
 * Part of the Entigram Federated Architecture
 */

ENTITY: Account
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - institution (String) [EDGE_BOUNDARY]
  - type (String) # e.g., Checking, Savings, Credit
  - currency (String)

ENTITY: Transaction
ATTRIBUTES:
  - id (UUID, PK)
  - amount (Decimal)
  - date (DateTime)
  - description (String)
  - status (String) # Pending, Posted, Flagged

ENTITY: Category
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - budget_limit (Decimal)

ENTITY: Budget
ATTRIBUTES:
  - id (UUID, PK)
  - period (String) # e.g., Monthly_2026_05
  - total_limit (Decimal)

ENTITY: Financial_Goal
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - target_amount (Decimal)
  - deadline (Date)
  - priority (Integer)

RELATIONSHIP: Account (1) [MUST] --- [MAY] (MANY) Transaction
RELATIONSHIP: Category (1) [MUST] --- [MAY] (MANY) Transaction
RELATIONSHIP: Budget (1) [MUST] --- [MAY] (MANY) Category
RELATIONSHIP: Account (1) [MUST] --- [MAY] (MANY) Financial_Goal
