
import os
import sys

# Fake class to test the method
class TestSolver:
    def __init__(self):
        self.log_path = os.path.abspath("trace_report.txt")
        print(f"Resolving path to: {self.log_path}")

    def _log_trace(self, request_id, section, content):
        import datetime
        import json
        import os
        timestamp = datetime.datetime.utcnow().isoformat()
        if isinstance(content, (dict, list)):
            text_content = json.dumps(content, indent=2, default=str)
        else:
            text_content = str(content)
        
        print(f"Writing to {self.log_path}...")
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                 f.write(f"\n[{timestamp}] [ID:{request_id}] [{section}]\n{text_content}\n{'-'*80}\n")
                 f.flush()
                 os.fsync(f.fileno())
            print("Write successful!")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    t = TestSolver()
    t._log_trace("TEST-ID-123", "TEST_SECTION", "This is a test log entry to verify file permissions and writing.")
