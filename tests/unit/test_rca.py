import json
import sys
import types

import pytest
from pydantic import ValidationError

from rootcause.agents.rca import RCAOutput, RootCauseItem, _evidence_grounded, _filter_grounded


def test_rca_output_parses_normal_input():
    data = {
        "root_causes": [{"description": "DB overload", "confidence": 0.9, "evidence": ["log1"]}],
        "contributing_factors": ["high traffic"],
    }
    result = RCAOutput(**data)
    assert len(result.root_causes) == 1
    assert result.root_causes[0].confidence == 0.9


def test_rca_output_parses_json_string_fields():
    """Claude Haiku sometimes returns fields as JSON strings instead of parsed lists."""
    root_causes_str = json.dumps([{"description": "DB overload", "confidence": 0.85, "evidence": ["err1"]}])
    factors_str = json.dumps(["high load", "missing index"])
    data = {"root_causes": root_causes_str, "contributing_factors": factors_str}
    result = RCAOutput(**data)
    assert len(result.root_causes) == 1
    assert result.root_causes[0].description == "DB overload"
    assert len(result.contributing_factors) == 2


def test_rca_output_tolerates_trailing_data_after_json():
    """Claude Haiku occasionally appends trailing commentary after the JSON
    array (e.g. a stray closing newline + extra text) -- this used to raise
    a pydantic 'Extra data' error and fall back to a content-free response.
    The eval run that found this traced 100% of its misses to this bug."""
    root_causes_str = json.dumps([{"description": "DB overload", "confidence": 0.85, "evidence": ["err1"]}]) + "\n\nNote: see also runbook RB-001."
    data = {"root_causes": root_causes_str, "contributing_factors": "[]"}
    result = RCAOutput(**data)
    assert len(result.root_causes) == 1
    assert result.root_causes[0].description == "DB overload"


def test_root_cause_confidence_bounds():
    with pytest.raises(ValidationError):
        RootCauseItem(description="test", confidence=1.5, evidence=[])

    with pytest.raises(ValidationError):
        RootCauseItem(description="test", confidence=-0.1, evidence=[])


def test_rca_output_multiple_root_causes():
    data = {
        "root_causes": [
            {"description": "cause 1", "confidence": 0.9, "evidence": ["a"]},
            {"description": "cause 2", "confidence": 0.6, "evidence": ["b"]},
        ],
        "contributing_factors": ["factor 1"],
    }
    result = RCAOutput(**data)
    assert len(result.root_causes) == 2


def test_evidence_grounded_exact_substring():
    source_lines = ["2026-06-17 12:00:00 connection pool exhausted, 200/200 in use"]
    assert _evidence_grounded("connection pool exhausted", source_lines)


def test_evidence_grounded_fuzzy_match():
    source_lines = ["postgres-primary replication lag spiked to 45 seconds at 12:02:00"]
    # paraphrase of the same fact, not a verbatim substring
    assert _evidence_grounded("replication lag on postgres reached 45s", source_lines)


def test_evidence_not_grounded_fabricated():
    source_lines = ["checkout-service deploy v3.4.0 rolled out at 14:55"]
    assert not _evidence_grounded("redis cluster failover triggered at 09:00", source_lines)


def test_filter_grounded_drops_ungrounded_evidence_lines():
    source_lines = ["postgres connections at 180/200"]
    root_causes = [
        RootCauseItem(
            description="connection pool exhaustion",
            confidence=0.8,
            evidence=["postgres connections at 180/200", "totally fabricated unrelated claim"],
        )
    ]
    filtered = _filter_grounded(root_causes, source_lines)
    assert len(filtered) == 1
    assert filtered[0].evidence == ["postgres connections at 180/200"]


def test_filter_grounded_drops_root_cause_with_no_grounded_evidence():
    source_lines = ["postgres connections at 180/200"]
    root_causes = [
        RootCauseItem(description="real cause", confidence=0.8, evidence=["postgres connections at 180/200"]),
        RootCauseItem(description="fabricated cause", confidence=0.7, evidence=["entirely made up evidence string"]),
    ]
    filtered = _filter_grounded(root_causes, source_lines)
    assert len(filtered) == 1
    assert filtered[0].description == "real cause"


class _FakeLLM:
    """Stands in for ChatAnthropic().with_structured_output(RCAOutput) --
    returns each entry in `responses` in order, raising if it's an exception."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[str] = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls.append(messages[0]["content"])
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _patch_llm(monkeypatch, fake_llm):
    from rootcause.agents import rca as rca_module

    monkeypatch.setattr(
        rca_module,
        "get_settings",
        lambda: types.SimpleNamespace(anthropic_api_key="fake-key", model_rca="fake-model"),
    )
    monkeypatch.setitem(
        sys.modules, "langchain_anthropic", types.SimpleNamespace(ChatAnthropic=lambda **kwargs: fake_llm)
    )
    return rca_module


def test_rca_node_retries_once_then_succeeds(monkeypatch):
    good_result = RCAOutput(
        root_causes=[RootCauseItem(description="real cause", confidence=0.9, evidence=["log line present"])],
        contributing_factors=[],
    )
    fake_llm = _FakeLLM([RuntimeError("truncated JSON"), good_result])
    rca_module = _patch_llm(monkeypatch, fake_llm)

    state = {"title": "t", "service": "svc", "severity": "high", "logs": "log line present", "retrieved_docs": []}
    result = rca_module.rca_node(state)

    assert len(fake_llm.calls) == 2
    assert "IMPORTANT" in fake_llm.calls[1]  # retry note only on the second call
    assert result["fallback"] is False
    assert result["root_causes"][0]["description"] == "real cause"


def test_rca_node_falls_back_after_retry_also_fails(monkeypatch):
    fake_llm = _FakeLLM([RuntimeError("truncated JSON"), RuntimeError("still truncated")])
    rca_module = _patch_llm(monkeypatch, fake_llm)

    state = {"title": "t", "service": "svc", "severity": "high", "logs": "", "retrieved_docs": []}
    result = rca_module.rca_node(state)

    assert len(fake_llm.calls) == 2
    assert result["fallback"] is True
    assert result["model_used"] == "fallback"
