import sys
from unittest.mock import MagicMock

# MOCK HEAVY ML DEPENDENCIES
sys.modules["torch"] = MagicMock()
sys.modules["torch.version"] = MagicMock()
sys.modules["torch.__version__"] = "2.0.0"
sys.modules["pix2text"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()

print("Importing app.api...")
try:
    # Add backend to path
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
    from app.api import app
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
