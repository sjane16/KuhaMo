from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from . import predictor


class FakeInterpreter:
    def __init__(self, output):
        self.output = np.asarray([output], dtype=np.float32)
        self.input_details = [{
            'index': 0,
            'shape': np.asarray([1, 224, 224, 3]),
            'dtype': np.float32,
            'quantization': (0.0, 0),
            'quantization_parameters': {'scales': np.asarray([]), 'zero_points': np.asarray([])},
        }]
        self.output_details = [{
            'index': 1,
            'shape': np.asarray([1, len(output)]),
            'dtype': np.float32,
            'quantization': (0.0, 0),
            'quantization_parameters': {'scales': np.asarray([]), 'zero_points': np.asarray([])},
        }]
        self.input_tensor = None
        self.allocate_tensors = Mock()
        self.invoke = Mock()

    def get_input_details(self):
        return self.input_details

    def get_output_details(self):
        return self.output_details

    def set_tensor(self, index, tensor):
        self.input_tensor = np.array(tensor, copy=True)

    def get_tensor(self, index):
        return self.output


class TFLiteInferenceTests(SimpleTestCase):
    def setUp(self):
        self.previous_model = predictor.MODEL
        predictor.MODEL = None
        self.addCleanup(setattr, predictor, 'MODEL', self.previous_model)

    def test_model_loads_lazily_once_from_tflite_artifact(self):
        interpreter = FakeInterpreter([0.1] * len(predictor.CLASS_NAMES))
        with patch.object(predictor, '_make_interpreter', return_value=interpreter) as make_interpreter:
            self.assertIsNone(predictor.MODEL)
            loaded = predictor._load_model()
            self.assertIs(loaded[0], interpreter)
            self.assertIs(predictor._load_model(), loaded)

        self.assertEqual(predictor.MODEL_PATH.name, 'faccheck_cnn_model.tflite')
        make_interpreter.assert_called_once()
        interpreter.allocate_tensors.assert_called_once_with()

    def test_missing_tflite_artifact_fails_without_fallback(self):
        with patch.object(predictor, 'MODEL_PATH', Path(__file__).with_name('missing.tflite')), \
             patch.object(predictor, '_make_interpreter') as make_interpreter:
            with self.assertRaises(FileNotFoundError):
                predictor._load_model()

        make_interpreter.assert_not_called()

    def test_float_tensor_metadata_is_checked(self):
        interpreter = FakeInterpreter([0.1] * len(predictor.CLASS_NAMES))
        interpreter.input_details[0]['dtype'] = np.int8
        with patch.object(predictor, '_make_interpreter', return_value=interpreter):
            with self.assertRaisesRegex(TypeError, 'Expected float32 TFLite input tensor'):
                predictor._load_model()

    def test_prediction_uses_rgb_224_rescale_and_existing_result_contract(self):
        probabilities = [0.02, 0.90, 0.01, 0.02, 0.02, 0.02, 0.01]
        interpreter = FakeInterpreter(probabilities)
        image_bytes = BytesIO()
        Image.new('RGB', (8, 8), (255, 128, 0)).save(image_bytes, format='PNG')
        image_bytes.seek(0)

        with patch.object(predictor, 'MODEL_PATH', Path(__file__)), \
             patch.object(predictor, '_make_interpreter', return_value=interpreter):
            result = predictor.predict_image(image_bytes)

        self.assertEqual(interpreter.input_tensor.shape, (1, 224, 224, 3))
        np.testing.assert_allclose(interpreter.input_tensor[0, 100, 100], [1.0, 128 / 255.0, 0.0], atol=1e-6)
        interpreter.invoke.assert_called_once_with()
        self.assertEqual(set(result), {
            'category', 'label', 'raw_label', 'confidence', 'margin', 'flagged_for_review',
        })
        self.assertEqual(result['category'], 'electrical')
        self.assertEqual(result['label'], 'Electrical')
        self.assertEqual(result['raw_label'], 'Electrical')
        self.assertAlmostEqual(result['confidence'], 0.9)
        self.assertAlmostEqual(result['margin'], 0.88)
        self.assertFalse(result['flagged_for_review'])
        self.assertEqual(image_bytes.tell(), 0)

    def test_low_confidence_and_margin_keep_others_fallback(self):
        interpreter = FakeInterpreter([0.26, 0.25, 0.20, 0.10, 0.08, 0.06, 0.05])
        image_bytes = BytesIO()
        Image.new('RGB', (8, 8), 'white').save(image_bytes, format='PNG')
        image_bytes.seek(0)

        with patch.object(predictor, 'MODEL_PATH', Path(__file__)), \
             patch.object(predictor, '_make_interpreter', return_value=interpreter):
            result = predictor.predict_image(image_bytes)

        self.assertEqual(result['raw_label'], 'Carpentry Masonry')
        self.assertEqual(result['label'], 'Others')
        self.assertEqual(result['category'], 'others')
        self.assertTrue(result['flagged_for_review'])

    def test_background_warmup_starts_only_once(self):
        previous_started = predictor._WARMUP_STARTED
        predictor.MODEL = None
        predictor._WARMUP_STARTED = False
        self.addCleanup(setattr, predictor, '_WARMUP_STARTED', previous_started)

        with patch.object(predictor, 'Thread') as thread:
            predictor.warm_model_async()
            predictor.warm_model_async()

        thread.assert_called_once_with(
            target=predictor._warm_model,
            name='cnn-model-warmup',
            daemon=True,
        )
        thread.return_value.start.assert_called_once()
