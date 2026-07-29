"""Collection of unit tests for testing the utility methods."""

from pathlib import Path

import pytest
from starlette.datastructures import FormData, UploadFile

from hub_adapter.utils import (
    HEALTH_TAG,
    analysis_tag,
    analysis_username,
    create_request_data,
    datastore_tag,
    health_username,
    is_uuid,
    link_path,
    parse_tags,
    project_tag,
    remove_file,
    serialize_query_content,
    type_tag,
    unzip_body_object,
    unzip_file_params,
    unzip_form_params,
    unzip_query_params,
    validate_datastore_name,
)

PROJECT_ID = "9cbefefe-2420-4b8e-8ac1-f48148a9fd40"
SERVICE_ID = "c2bfa0be-e8ff-4c82-be50-734432dd4579"
ANALYSIS_ID = "1c9cb547-4afc-4398-bcb6-954bc61a1bb1"


class TestUtils:
    """Collection of unit tests for testing the utility methods."""

    def test_create_request_data(self):
        """Test the create_request_data method."""
        test_form = {"foo": "bar"}
        test_body = {"bar": "baz"}

        assert create_request_data(test_form, None) == test_form
        assert create_request_data(None, test_body) == test_body
        assert create_request_data(test_form, test_body) == test_form  # Form takes precedence
        assert create_request_data(None, None) is None

    @pytest.mark.asyncio
    async def test_serialize_query_content(self):
        """Test the serialize_query_content method."""
        key = "key"
        value = "value"
        assert await serialize_query_content(key, value) == {key: value}

    @pytest.mark.asyncio
    async def test_unzip_query_params(self):
        """Test the unzip_query_params method."""
        test_additional = {"foo": "bar"}
        test_req = {"bar": "baz"}

        assert await unzip_query_params(test_additional) == dict()
        assert await unzip_query_params(test_additional, ["foo"]) == test_additional
        assert await unzip_query_params(test_additional, req_params=test_req) == test_req

    @pytest.mark.asyncio
    async def test_unzip_body_object(self):
        """Test the unzip_body_object method."""
        test_additional = {"foo": "bar"}
        test_specified = ["foo"]

        assert await unzip_body_object(test_additional) is None
        assert await unzip_body_object(test_additional, test_specified) == test_additional
        assert await unzip_body_object(test_additional, ["bar"]) == {"bar": None}

    @pytest.mark.asyncio
    async def test_unzip_form_params(self):
        """Test the unzip_form_params method."""
        test_additional = {"foo": "bar"}
        test_specified = ["foo"]
        test_form_dict = {"bar": "baz"}
        test_form = FormData(test_form_dict)

        assert await unzip_form_params(test_additional) is None
        assert await unzip_form_params(test_additional, test_specified) == test_additional
        assert await unzip_form_params(test_additional, ["bar"]) == {"bar": None}
        assert await unzip_form_params(test_additional, test_specified, test_form) == test_additional | test_form_dict

    @pytest.mark.asyncio
    async def test_unzip_file_params(self):
        """Test the unzip_file_params method."""
        fake_file = Path("./fake_file.txt")
        fake_file.touch()

        with open(fake_file, "rb") as ff:
            test_additional = {"foo": UploadFile(ff)}
            test_specified = ["foo"]

            assert await unzip_file_params(test_additional) is None
            assert await unzip_file_params(test_additional, test_specified) == {"foo": b""}
            assert await unzip_file_params(test_additional, ["bar"]) == {}

        fake_file.unlink(missing_ok=True)

    def test_remove_file(self):
        """Test the remove_file method."""
        file_path = "./fake_file.txt"
        fake_file = Path(file_path)
        fake_file.touch()

        assert fake_file.exists()
        remove_file(file_path)

        assert not fake_file.exists()


class TestKongIdentityHelpers:
    """Unit tests for the Kong identity/tag helpers."""

    def test_tag_builders(self):
        assert HEALTH_TAG == "health"
        assert project_tag(PROJECT_ID) == f"project:{PROJECT_ID}"
        assert datastore_tag(SERVICE_ID) == f"datastore:{SERVICE_ID}"
        assert analysis_tag(ANALYSIS_ID) == f"analysis:{ANALYSIS_ID}"
        assert type_tag("fhir") == "type:fhir"

    def test_type_tag_accepts_enum(self):
        from hub_adapter.schemas.kong import DataStoreType

        assert type_tag(DataStoreType.S3) == "type:s3"

    def test_usernames_and_path(self):
        assert analysis_username(ANALYSIS_ID) == f"analysis-{ANALYSIS_ID}"
        assert health_username(PROJECT_ID) == f"health-{PROJECT_ID}"
        assert link_path(PROJECT_ID, SERVICE_ID) == f"/{PROJECT_ID}/{SERVICE_ID}"

    def test_parse_tags_roundtrip(self):
        tags = [project_tag(PROJECT_ID), datastore_tag(SERVICE_ID), type_tag("fhir")]
        parsed = parse_tags(tags)
        assert parsed == {"project": PROJECT_ID, "datastore": SERVICE_ID, "type": "fhir"}

    def test_parse_tags_handles_none_and_plain_tags(self):
        assert parse_tags(None) == {}
        assert parse_tags(["health"]) == {}

    def test_is_uuid(self):
        assert is_uuid(PROJECT_ID)
        assert not is_uuid("my-fhir-store")

    def test_validate_datastore_name_accepts_good_names(self):
        assert validate_datastore_name("hospital-fhir_prod.v1~x") == "hospital-fhir_prod.v1~x"

    def test_validate_datastore_name_rejects_uuid(self):
        with pytest.raises(ValueError, match="UUID"):
            validate_datastore_name(PROJECT_ID)

    def test_validate_datastore_name_rejects_bad_charset(self):
        for bad in ("has space", "has/slash", "has,comma", ""):
            with pytest.raises(ValueError):
                validate_datastore_name(bad)
