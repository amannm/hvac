#!/usr/bin/env python3
"""kicad_sch_debug_fix.py

A small, intentionally conservative helper for debugging KiCad schematic (.kicad_sch)
S-expression issues based ONLY on KiCad's dev docs:
- S-expression Format intro
- S-expression Schematic format

It:
1) Parses the file as an s-expression (handles strings + ;; comments).
2) Prints diagnostics for a few high-signal structural issues.
3) Applies a few *obvious* auto-fixes:
   - Unquote generator argument if it is a valid token (lowercase/digits/_)
   - Unquote paper size if it matches known page sizes
   - Unquote (uuid "...") -> (uuid ...)
   - For schematic items whose grammar shows a trailing UNIQUE_IDENTIFIER,
     unwrap a final (uuid ...) list into a bare UUID atom.

This is NOT a full KiCad schematic writer.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union


# ------------------------
# Tokenization / parsing
# ------------------------

@dataclass
class Sym:
    v: str

@dataclass
class Str:
    v: str

Atom = Union[Sym, Str]
SExpr = Union[Atom, List["SExpr"]]


_TOKEN_SAFE_RE = re.compile(r"^[a-z0-9_]+$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# From the sexpr-intro 'paper' token description.
# (paper PAPER_SIZE | WIDTH HEIGHT [portrait])
# Valid named sizes include A0..A5 and A..E.
_KNOWN_PAPER_SIZES = {
    "A0", "A1", "A2", "A3", "A4", "A5",
    "A", "B", "C", "D", "E",
}


class ParseError(Exception):
    pass


def tokenize(text: str) -> Iterable[Tuple[str, str, int, int]]:
    """Yield (kind, value, line, col). kind in: LPAR, RPAR, SYM, STR."""
    i = 0
    line = 1
    col = 1
    n = len(text)

    def advance(ch: str):
        nonlocal line, col
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1

    while i < n:
        ch = text[i]

        # Whitespace
        if ch.isspace():
            advance(ch)
            i += 1
            continue

        # ;; comment to end-of-line (shown in schematic header example)
        if ch == ";" and i + 1 < n and text[i + 1] == ";":
            # consume until newline or EOF
            while i < n and text[i] != "\n":
                advance(text[i])
                i += 1
            continue

        if ch == "(":
            yield ("LPAR", ch, line, col)
            advance(ch)
            i += 1
            continue
        if ch == ")":
            yield ("RPAR", ch, line, col)
            advance(ch)
            i += 1
            continue

        if ch == '"':
            start_line, start_col = line, col
            i += 1
            advance('"')
            buf = []
            esc = False
            while i < n:
                c = text[i]
                if esc:
                    buf.append(c)
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    # end string
                    i += 1
                    advance('"')
                    yield ("STR", "".join(buf), start_line, start_col)
                    break
                else:
                    buf.append(c)
                advance(c)
                i += 1
            else:
                raise ParseError(f"Unterminated string at {start_line}:{start_col}")
            continue

        # Symbol / atom
        start_line, start_col = line, col
        buf = []
        while i < n and (not text[i].isspace()) and text[i] not in '()"':
            buf.append(text[i])
            advance(text[i])
            i += 1
        yield ("SYM", "".join(buf), start_line, start_col)


def parse(tokens: Iterable[Tuple[str, str, int, int]]) -> SExpr:
    stack: List[List[SExpr]] = []
    current: List[SExpr] = []
    started = False

    for kind, val, line, col in tokens:
        if kind == "LPAR":
            started = True
            stack.append(current)
            current = []
        elif kind == "RPAR":
            if not stack:
                raise ParseError(f"Unexpected ')' at {line}:{col}")
            finished = current
            current = stack.pop()
            current.append(finished)
        elif kind == "SYM":
            current.append(Sym(val))
        elif kind == "STR":
            current.append(Str(val))
        else:
            raise ParseError(f"Unknown token kind {kind}")

    if stack:
        raise ParseError("Unclosed '(' at end of file")
    if not started:
        raise ParseError("No s-expression found")

    # Typical KiCad files have a single top-level list.
    if len(current) != 1 or not isinstance(current[0], list):
        raise ParseError("Expected a single top-level s-expression list")
    return current[0]


# ------------------------
# Helpers
# ------------------------

def is_sym(x: SExpr, v: Optional[str] = None) -> bool:
    return isinstance(x, Sym) and (v is None or x.v == v)


def head(expr: SExpr) -> Optional[str]:
    if isinstance(expr, list) and expr and isinstance(expr[0], Sym):
        return expr[0].v
    return None


def symval(expr: SExpr) -> Optional[str]:
    return expr.v if isinstance(expr, Sym) else None


def strval(expr: SExpr) -> Optional[str]:
    return expr.v if isinstance(expr, Str) else None


def walk(expr: SExpr) -> Iterable[SExpr]:
    yield expr
    if isinstance(expr, list):
        for ch in expr:
            yield from walk(ch)


# ------------------------
# Diagnostics
# ------------------------

@dataclass
class Issue:
    code: str
    message: str


def collect_issues(root: SExpr) -> List[Issue]:
    issues: List[Issue] = []

    if head(root) != "kicad_sch":
        issues.append(Issue("E_ROOT", "Top-level list head is not 'kicad_sch' (required header token)."))
        return issues

    # header contains (version VERSION) and (generator GENERATOR)
    def find_child_list(token_name: str) -> Optional[List[SExpr]]:
        if not isinstance(root, list):
            return None
        for item in root[1:]:
            if isinstance(item, list) and head(item) == token_name:
                return item
        return None

    ver = find_child_list("version")
    if not ver or len(ver) < 2 or not isinstance(ver[1], Sym) or not re.fullmatch(r"\d{8}", ver[1].v):
        issues.append(Issue("E_VERSION", "Missing/invalid (version YYYYMMDD) in header."))

    gen = find_child_list("generator")
    if not gen or len(gen) < 2:
        issues.append(Issue("E_GENERATOR", "Missing (generator GENERATOR) in header."))
    elif isinstance(gen[1], Str):
        issues.append(Issue("W_GENERATOR_QUOTED", "(generator ...) argument is quoted; docs show it as an unquoted token."))

    pap = find_child_list("paper")
    if pap and len(pap) >= 2 and isinstance(pap[1], Str):
        issues.append(Issue("W_PAPER_QUOTED", "(paper ...) argument is quoted; docs show paper sizes as unquoted tokens."))

    # Token names must be lowercase (s-expression intro)
    for node in walk(root):
        if isinstance(node, list) and node and isinstance(node[0], Sym):
            t = node[0].v
            if any(c.isupper() for c in t):
                issues.append(Issue("W_TOKEN_CASE", f"Token '{t}' contains uppercase letters; token names should be lowercase."))

    # uuid usage
    for node in walk(root):
        if isinstance(node, list) and head(node) == "uuid":
            if len(node) != 2:
                issues.append(Issue("W_UUID_ARITY", "(uuid ...) does not have exactly one attribute."))
            elif isinstance(node[1], Str):
                issues.append(Issue("W_UUID_QUOTED", "(uuid ...) attribute is quoted; docs show UUID attribute unquoted."))

    # For some schematic sections, docs show a trailing UNIQUE_IDENTIFIER (bare), not (uuid ...)
    bare_uuid_end_tokens = {
        "junction",
        "no_connect",
        "bus_entry",
        "wire",
        "bus",
        "polyline",
        "text",
        "label",
        "global_label",
        "hierarchical_label",
        "symbol",
        "sheet",
    }
    for node in walk(root):
        if isinstance(node, list) and head(node) in bare_uuid_end_tokens and node:
            last = node[-1]
            if isinstance(last, list) and head(last) == "uuid":
                issues.append(Issue("W_UUID_WRAPPED", f"{head(node)} ends with (uuid ...); docs show a trailing UNIQUE_IDENTIFIER atom."))

    return issues


# ------------------------
# Auto-fixes (conservative)
# ------------------------


def _maybe_unquote_to_sym(a: Atom) -> Atom:
    """Convert Str("foo") -> Sym(foo) if it matches token rule; else keep as Str."""
    if isinstance(a, Str) and _TOKEN_SAFE_RE.fullmatch(a.v):
        return Sym(a.v)
    return a


def fix_in_place(root: SExpr) -> Tuple[SExpr, List[str]]:
    """Return (fixed_root, applied_fixes)."""
    applied: List[str] = []

    if not isinstance(root, list) or head(root) != "kicad_sch":
        return root, applied

    # Fix header generator quoting
    for item in root[1:]:
        if isinstance(item, list) and head(item) == "generator" and len(item) >= 2 and isinstance(item[1], Str):
            new_atom = _maybe_unquote_to_sym(item[1])
            if isinstance(new_atom, Sym) and new_atom.v != item[1].v:
                # same value, type changes
                pass
            if isinstance(new_atom, Sym):
                item[1] = new_atom
                applied.append("Unquoted (generator \"...\") -> (generator ...) when safe")

    # Fix header paper quoting for known sizes
    for item in root[1:]:
        if isinstance(item, list) and head(item) == "paper" and len(item) >= 2 and isinstance(item[1], Str):
            if item[1].v in _KNOWN_PAPER_SIZES:
                item[1] = Sym(item[1].v)
                applied.append("Unquoted (paper \"A4\") -> (paper A4) for known paper sizes")

    # Unquote all (uuid "...") -> (uuid ...)
    for node in walk(root):
        if isinstance(node, list) and head(node) == "uuid" and len(node) == 2 and isinstance(node[1], Str):
            if _UUID_RE.fullmatch(node[1].v):
                node[1] = Sym(node[1].v)
                applied.append("Unquoted UUID attribute in (uuid ...)")

    # Unwrap trailing (uuid ...) into bare UUID for tokens whose grammar shows UNIQUE_IDENTIFIER
    bare_uuid_end_tokens = {
        "junction",
        "no_connect",
        "bus_entry",
        "wire",
        "bus",
        "polyline",
        "text",
        "label",
        "global_label",
        "hierarchical_label",
        "symbol",
        "sheet",
    }

    for node in walk(root):
        if isinstance(node, list) and head(node) in bare_uuid_end_tokens and len(node) >= 2:
            last = node[-1]
            if isinstance(last, list) and head(last) == "uuid" and len(last) == 2:
                uuid_atom = last[1]
                if isinstance(uuid_atom, Str) and _UUID_RE.fullmatch(uuid_atom.v):
                    uuid_atom = Sym(uuid_atom.v)
                if isinstance(uuid_atom, (Sym, Str)):
                    node[-1] = uuid_atom
                    applied.append(f"Unwrapped trailing (uuid ...) into bare UNIQUE_IDENTIFIER for '{head(node)}'")

    return root, applied


# ------------------------
# Pretty printer
# ------------------------


def _escape_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def render(expr: SExpr, indent: int = 0) -> str:
    sp = "\t" * indent

    if isinstance(expr, Sym):
        return expr.v
    if isinstance(expr, Str):
        return '"' + _escape_str(expr.v) + '"'

    assert isinstance(expr, list)
    if not expr:
        return sp + "()"

    # decide compact vs expanded
    # compact if all children are atoms and list is short
    all_atoms = all(isinstance(x, (Sym, Str)) for x in expr)
    if all_atoms and len(expr) <= 5:
        inside = " ".join(render(x, 0) for x in expr)
        return sp + f"({inside})"

    # expanded
    out = [sp + "("]
    for i, child in enumerate(expr):
        if i == 0 and isinstance(child, Sym):
            # token name: keep on same line if next items small?
            out[-1] = sp + f"({child.v}"
            continue
        out.append(render(child, indent + 1))
    # close paren
    if out:
        # if first line already has '(token', close it on its own line
        out.append(sp + ")")
    return "\n".join(out)


# ------------------------
# CLI
# ------------------------


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Diagnose and apply conservative fixes to KiCad .kicad_sch s-expr files")
    ap.add_argument("input", type=Path, help="Input .kicad_sch file")
    ap.add_argument("-o", "--output", type=Path, default=None, help="Output path (default: input.fixed.kicad_sch)")
    ap.add_argument("--no-write", action="store_true", help="Only print diagnostics; do not write output")
    args = ap.parse_args(argv)

    text = args.input.read_text(encoding="utf-8", errors="replace")

    try:
        root = parse(tokenize(text))
    except ParseError as e:
        print(f"PARSE ERROR: {e}", file=sys.stderr)
        return 2

    issues = collect_issues(root)
    if issues:
        print("Diagnostics:")
        for it in issues:
            print(f"  [{it.code}] {it.message}")
    else:
        print("No issues detected by this limited checker.")

    fixed_root, applied = fix_in_place(root)

    if applied:
        print("\nApplied fixes:")
        for s in sorted(set(applied)):
            print(f"  - {s}")
    else:
        print("\nNo auto-fixes applied.")

    if args.no_write:
        return 0

    out_path = args.output
    if out_path is None:
        out_path = args.input.with_suffix(".fixed.kicad_sch")

    out_text = render(fixed_root) + "\n"
    out_path.write_text(out_text, encoding="utf-8")
    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
