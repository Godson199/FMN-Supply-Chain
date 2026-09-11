import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main


def test_uses_openai_compatible_model_config():
    assert "claude" not in main.MODEL_NAME.lower()
    assert "gpt" in main.MODEL_NAME.lower() or "openai/" in main.MODEL_NAME.lower()
