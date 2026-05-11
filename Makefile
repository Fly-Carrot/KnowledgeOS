SMOKE_TASK ?= KOS-T008

.PHONY: doctor doctor-summary route tools dispatch guard migrate-plan reset-dry-run scenarios test smoke

doctor:
	./bin/knowledgeos doctor --root . --project-root .

doctor-summary:
	./bin/knowledgeos doctor --root . --project-root . --summary

route:
	./bin/knowledgeos route-task --project-root . --task-id $(SMOKE_TASK)

tools:
	./bin/knowledgeos tool-registry --project-root . --check-paths

dispatch:
	./bin/knowledgeos dispatch-task --project-root . --task-id $(SMOKE_TASK)

guard:
	./bin/knowledgeos check-route-write --project-root . --task-id $(SMOKE_TASK) --path docs/route-bound-execution-guard.md

migrate-plan:
	./bin/knowledgeos migrate-legacy-project --project-root . --write-plan --dry-run

reset-dry-run:
	./bin/knowledgeos reset-project --project-root . --mode soft --dry-run

scenarios:
	./examples/scenarios/run_guardrail_scenarios.sh

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v

smoke: doctor-summary route tools dispatch guard scenarios test
