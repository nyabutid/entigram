# Agent Instructions

Read and follow `.etg/agent_policy.md` before changing this repository.

In short:

1. Run `hydrate`.
2. Use `etg broker preflight --file <path>` and
   `etg broker impact --file <path>` before risky implementation/schema
   changes.
3. Before handoff, run `etg broker handoff`, then `etg broker status`.
4. Do not hand off unless `broker status` reports `Delivery status: current`.
