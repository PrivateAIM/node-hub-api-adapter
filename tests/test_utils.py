"""Collection of unit tests for testing the utility methods."""

from pathlib import Path

import pytest
from starlette.datastructures import FormData, UploadFile

from hub_adapter.utils import (
    create_request_data,
    remove_file,
    serialize_query_content,
    unzip_body_object,
    unzip_file_params,
    unzip_form_params,
    unzip_query_params,
)


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
