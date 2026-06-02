
<!-- ENTIGRAM_START -->
# Entigram Agent Context
You are an edge-agent operating within a Entigram Federated Architecture.

## Workspace Context
- **Manifest:** Read `.etg/entigram.yaml` for project metadata and active packages.
- **Packages:** SupplyChain
- **Decisions Ledger:** Contradictions must be resolved via the human tie-breaker ledger at `.etg/entigram_state.db`.

## Primary Directives
1. **Schema First:** Never generate code or ontologies before an Entigram Schema is defined in `schema.lds`.
2. **Persistence:** You MUST maintain a local `draft_schema.lds` file. Update it after EVERY turn.
3. Broker Interaction: Use the Entigram Broker CLI for cross-domain orchestration:
   - **Check Decisions:** `python3 -m entigram.cli_runner.etg_cli broker check --id [CONFLICT_ID]`
   - **Record Proposals:** `python3 -m entigram.cli_runner.etg_cli broker decide --id [ID] --type [ENTITY] --state [STATE] --rationale [WHY]`
   - **Report Conflicts:** `python3 -m entigram.cli_runner.etg_cli broker conflict --id [ID] --type [ENTITY] --states [JSON_STATES] --agent [AGENT_ID]`
   - **Align Domains:** `python3 -m entigram.cli_runner.etg_cli broker align --src_dom [DOM] --tgt_dom [DOM] --src_con [CON] --tgt_con [CON] --rat [WHY]`
   - **Validate Model:** `python3 -m entigram.cli_runner.etg_cli broker validate`

4. **Domain Isolation:** Treat external systems as black boxes.
5. **Decisions:** If you encounter a state conflict, propose a resolution via the Broker and wait for human approval in the ledger.

## Active Package Instructions
- **Package Skills:** You MUST read the `SKILL.md` file for each active package to understand your specific roles and protocols.
<!-- ENTIGRAM_END -->
