import json
import logging
from pathlib import Path
from threading import Lock, Thread

ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "faccheck_cnn_model.tflite"
LABELS_PATH = ML_DIR / "class_labels.json"
CONFIG_PATH = ML_DIR / "inference_config.json"

MODEL = None
_MODEL_LOCK = Lock()
_INFERENCE_LOCK = Lock()
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


class ImageDecodeError(ValueError):
    """The uploaded file is not an image the model can read."""


def _make_interpreter():
    from ai_edge_litert.interpreter import Interpreter

    return Interpreter(model_path=str(MODEL_PATH))


def _validate_tensor_details(input_details, output_details):
    import numpy as np

    if len(input_details) != 1 or len(output_details) != 1:
        raise ValueError("The TFLite model must have exactly one input and one output tensor.")

    input_detail, output_detail = input_details[0], output_details[0]
    input_shape = tuple(int(value) for value in input_detail["shape"])
    output_shape = tuple(int(value) for value in output_detail["shape"])
    if input_shape != (1, 224, 224, 3):
        raise ValueError(f"Unexpected TFLite input shape: {input_shape}")
    if output_shape != (1, len(CLASS_NAMES)):
        raise ValueError(f"TFLite output shape {output_shape} does not match {len(CLASS_NAMES)} class labels.")

    for label, detail in (("input", input_detail), ("output", output_detail)):
        if np.dtype(detail["dtype"]) != np.dtype(np.float32):
            raise TypeError(f"Expected float32 TFLite {label} tensor, got {detail['dtype']}.")
        quantization = detail.get("quantization", (0.0, 0))
        scales = detail.get("quantization_parameters", {}).get("scales", ())
        if quantization[0] != 0 or len(scales):
            raise ValueError(f"Unexpected quantization parameters for the float32 TFLite {label} tensor.")

    if CONFIG.get("class_names") and CONFIG["class_names"] != CLASS_NAMES:
        raise ValueError("inference_config.json class_names do not match class_labels.json.")


def _load_model():
    global MODEL
    if MODEL is None:
        with _MODEL_LOCK:
            if MODEL is None:
                if not MODEL_PATH.is_file():
                    raise FileNotFoundError(f"TFLite model not found: {MODEL_PATH}")
                interpreter = _make_interpreter()
                interpreter.allocate_tensors()
                input_details = interpreter.get_input_details()
                output_details = interpreter.get_output_details()
                _validate_tensor_details(input_details, output_details)
                MODEL = (interpreter, input_details[0], output_details[0])
    return MODEL


def _warm_model():
    global _WARMUP_STARTED
    try:
        _load_model()
    except Exception:
        logger.exception("TFLite model background warm-up failed")
    finally:
        with _WARMUP_LOCK:
            _WARMUP_STARTED = False


def warm_model_async():
    """Load the TFLite interpreter in the background while the user fills out a report."""
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
    try:
        with Image.open(image_file) as source:
            image = source.convert("RGB").resize((224, 224), Image.Resampling.NEAREST)
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:  # OSError covers UnidentifiedImageError
        raise ImageDecodeError("Uploaded photo could not be decoded.") from exc
    finally:
        image_file.seek(0)

    # This matches the Colab training and validation ImageDataGenerator rescale=1./255.
    image_array = np.asarray(image, dtype=np.float32) / 255.0
    image_array = np.expand_dims(image_array, axis=0)

    interpreter, input_detail, output_detail = _load_model()
    with _INFERENCE_LOCK:
        interpreter.set_tensor(input_detail["index"], image_array)
        interpreter.invoke()
        predictions = interpreter.get_tensor(output_detail["index"])[0].astype(np.float32)

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
