import sys
import re

def parse_sexp(s):
    s = s.replace('(', ' ( ').replace(')', ' ) ')
    tokens = s.split()
    stack = [[]]
    for token in tokens:
        if token == '(': 
            l = []
            stack[-1].append(l)
            stack.append(l)
        elif token == ')':
            stack.pop()
            if not stack:
                raise ValueError('Missing open parenthesis')
        else:
            stack[-1].append(token)
    if len(stack) > 1:
        raise ValueError('Missing close parenthesis')
    return stack[0]

def tokenize(s):
    # Improved tokenizer that handles quoted strings with spaces and escaped quotes
    tokens = []
    i = 0
    n = len(s)
    current_token = []
    in_string = False
    escaped = False
    
    while i < n:
        c = s[i]
        if in_string:
            if escaped:
                current_token.append(c)
                escaped = False
            elif c == '\\':
                escaped = True
                current_token.append(c)
            elif c == '"':
                current_token.append(c)
                in_string = False
                tokens.append("".join(current_token))
                current_token = []
            else:
                current_token.append(c)
        else:
            if c == '(': 
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append('(')
            elif c == ')':
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
                tokens.append(')')
            elif c == '"':
                if current_token: # Should not happen if space separated
                    tokens.append("".join(current_token))
                    current_token = []
                current_token.append(c)
                in_string = True
            elif c.isspace():
                if current_token:
                    tokens.append("".join(current_token))
                    current_token = []
            else:
                current_token.append(c)
        i += 1
    if current_token:
         tokens.append("".join(current_token))
    return tokens

def parse_tokens(tokens):
    stack = [[]]
    for token in tokens:
        if token == '(': 
            l = []
            stack[-1].append(l)
            stack.append(l)
        elif token == ')':
            if len(stack) > 1:
                stack.pop()
            else:
                raise ValueError("Too many closing parentheses")
        else:
            stack[-1].append(token)
    if len(stack) > 1:
        raise ValueError("Too many opening parentheses")
    return stack[0]

def dump_sexp(sexp, indent=0):
    lines = []
    indent_str = '\t' * indent
    
    if isinstance(sexp, list):
        if not sexp:
            return ""
        
        head = sexp[0]
        # Heuristic for formatting:
        # Some items should be inline, others multiline.
        # KiCad usually puts the head and some atomic args on the same line,
        # then lists on new lines.
        
        # Lists that are usually on one line:
        inline_tags = {'offset', 'at', 'size', 'start', 'end', 'pts', 'xy', 'stroke', 'fill', 'effects', 'font', 'justify', 'color', 'uuid', 'date', 'rev', 'company', 'comment', 'path', 'page', 'version', 'generator', 'generator_version', 'paper'}
        # Also property simple values
        
        is_inline = False
        if isinstance(head, str) and head in inline_tags:
             # Check if all children are atoms or simple lists
             is_inline = True
             for child in sexp[1:]:
                 if isinstance(child, list):
                     # If child list is not a simple coordinate/value, maybe not inline
                     # But most inline tags only have simple args
                     pass
        
        # Special case for 'pin_names' which was the issue
        if head == 'pin_names':
            is_inline = False 
            
        if is_inline:
             # serialize strictly on one line
             content = []
             for item in sexp:
                 if isinstance(item, list):
                     content.append(dump_sexp(item, 0)) # 0 indent for inline
                 else:
                     content.append(item)
             return "(" + " ".join(content) + ")"
        
        # Multiline block
        res = indent_str + "(" + str(head)
        
        # Check arguments
        args_inline = []
        children = []
        for item in sexp[1:]:
            if isinstance(item, list):
                children.append(item)
            else:
                args_inline.append(item)
        
        if args_inline:
            res += " " + " ".join(args_inline)
            
        if children:
            res += "\n"
            for child in children:
                res += dump_sexp(child, indent + 1)
                if child is not children[-1]:
                    res += "\n"
            res += "\n" + indent_str + ")"
        else:
            res += ")"
            
        return res
    else:
        return str(sexp)

