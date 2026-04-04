"""Tests for typed API contracts and versioning."""

from __future__ import annotations

from pathlib import Path

from resonance.api.contracts import (
    API_CONTRACT_VERSION,
    COMMAND_NAMES,
    AppRequest,
    ApplyRequest,
    ApiResult,
    AuditRequest,
    DecideRequest,
    DoctorRequest,
    IdentifyRequest,
    PlanRequest,
    PromptRequest,
    ResolveRequest,
    RollbackRequest,
    ScanRequest,
    UnjailRequest,
)


def test_contract_version_is_stable() -> None:
    assert API_CONTRACT_VERSION == "v1"


def test_request_models_have_expected_defaults() -> None:
    scan = ScanRequest(library_root=Path("/music"), state_db=Path("state.db"))
    assert scan.command == "scan"
    assert scan.mode == "interactive"

    resolve = ResolveRequest(library_root=Path("/music"), state_db=Path("state.db"))
    assert resolve.command == "resolve"
    assert resolve.auto_probable_min_gap == 0.15

    decide = DecideRequest(library_root=Path("/music"), state_db=Path("state.db"))
    assert decide.command == "decide"
    assert decide.headless is False


def test_api_result_includes_contract_version() -> None:
    result = ApiResult(command="scan", exit_code=0, status="OK")
    assert result.contract_version == API_CONTRACT_VERSION


def test_contracts_cover_all_commands() -> None:
    assert set(COMMAND_NAMES) == {
        "app",
        "scan",
        "resolve",
        "prompt",
        "identify",
        "plan",
        "apply",
        "decide",
        "audit",
        "doctor",
        "rollback",
        "unjail",
    }


def test_request_model_defaults_for_remaining_commands() -> None:
    assert PromptRequest().command == "prompt"
    assert IdentifyRequest().command == "identify"
    assert PlanRequest().command == "plan"
    assert ApplyRequest().command == "apply"
    assert AuditRequest().command == "audit"
    assert DoctorRequest().command == "doctor"
    assert RollbackRequest().command == "rollback"
    assert UnjailRequest().command == "unjail"
    assert AppRequest().command == "app"
