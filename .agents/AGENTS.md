<RULE[entigram_handoff]>
# Post-Commit Governance Sequence

When editing Entigram source code or schema files, before handing the turn back to the user or closing out a task, you MUST execute the Expectation Guard Pre-Handoff Gate to anchor your changes. 

Do this by running the following commands in sequence:
1. `python3 -m entigram.cli_runner.etg_cli broker guard`
2. `python3 -m entigram.cli_runner.etg_cli broker deliver`
3. `python3 -m entigram.cli_runner.etg_cli warden lock`

Once complete, commit the modified `.etg/entigram.yaml` delivery snapshot before handing off.
</RULE[entigram_handoff]>
