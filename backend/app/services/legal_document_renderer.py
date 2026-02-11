from html import escape


def markdown_to_basic_html(content_md: str) -> str:
    """
    Minimal markdown-to-HTML renderer for legal text storage.
    Frontend still renders markdown for display fidelity.
    """
    lines = (content_md or "").splitlines()
    html_lines = []
    in_list = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{escape(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{escape(line[4:].strip())}</h3>")
            continue
        if line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{escape(line[2:].strip())}</li>")
            continue
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{escape(line)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)
