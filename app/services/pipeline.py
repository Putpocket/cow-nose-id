from app.db import get_cow_info
from app.services.crop import crop_image
from app.services.dino import extract_vector
from app.services.faiss_search import search_similar
from app.services.yolo import detect_nose


def process_image(image_path):
    """Best-effort pipeline wiring.

    This keeps current lightweight service stubs but executes real flow steps
    and returns structured JSON for frontend integration.
    """
    bbox = detect_nose(image_path)
    cropped = crop_image(image_path, bbox)
    vector = extract_vector(cropped)
    cow_id = search_similar(vector)
    cow_info = get_cow_info(cow_id)

    matched = "error" not in cow_info
    return {
        "matched": matched,
        "cow_id": cow_id if matched else None,
        "bbox": bbox,
        "cow": cow_info if matched else None,
    }
