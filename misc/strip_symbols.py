import sys
import re

def tokenize(s):
    # Same tokenizer as before
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
                if current_token:
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

def dump_kicad(sexp, indent=0):
    # Reusing the simple dumper logic but implemented simpler here for just dumping
    if not isinstance(sexp, list):
        return str(sexp)
    if not sexp: return "()"
    
    head = sexp[0]
    
    s = "\t" * indent + "(" + str(head)
    
    # Heuristic for single line vs multiline
    # Just force multiline for simplicity if complex
    
    is_complex = False
    for item in sexp[1:]:
        if isinstance(item, list):
            is_complex = True
            break
            
    if not is_complex:
        # One line
        for item in sexp[1:]:
            s += " " + str(item)
        s += ")"
        return s
    
    # Multiline
    # Check if there are atomic args
    for item in sexp[1:]:
        if not isinstance(item, list):
            s += " " + str(item)
            
    for item in sexp[1:]:
        if isinstance(item, list):
            s += "\n" + dump_kicad(item, indent + 1)
            
    s += "\n" + "\t" * indent + ")"
    return s

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    tokens = tokenize(content)
    sexps = parse_tokens(tokens)
    
    for item in sexps:
        # Find (lib_symbols ...)
        if isinstance(item, list) and item and item[0] == 'kicad_sch':
            # It's nested inside kicad_sch
            # We need to find lib_symbols inside item
            for child in item:
                if isinstance(child, list) and child and child[0] == 'lib_symbols':
                    # Empty it
                    del child[1:]
                    break
    
    with open(filepath + ".stripped", 'w') as f:
        for s in sexps:
             f.write(dump_kicad(s))
             f.write("\n")

if __name__ == '__main__':
    process_file(sys.argv[1])
