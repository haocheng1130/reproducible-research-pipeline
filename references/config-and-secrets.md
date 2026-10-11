# Configuration and Secrets

## Principle (Twelve-Factor App, factor III)
"Config varies substantially across deploys, code does not." Config covers
database handles, credentials, per-machine paths and run windows. It lives in the
environment, never as constants in code. Environment variables are easy to
change per deploy, hard to commit by accident, and language-agnostic. The same
code then runs on a laptop, an HPC node, CI and an autograder. Only `.env`
differs.

## Rules
1. **One config module**: `src/settings.py`. Every other file does:
   ```python
   from settings import config
   DATA_DIR = config("DATA_DIR")
   WRDS_USERNAME = config("WRDS_USERNAME")
   ```
   No module reads `os.environ` directly or hard-codes a path.
2. **`.env` is never committed**, and must not appear anywhere in git history.
   `.gitignore` contains `.env*` and `!.env.example*`.
3. **`.env.example` is committed.** It lists every variable with a dummy value
   and a comment saying when it is needed.
4. **Sensible defaults** live in `settings.py`, so the project runs with an empty
   `.env` wherever no secret is needed.
5. **Validate early.** A missing required variable raises an error that tells the
   user how to set it.
6. Separate files per environment (`.env.development`, `.env.production`) are
   fine. Copy one to `.env` to switch.

## Precedence (course template)
1. Command-line `--VAR=value` (or `--VAR value`), all-caps names only
2. Environment variable, or `.env` via python-decouple
3. `settings.py` defaults dictionary
4. In-line default passed to `config("VAR", default=...)`
5. Error, with instructions

Any variable whose name contains `DIR` is converted to an absolute path,
resolved relative to the project root (`BASE_DIR`). Relative paths in `.env`
therefore work from anywhere.

## Typical variables
```dotenv
# .env.example
# Paths (relative paths are resolved from the project root)
DATA_DIR=_data
OUTPUT_DIR=_output

# Sample window
START_DATE=1963-07-01
END_DATE=2024-12-31

# Credentials (only needed when pulling live)
WRDS_USERNAME=
# FRED_API_KEY=

# False: download the cached extract (no account needed). True: pull live.
NO_CACHE=False
```
WRDS: the `wrds` package can authenticate without a prompt through a
`~/.pgpass` file created on first login. That file lives in the home directory,
never in the repo.

## Minimal settings.py
See `templates/project/src/settings.py` for a complete, commented version. The
core:
```python
from decouple import config as _config   # python-decouple
BASE_DIR = Path(__file__).absolute().parent.parent
defaults = {"DATA_DIR": BASE_DIR / "_data", "OUTPUT_DIR": BASE_DIR / "_output",
            "START_DATE": "1913-01-01", "END_DATE": "2024-12-31"}

def config(name, default=None, cast=None):
    """CLI > env/.env > settings defaults > in-line default > error."""
    ...

if __name__ == "__main__":
    config("DATA_DIR").mkdir(parents=True, exist_ok=True)
    config("OUTPUT_DIR").mkdir(parents=True, exist_ok=True)
```

## Pattern: cached extract vs live pull (from HW0)
Projects that depend on licensed data, such as WRDS, should still run for
someone without credentials (a grader, a teammate whose account is pending, or
CI):
- `NO_CACHE=False` (default): download a small cached extract and save it to the
  **same path** the live pull would write.
- `NO_CACHE=True`: run the real queries. The queries stay in the repo either way,
  because "every number traces back to code".
- In `dodo.py`, add `"uptodate": [config_changed(str(NO_CACHE))]` so switching
  the flag reruns the task.
- Only publish a cached extract if the data license allows it.

## Secrets hygiene checklist
- [ ] `git ls-files | grep -E '(^|/)\.env$'` returns nothing
- [ ] `git log --all --oneline -- .env` returns nothing. If it does, rewrite history (for example with `git filter-repo`) **and rotate the secret**
- [ ] No keys or passwords in notebooks, outputs, logs or CI YAML. CI uses repository secrets
- [ ] No licensed raw data (CRSP, Compustat, TAQ, ...) committed, even in `_output` samples
