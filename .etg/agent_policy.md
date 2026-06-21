# Entigram Agent Policy

This file is the canonical project policy for all agents working in this
repository. Agent-specific instruction files must point here instead of
duplicating handoff rules.

## Boot Sequence

1. Run `python3 -m entigram.cli_runner.etg_cli hydrate`.
2. Read `.etg/entigram.yaml`, `schema.lds`, and this file.
3. If changing implementation behavior, run impact analysis before editing:
   `python3 -m entigram.cli_runner.etg_cli broker impact --file <path>`.

## Governance Rules

- Treat `schema.lds` as the closed-world contract for entities and attributes.
- Use MCP/CLI tools for governed writes; do not bypass ledger APIs with ad hoc
  SQL or direct state mutation.
- Unknown entities, invented attributes, unverified alignments, and schema drift
  must be rejected or escalated to the human operator.
- Resolve conflicts through `.etg/state.db`.

## Pre-Handoff Gate

Before handing work back after source, schema, ontology, package, or release
changes:

1. Run `make handoff` (this automatically runs `broker guard`, `warden lock`, and `broker deliver`).
2. Run `python3 -m entigram.cli_runner.etg_cli broker status`.

`broker status` must report `Delivery status: current` before handoff.
Do not run `warden lock` after `broker deliver`; `warden lock` mutates
`.etg/entigram.yaml` and immediately invalidates the delivery snapshot.

Commit `.etg/entigram.yaml` only when it changed because a schema or ontology
lock was required.
