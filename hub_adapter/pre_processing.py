"""Pre-processing functions to apply to the kwargs of the forwards parameters."""


def extract_po_params(image_data: dict) -> dict:
    """Get the meat of the PO create analysis data."""
    return image_data["image_url_resp"]
