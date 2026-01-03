
import re

def check_symbols(filename):
    with open(filename, 'r') as f:
        content = f.read()

    # Find the lib_symbols block
    start_match = re.search(r'\(lib_symbols', content)
    if not start_match:
        print("No lib_symbols block found")
        return
    
    start_pos = start_match.start()
    
    # Extract just the lib_symbols block content to analyze it specifically
    # but we need to find where it ends.
    balance = 0
    in_string = False
    escaped = False
    symbols = []
    current_symbol_start = -1
    
    for i in range(start_pos, len(content)):
        char = content[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == '(': 
                balance += 1
                # Check for start of a symbol inside lib_symbols
                if balance == 2: # (lib_symbols (symbol ...))
                    if content[i:].startswith('(symbol'):
                        current_symbol_start = i
            elif char == ')':
                if balance == 2 and current_symbol_start != -1:
                    symbols.append(content[current_symbol_start:i+1])
                    current_symbol_start = -1
                balance -= 1
                if balance == 0:
                    break

    print(f"Found {len(symbols)} symbols in lib_symbols")
    
    # Now check if there is anything BETWEEN lib_symbols and the first symbol, 
    # or between symbols, that isn't whitespace. 
    
if __name__ == "__main__":
    check_symbols('../src/device.kicad_sch')
