from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.runtime_registry import (
    ConfigurationFamilyGateway,
    ConfigurationRuntimeRegistry,
)
from src.api.settings import ApiSettings


def navigation_response(
    *,
    complete: bool,
    next_field: str | None,
    state_token: str,
):
    options = (
        ()
        if complete
        else (
            SimpleNamespace(
                field_code=next_field,
                display_value="1530 (ANSI)",
                option_token="option-token-" + "x" * 40,
            ),
        )
    )

    return SimpleNamespace(
        family_code="FYBROC",
        runtime_revision=(
            "publication:1;series-batch:2;"
            "combination-batch:2;"
            "dependency-batch:1"
        ),
        state_token=state_token,
        complete=complete,
        next_field_code=next_field,
        selection_count=(
            41
            if complete
            else 0
        ),
        options=options,
    )


class FakeNavigationSession:
    def start(self, *, family_code):
        assert family_code == "FYBROC"
        return navigation_response(
            complete=False,
            next_field="SERIES",
            state_token=(
                "state-token-start-" + "s" * 40
            ),
        )

    def resume(
        self,
        *,
        state_token,
    ):
        return navigation_response(
            complete=state_token.startswith(
                "state-token-complete"
            ),
            next_field=(
                None
                if state_token.startswith(
                    "state-token-complete"
                )
                else "SERIES"
            ),
            state_token=state_token,
        )

    def advance(
        self,
        *,
        state_token,
        option_token,
    ):
        assert state_token.startswith(
            "state-token-start"
        )
        assert option_token.startswith(
            "option-token"
        )

        return navigation_response(
            complete=True,
            next_field=None,
            state_token=(
                "state-token-complete-" + "c" * 40
            ),
        )


class FakePersistentSession:
    def finalize_and_persist(
        self,
        *,
        state_token,
        requested_by,
    ):
        assert state_token.startswith(
            "state-token-complete"
        )
        assert requested_by == "api-test"

        now = datetime.now(timezone.utc)

        persisted = SimpleNamespace(
            configured_product_registry_id=1,
            was_created=False,
            configuration_signature="a" * 64,
            part_number=(
                "F1530-B-1-1-AA-0001-0Y-"
                "1Q-002-XXX-T00"
            ),
            sku=(
                "F1530-V1-B11AA00010Y1Q"
                "002XXXT00"
            ),
            request_count=3,
            runtime_revision=(
                "publication:1;series-batch:2;"
                "combination-batch:2;"
                "dependency-batch:1"
            ),
            metadata_publication_id=1,
            series_batch_id=2,
            combination_batch_id=2,
            dependency_batch_id=1,
            created_at=now,
            last_requested_at=now,
        )

        completed = SimpleNamespace(
            selections={
                f"FIELD_{index}": str(index)
                for index in range(1, 42)
            },
            identifier_result=SimpleNamespace(
                segments=tuple(
                    range(10)
                )
            ),
        )

        return SimpleNamespace(
            completed_configuration=completed,
            persisted_product=persisted,
        )


def build_test_client() -> TestClient:
    registry = ConfigurationRuntimeRegistry(
        {
            "FYBROC": ConfigurationFamilyGateway(
                family_code="FYBROC",
                navigation_session=(
                    FakeNavigationSession()
                ),
                persistent_session=(
                    FakePersistentSession()
                ),
            )
        }
    )

    app = create_app(
        settings=ApiSettings.for_testing(
            project_root=Path.cwd()
        ),
        runtime_registry=registry,
    )

    return TestClient(app)


def test_closed_three_operation_flow() -> None:
    with build_test_client() as client:
        start = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/start"
            ),
            json={},
        )

        assert start.status_code == 200
        start_body = start.json()
        assert start_body["nextFieldCode"] == (
            "SERIES"
        )
        assert len(start_body["options"]) == 1

        advance = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/advance"
            ),
            json={
                "stateToken": (
                    start_body["stateToken"]
                ),
                "optionToken": (
                    start_body["options"][0][
                        "optionToken"
                    ]
                ),
            },
        )

        assert advance.status_code == 200
        advance_body = advance.json()
        assert advance_body["complete"] is True
        assert advance_body["options"] == []

        final = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/finalize"
            ),
            json={
                "stateToken": (
                    advance_body["stateToken"]
                )
            },
            headers={
                "X-Requested-By": "api-test"
            },
        )

        assert final.status_code == 200
        final_body = final.json()
        assert (
            final_body[
                "configuredProductRegistryId"
            ]
            == 1
        )
        assert final_body["wasCreated"] is False
        assert final_body["selectionCount"] == 41
        assert final_body["segmentCount"] == 10


def test_start_rejects_engineering_fields() -> None:
    with build_test_client() as client:
        response = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/start"
            ),
            json={
                "series": "1530"
            },
        )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "request_schema_violation"
    )


def test_advance_rejects_field_value_submission() -> None:
    with build_test_client() as client:
        response = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/advance"
            ),
            json={
                "stateToken": (
                    "state-token-" + "s" * 40
                ),
                "optionToken": (
                    "option-token-" + "o" * 40
                ),
                "fieldCode": "SIZE",
                "value": "6x10x8",
            },
        )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "request_schema_violation"
    )


def test_finalize_rejects_selection_payload() -> None:
    with build_test_client() as client:
        response = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/finalize"
            ),
            json={
                "stateToken": (
                    "state-token-" + "s" * 40
                ),
                "selections": {
                    "SIZE": "6x10x8"
                },
            },
        )

    assert response.status_code == 422


def test_unsupported_family_returns_not_found() -> None:
    with build_test_client() as client:
        response = client.post(
            (
                "/api/v1/families/UNKNOWN/"
                "configurations/start"
            ),
            json={},
        )

    assert response.status_code == 404
    assert (
        response.json()["error"]["code"]
        == "pump_family_not_configured"
    )


def test_openapi_exposes_only_closed_request_fields() -> None:
    with build_test_client() as client:
        schema = client.get(
            "/openapi.json"
        ).json()

    components = schema["components"]["schemas"]

    assert (
        components[
            "StartConfigurationRequest"
        ].get("properties", {})
        == {}
    )

    assert set(
        components[
            "AdvanceConfigurationRequest"
        ]["properties"]
    ) == {
        "stateToken",
        "optionToken",
    }

    assert set(
        components[
            "FinalizeConfigurationRequest"
        ]["properties"]
    ) == {
        "stateToken",
    }
