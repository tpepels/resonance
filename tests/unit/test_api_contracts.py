"""Tests for typed API contracts and versioning."""

from __future__ import annotations

from pathlib import Path

from resonance.api.contracts import (
    API_CONTRACT_VERSION,
    ApiResult,
    DecideRequest,
    ResolveRequest,
    ScanRequest,
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
