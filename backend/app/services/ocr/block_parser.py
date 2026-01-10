import re
from typing import List, Dict, Any

class MarkdownBlockParser:
    """
    Parses raw OCR markdown into structured blocks: text, math, figure.
    """
    
    # Regex for Pix2Text/Markdown figure blocks: ![](figures/...)
    FIGURE_PATTERN = re.compile(r'!\[.*?\]\((figures/.*?)\)')
    
    # Regex for math blocks: $$...$$, \[...\], \(...\)
    # We focus on the most common one first: $$...$$
    MATH_BLOCK_PATTERN = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    
    def parse(self, text: str) -> List[Dict[str, Any]]:
        blocks = []
        
        # This is a simplified sequential parser. 
        # For production, we'd use a more robust split/match approach.
        
        last_idx = 0
        # Combine patterns to find the next matching block of any type
        combined_pattern = re.compile(r'(!\[.*?\]\(figures/.*?\))|(\$\$.*?\$\$)', re.DOTALL)
        
        for match in combined_pattern.finditer(text):
            # 1. Capture text before the match
            if match.start() > last_idx:
                text_content = text[last_idx:match.start()].strip()
                if text_content:
                    blocks.append({"type": "text", "content": text_content})
            
            # 2. Capture the matched block
            full_match = match.group(0)
            if full_match.startswith('!['):
                # Figure block
                img_match = self.FIGURE_PATTERN.search(full_match)
                asset_id = img_match.group(1) if img_match else full_match
                blocks.append({
                    "type": "figure", 
                    "content": full_match,
                    "asset_id": asset_id
                })
            elif full_match.startswith('$$'):
                # Math block
                math_content = full_match.strip('$').strip()
                blocks.append({
                    "type": "math", 
                    "content": math_content
                })
            
            last_idx = match.end()
            
        # 3. Capture remaining text
        if last_idx < len(text):
            text_content = text[last_idx:].strip()
            if text_content:
                blocks.append({"type": "text", "content": text_content})
                
        return blocks

markdown_block_parser = MarkdownBlockParser()