# Specialized dumper for KiCad to match style closer
def dump_kicad(sexp, indent=0):
    if not isinstance(sexp, list):
        return str(sexp)
    if not sexp: return "()"
    
    head = sexp[0]
    
    # Items that should be single line
    oneline = False
    if head in ['at', 'size', 'offset', 'xy', 'pts', 'start', 'end', 'stroke', 'fill', 'uuid', 'version', 'generator', 'generator_version', 'paper', 'date', 'rev', 'company', 'comment', 'page', 'path', 'exclude_from_sim', 'in_bom', 'on_board', 'dnp', 'fields_autoplaced', 'embedded_fonts', 'pin_names']:
        # check if it contains complex nested lists
        # For 'pin_names', the issue was (pin_names (offset 1.016)) on one line in the bad file, 
        # but in the valid file it was multiline. 
        # My 'test.kicad_sch' that worked had it multiline.
        # But (pin_names (offset 1.016)) on one line SHOULD be valid sexp.
        # Unless 'pin_names' expects 'offset' to be an attribute, not a child list?
        # No, (offset 1.016) is a list.
        
        # Let's force multiline for 'pin_names' to be safe.
        if head != 'pin_names':
            oneline = True
            for item in sexp[1:]:
                 if isinstance(item, list):
                      if item[0] in ['effects', 'font']: # These can be nested deep
                           oneline = False
    
    # 'property' is special, it has key val (at ...) (effects ...)
    # usually: (property "Key" "Val" (at ...) (effects ...))
    # We want (at) and (effects) on new lines?
    # KiCad default:
    # (property "Reference" "R" (at 0 2.54 0)
    #   (effects (font (size 1.27 1.27)))
    # )
    
    s = "\t" * indent + "(" + head
    
    # Print atoms and simple lists inline
    atoms = []
    lists = []
    
    for item in sexp[1:]:
        if isinstance(item, list):
            lists.append(item)
        else:
            atoms.append(item)
            
    if atoms:
        s += " " + " ".join(atoms)
        
    if oneline and not lists:
        s += ")"
        return s

    if oneline and lists:
        # Check if lists are also simple
        all_simple = True
        for l in lists:
            # Check if l is deep
            pass 
        # Just simpler to recurse if lists exist, unless we know they are short
        if head in ['pts', 'stroke', 'fill', 'font']: # These usually have simple lists or none
             pass # keep oneline logic? 
             # pts has (xy ...) list
             # (pts (xy 1 1) (xy 2 2)) -> Multiline is better for diffs but oneline is valid?
             # existing files have (stroke (width 0) (type default)) on multiline
             pass

    # Force multiline for lists
    if lists:
        # close the opening line if we have atoms?
        # No, usually (property "K" "V" <newline> (at ...) ...)
        
        # Special handling for 'pts' which contains many 'xy'
        if head == 'pts':
            s += "\n"
            for l in lists:
                s += dump_kicad(l, indent + 1) + "\n"
            s += "\t" * indent + ")"
            return s.strip() # Remove last newline?
            
        for l in lists:
             s += "\n" + dump_kicad(l, indent + 1)
        
        s += "\n" + "\t" * indent + ")"
    else:
        s += ")"
        
    return s

def fix_structure(sexp):
    if not isinstance(sexp, list):
        return

    # Fix property (hide yes) location
    # Expected: (property ... (effects ... (hide yes)))
    # Found: (property ... (hide yes) (effects ...))
    
    if len(sexp) > 0 and sexp[0] == 'property':
        hide_node = None
        effects_node = None
        
        for item in sexp:
            if isinstance(item, list):
                if item[0] == 'hide':
                    hide_node = item
                elif item[0] == 'effects':
                    effects_node = item
        
        if hide_node and effects_node:
            # Move hide_node into effects_node
            sexp.remove(hide_node)
            effects_node.append(hide_node)

    # Recurse
    for item in sexp:
        if isinstance(item, list):
            fix_structure(item)

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    tokens = tokenize(content)
    sexps = parse_tokens(tokens)
    
    # Fix generator
    for item in sexps:
        if isinstance(item, list) and item and item[0] == 'generator':
            if len(item) > 1 and item[1] == '"chatgpt"':
                item[1] = '"eeschema"'
        fix_structure(item)
    
    # Dump
    # Use a custom simple dumper that is robust
    with open(filepath, 'w') as f:
        # Iterate over top level items and dump them
        for s in sexps:
             f.write(dump_kicad(s))
             f.write("\n")

if __name__ == '__main__':
    process_file(sys.argv[1])
