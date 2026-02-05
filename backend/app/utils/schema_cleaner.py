
from typing import Dict, Any, List

def enforce_strict(node: Any) -> Any:
    """
    Recursively validates and cleans a JSON schema to ensure strict compatibility 
    with OpenAI Structured Outputs (Schema v1.0).
    
    Handles:
    - Pruning unsupported keys (title, description, default, examples)
    - Enforcing strict object properties
    - Normalizing type fields (removing 'null', handling list types)
    """
    if not isinstance(node, dict):
        return node
    
    # Remove unsupported keys for OpenAI strict mode validation
    node.pop('title', None)
    node.pop('description', None)
    node.pop('default', None)
    node.pop('examples', None)
    # OpenAI strict mode doesn't support these keywords at all
    node.pop('allOf', None)
    node.pop('if', None)
    node.pop('then', None)
    node.pop('else', None)
    
    # Handle 'type' normalization
    if "type" in node:
        t = node["type"]
        
        # Explicit check for bad type strings "None" or "null" which bypass list check
        if t == "None" or t == "null":
             # Fallback to object or string if type is weirdly None. 
             # Usually if it has properties it's object.
             if "properties" in node:
                 node["type"] = "object"
             else:
                 node["type"] = "string" # Safe fallback
        
        # Case 1: type is a list implies nullable or union
        elif isinstance(t, list):
            # Strict mode doesn't support type: ["string", "null"]
            # We must map this to anyOf if multiple non-null types exist,
            # or simply unwrap if it's just ["type", "null"]
            
            # Filter out 'null' ("None" check invalid for standard json schema but good for python None)
            valid_types = [x for x in t if x != "null" and x is not None and x != "None"]
            
            if not valid_types:
                # Fallback if everything was null
                node["type"] = "string" # Safe fallback?
            elif len(valid_types) == 1:
                node["type"] = valid_types[0]
            else:
                # If multiple valid types remain (e.g. string | number), OpenAI strict requires anyOf
                # Construct anyOf branch
                # But wait, OpenAI strict mode has specific requirements for anyOf.
                # Simplification: Just pick the first one or default to string to pass validation if complex.
                # For now, let's try to unwrap the first valid type to be safe and simple.
                # Ideally we'd convert to anyOf, but that requires restructuring the node.
                node["type"] = valid_types[0]
                
    # Handle objects
    if node.get("type") == "object" or "properties" in node:
        node["type"] = "object"
        node["additionalProperties"] = False
        
        props = node.get("properties", {})
        # Strict mode requires all properties to be required
        if props:
            node["required"] = list(props.keys()) 
        else:
            node["required"] = []

        for prop_name, prop_schema in props.items():
            enforce_strict(prop_schema)
            
    # Handle arrays
    if node.get("type") == "array":
        if "items" in node:
            enforce_strict(node["items"])
            
    # Handle definitions ($defs)
    if "$defs" in node:
        for def_name, def_schema in node["$defs"].items():
            enforce_strict(def_schema)
            
    # Handle anyOf, allOf, oneOf
    for key in ["anyOf", "oneOf"]:
         if key in node:
            cleaned_nodes = []
            for sub_node in node[key]:
                # Skip pure null options if they exist as separate schemas
                if isinstance(sub_node, dict) and (sub_node.get("type") == "null" or sub_node.get("type") == "None"):
                    continue
                enforce_strict(sub_node)
                cleaned_nodes.append(sub_node)
            
            # Update the list
            node[key] = cleaned_nodes
            
            # If only one option remains, unwrap it
            if len(cleaned_nodes) == 1:
                # Merge the single option into the parent
                single = cleaned_nodes[0]
                del node[key]
                node.update(single)
                # Re-run enforce strict on the merged node to ensure consistency
                enforce_strict(node)

    return node
