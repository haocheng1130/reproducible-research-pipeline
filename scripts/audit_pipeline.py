"""Static audit of a research / data-pipeline repository against the
reproducible-research-pipeline conventions
(https://github.com/haocheng1130/reproducible-research-pipeline).

Usage:
    python audit_pipeline.py [REPO_DIR] [--json]

Standard library only, so it runs before the project's environment exists.
Uses `git` if it is on PATH to inspect tracked files and history.
Exit code 1 if any FAIL finding, else 0.

It does not run the pipeline. A clean audit is necessary, not sufficient: still
check that `doit` works from a fresh clone and that the tests are well motivated.
"""

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FAIL, WARN, INFO = "FAIL", "WARN", "INFO"
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "_data", "_output",
             "docs", "_docs", "node_modules", ".pixi", "build", "dist", ".ipynb_checkpoints"}
DATA_EXTENSIONS = {".parquet", ".csv", ".feather", ".h5", ".hdf5", ".sas7bdat",
                   ".dta", ".pkl", ".pickle", ".zip", ".gz", ".xlsx", ".xls"}
SECRET_NAME = re.compile(r"(password|passwd|secret|api_?key|token|access_?key)", re.I)
NOT_SECRET_SUFFIX = re.compile(r"(_URL|_URI|_PATH|_FILE|_DIR|_NAME|_ENV|_VAR)$", re.I)
ENV_FILE = re.compile(r"^\.env(\..+)?$")
ENV_TEMPLATE = re.compile(r"^\.env\.(example|sample|template)", re.I)
RUN_COMMAND = re.compile(r"(^|\n)[ \t>$`]*(doit|make|snakemake|uv run|pixi run)\b")
ABS_PATH = re.compile(r"^(/Users/|/home/|/mnt/|[A-Za-z]:[\\/])")
NETWORK_CALLS = {"urlopen", "Connection", "raw_sql", "DataReader", "bdh", "bdp", "download"}
NETWORK_MODULES = {"requests", "httpx", "urllib", "wrds", "yf", "yfinance", "web"}
SAVE_CALLS = {"to_parquet", "to_csv", "to_excel", "savefig", "write_html", "write_parquet",
              "write_csv", "sink_parquet", "to_pickle"}


def add(findings, level, area, message, path=None):
    findings.append({"level": level, "area": area, "message": message,
                     "path": str(path) if path else None})


def run_git(repo, *args):
    """Run a git command in `repo`; return stdout lines, or None if git is unavailable."""
    if shutil.which("git") is None:
        return None
    inside = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line.strip()]


def iter_python_files(repo):
    """Project .py files, skipping generated folders and dot-folders (.claude, .venv, ...)."""
    for path in sorted(repo.rglob("*.py")):
        parts = path.relative_to(repo).parts[:-1]
        if not any(part in SKIP_DIRS or part.startswith(".") for part in parts):
            yield path


