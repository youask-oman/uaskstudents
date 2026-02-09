import os

path = "app/api.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_admin_def = False
def_range = []

for i, line in enumerate(lines):
    if not in_admin_def:
        if line.strip().startswith("async def admin_") or line.strip().startswith("def admin_"):
            in_admin_def = True
            def_range = [i]
            if "):" in line:
                # Single line
                if "get_admin_user" not in line:
                    lines[i] = line.replace("):", ", admin: User = Depends(get_admin_user)):")
                in_admin_def = False
        new_lines.append(lines[i])
    else:
        def_range.append(i)
        if "):" in line:
            # End of multi-line def
            # Check if any line in def_range has get_admin_user
            full_def = "".join(lines[r] for r in def_range)
            if "get_admin_user" not in full_def:
                # Inject before ):
                # If there's a comma on the previous line or this line...
                # Let's just be simple: replace '):' with ', admin: User = Depends(get_admin_user)): '
                # but handle if there's already a comma on the previous line.
                
                # If the current line is just '    ):' or similar
                if line.strip() == "):":
                    # Check the PREVIOUS line
                    prev = lines[i-1].rstrip()
                    if prev.endswith(","):
                        lines[i] = line.replace("):", "admin: User = Depends(get_admin_user)):")
                    else:
                        lines[i] = line.replace("):", ", admin: User = Depends(get_admin_user)):")
                else:
                    # It's like '  db: Session = Depends(get_session)):'
                    lines[i] = line.replace("):", ", admin: User = Depends(get_admin_user)):")
                    
            in_admin_def = False
        new_lines.append(lines[i])

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)
