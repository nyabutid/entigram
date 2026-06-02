/* 
 * Business Strategy Entigram Schema 
 * Focused on Long-term Planning and KPI Tracking
 */

ENTITY: Strategic_Goal
ATTRIBUTES:
  - id (UUID, PK)
  - statement (String)
  - target_date (Date)
  - priority (Integer)

ENTITY: KPI
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - current_value (Decimal)
  - target_value (Decimal)
  - unit (String)

ENTITY: Revenue_Stream
ATTRIBUTES:
  - id (UUID, PK)
  - source (String) # e.g., Subscription, Licensing
  - type (String) # Recurring, One-time

ENTITY: Cost_Structure
ATTRIBUTES:
  - id (UUID, PK)
  - item (String)
  - frequency (String)
  - estimated_amount (Decimal)

ENTITY: Strategic_Initiative
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - status (String) # Planned, Active, Completed

RELATIONSHIP: Strategic_Goal (1) [MUST] --- [MAY] (MANY) KPI
RELATIONSHIP: Strategic_Goal (1) [MUST] --- [MAY] (MANY) Strategic_Initiative
RELATIONSHIP: Revenue_Stream (1) [MUST] --- [MAY] (MANY) KPI
RELATIONSHIP: Cost_Structure (1) [MUST] --- [MAY] (MANY) Strategic_Initiative
