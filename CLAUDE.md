# aspi

Experimental programming language based on Lambda DCS (Lambda Dependency-Based Compositional Semantics). Compiles to either Answer Set Programming (clingo) or SWI-Prolog.

## Running

```bash
# Use uv for all Python execution
uv run python -m aspi              # Hybrid ASP+Prolog backend (default)
uv run python -m aspi data.csv < program.ldcs
uv run python -m aspi.asp          # Pure ASP/clingo backend

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
| `aspi/ldcs.py` | Lark grammar + LDCS transformer (shared base for both backends) |
| `aspi/asp.py` | ASP/clingo backend — ClingoContext, ASPI, run_clingo |
| `aspi/prolog/ast.py` | PTerm/PGoal dataclasses, type aliases |
| `aspi/prolog/render.py` | render_term, render_goal, render_body |
| `aspi/prolog/analysis.py` | term_vars, goal_vars, goal_needs_ground, _DIRECTIONAL |
| `aspi/prolog/macros.py` | _MacroExpander, _to_pterm |
| `aspi/prolog/compiler.py` | PrologLDCS transformer (LDCS → Prolog AST) |
| `aspi/prolog/engine.py` | PrologEngine (subprocess swipl) |
| `aspi/prolog/formatting.py` | Result parsing and sorting |
| `aspi/prolog/repl.py` | PrologASPI (hybrid REPL + coordination) |
| `aspi/__main__.py` | Unified CLI entrypoint |
| `lib/prelude.pl` | Prolog prelude (modules, helpers, aggregation) |
| `lib/prelude.lp` | ASP prelude |
| `lib/macros.ldcs` | Domain macros (n1-n4) used by ASP backend |
| `test/` | Test programs (.ldcs), expected output (.log), CSV data (.csv) |

### Prolog Backend (`aspi/prolog/`)

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
- Subprocess swipl (not janus) — writes temp files, uses `writeq` for output (`double_quotes=string` preserves string/atom distinction)
- Both backends lazily initialized — ASP on first `!`/`?!`, Prolog compilation on first `?`
- `_parse_result_term` parses result strings into PTerm for structural sorting

### LDCS Language

See README.md for syntax. Key concepts:
- `.` joins predicates: `place_of_birth.seattle` = "place of birth of Seattle"
- `'` reverses: `children'.X` = "what X is a child of"
- `~` negates: `~red` = "not red"
- `{}` aggregates: `count{type.us_state}`, `sum{...}`, `max{...}`
- `X` (uppercase) = mu-abstraction (self-reference variable)
- Lines end with `.` (claim), `?` (query), `!` (plan), or `?!` (ASP-routed query)

## Testing

`.log` files are ASP-canonical — always generated from `uv run python -m aspi.asp`. Both test suites compare result lines (`that:`/`understood.`/`impossible.`/`yes.`/`no.`) including multiline continuation (`| ...` lines). Never regenerate `.log` files from the Prolog backend.

**Never filter test output.** No `-q`, `--tb=short`, `--tb=line`, `| tail`, `| grep`. Just run `uv run pytest` bare. The UI shows a compact scrolling view — full output is always needed to see what's actually failing.

## Backend Status

335 passed (across all test suites).

Planning (`!` goals) works via ASP fallback (parallel ASPI instance).
Proof tracking works via `prove/2` meta-interpreter in prelude.

### Hybrid ASP+Prolog via `?!`

Queries ending with `?!` route through the ASP backend instead of Prolog. This solves:
- **Performance**: Combinatorial search queries (euler/011, 023, 027, 030) use ASP's ground-and-solve
- **Planning state**: Queries needing ASP planning state (shrdlu) see ASP's world model directly
- **`that` sync**: `_asp_query()` syncs `that` facts to Prolog for mixed `?!`→`?` sequences

### Performance notes

Most tests Prolog is 2-4x faster than ASP. Previously slow tests now use `?!` routing:
- **euler/011**: 31s → 1.2s (via `?!`)
- **euler/023**: 25s → 3.3s (via `?!`)
- **euler/027**: 40s → 5.8s (via `?!`)
- **euler/009**: Pythagorean triples (also `?!`)
- Every test at or above ASP parity, 2x faster overall

