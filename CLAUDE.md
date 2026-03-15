# aspi

Experimental programming language based on Lambda DCS (Lambda Dependency-Based Compositional Semantics). Compiles to either Answer Set Programming (clingo) or SWI-Prolog.

## Running

```bash
# Use uv for all Python execution
uv run python aspi.py          # ASP/clingo backend (original)
uv run python prolog.py        # Prolog backend (in development on prolog-backend branch)
uv run python prolog.py data.csv < program.ldcs   # With CSV data

# Tests
uv run pytest test_aspi.py     # ASP backend tests
uv run pytest test_prolog.py   # Prolog backend tests
uv run pytest test_ast.py      # Prolog AST unit tests
uv run pytest test_backends.py # Cross-backend comparison
uv run python test_bench.py    # Performance benchmarks
```

## Architecture

### Files

| File | Purpose |
|------|---------|
| `ldcs.py` | Lark grammar + LDCS transformer (shared base for both backends) |
| `aspi.py` | ASP/clingo backend — accumulates ASP rules, shells out to clingo |
| `prolog.py` | Prolog backend — PTerm/PGoal AST, PrologLDCS transformer, subprocess swipl |
| `lib/prelude.pl` | Prolog prelude (modules, helpers, string ops, aggregation) |
| `lib/prelude.lp` | ASP prelude |
| `lib/macros.ldcs` | Domain macros (n1-n4) used by ASP backend |
| `test/` | Test programs (.ldcs), expected output (.log), CSV data (.csv) |

### Prolog Backend (`prolog.py`)

**AST types:**
- `PTerm`: `PVar | PAtom | PNum | PStr | PCompound | PArith` — all have `__str__` traps (raise TypeError) to prevent accidental string conversion
- `PGoal`: `GCall | GUnify | GIs | GCompare | GBetween | GNot | GFindAll | GBagOf | GWhen | GRaw`
- `PCSym = (PTerm, list[PGoal])` — a computed value and its goals
- `PUnary = Callable[[PTerm], list[PGoal]]` — takes result var, returns goals

**Key design:**
- `render_goal` auto-wraps directional builtins in `when/2` and bidirectional ones in `when(ground(A);ground(B), ...)`
- `conj()` partitions positive goals before GNot goals (generators before filters) — natural NAF without body reordering
- `define()` picks the LAST GCall as head (since `join` puts call at end)
- `_BUILTINS` dict replaces `lib/macros.ldcs` for the Prolog backend
- `_MacroExpander` only handles user-defined `#macro` rules
- Subprocess swipl (not janus) — writes temp files, uses `term_to_atom` for output
- `_parse_result_term` parses result strings into PTerm for structural sorting

### LDCS Language

See README.md for syntax. Key concepts:
- `.` joins predicates: `place_of_birth.seattle` = "place of birth of Seattle"
- `'` reverses: `children'.X` = "what X is a child of"
- `~` negates: `~red` = "not red"
- `{}` aggregates: `count{type.us_state}`, `sum{...}`, `max{...}`
- `X` (uppercase) = mu-abstraction (self-reference variable)
- Lines end with `.` (claim), `?` (query), or `!` (plan)

## Testing

Tests use full transcript checking — every line of output (understood/that/impossible/yes/no) is compared against `.log` files.

**Never filter test output.** No `-q`, `--tb=short`, `--tb=line`, `| tail`, `| grep`. Just run `uv run pytest` bare. The UI shows a compact scrolling view — full output is always needed to see what's actually failing.

Test with `--runxfail` to see actual failures for xfailed tests:
```bash
uv run pytest test_prolog.py -k "euler/002" --runxfail
```

## Prolog Backend Status (branch: prolog-backend)

219 passed, 3 xfailed:
- **euler/011, 027, 030**: Performance (would benefit from CLP(FD))

Remaining phases: CLP(FD) constraints, planning fallback (`!` goals).
