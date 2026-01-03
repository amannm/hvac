import sys

def check_parens(filename):
    with open(filename, 'r') as f:
        content = f.read()

    stack = []
    in_string = False
    escaped = False
    
    for i, char in enumerate(content):
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
                line_num = content[:i].count('\n') + 1
                stack.append(line_num)
            elif char == ')':
                if not stack:
                    line_num = content[:i].count('\n') + 1
                    print(f"Error: Unexpected closing parenthesis at line {line_num}")
                    return
                stack.pop()

    if stack:
        print(f"Error: {len(stack)} unclosed parentheses. First unclosed at line {stack[0]}")
    else:
        print("Success: Parentheses are balanced.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_parens(sys.argv[1])
    else:
        check_parens('../src/device.kicad_sch')