"""data/ alignment guard: the committed expected_decisions.json must equal what
the real code path produces for committed loan_applications.json. If a policy
check or decision rule changes, regenerate via scripts/generate_expected.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loan_ops.policy import VALID_OUTCOMES

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_FILE = DATA_DIR / "loan_applications.json"
EXPECTED_FILE = DATA_DIR / "expected_decisions.json"


@pytest.fixture(scope="module")
def dataset() -> tuple[list[dict], list[dict]]:
    inputs = json.loads(INPUT_FILE.read_text())
    expected = json.loads(EXPECTED_FILE.read_text())
    return inputs["applications"], expected["decisions"]


def test_files_exist_and_shapes_agree(dataset: tuple[list[dict], list[dict]]) -> None:
    inputs, decisions = dataset
    assert inputs, "input dataset is empty"
    assert len(decisions) == len(inputs)
    assert {d["application_id"] for d in decisions} == {i["application_id"] for i in inputs}


def test_expected_statuses_are_reproducible_from_code(
    dataset: tuple[list[dict], list[dict]], monkeypatch
) -> None:
    """Re-running scripts/generate_expected.py must reproduce the file."""
    import sys

    sys.path.insert(0, str(DATA_DIR.parent / "scripts"))
    import generate_expected  # noqa: E402

    inputs, decisions = dataset
    monkeypatch.setattr(generate_expected, "DATA", DATA_DIR)
    monkeypatch.setattr(generate_expected, "INPUT", INPUT_FILE)
    monkeypatch.setattr(generate_expected, "OUTPUT", DATA_DIR / "_regen_tmp.json")
    try:
        generate_expected.main()
        regenerated = json.loads((DATA_DIR / "_regen_tmp.json").read_text())["decisions"]
    finally:
        (DATA_DIR / "_regen_tmp.json").unlink(missing_ok=True)
    assert regenerated == decisions
    assert [d["application_id"] for d in regenerated] == [i["application_id"] for i in inputs]


def test_status_values_follow_the_contract(dataset: tuple[list[dict], list[dict]]) -> None:
    """Decisions use the three-outcome contract; anything else is intake
    rejection (returned to applicant, never a decision — docs/PROC.md step 2)."""
    for d in dataset[1]:
        assert d["status"] in (*VALID_OUTCOMES, "rejected_at_intake")
        if d["status"] in VALID_OUTCOMES:
            assert len(d["checks"]) == 4
            assert {c["check"] for c in d["checks"]} == {
                "identity",
                "credit",
                "affordability",
                "fraud",
            }
            assert {c["result_class"] for c in d["checks"]} <= {"pass", "fail", "refer"}
        else:
            assert d["checks"] == []
        assert d["reason"].strip(), f"{d['application_id']} has no reason"


def test_covered_boundaries(dataset: tuple[list[dict], list[dict]]) -> None:
    statuses = {d["application_id"]: d["status"] for d in dataset[1]}
    # every boundary class from docs/POLICY.md is exercised once
    assert statuses["APP-0002"] == "approved"  # amount exactly at the $50k cap
    assert statuses["APP-0003"] == "refer"  # amount above cap, checks all pass
    assert statuses["APP-0004"] == "approved"  # DTI exactly 40%
    assert statuses["APP-0006"] == "denied"  # DTI just above 44%
    assert statuses["APP-0008"] == "approved"  # address doc exactly 90 days
    assert statuses["APP-0011"] == "denied"  # score below the 580 hard floor
    assert statuses["APP-0013"] == "approved"  # score exactly 650
    assert statuses["APP-0026"] == "rejected_at_intake"  # invalid intake
    # the three decisions all appear in the dataset
    assert statuses["APP-0001"] == "approved"
    assert statuses["APP-0006"] == "denied"
    assert statuses["APP-0023"] == "refer"
