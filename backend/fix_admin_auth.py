import re
import os

path = "app/api.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern to find admin functions and their arguments
# Handles both single line and multi-line definitions
# We look for 'async def admin_name(args)' or 'def admin_name(args)'
pattern = re.compile(r"((?:async\s+)?def\s+admin_[a-zA-Z0-9_]+\s*\()([^)]*)(\)\s*:)", re.MULTILINE | re.DOTALL)

def replacer(match):
    prefix = match.group(1)
    args = match.group(2).strip()
    suffix = match.group(3)
    
    if "get_admin_user" in args:
        return match.group(0)
        
    if not args:
        # e.g. def admin_something():
        return f"{prefix}admin: User = Depends(get_admin_user){suffix}"
    
    # Check if last arg has a comma
    if args.endswith(","):
        return f"{prefix}{args}\n    admin: User = Depends(get_admin_user)\n{suffix}"
    else:
        return f"{prefix}{args}, admin: User = Depends(get_admin_user){suffix}"

new_content = pattern.sub(replacer, content)

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)
