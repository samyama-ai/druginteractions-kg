"""Tests for shared Cypher helpers."""

import pytest
from etl.helpers import _escape, _q, _prop_str, Registry, ProgressReporter


class TestEscape:
    def test_plain_string(self):
        assert _escape("hello") == "hello"

    def test_single_quote(self):
        assert _escape("it's") == "it\\'s"

    def test_double_quote(self):
        assert _escape('say "hi"') == 'say \\"hi\\"'

    def test_backslash(self):
        assert _escape("a\\b") == "a\\\\b"

    def test_non_string_passthrough(self):
        assert _escape(42) == "42"

    def test_combined(self):
        assert _escape("it's a \"test\"\\n") == "it\\'s a \\\"test\\\"\\\\n"


class TestQ:
    def test_none(self):
        assert _q(None) == "null"

    def test_bool_true(self):
        assert _q(True) == "true"

    def test_bool_false(self):
        assert _q(False) == "false"

    def test_int(self):
        assert _q(42) == "42"

    def test_float(self):
        assert _q(3.14) == "3.14"

    def test_string(self):
        assert _q("hello") == "'hello'"

    def test_string_with_quotes(self):
        assert _q("it's") == "'it\\'s'"


class TestPropStr:
    def test_empty(self):
        assert _prop_str({}) == "{}"

    def test_single_string(self):
        assert _prop_str({"name": "aspirin"}) == "{name: 'aspirin'}"

    def test_mixed_types(self):
        result = _prop_str({"name": "aspirin", "score": 0.95, "active": True})
        assert "name: 'aspirin'" in result
        assert "score: 0.95" in result
        assert "active: true" in result

    def test_none_values_skipped(self):
        result = _prop_str({"name": "aspirin", "cas": None})
        assert "cas" not in result
        assert "name: 'aspirin'" in result


class TestRegistry:
    def test_default_empty(self):
        reg = Registry()
        assert len(reg.drugs) == 0
        assert len(reg.genes) == 0
        assert len(reg.side_effects) == 0

    def test_add_drug(self):
        reg = Registry()
        reg.drugs.add("DB00945")
        assert "DB00945" in reg.drugs

    def test_dedup(self):
        reg = Registry()
        reg.drugs.add("DB00945")
        reg.drugs.add("DB00945")
        assert len(reg.drugs) == 1

    def test_all_entity_sets(self):
        reg = Registry()
        assert hasattr(reg, "drugs")
        assert hasattr(reg, "genes")
        assert hasattr(reg, "side_effects")
        assert hasattr(reg, "indications")
        assert hasattr(reg, "bioactivities")
        assert hasattr(reg, "targets")
        assert hasattr(reg, "drug_classes")
        assert hasattr(reg, "adverse_events")

    def test_all_edge_sets(self):
        reg = Registry()
        assert hasattr(reg, "interacts_with_gene")
        assert hasattr(reg, "has_side_effect")
        assert hasattr(reg, "has_indication")
        assert hasattr(reg, "has_bioactivity")
        assert hasattr(reg, "bioactivity_target")
        assert hasattr(reg, "ttd_targets")
        assert hasattr(reg, "has_adverse_event")
        assert hasattr(reg, "classified_as")
        assert hasattr(reg, "parent_class")


class TestProgressReporter:
    def test_init(self):
        pr = ProgressReporter("test", total=100)
        assert pr.phase == "test"
        assert pr.total == 100
        assert pr.count == 0
        assert pr.errors == 0

    def test_tick(self):
        pr = ProgressReporter("test")
        pr.tick(5)
        assert pr.count == 5

    def test_error(self):
        pr = ProgressReporter("test")
        pr.error()
        assert pr.errors == 1

    def test_summary(self):
        pr = ProgressReporter("test", total=10)
        pr.tick(10)
        pr.error()
        s = pr.summary()
        assert s["phase"] == "test"
        assert s["processed"] == 10
        assert s["errors"] == 1
        assert "elapsed_s" in s
        assert "rate" in s
