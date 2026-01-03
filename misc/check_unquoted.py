
import re

def check_barewords(filename):
    with open(filename, 'r') as f:
        content = f.read()

    # Regex for tokens: 
    # 1. Quoted string
    # 2. Parentheses
    # 3. Bareword (unquoted)
    token_pattern = re.compile(r'"(?:\\.|[^""])*"|\(|\)|[^\s\(\)"]+')
    
    in_string = False
    escaped = False
    
    # We'll just use a simple state machine to find tokens NOT inside quotes
    pos = 0
    line_num = 1
    while pos < len(content):
        char = content[pos]
        if char == '\n':
            line_num += 1
            pos += 1
            continue
        if char.isspace():
            pos += 1
            continue
            
        if char == '"':
            # Skip quoted string
            pos += 1
            while pos < len(content):
                if content[pos] == '"' and content[pos-1] != '\\':
                    pos += 1
                    break
                pos += 1
            continue
            
        if char in '()':
            pos += 1
            continue
            
        # Bareword
        match = re.match(r'[^\s\(\)"]+', content[pos:])
        if match:
            bareword = match.group(0)
            # KiCad barewords usually don't have special characters
            # Let's see if any look suspicious (e.g. containing / or : if not expected)
            # Actually, let's just print them all for now if they are long or weird
            if not re.match(r'^[a-zA-Z0-9_\.\-\+]+$', bareword):
                 print(f"Suspicious bareword at line {line_num}: {bareword}")
            pos += len(bareword)
        else:
            pos += 1

if __name__ == "__main__":
    check_barewords('../src/device.kicad_sch')
