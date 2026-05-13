# Acceptance Criteria

- kernel responsibilities stay small and explicit
- route remains a policy guard rather than a heavyweight workflow engine
- modules are pluggable and project-profile driven
- apps read OS state and do not become required kernel
- every major operational step can emit TRACE_OK
- every lifecycle phase emits CHECKPOINT_OK
- every capability call emits CAPABILITY_OK
- no command evidence means no success claim
