"""Pure validation and explicit encoding of subagent history isolation.

This module does not grant full-history approval or verify a decision ledger.
The caller must authorize "all" against the current task/run and bind that
override to the adapter, never to persistent registry policy.
"""


def validate_fork_turns(value: str = "none", allow_all: bool = False) -> str:
    """Accept only none, canonical 1..8, or explicitly authorized all.

    Omitted input defaults to none; explicit blank or non-string input fails.
    allow_all is an authorization result supplied by the caller, not evidence.
    """
    if type(allow_all) is not bool:
        raise ValueError("allow_all must be an explicit boolean")
    if not isinstance(value, str):
        raise ValueError("fork_turns must be an explicit string")
    if value == "none" or value in ("1", "2", "3", "4", "5", "6", "7", "8"):
        return value
    if value == "all":
        if allow_all:
            return value
        raise ValueError("fork_turns=all requires a run-bound human-approved override")
    raise ValueError("fork_turns must be none or a canonical string from 1 through 8")


def _validate_control(name: str, schema: dict, value, kind: str) -> None:
    """Validate the supported scalar schema subset without coercion."""
    if not isinstance(schema, dict) or schema.get("type") != kind:
        raise ValueError(f"{name} requires an explicit {kind} schema")
    supported = {"type", "enum", "const", "title", "description", "default"}
    unknown = set(schema) - supported
    if unknown:
        raise ValueError(f"{name} has unsupported schema keywords: {unknown!r}")
    scalar_type = str if kind == "string" else bool
    for annotation in ("title", "description"):
        if annotation in schema and not isinstance(schema[annotation], str):
            raise ValueError(f"{name}.{annotation} must be a string")
    if "default" in schema and type(schema["default"]) is not scalar_type:
        raise ValueError(f"{name}.default must be a {kind}")
    if "enum" in schema:
        choices = schema["enum"]
        if (not isinstance(choices, list) or not choices
                or any(type(choice) is not scalar_type for choice in choices)):
            raise ValueError(f"{name}.enum must be a nonempty list of {kind} values")
        if len(set(choices)) != len(choices):
            raise ValueError(f"{name}.enum must not contain duplicates")
        if value not in choices:
            raise ValueError(f"{name} value is not allowed by enum")
    if "const" in schema:
        if type(schema["const"]) is not scalar_type:
            raise ValueError(f"{name}.const must be a {kind}")
        if value != schema["const"]:
            raise ValueError(f"{name} value is not allowed by const")


def history_arguments(value: str, properties: dict) -> dict:
    """Encode a policy-selected value against runtime schema properties.

    This is an encoder, not an approval gate: callers must authorize "all"
    before calling. Pass the properties mapping, not the whole tool schema.
    Outer schema constraints and runtime behavior remain the caller's concern.

    Supported control schemas have an explicit string/boolean type, optional
    enum/const constraints, and title/description/default annotations. Defaults
    never select history. Other keywords fail closed. Unrelated properties are
    ignored. Inputs are not mutated and no filesystem or runtime is accessed.
    """
    value = validate_fork_turns(value, allow_all=True)
    if not isinstance(properties, dict):
        raise ValueError("runtime properties must be a dict")
    has_turns = "fork_turns" in properties
    has_context = "fork_context" in properties
    if not has_turns and not has_context:
        raise ValueError("runtime has no supported explicit history control")
    arguments = {}
    if has_turns:
        _validate_control("fork_turns", properties["fork_turns"], value, "string")
        arguments["fork_turns"] = value
    if has_context:
        # A boolean cannot encode a bounded window, even alongside fork_turns.
        if value not in ("none", "all"):
            raise ValueError("fork_context cannot represent bounded fork_turns")
        context = value == "all"
        _validate_control("fork_context", properties["fork_context"], context, "boolean")
        arguments["fork_context"] = context
    return arguments
