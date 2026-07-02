"""Unit tests for the Kong identity/tag helpers."""

import pytest

from hub_adapter.kong_ident import (
    HEALTH_TAG,
    analysis_tag,
    analysis_username,
    datastore_tag,
    health_username,
    is_uuid,
    link_path,
    parse_tags,
    project_tag,
    type_tag,
    validate_datastore_name,
)

PROJECT_ID = "9cbefefe-2420-4b8e-8ac1-f48148a9fd40"
SERVICE_ID = "c2bfa0be-e8ff-4c82-be50-734432dd4579"
ANALYSIS_ID = "1c9cb547-4afc-4398-bcb6-954bc61a1bb1"


def test_tag_builders():
    assert HEALTH_TAG == "health"
    assert project_tag(PROJECT_ID) == f"project:{PROJECT_ID}"
    assert datastore_tag(SERVICE_ID) == f"datastore:{SERVICE_ID}"
    assert analysis_tag(ANALYSIS_ID) == f"analysis:{ANALYSIS_ID}"
    assert type_tag("fhir") == "type:fhir"


def test_type_tag_accepts_enum():
    from hub_adapter.schemas.kong import DataStoreType

    assert type_tag(DataStoreType.S3) == "type:s3"


def test_usernames_and_path():
    assert analysis_username(ANALYSIS_ID) == f"analysis-{ANALYSIS_ID}"
    assert health_username(PROJECT_ID) == f"health-{PROJECT_ID}"
    assert link_path(PROJECT_ID, SERVICE_ID) == f"/{PROJECT_ID}/{SERVICE_ID}"


def test_parse_tags_roundtrip():
    tags = [project_tag(PROJECT_ID), datastore_tag(SERVICE_ID), type_tag("fhir")]
    parsed = parse_tags(tags)
    assert parsed == {"project": PROJECT_ID, "datastore": SERVICE_ID, "type": "fhir"}


def test_parse_tags_handles_none_and_plain_tags():
    assert parse_tags(None) == {}
    assert parse_tags(["health"]) == {}


def test_is_uuid():
    assert is_uuid(PROJECT_ID)
    assert not is_uuid("my-fhir-store")


def test_validate_datastore_name_accepts_good_names():
    assert validate_datastore_name("hospital-fhir_prod.v1~x") == "hospital-fhir_prod.v1~x"


def test_validate_datastore_name_rejects_uuid():
    with pytest.raises(ValueError, match="UUID"):
        validate_datastore_name(PROJECT_ID)


def test_validate_datastore_name_rejects_bad_charset():
    for bad in ("has space", "has/slash", "has,comma", ""):
        with pytest.raises(ValueError):
            validate_datastore_name(bad)
