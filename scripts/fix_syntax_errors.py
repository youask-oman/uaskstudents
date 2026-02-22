
import os

def fix_backslash_quote(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    # Replace \" with "
    new_content = content.replace('\\"provider\\"', '"provider"')
    
    if new_content == content:
        print(f"No changes made to {path}")
        return

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print(f"Fixed {path}")

# Fix api.py
fix_backslash_quote(r"d:\uaskstudents\backend\app\api.py")

def add_import(path, line_prefix, add):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8', newline='') as f:
        lines = f.readlines()
    
    new_lines = []
    found_line = False
    for line in lines:
        if line.startswith(line_prefix) and add not in line:
            new_lines.append(line.rstrip() + ", " + add + "\n")
            found_line = True
        else:
            new_lines.append(line)
            
    if not found_line:
        print(f"Could not find prefix {line_prefix} or import {add} already exists in that line in {path}")
        return

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(new_lines)
    print(f"Added import {add} to {path}")

# Fix batch_tier_runtime.py import
add_import(r"d:\uaskstudents\backend\app\services\solve\batch_tier_runtime.py", "from app.services.llm.manager import", "get_llm_manager")
