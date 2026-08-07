"""Executes generated code for real, inside an isolated Docker container
(no network, capped CPU/memory) — no LLM judgment, just what actually happened.
Requires Docker. If tests exist, runs them; otherwise checks the files parse.
"""
import subprocess
import tempfile
from pathlib import Path

from backend.schemas import EngineerOutput, RunResult

SANDBOX_DIR = Path(__file__).parent.parent / "sandbox"

# Docker Desktop and Colima only bind-mount paths under $HOME by default — the
# system tempdir (/var/folders/... on macOS) is invisible inside the VM, so
# volume mounts from tempfile's default location silently show up empty.
SANDBOX_TMP_ROOT = Path.home() / ".cache" / "hedgi-sandbox"

LANGUAGES = {
    "python": {
        "extensions": {".py"},
        "image": "hedgi-sandbox-python",
        "dockerfile": "Dockerfile.python",
        "test_glob": ("test_*.py", "*_test.py"),
        "test_cmd": ["pytest", "-q"],
        "check_cmd": ["sh", "-c", "for f in *.py; do python -m py_compile \"$f\" || exit 1; done"],
    },
    "node": {
        "extensions": {".js", ".ts"},
        "image": "hedgi-sandbox-node",
        "dockerfile": "Dockerfile.node",
        "test_glob": ("*.test.js",),
        "test_cmd": ["node", "--test"],
        "check_cmd": ["sh", "-c", "for f in *.js *.ts; do [ -e \"$f\" ] && (node --check \"$f\" || exit 1); done; true"],
    },
}


def _ensure_image(lang: dict) -> None:
    exists = subprocess.run(
        ["docker", "images", "-q", lang["image"]], capture_output=True, text=True
    ).stdout.strip()
    if exists:
        return
    subprocess.run(
        ["docker", "build", "-t", lang["image"], "-f", str(SANDBOX_DIR / lang["dockerfile"]), str(SANDBOX_DIR)],
        check=True, capture_output=True,
    )


def _run_in_sandbox(root: Path, lang: dict, has_tests: bool) -> subprocess.CompletedProcess:
    cmd = lang["test_cmd"] if has_tests else lang["check_cmd"]
    return subprocess.run(
        [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "256m",
            "--cpus", "1",
            "-v", f"{root}:/workspace",
            lang["image"],
            *cmd,
        ],
        capture_output=True, text=True, timeout=120,
    )


def run_runner(output: EngineerOutput) -> RunResult:
    SANDBOX_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SANDBOX_TMP_ROOT) as tmp:
        root = Path(tmp)
        for f in output.files:
            path = root / f.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f.content)

        used_extensions = {Path(f.path).suffix for f in output.files}
        logs, all_passed = [], True

        for name, lang in LANGUAGES.items():
            if not lang["extensions"] & used_extensions:
                continue
            has_tests = any(next(root.rglob(g), None) for g in lang["test_glob"])
            try:
                _ensure_image(lang)
                result = _run_in_sandbox(root, lang, has_tests)
            except FileNotFoundError:
                return RunResult(passed=False, log="Docker not found — install Docker to run the verification sandbox.")
            except subprocess.TimeoutExpired:
                all_passed = False
                logs.append(f"{name}: TIMED OUT after 120s")
                continue

            passed = result.returncode == 0
            all_passed &= passed
            mode = "tests" if has_tests else "syntax check"
            logs.append(f"{name} ({mode}): {'OK' if passed else 'FAILED'}\n{result.stdout}{result.stderr}")

        if not logs:
            return RunResult(passed=True, log="No checkable files (e.g. HTML-only output).")
        return RunResult(passed=all_passed, log="\n\n".join(logs))
