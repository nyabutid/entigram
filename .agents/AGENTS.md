<RULE[entigram_handoff]>
# Pre-Handoff Governance Sequence

When editing Entigram source code or schema files, before handing the turn back to the user or closing out a task, you MUST execute the Expectation Guard Pre-Handoff Gate and leave the delivery state current.

Run these commands in this order:
1. `python3 -m entigram.cli_runner.etg_cli broker guard`
2. If `schema.lds`, `schema.ttl`, `draft_schema.lds`, `draft_schema.ttl`, or other governed ontology/schema artifacts changed, run `python3 -m entigram.cli_runner.etg_cli warden lock`
3. `python3 -m entigram.cli_runner.etg_cli broker deliver`
4. `python3 -m entigram.cli_runner.etg_cli broker status`

`broker status` must report `Delivery status: current` before handoff. Do not run `warden lock` after `broker deliver`; it mutates `.etg/entigram.yaml` and immediately invalidates the delivery snapshot. Commit `.etg/entigram.yaml` only when it changed because a schema/ontology lock was required.
</RULE[entigram_handoff]>
