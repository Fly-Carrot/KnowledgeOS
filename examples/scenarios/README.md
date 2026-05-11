# KnowledgeOS Scenarios

These scenarios are executable guardrail probes. They create isolated temporary KnowledgeOS runtimes and projects, then simulate mistakes that a distracted agent might make.

Run all current scenarios:

```bash
./examples/scenarios/run_guardrail_scenarios.sh
```

The runner prints checkpoint blocks. A checkpoint passes only when the OS guard returns the expected status code and evidence.
