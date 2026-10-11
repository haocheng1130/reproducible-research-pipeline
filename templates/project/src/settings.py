"""Project configuration: the single place where paths, dates and credentials are defined.

Every other module reads configuration through this file:

    from settings import config
    DATA_DIR = config("DATA_DIR")

Precedence (highest first):
1. Command line:        python src/some_script.py --END_DATE=2020-12-31
2. Environment / .env:  END_DATE=2020-12-31   (python-decouple; project-root .env only)
3. The `defaults` dictionary below
4. An in-line default:  config("FRED_API_KEY", default="")
5. Otherwise an error that explains how to set the variable

Conventions:
- Names containing "DIR" are returned as absolute `Path`s. Relative paths are
  resolved from the project root, so `.env` can say `DATA_DIR=_data`.
- Names ending in "_DATE" are returned as `pandas.Timestamp`.
- `cast=bool` understands "True"/"False"/"1"/"0"/"yes"/"no" strings.

Run `python src/settings.py` to create the data and output directories.
"""

import sys
from pathlib import Path

import pandas as pd
from decouple import Config, RepositoryEmpty, RepositoryEnv

BASE_DIR = Path(__file__).absolute().parent.parent

# Read environment variables plus the project's own .env only. (decouple's
# default `config` would also pick up a .env found in any parent directory.)
_ENV_FILE = BASE_DIR / ".env"
_decouple_config = Config(
    RepositoryEnv(str(_ENV_FILE)) if _ENV_FILE.exists() else RepositoryEmpty()
)

defaults = {
    "BASE_DIR": BASE_DIR,
    "DATA_DIR": "_data",
    "MANUAL_DATA_DIR": "data_manual",
    "OUTPUT_DIR": "_output",
    "START_DATE": "1990-01-01",
    "END_DATE": "2024-12-31",
}

_MISSING = object()
_TRUE_STRINGS = {"1", "true", "yes", "y", "on", "t"}
_FALSE_STRINGS = {"0", "false", "no", "n", "off", "f", ""}


def find_all_caps_cli_vars(argv):
    """Return {NAME: value} for options written as --NAME=value or --NAME value.

    Only all-caps names are treated as configuration, so ordinary flags pass through.

    >>> find_all_caps_cli_vars(["x.py", "--END_DATE=2020-12-31", "--DATA_DIR", "/tmp/d", "-v"])
    {'END_DATE': '2020-12-31', 'DATA_DIR': '/tmp/d'}
    """
    found = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--") and "=" in arg and arg[2:].split("=")[0].isupper():
            name, value = arg[2:].split("=", 1)
            found[name] = value
        elif (
            arg.startswith("--")
            and arg[2:].isupper()
            and i + 1 < len(argv)
            and not argv[i + 1].startswith("--")
        ):
            found[arg[2:]] = argv[i + 1]
            i += 1
        i += 1
    return found


def if_relative_make_abs(path):
    """Resolve `path` against the project root unless it is already absolute."""
    path = Path(path)
    return path.resolve() if path.is_absolute() else (BASE_DIR / path).resolve()


def cast_bool(value):
    """Interpret common string spellings of booleans; reject anything ambiguous."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_STRINGS:
        return True
    if text in _FALSE_STRINGS:
        return False
    raise ValueError(f"Cannot interpret {value!r} as a boolean")


def standardize(name, value):
    """Apply the naming conventions: *DIR* -> absolute Path, *_DATE -> Timestamp."""
    if "DIR" in name:
        return if_relative_make_abs(value)
    if name.endswith("_DATE"):
        return pd.Timestamp(value)
    return value


def config(name, default=_MISSING, cast=None):
    """Return the configuration value `name` following the documented precedence."""
    cli_vars = find_all_caps_cli_vars(sys.argv[1:])
    if name in cli_vars:
        value = cli_vars[name]
    else:
        env_value = _decouple_config(name, default=_MISSING)
        if env_value is not _MISSING:
            value = env_value
        elif name in defaults:
            value = defaults[name]
        elif default is not _MISSING:
            value = default
        else:
            raise ValueError(
                f"Configuration variable '{name}' is not defined. Set it with one of:\n"
                f"  1. Command line: --{name}=value\n"
                f"  2. Environment variable or .env file: {name}=value\n"
                f"  3. The `defaults` dictionary in src/settings.py\n"
                f"Document it in .env.example as well."
            )
    if cast is bool:
        value = cast_bool(value)
    elif cast is not None:
        value = cast(value)
    return standardize(name, value)


def create_directories():
    """Create the data and output directories if they do not exist."""
    config("DATA_DIR").mkdir(parents=True, exist_ok=True)
    config("OUTPUT_DIR").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    create_directories()
