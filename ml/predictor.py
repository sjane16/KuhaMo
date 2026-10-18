import json
import logging
from pathlib import Path
from threading import Lock, Thread

ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "faccheck_cnn_model.keras"
LABELS_PATH = ML_DIR / "class_labels.json"
CONFIG_PATH = ML_DIR / "inference_config.json"

MODEL = None
_MODEL_LOCK = Lock()
_WARMUP_LOCK = Lock()
_WARMUP_STARTED = False
logger = logging.getLogger(__name__)

with open(LABELS_PATH, "r", encoding="utf-8") as file:
    CLASS_NAMES = json.load(file)

with open(CONFIG_PATH, "r", encoding="utf-8") as file:
    CONFIG = json.load(file)

CONFIDENCE_THRESHOLD = CONFIG["confidence_threshold"]
MARGIN_THRESHOLD = CONFIG["margin_threshold"]
FALLBACK_LABEL = CONFIG["fallback_label"]

CATEGORY_MAP = {
    "Carpentry Masonry": "carpentry_masonry",
    "Electrical": "electrical",
    "Others": "others",
    "Painting": "painting",
    "Plumbing": "plumbing",
    "Refrigeration ACUs": "refrigeration_acu",
    "Vehicle Check-Up": "vehicle_checkup",
}


def _load_model():
    global MODEL
    if MODEL is None:
        with _MODEL_LOCK:
            if MODEL is None:
                import tensorflow as tf
                MODEL = tf.keras.models.load_model(MODEL_PATH, compile=False)
    return MODEL


def _warm_model():
    global _WARMUP_STARTED
    try:
        _load_model()
    except Exception:
        logger.exception("CNN model background warm-up failed")
    finally:
        with _WARMUP_LOCK:
            _WARMUP_STARTED = False


def warm_model_async():
    """Load the model in the background while the user fills out a report."""
    global _WARMUP_STARTED
    if MODEL is not None:
        return
    with _WARMUP_LOCK:
        if MODEL is not None or _WARMUP_STARTED:
            return
        _WARMUP_STARTED = True
        Thread(target=_warm_model, name="cnn-model-warmup", daemon=True).start()


def predict_image(image_file):
    import numpy as np
    from PIL import Image

    image_file.seek(0)

    image = Image.open(image_file).convert("RGB")
    image = image.resize((224, 224))

    image_array = np.asarray(image, dtype=np.float32)
    image_array = image_array / 255.0
    image_array = np.expand_dims(image_array, axis=0)

    predictions = _load_model().predict(image_array, verbose=0)[0]

    sorted_indices = np.argsort(predictions)[::-1]

    top_index = int(sorted_indices[0])
    second_index = int(sorted_indices[1])

    raw_label = CLASS_NAMES[top_index]
    confidence = float(predictions[top_index])
    margin = float(predictions[top_index] - predictions[second_index])

    flagged_for_review = (
        confidence < CONFIDENCE_THRESHOLD
        or margin < MARGIN_THRESHOLD
    )

    final_label = FALLBACK_LABEL if flagged_for_review else raw_label
    category = CATEGORY_MAP[final_label]

    image_file.seek(0)

    return {
        "category": category,
        "label": final_label,
        "raw_label": raw_label,
        "confidence": confidence,
        "margin": margin,
        "flagged_for_review": flagged_for_review,
    }
