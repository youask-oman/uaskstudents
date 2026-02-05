"""Test Pydantic schema generation and enforce_strict output."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.schemas.na_math_solver_v3 import get_json_schema_for_openai_v3

schema = get_json_schema_for_openai_v3()
schema_str = json.dumps(schema, indent=2)

# Check for problematic patterns
patterns = ['"None"', ': null', '"null"', 'null]']
found_issues = []

for i, line in enumerate(schema_str.split('\n'), 1):
    for pattern in patterns:
        if pattern in line:
            found_issues.append((i, pattern, line.strip()))

if found_issues:
    print('ISSUES FOUND:')
    for line_num, pattern, content in found_issues:
        print(f'  Line {line_num} ({pattern}): {content}')
else:
    print('No obvious issues in generated schema')

print(f'\nTotal schema length: {len(schema_str)} chars')

# Save full schema for inspection
output_path = Path(__file__).parent / "generated_schema.json"
with open(output_path, "w") as f:
    f.write(schema_str)
print(f"Full schema saved to: {output_path}")
