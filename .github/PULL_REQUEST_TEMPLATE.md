## Entigram Pull Request

### Stack Physics Verification
Please confirm that your changes adhere to Entigram's Stack Physics by checking the boxes below:

- [ ] **No Customer Data:** I have verified that this PR does not introduce customer-specific instances, demo data (e.g. Acme Corp), or PII into standard packages.
- [ ] **Strict Abstraction:** If modifying a standard package in the core `packages/` directory, the changes are universally applicable and abstract. Specific customer implementations or demos belong in isolated workspaces (`.etg/packages/`).
- [ ] **Sentinel Scanned:** I have run the governance scanner (`python3 -m entigram.cli_runner.etg_cli broker scan`) and resolved any new vulnerabilities, specifically checking for `SNTNL-RULE-004` (Polluted Core) and `SNTNL-RULE-005` (Standard Package Pollution).
- [ ] **LDS First:** All ontology or code generation changes were preceded by John Carlis-style Logical Data Structure (`schema.lds`) updates.