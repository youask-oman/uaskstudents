
import re
import os

def fix_file(path, pattern, replacement):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        print(f"No changes made to {path} with pattern {pattern}")
        # Try without newline sensitivity
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        if new_content == content:
           return

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print(f"Fixed {path}")

# Fix batch_tier_runtime.py
fix_file(
    r"d:\uaskstudents\backend\app\services\solve\batch_tier_runtime.py",
    r"llm_manager = LLMManager\(\)\s+primary_provider = \(llm_manager\.primary_provider or \"openai\"\)\.strip\(\)\.lower\(\)",
    r"llm_manager = get_llm_manager()\n    primary_provider = llm_manager.get_active_provider(session)"
)

# Fix api.py
fix_file(
    r"d:\uaskstudents\backend\app\api.py",
    r"mgr = get_llm_manager\(\)\s+provider = mgr\.primary_provider",
    r"mgr = get_llm_manager()\n        provider = mgr.get_active_provider(db)"
)

# Fix health check in api.py
fix_file(
    r"d:\uaskstudents\backend\app\api.py",
    r"\"provider\": mgr\.provider if hasattr\(mgr, \"provider\"\) else \"unknown\"",
    r"\"provider\": mgr.get_active_provider()"
)

# Fix superset_v2_pipeline.py
fix_file(
    r"d:\uaskstudents\backend\app\services\solve\superset_v2_pipeline.py",
    r"provider_name = \(solver\.client_manager\.primary_provider or \"openai\"\)\.strip\(\)\.lower\(\)",
    r"provider_name = solver.client_manager.get_active_provider(session)"
)

# Fix solver_v3.py
fix_file(
    r"d:\uaskstudents\backend\app\services\solver_v3.py",
    r"self\.client_manager\.primary_provider",
    r"self.client_manager.get_active_provider()"
)