def check_structure(repo, findings):
    if not (repo / "README.md").exists():
        add(findings, FAIL, "structure", "No README.md (the README is the run book).")
    else:
        readme = (repo / "README.md").read_text(errors="ignore")
        if not RUN_COMMAND.search(readme):
            add(findings, WARN, "structure",
                "README does not mention how to run the pipeline (e.g. `doit`).", "README.md")

    runners = ["dodo.py", "Makefile", "Snakefile", "pixi.toml"]
    if not any((repo / r).exists() for r in runners):
        add(findings, FAIL, "structure",
            "No task runner file (dodo.py / Makefile / Snakefile / pixi tasks).")

    env_specs = ["requirements.txt", "pyproject.toml", "environment.yml", "pixi.toml", "uv.lock"]
    if not any((repo / e).exists() for e in env_specs):
        add(findings, FAIL, "environment",
            "No dependency specification (requirements.txt / pyproject.toml / environment.yml).")
    req = repo / "requirements.txt"
    if req.exists() and not (repo / "uv.lock").exists() and not (repo / "pixi.lock").exists():
        lines = [ln.split("#")[0].strip() for ln in req.read_text(errors="ignore").splitlines()]
        pkgs = [ln for ln in lines if ln and not ln.startswith(("-", "git+", "http"))]
        unpinned = [p for p in pkgs if "==" not in p]
        if unpinned:
            add(findings, WARN, "environment",
                f"{len(unpinned)}/{len(pkgs)} requirements not pinned with '==': "
                + ", ".join(unpinned[:8]) + (" ..." if len(unpinned) > 8 else ""),
                "requirements.txt")

    if not (repo / ".env.example").exists() and not list(repo.glob(".env.example*")):
        add(findings, WARN, "config", "No .env.example documenting configuration variables.")

    gitignore = repo / ".gitignore"
    if not gitignore.exists():
        add(findings, FAIL, "git", "No .gitignore.")
    else:
        text = gitignore.read_text(errors="ignore")
        rules = [ln.strip() for ln in text.splitlines()
                 if ln.strip() and not ln.strip().startswith(("#", "!"))]
        for needle, why in [("_data", "pulled data"), ("_output", "generated outputs"),
                            (".env", "secrets")]:
            if not any(needle in rule for rule in rules):
                add(findings, WARN, "git", f".gitignore does not ignore {needle} ({why}).",
                    ".gitignore")

    if not any((repo / "src" / name).exists() for name in ("settings.py", "config.py")):
        add(findings, WARN, "config",
            "No src/settings.py (or config.py): configuration should have one home.")

    tests = [p for p in iter_python_files(repo)
             if p.name.startswith("test_") or p.name.endswith("_test.py")]
    if not tests:
        add(findings, FAIL, "tests", "No test files (test_*.py).")

    workflows = list((repo / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        add(findings, WARN, "ci", "No GitHub Actions workflow (.github/workflows/*.yml).")
    elif not any("pytest" in w.read_text(errors="ignore") for w in workflows):
        add(findings, WARN, "ci", "No workflow runs pytest.")


def check_git(repo, findings):
    tracked = run_git(repo, "ls-files")
    if tracked is None:
        add(findings, INFO, "git", "Not a git repo (or git unavailable): history checks skipped.")
        return
    env_files = [t for t in tracked
                 if ENV_FILE.match(Path(t).name) and not ENV_TEMPLATE.match(Path(t).name)]
    if env_files:
        add(findings, FAIL, "secrets", "Tracked env file(s): " + ", ".join(env_files))
    history = run_git(repo, "log", "--all", "--name-only", "--format=")
    if history:
        leaked = sorted({h for h in history if Path(h).name in (".env", ".pgpass")})
        if leaked:
            add(findings, FAIL, "secrets",
                "Secret file(s) present in git history: " + ", ".join(leaked)
                + ". Rewrite history and rotate credentials.")
    generated = [t for t in tracked if t.startswith(("_data/", "_output/"))]
    if generated:
        add(findings, WARN, "git",
            f"{len(generated)} tracked file(s) under _data/ or _output/ (should be generated).")
    for t in tracked:
        path = repo / t
        if not path.is_file():
            continue
        size_mb = path.stat().st_size / 1e6
        if path.suffix.lower() in DATA_EXTENSIONS and not t.startswith("data_manual/") \
                and size_mb > 1:
            add(findings, WARN, "data",
                f"Data-like file tracked outside data_manual/ ({size_mb:.1f} MB). "
                "Check the license; prefer regenerating it.", t)
        elif size_mb > 20:
            add(findings, WARN, "git", f"Large tracked file ({size_mb:.1f} MB).", t)
        if path.suffix == ".ipynb":
            try:
                nb = json.loads(path.read_text(errors="ignore"))
                if any(cell.get("outputs") for cell in nb.get("cells", [])):
                    add(findings, WARN, "notebooks",
                        "Notebook committed with outputs; prefer jupytext *.ipynb.py "
                        "and let the DAG execute it.", t)
            except (json.JSONDecodeError, OSError):
                pass


def call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def is_network_call(node):
    """True for calls like requests.get(...), wrds.Connection(...), urlopen(...)."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
            and func.value.id in NETWORK_MODULES:
        return True
    return call_name(node) in NETWORK_CALLS


def check_python_file(path, repo, local_modules, findings):
    rel = path.relative_to(repo)
    source = path.read_text(errors="ignore")
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        add(findings, FAIL, "code", f"Syntax error: {err}", rel)
        return
    is_notebook = path.name.endswith(".ipynb.py")
    is_test = path.name.startswith("test_")
    is_config = path.name in ("settings.py", "config.py")

    if not is_notebook and path.name != "__init__.py" and ast.get_docstring(tree) is None:
        add(findings, WARN, "style", "Missing module docstring stating the file's purpose.", rel)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and ABS_PATH.match(node.value) and "\n" not in node.value:
            add(findings, WARN, "paths",
                f"Hard-coded absolute path {node.value[:60]!r}; use settings.config().", rel)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str) and len(node.value.value) >= 8:
            for target in node.targets:
                value = node.value.value
                if isinstance(target, ast.Name) and SECRET_NAME.search(target.id) \
                        and not NOT_SECRET_SUFFIX.search(target.id) \
                        and not value.startswith(("http://", "https://", "/", "./")) \
                        and " " not in value and not is_test:
                    add(findings, FAIL, "secrets",
                        f"Possible hard-coded secret assigned to {target.id}.", rel)
        if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv") \
                and isinstance(node.value, ast.Name) and node.value.id == "os" \
                and not is_config and path.name != "dodo.py":
            add(findings, WARN, "config",
                "Reads os.environ directly; route configuration through settings.config().",
                rel)
        if isinstance(node, ast.ExceptHandler):
            if node.type is None or (
                isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
                and len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            ):
                add(findings, WARN, "code",
                    f"Broad except at line {node.lineno} may hide data errors.", rel)
        if isinstance(node, ast.Import) and not is_notebook:
            for alias in node.names:
                if alias.asname and alias.name in local_modules:
                    add(findings, INFO, "style",
                        f"Local module imported with alias ({alias.name} as {alias.asname}).", rel)

    if is_notebook:
        if "sys.path" in source or "__file__" in source:
            add(findings, WARN, "notebooks",
                "Notebook uses sys.path/__file__, which break after jupytext conversion.", rel)
        return

    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in functions:
        if re.search(r"[a-z][A-Z]", fn.name) and not fn.name.startswith("test"):
            add(findings, INFO, "style", f"camelCase function name {fn.name}().", rel)
        calls = {call_name(c) for c in ast.walk(fn) if isinstance(c, ast.Call)}
        if fn.name.startswith("load_"):
            pulls = {c for c in calls if c.startswith("pull_")} | {
                call_name(c) for c in ast.walk(fn)
                if isinstance(c, ast.Call) and is_network_call(c)}
            if pulls:
                add(findings, WARN, "pull/load",
                    f"{fn.name}() calls {sorted(pulls)}; load_ should only read from disk.", rel)
        if fn.name.startswith("pull_"):
            saves = calls & SAVE_CALLS
            if saves:
                add(findings, WARN, "pull/load",
                    f"{fn.name}() also saves ({sorted(saves)}); save in __main__ instead.", rel)

    if path.name.startswith("pull_"):
        names = {fn.name for fn in functions}
        if not any(n.startswith("pull") for n in names):
            add(findings, WARN, "pull/load", "pull_ module defines no pull_* function.", rel)
        if not any(n.startswith("load") for n in names):
            add(findings, WARN, "pull/load",
                "pull_ module defines no load_* function to read the cached data.", rel)

    if not is_test and path.name != "dodo.py":
        n_prints = sum(1 for c in ast.walk(tree)
                       if isinstance(c, ast.Call) and call_name(c) == "print")
        if n_prints > 3:
            add(findings, INFO, "style",
                f"{n_prints} print() calls; prefer quiet code (or logging).", rel)


def check_dodo(repo, findings):
    dodo = repo / "dodo.py"
    if not dodo.exists():
        return
    tree = ast.parse(dodo.read_text(errors="ignore"))
    text = dodo.read_text(errors="ignore")
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("task_")]:
        for d in [n for n in ast.walk(fn) if isinstance(n, ast.Dict)]:
            keys = {k.value for k in d.keys if isinstance(k, ast.Constant)}
            if "actions" not in keys:
                continue
            label = f"{fn.name}"
            if "file_dep" not in keys and "uptodate" not in keys:
                add(findings, INFO, "dag",
                    f"{label}: no file_dep/uptodate, so it reruns on every `doit`.", "dodo.py")
            if "targets" not in keys:
                add(findings, INFO, "dag",
                    f"{label}: no targets; downstream tasks cannot depend on its outputs.",
                    "dodo.py")
            if "pull" in fn.name:
                for k, v in zip(d.keys, d.values):
                    if isinstance(k, ast.Constant) and k.value == "clean" \
                            and isinstance(v, ast.Constant) and v.value is True:
                        add(findings, WARN, "dag",
                            f"{label}: clean=True lets `doit clean` delete expensive pulls; "
                            "use clean: [].", "dodo.py")
    settings_text = ""
    for name in ("settings.py", "config.py"):
        if (repo / "src" / name).exists():
            settings_text += (repo / "src" / name).read_text(errors="ignore")
    if ("START_DATE" in settings_text or "END_DATE" in settings_text) \
            and "config_changed" not in text:
        add(findings, INFO, "dag",
            "Dates are configurable but dodo.py never uses config_changed: changing "
            "END_DATE will not trigger reruns.", "dodo.py")


def audit(repo):
    findings = []
    check_structure(repo, findings)
    check_git(repo, findings)
    py_files = list(iter_python_files(repo))
    local_modules = {p.stem for p in py_files}
    for path in py_files:
        check_python_file(path, repo, local_modules, findings)
    check_dodo(repo, findings)
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    findings = audit(repo)
    order = {FAIL: 0, WARN: 1, INFO: 2}
    findings.sort(key=lambda f: (order[f["level"]], f["area"], f["path"] or ""))
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        counts = {lvl: sum(f["level"] == lvl for f in findings) for lvl in order}
        print(f"Audit of {repo}")
        print(f"  {counts[FAIL]} FAIL, {counts[WARN]} WARN, {counts[INFO]} INFO\n")
        for f in findings:
            where = f" [{f['path']}]" if f["path"] else ""
            print(f"{f['level']:4}  {f['area']:<10} {f['message']}{where}")
    sys.exit(1 if any(f["level"] == FAIL for f in findings) else 0)


if __name__ == "__main__":
    main()
