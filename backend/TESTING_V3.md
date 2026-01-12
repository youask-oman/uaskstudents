# Math Solver V3 - How to Run Tests

## Overview

Math Solver V3 includes comprehensive test coverage:
- **28 Unit Tests**: Individual component validation
- **6 Integration Tests**: End-to-end scenarios
- **Total: 34 tests**

---

## Prerequisites

1. **Install Dependencies**:
   ```powershell
   cd backend
   pip install -r requirements.txt
   ```

2. **Set API Key** (for integration tests):
   ```powershell
   $env:OPENAI_API_KEY="your-key-here"
   ```

---

## Running Tests

### All Tests (Recommended)

```powershell
cd backend
pytest tests/test_*v3*.py -v
```

### Individual Test Suites

**Unit Tests - Prompt Registry**:
```powershell
cd backend
python tests/test_prompt_registry.py
```
- 9 tests covering prompt loading, versioning, schema extraction, environment overrides

**Unit Tests - Validation**:
```powershell
python tests/test_validation_v3.py
```
- 7 tests covering JSON Schema validation, Pydantic validation, repair prompts, error responses

**Unit Tests - Visualization**:
```powershell
python tests/test_visualization_v3.py
```
- 12 tests covering decision engine, plot plan generation, rendering

**Integration Tests** (requires OpenAI API key):
```powershell
$env:OPENAI_API_KEY="your-key"
python tests/test_solver_v3_integration.py
```
- 6 end-to-end tests with real LLM calls

---

## Test Coverage

### Prompt Registry (`test_prompt_registry.py`)
✅ Registry initialization  
✅ Load solver_system.txt  
✅ Load na_math_solver schema  
✅ Prompt versioning  
✅ Error handling (not found)  
✅ Singleton pattern  
✅ Environment override  
✅ List all prompts  

### Validation (`test_validation_v3.py`)
✅ Validate valid response  
✅ Detect missing fields  
✅ Enforce minimum verification count  
✅ Generate repair prompts  
✅ Create error responses  
✅ Pydantic strictness  
✅ Validator singleton  

### Visualization (`test_visualization_v3.py`)
✅ Detect explicit keywords (graph, plot, etc.)  
✅ Detect functions (single & system)  
✅ Detect inequalities  
✅ Detect quadratics  
✅ Generate function plot plan  
✅ Generate system plot plan  
✅ Generate number line plan  
✅ Generate visualization alternatives  
✅ Render function plots  
✅ Safe expression evaluation  
✅ Engine singleton  
✅ Renderer singleton  

### Integration (`test_solver_v3_integration.py`)
✅ Quadratic equation (x² - 5x + 6 = 0)  
✅ System of equations (y = 2x + 3, y = -x + 6)  
✅ Inequality (2x + 5 > 11)  
✅ Simple algebra (3x + 7 = 22)  
✅ Schema validation  
✅ Visualization engine  

---

## Expected Output

### Successful Unit Test Run
```
======================================================================
PROMPT REGISTRY UNIT TESTS
======================================================================

test_prompt_registry_initialization...
✅ Registry initialized with 4 prompts

test_load_solver_system_prompt...
✅ Loaded solver_system prompt: 1463 characters

[... more tests ...]

======================================================================
PASSED: 9/9
======================================================================
```

### Successful Integration Test Run
```
======================================================================
TEST 1: Quadratic Equation
======================================================================

[SOLVER_V3] ==================== START ====================
[SOLVER_V3] Problem: Solve x^2 - 5x + 6 = 0...
[SOLVER_V3] ✅ Loaded prompts and schema
[SOLVER_V3] ✅ Received LLM response
[SOLVER_V3] ✅ Success! Returning valid response
[SOLVER_V3] ==================== SUCCESS ====================

✅ Quadratic test passed!
   - Verification methods: 2
   - Similar examples: 2
   - Should plot: true
   - Final answer: x = 2 or x = 3

[... more tests ...]

======================================================================
TOTAL: 6/6 tests passed (100%)
======================================================================
```

---

## Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'app'
```

**Solution**: Run tests from `backend/` directory:
```powershell
cd backend
python tests/test_prompt_registry.py
```

### API Key Missing
```
❌ ERROR: OPENAI_API_KEY not set
```

**Solution**: Set environment variable:
```powershell
$env:OPENAI_API_KEY="sk-..."
```

### Schema Validation Errors
```
ValidationError: verification field required
```

**Solution**: This is expected for invalid test data. The test should pass if it correctly detects the error.

---

## CI/CD Integration

For automated testing in CI/CD:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run unit tests
        run: |
          cd backend
          pytest tests/test_prompt_registry.py -v
          pytest tests/test_validation_v3.py -v
          pytest tests/test_visualization_v3.py -v
      - name: Run integration tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          cd backend
          python tests/test_solver_v3_integration.py
```

---

## Quick Reference

| Test Suite | Command | Tests | Requires API Key |
|------------|---------|-------|------------------|
| Prompt Registry | `python tests/test_prompt_registry.py` | 9 | ❌ |
| Validation | `python tests/test_validation_v3.py` | 7 | ❌ |
| Visualization | `python tests/test_visualization_v3.py` | 12 | ❌ |
| Integration | `python tests/test_solver_v3_integration.py` | 6 | ✅ |
| **All Tests** | `pytest tests/test_*v3*.py -v` | **34** | ✅ (for integration) |
