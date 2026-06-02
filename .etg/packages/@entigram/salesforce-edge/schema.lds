/* 
 * Salesforce Edge - Full Lead-to-Cash Semantic Mapping
 * This Schema maps the core Sales Cloud domain, concealing the 
 * architectural complexity of the Salesforce vendor system.
 */

[EDGE_BOUNDARY]

ENTITY: SF_User
ATTRIBUTES:
  - id (String, PK)
  - email (String)
  - name (String)
  - is_active (Boolean)

ENTITY: SF_Account
ATTRIBUTES:
  - id (String, PK)
  - name (String)
  - type (String) # Customer - Direct, Customer - Channel, Prospect
  - industry (String)
  - annual_revenue (Decimal)

ENTITY: SF_Contact
ATTRIBUTES:
  - id (String, PK)
  - first_name (String)
  - last_name (String)
  - email (String)
  - phone (String)

ENTITY: SF_Lead
ATTRIBUTES:
  - id (String, PK)
  - company (String)
  - first_name (String)
  - last_name (String)
  - email (String)
  - status (String) # Open, Contacted, Qualified, Unqualified

ENTITY: SF_Opportunity
ATTRIBUTES:
  - id (String, PK)
  - name (String)
  - stage (String) # Prospecting, Qualification, Closed Won, Closed Lost
  - amount (Decimal)
  - close_date (Date)

ENTITY: SF_Product
ATTRIBUTES:
  - id (String, PK)
  - name (String)
  - product_code (String)
  - description (String)

ENTITY: SF_Pricebook
ATTRIBUTES:
  - id (String, PK)
  - name (String)
  - is_active (Boolean)

ENTITY: SF_PricebookEntry
ATTRIBUTES:
  - id (String, PK)
  - unit_price (Decimal)
  - use_standard_price (Boolean)

ENTITY: SF_OpportunityLineItem
ATTRIBUTES:
  - id (String, PK)
  - quantity (Decimal)
  - unit_price (Decimal)
  - total_price (Decimal)

ENTITY: SF_Campaign
ATTRIBUTES:
  - id (String, PK)
  - name (String)
  - status (String)
  - type (String) # Email, Webinar, Conference

/* Relationships & Operational Constraints */

// Ownership & Governance
RELATIONSHIP: SF_User (1) [MUST] --- [MAY] (MANY) SF_Account
RELATIONSHIP: SF_User (1) [MUST] --- [MAY] (MANY) SF_Contact
RELATIONSHIP: SF_User (1) [MUST] --- [MAY] (MANY) SF_Opportunity
RELATIONSHIP: SF_User (1) [MUST] --- [MAY] (MANY) SF_Lead

// Core CRM Web
RELATIONSHIP: SF_Account (1) [MUST] --- [MAY] (MANY) SF_Contact
RELATIONSHIP: SF_Account (1) [MUST] --- [MAY] (MANY) SF_Opportunity

// Product & Pricing Engine (The Complex Moat)
RELATIONSHIP: SF_Product (1) [MUST] --- [MAY] (MANY) SF_PricebookEntry
RELATIONSHIP: SF_Pricebook (1) [MUST] --- [MAY] (MANY) SF_PricebookEntry
RELATIONSHIP: SF_PricebookEntry (1) [MUST] --- [MAY] (MANY) SF_OpportunityLineItem
RELATIONSHIP: SF_Opportunity (1) [MUST] --- [MUST] (MANY) SF_OpportunityLineItem

// Marketing Influence
RELATIONSHIP: SF_Campaign (1) [MUST] --- [MAY] (MANY) SF_Lead
RELATIONSHIP: SF_Campaign (1) [MUST] --- [MAY] (MANY) SF_Opportunity
