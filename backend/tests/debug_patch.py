from unittest.mock import patch
import app.api

def test_debug_patch():
    try:
        with patch("app.services.solver_v3.get_solver_v3"):
            print("Patched successfully")
    except AttributeError as e:
        print(f"AttributeError: {e}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_debug_patch()
