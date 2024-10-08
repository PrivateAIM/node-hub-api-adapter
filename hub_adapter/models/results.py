"""Results microservice models."""

from pydantic import BaseModel


class ResultsUploadResponse(BaseModel):
    """Response from uploading a file using the results microservice."""

    url: str
