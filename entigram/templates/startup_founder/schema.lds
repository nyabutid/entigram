/* 
 * Startup Founder Entigram Schema 
 * Focused on Idea Validation and Product-Market Fit
 */

ENTITY: Idea
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - description (String)
  - problem_statement (String)

ENTITY: Value_Proposition
ATTRIBUTES:
  - id (UUID, PK)
  - core_benefit (String)
  - differentiator (String)

ENTITY: Market_Segment
ATTRIBUTES:
  - id (UUID, PK)
  - target_audience (String)
  - estimated_size (String)

ENTITY: Competitor
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - strengths (String)
  - weaknesses (String)

ENTITY: User_Persona
ATTRIBUTES:
  - id (UUID, PK)
  - role (String)
  - goals (String)
  - pain_points (String)

RELATIONSHIP: Idea (1) [MUST] --- [MUST] (1) Value_Proposition
RELATIONSHIP: Idea (1) [MUST] --- [MAY] (MANY) Market_Segment
RELATIONSHIP: Idea (1) [MUST] --- [MAY] (MANY) Competitor
RELATIONSHIP: Market_Segment (1) [MUST] --- [MAY] (MANY) User_Persona
