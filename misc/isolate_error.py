import sys
import subprocess
import os

# Reuse tokenizer/parser/dumper
def tokenize(s):
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
    return stack[0]

def dump_kicad(sexp, indent=0):
    if not isinstance(sexp, list):
        return str(sexp)
    if not sexp: return "()"
    head = sexp[0]
    s = "\t" * indent + "(" + str(head)
    
    # Simple dump
    is_complex = False
    for item in sexp[1:]:
        if isinstance(item, list):
            is_complex = True
            break
    if not is_complex:
        for item in sexp[1:]:
            s += " " + str(item)
        s += ")"
        return s
    
    for item in sexp[1:]:
        if not isinstance(item, list):
            s += " " + str(item)
            
    for item in sexp[1:]:
        if isinstance(item, list):
            s += "\n" + dump_kicad(item, indent + 1)
            
    s += "\n" + "\t" * indent + ")"
    return s

def test_file(filepath):
    # Run kicad-cli
    try:
        res = subprocess.run(['kicad-cli', 'sch', 'erc', filepath, '--format', 'json', '--output', filepath + '.json'], capture_output=True)
    except FileNotFoundError:
        print("kicad-cli not found!")
        return False
        
    if res.returncode != 0:
        # print(f"kicad-cli failed with {res.returncode}")
        # print(res.stdout)
        # print(res.stderr)
        pass
        
    # If return code is 0, it loaded.
    # If return code is not 0, it might be violations (if flag set) or error.
    # We didn't set --exit-code-violations, so 0 means OK, non-zero means Error.
    return res.returncode == 0

def main(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    tokens = tokenize(content)
    sexps = parse_tokens(tokens)
    
    # We assume sexps is a list of top-level items. Usually just one (kicad_sch ...)
    root = sexps[0]
    if root[0] != 'kicad_sch':
        print("Not a kicad_sch file")
        return

    # Categories
    header_items = []
    lib_symbols = None
    wires = []
    labels = []
    instances = []
    sheet_instances = None
    others = []

    for item in root[1:]:
        if isinstance(item, list):
            tag = item[0]
            if tag == 'lib_symbols':
                lib_symbols = item
            elif tag == 'wire':
                wires.append(item)
            elif tag == 'label':
                labels.append(item)
            elif tag == 'symbol':
                instances.append(item)
            elif tag == 'sheet_instances':
                sheet_instances = item
            elif tag in ['version', 'generator', 'generator_version', 'uuid', 'paper', 'title_block']:
                header_items.append(item)
            else:
                others.append(item)
    
    # Construct base
    base_root = ['kicad_sch'] + header_items
    if sheet_instances:
        base_root.append(sheet_instances)
    
    # Test base
    print("Testing base...")
    with open('iso_test.kicad_sch', 'w') as f:
        f.write(dump_kicad(base_root))
    if not test_file('iso_test.kicad_sch'):
        print("Base failed!")
        return

    # Add lib_symbols
    if lib_symbols:
        print("Testing lib_symbols...")
        # Check if lib_symbols has many symbols
        symbols = [s for s in lib_symbols[1:] if isinstance(s, list)]
        # Add symbols one by one?
        # Let's try adding all first
        current_lib = ['lib_symbols'] + symbols
        current_root = base_root + [current_lib]
        with open('iso_test.kicad_sch', 'w') as f:
             f.write(dump_kicad(current_root))
        if not test_file('iso_test.kicad_sch'):
            print("lib_symbols failed! Testing individual symbols...")
            valid_symbols = []
            for sym in symbols:
                test_lib = ['lib_symbols'] + valid_symbols + [sym]
                current_root = base_root + [test_lib]
                with open('iso_test.kicad_sch', 'w') as f:
                     f.write(dump_kicad(current_root))
                if test_file('iso_test.kicad_sch'):
                    valid_symbols.append(sym)
                else:
                    print(f"Symbol {sym[1]} failed!")
            
            # Use valid symbols for next steps
            base_root.append(['lib_symbols'] + valid_symbols)
        else:
            base_root.append(current_lib)

    # Add wires
    if wires:
        print("Testing wires...")
        current_root = base_root + wires
        with open('iso_test.kicad_sch', 'w') as f:
             f.write(dump_kicad(current_root))
        if not test_file('iso_test.kicad_sch'):
             print("Wires failed!")
             # Bisect wires?
             valid_wires = []
             for w in wires:
                 current_root = base_root + valid_wires + [w]
                 with open('iso_test.kicad_sch', 'w') as f:
                     f.write(dump_kicad(current_root))
                 if test_file('iso_test.kicad_sch'):
                     valid_wires.append(w)
                 else:
                     print("A wire failed!")
             base_root += valid_wires
        else:
             base_root += wires

    # Add labels
    if labels:
        print("Testing labels...")
        current_root = base_root + labels
        with open('iso_test.kicad_sch', 'w') as f:
             f.write(dump_kicad(current_root))
        if not test_file('iso_test.kicad_sch'):
             print("Labels failed!")
        else:
             base_root += labels
             
    # Add instances
    if instances:
        print("Testing instances...")
        current_root = base_root + instances
        with open('iso_test.kicad_sch', 'w') as f:
             f.write(dump_kicad(current_root))
        if not test_file('iso_test.kicad_sch'):
             print("Instances failed! Testing individual instances...")
             valid_instances = []
             for inst in instances:
                 current_root = base_root + valid_instances + [inst]
                 with open('iso_test.kicad_sch', 'w') as f:
                     f.write(dump_kicad(current_root))
                 if test_file('iso_test.kicad_sch'):
                     valid_instances.append(inst)
                 else:
                     print(f"Instance {inst[1]} failed!")
             base_root += valid_instances
        else:
             base_root += instances
             
    print("Done. Final valid file is src/iso_test.kicad_sch")

if __name__ == '__main__':
    main(sys.argv[1])
