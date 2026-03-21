"""Output formatting — parsing and sorting Prolog result terms."""

import re

from aspi.prolog.ast import PTerm, PVar, PAtom, PNum, PStr, PCompound, PArith


def _quote_atoms_in_term(s: str) -> str:
    result = []
    i = 0
    while i < len(s):
        if s[i] == "'":
            j = i + 1
            while j < len(s) and s[j] != "'": j += 1
            result.append(f'"{s[i+1:j]}"')
            i = j + 1
            continue
        if s[i] == '"':
            j = i + 1
            while j < len(s) and s[j] != '"': j += 1
            result.append(s[i:j+1])
            i = j + 1
            continue
        m = re.match(r'-?\d+(\.\d+)?', s[i:])
        if m:
            result.append(m.group(0))
            i += len(m.group(0))
            continue
        m = re.match(r'[a-z_][a-zA-Z0-9_]*', s[i:])
        if m:
            word = m.group(0)
            end = i + len(word)
            if end < len(s) and s[end] == '(':
                result.append(word)
            else:
                result.append(f'"{word}"')
            i = end
            continue
        result.append(s[i])
        i += 1
    return ''.join(result)


def _parse_result_term(s: str) -> PTerm:
    """Parse a Prolog term string (from term_to_atom) into a PTerm for sorting."""
    s = s.strip()
    if not s:
        return PAtom('')
    if s.startswith('"') and s.endswith('"'):
        return PStr(s[1:-1])
    if s.lstrip('-').isdigit():
        return PNum(int(s))
    if s == '_' or (s[0].isupper() and '(' not in s):
        return PVar(s)
    # Compound: name(args)
    m = re.match(r'([a-z_]\w*)\((.+)\)$', s)
    if m:
        name = m.group(1)
        args = []
        depth = 0
        cur = ''
        for ch in m.group(2):
            if ch in '([': depth += 1
            elif ch in ')]': depth -= 1
            if ch == ',' and depth == 0:
                args.append(_parse_result_term(cur))
                cur = ''
            else:
                cur += ch
        if cur:
            args.append(_parse_result_term(cur))
        return PCompound(name, tuple(args))
    return PAtom(s)


def _term_sort_key(s: str):
    """Sort key for Prolog result terms — structural comparison."""
    t = _parse_result_term(s)
    return _pterm_sort_key(t)


def _pterm_sort_key(t: PTerm):
    """Recursive sort key for PTerms."""
    match t:
        case PNum(v): return (0, v)
        case PStr(v): return (1, v)
        case PAtom(n): return (2, n)
        case PVar(n): return (3, n)
        case PCompound(f, args): return (4, f, tuple(_pterm_sort_key(a) for a in args))
        case PArith(op, l, r): return (5, op, _pterm_sort_key(l), _pterm_sort_key(r))
    return (6, repr(t))


def _parse_prolog_list(s: str) -> list:
    """Parse a Prolog list string like '[1,2,3]' into individual element strings."""
    s = s.strip()
    if not s.startswith('[') or not s.endswith(']'):
        return [s]
    inner = s[1:-1]
    if not inner:
        return []
    elements = []
    depth = 0
    cur = ''
    for ch in inner:
        if ch in '([': depth += 1
        elif ch in ')]': depth -= 1
        if ch == ',' and depth == 0:
            elements.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        elements.append(cur.strip())
    return elements


def _format_prolog_term(val) -> str:
    """Format a Prolog term (from writeq output) for display."""
    if isinstance(val, str):
        if val.startswith("'") and val.endswith("'"): return f'"{val[1:-1]}"'
        if "'" in val: return re.sub(r"'([^']*)'", r'"\1"', val)
        return val
    return str(val)
