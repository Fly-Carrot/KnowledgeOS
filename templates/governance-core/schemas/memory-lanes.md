# Memory Lanes

The minimal kernel provides these memory lanes:

- `decision-log.ndjson`: durable decisions and rationale;
- `handoffs.ndjson`: continuation state for the next agent;
- `open-loops.ndjson`: unresolved questions and blockers;
- `promoted-learnings.ndjson`: stable reusable learnings;
- `user-question-profiles.ndjson`: distilled user preference/profile updates.

These files are structured ledgers, not raw chat archives.
