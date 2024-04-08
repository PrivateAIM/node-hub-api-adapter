"""Post-processing methods for passing returned responses to frontend."""


def parse_containers(analysis_response: dict) -> dict:
    """Parse analysis response from the hub."""
    containers = []
    for hit in analysis_response["data"]:
        data = {
            "id": hit["id"],  # id
            "name": hit["analysis"]["name"],
            "job_id": hit["analysis"]["id"],
            "image": hit["analysis"]["master_image_id"],
            "state": hit["run_status"],
            "status": hit["analysis"]["result_status"],
            "next_tag": "Köln",  # TODO remove/replace
            "repo": "/data",
            "train_class_id": "choochoo",
        }
        containers.append(data)

    return {"containers": containers}
