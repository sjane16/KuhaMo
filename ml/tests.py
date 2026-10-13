import sys
import types
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from . import predictor


class LazyModelLoadingTests(SimpleTestCase):
    def test_model_loads_only_when_requested_and_is_reused(self):
        previous_model = predictor.MODEL
        self.addCleanup(setattr, predictor, "MODEL", previous_model)
        predictor.MODEL = None

        model = Mock()
        tensorflow = types.SimpleNamespace(
            keras=types.SimpleNamespace(
                models=types.SimpleNamespace(load_model=Mock(return_value=model))
            )
        )

        with patch.dict(sys.modules, {"tensorflow": tensorflow}):
            self.assertIs(predictor._load_model(), model)
            self.assertIs(predictor._load_model(), model)

        tensorflow.keras.models.load_model.assert_called_once_with(
            predictor.MODEL_PATH,
            compile=False,
        )
