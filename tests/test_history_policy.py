"""Regression tests for explicit, fail-closed subagent history controls."""

import copy
import unittest

from knowledgeos.history_policy import history_arguments, validate_fork_turns


class ValidateForkTurnsTests(unittest.TestCase):
    def test_default_is_none(self):
        self.assertEqual(validate_fork_turns(), "none")

    def test_canonical_local_policy(self):
        for value in ("none", *(str(i) for i in range(1, 9))):
            with self.subTest(value=value):
                self.assertEqual(validate_fork_turns(value), value)

    def test_full_history_requires_explicit_boolean_opt_in(self):
        with self.assertRaises(ValueError):
            validate_fork_turns("all")
        self.assertEqual(validate_fork_turns("all", allow_all=True), "all")
        for flag in (None, 0, 1, "true", "false", [], {}):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                validate_fork_turns("all", allow_all=flag)

    def test_rejects_noncanonical_and_nonstring_values(self):
        values = (
            "", " ", "\n", "0", "9", "10", "01", "08", "-1", "+1",
            "1.0", "1e0", " 1", "1 ", "1\n", "NONE", "All", "all ",
            "\u0661", "\uff11", "9" * 10000, None, False, True, 1, 8.0,
            b"none", [], {},
        )
        for value in values:
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                validate_fork_turns(value, allow_all=True)


class HistoryArgumentsTests(unittest.TestCase):
    def test_string_control_is_always_explicit(self):
        properties = {"fork_turns": {"type": "string"}}
        for value in ("none", "all", *(str(i) for i in range(1, 9))):
            with self.subTest(value=value):
                self.assertEqual(history_arguments(value, properties), {"fork_turns": value})

    def test_boolean_control_is_explicit_and_exact(self):
        properties = {"fork_context": {"type": "boolean"}}
        for value, expected in (("none", False), ("all", True)):
            result = history_arguments(value, properties)
            self.assertEqual(result, {"fork_context": expected})
            self.assertIs(result["fork_context"], expected)

    def test_boolean_control_never_widens_bounded_history(self):
        for i in range(1, 9):
            with self.subTest(turns=i), self.assertRaises(ValueError):
                history_arguments(str(i), {"fork_context": {"type": "boolean"}})

    def test_dual_controls_are_both_explicit_and_consistent(self):
        properties = {
            "fork_turns": {"type": "string"},
            "fork_context": {"type": "boolean"},
        }
        for value, expected in (("none", False), ("all", True)):
            self.assertEqual(history_arguments(value, properties), {
                "fork_turns": value, "fork_context": expected,
            })
        for i in range(1, 9):
            with self.subTest(turns=i), self.assertRaises(ValueError):
                history_arguments(str(i), properties)

    def test_enum_membership_is_enforced_for_each_control(self):
        cases = (
            ("fork_turns", "string", "none", "all"),
            ("fork_context", "boolean", False, True),
        )
        for name, kind, isolated, shared in cases:
            with self.subTest(name=name):
                properties = {name: {"type": kind, "enum": [isolated]}}
                self.assertEqual(history_arguments("none", properties), {name: isolated})
                with self.assertRaises(ValueError):
                    history_arguments("all", properties)
                properties[name]["enum"] = [shared]
                with self.assertRaises(ValueError):
                    history_arguments("none", properties)

    def test_const_is_enforced(self):
        for name, kind, value in (("fork_turns", "string", "none"),
                                  ("fork_context", "boolean", False)):
            with self.subTest(name=name):
                properties = {name: {"type": kind, "const": value}}
                self.assertEqual(history_arguments("none", properties), {name: value})
                with self.assertRaises(ValueError):
                    history_arguments("all", properties)

    def test_rejects_missing_or_malformed_properties(self):
        for properties in (None, [], "", False, {}, {"prompt": {"type": "string"}},
                           {"type": "object", "properties": {"fork_turns": {"type": "string"}}}):
            with self.subTest(properties=properties), self.assertRaises(ValueError):
                history_arguments("none", properties)

    def test_rejects_malformed_control_schemas(self):
        for name, kind, wrong in (("fork_turns", "string", "boolean"),
                                   ("fork_context", "boolean", "string")):
            for schema in (None, False, True, [], "", {}, {"type": wrong},
                           {"type": [kind]}, {"type": [kind, "null"]},
                           {"enum": ["none"]}):
                with self.subTest(name=name, schema=schema), self.assertRaises(ValueError):
                    history_arguments("none", {name: schema})

    def test_rejects_malformed_enums_not_python_truthiness(self):
        for name, kind, enums in (
            ("fork_turns", "string", (None, [], "none", ("none",), [None],
                                        ["none", 1], ["none", "none"])),
            ("fork_context", "boolean", (None, [], False, [0], [1], [False, 0],
                                            [False, None], [False, False])),
        ):
            for enum in enums:
                with self.subTest(name=name, enum=enum), self.assertRaises(ValueError):
                    history_arguments("none", {name: {"type": kind, "enum": enum}})

    def test_rejects_malformed_consts_and_annotations(self):
        for name, kind, wrong in (("fork_turns", "string", False),
                                   ("fork_context", "boolean", 0)):
            for annotation, value in (("const", wrong), ("default", wrong),
                                      ("description", None), ("title", [])):
                with self.subTest(name=name, annotation=annotation), self.assertRaises(ValueError):
                    history_arguments("none", {name: {"type": kind, annotation: value}})

    def test_unknown_constraints_are_not_silently_ignored(self):
        constraints = {
            "pattern": "^all$", "minLength": 1, "maxLength": 3,
            "anyOf": [{"const": "none"}], "oneOf": [], "allOf": [],
            "not": {"const": "none"}, "$ref": "#/definitions/history",
            "if": {}, "then": {}, "else": {}, "nullable": True,
            "x-history-policy": "inherit", "format": "history",
        }
        for name, kind in (("fork_turns", "string"), ("fork_context", "boolean")):
            for key, value in constraints.items():
                with self.subTest(name=name, key=key), self.assertRaises(ValueError):
                    history_arguments("none", {name: {"type": kind, key: value}})

    def test_other_control_cannot_hide_invalid_or_conflicting_schema(self):
        for schema in (None, {"type": "string"}, {"type": "boolean", "enum": [True]},
                       {"type": "boolean", "const": True}, {"type": "boolean", "not": {}}):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                history_arguments("none", {
                    "fork_turns": {"type": "string"}, "fork_context": schema,
                })
        with self.assertRaises(ValueError):
            history_arguments("none", {
                "fork_turns": {"type": "string", "enum": ["all"]},
                "fork_context": {"type": "boolean"},
            })

    def test_defaults_never_replace_explicit_isolation_and_inputs_are_unchanged(self):
        properties = {
            "fork_turns": {"type": "string", "default": "all", "title": "History",
                           "description": "History selection", "enum": ["none", "all"]},
            "fork_context": {"type": "boolean", "default": True},
            "prompt": {"type": "string", "minLength": 1},
        }
        before = copy.deepcopy(properties)
        result = history_arguments("none", properties)
        self.assertEqual(result, {"fork_turns": "none", "fork_context": False})
        self.assertEqual(properties, before)
        result["fork_turns"] = "all"
        self.assertEqual(history_arguments("none", properties)["fork_turns"], "none")

    def test_schema_cannot_expand_local_bounded_policy(self):
        properties = {"fork_turns": {"type": "string", "enum": ["9", "01", "none"]}}
        for value in ("9", "01", "", None, 1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                history_arguments(value, properties)


if __name__ == "__main__":
    unittest.main()
