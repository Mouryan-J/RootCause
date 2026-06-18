import json

import pytest
from pydantic import ValidationError

from rootcause.agents.rca import RCAOutput, RootCauseItem


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
