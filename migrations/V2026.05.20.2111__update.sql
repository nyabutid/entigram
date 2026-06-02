-- Entigram Generated Schema

-- Flyway Versioned Migration

PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS entigram_projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  path TEXT NOT NULL UNIQUE,
  version TEXT,
  current_phase TEXT
);

CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY,
  name TEXT
);

CREATE TABLE IF NOT EXISTS sf_products (
  id TEXT PRIMARY KEY,
  product_code TEXT
);

CREATE TABLE IF NOT EXISTS sf_opportunitylineitems (
  id TEXT PRIMARY KEY,
  quantity REAL
);

CREATE TABLE IF NOT EXISTS entigram_packages (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  type TEXT,
  entigram_project_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id)
);

CREATE TABLE IF NOT EXISTS entigram_agents (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  constraints TEXT,
  directives TEXT,
  package TEXT,
  entigram_package_id TEXT,
  FOREIGN KEY (entigram_package_id) REFERENCES entigram_packages(id)
);

CREATE TABLE IF NOT EXISTS entigram_conflicts (
  id TEXT PRIMARY KEY,
  conflict_id TEXT UNIQUE,
  entity_type TEXT,
  proposed_states TEXT,
  source_agents TEXT,
  timestamp TEXT,
  entigram_project_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id)
);

CREATE TABLE IF NOT EXISTS entigram_resolutions (
  id TEXT PRIMARY KEY,
  conflict_id TEXT,
  entity_type TEXT,
  resolved_state TEXT,
  rationale TEXT,
  version INTEGER,
  timestamp TEXT,
  entigram_project_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id)
);

CREATE TABLE IF NOT EXISTS entigram_alignments (
  id TEXT PRIMARY KEY,
  source_domain TEXT,
  target_domain TEXT,
  source_concept TEXT,
  target_concept TEXT,
  relation TEXT,
  confidence REAL,
  rationale TEXT,
  verified INTEGER,
  entigram_project_id TEXT,
  partner_organization_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id),
  FOREIGN KEY (partner_organization_id) REFERENCES partner_organizations(id)
);

CREATE TABLE IF NOT EXISTS entigram_synonyms (
  id TEXT PRIMARY KEY,
  term TEXT,
  synonym TEXT,
  confidence REAL,
  entigram_project_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id)
);

CREATE TABLE IF NOT EXISTS partner_organizations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  remote_endpoint TEXT,
  trust_level TEXT,
  status TEXT,
  entigram_project_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id)
);

CREATE TABLE IF NOT EXISTS vulnerability_findings (
  id TEXT PRIMARY KEY,
  vulnerability_id TEXT,
  severity TEXT,
  description TEXT,
  detected_at TEXT,
  entigram_package_id TEXT,
  FOREIGN KEY (entigram_package_id) REFERENCES entigram_packages(id)
);

CREATE TABLE IF NOT EXISTS security_bypasses (
  id TEXT PRIMARY KEY,
  vulnerability_id TEXT,
  rationale TEXT,
  authorized_by TEXT,
  authorized_at TEXT,
  entigram_package_id TEXT,
  FOREIGN KEY (entigram_package_id) REFERENCES entigram_packages(id)
);

CREATE TABLE IF NOT EXISTS migrations (
  id TEXT PRIMARY KEY,
  filename TEXT,
  executed_at TEXT,
  entigram_project_id TEXT,
  FOREIGN KEY (entigram_project_id) REFERENCES entigram_projects(id)
);

CREATE TABLE IF NOT EXISTS salesforce_integrations (
  id TEXT PRIMARY KEY,
  sf_org_id TEXT,
  sync_status TEXT,
  last_forecast_date TEXT
);

CREATE TABLE IF NOT EXISTS inventory_forecasts (
  id TEXT PRIMARY KEY,
  product_sku TEXT,
  forecasted_demand INTEGER,
  confidence_interval REAL,
  salesforce_integration_id TEXT,
  FOREIGN KEY (salesforce_integration_id) REFERENCES salesforce_integrations(id)
);

CREATE TABLE IF NOT EXISTS warehouses (
  id TEXT PRIMARY KEY,
  location_name TEXT,
  capacity INTEGER
);

CREATE TABLE IF NOT EXISTS inventory_items (
  id TEXT PRIMARY KEY,
  quantity INTEGER,
  last_updated TEXT,
  warehouse_id TEXT,
  product_id TEXT,
  FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS suppliers (
  id TEXT PRIMARY KEY,
  name TEXT,
  tax_id TEXT,
  rating REAL
);

CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  sku TEXT UNIQUE,
  name TEXT,
  category TEXT,
  supplier_id TEXT,
  supplier_id TEXT,
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);