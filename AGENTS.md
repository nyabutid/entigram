# Agent Instructions

Read and follow `.etg/agent_policy.md` before changing this repository.

In short:

1. Run `python3 -m entigram.cli_runner.etg_cli hydrate`.
2. Use `python3 -m entigram.cli_runner.etg_cli broker impact --file <path>`
   before risky implementation/schema changes.
3. Before handoff, run `broker guard`, optional `warden lock` for governed
   schema/ontology changes, `broker deliver`, then `broker status`.
4. Do not hand off unless `broker status` reports `Delivery status: current`.
