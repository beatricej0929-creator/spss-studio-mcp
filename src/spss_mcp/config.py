"""
Configuration loading and SPSS installation detection for SPSS MCP (macOS).

This MCP targets IBM SPSS Statistics for macOS only.  The engine is located
inside the ``IBM SPSS Statistics.app`` bundle (``Contents/bin/spssengine``)
and driven through the bundled Python launcher ``Contents/bin/statisticspython3``.
"""

import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from project root first and let repo-local settings override inherited shell values.
load_dotenv(_PROJECT_ROOT / ".env", override=True)
load_dotenv()


def _mac_candidate_engine_paths(base: Path) -> list[Path]:
    """Given a user-supplied base path, return candidate spssengine paths.

    SPSS_INSTALL_PATH on macOS may point at any of:
      - the spssengine binary itself
      - .../Contents/bin
      - .../Contents
      - the .app bundle
      - the parent "IBM SPSS Statistics" folder
    """
    base = base.expanduser().resolve()
    if base.name == "spssengine":
        return [base]
    if base.name == "bin":
        return [base / "spssengine"]
    if base.name == "Contents":
        return [base / "bin" / "spssengine"]
    return [
        base / "Contents" / "bin" / "spssengine",
        base / "bin" / "spssengine",
        base / "IBM SPSS Statistics.app" / "Contents" / "bin" / "spssengine",
    ]


def _find_spss_via_filesystem_darwin() -> str | None:
    """Locate the SPSS engine binary inside the .app bundle on macOS."""
    engine_rel = Path("Contents") / "bin" / "spssengine"
    candidates: list[Path] = [
        Path("/Applications/IBM SPSS Statistics/IBM SPSS Statistics.app") / engine_rel,
    ]
    for root in (Path("/Applications"), Path.home() / "Applications"):
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if "spss" not in entry.name.lower():
                continue
            # IBM SPSS Statistics/IBM SPSS Statistics.app
            nested_app = entry / "IBM SPSS Statistics.app" / engine_rel
            candidates.append(nested_app)
            # any *.app bundle directly under the root
            if entry.suffix == ".app":
                candidates.append(entry / engine_rel)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def get_spss_executable() -> str | None:
    """
    Return path to the SPSS engine executable, or None if SPSS is not installed.

    macOS detection order:
    1. SPSS_NO_SPSS env var (forces file-only mode)
    2. SPSS_INSTALL_PATH env var (explicit path to the engine or .app bundle)
    3. Auto-discovery of the .app bundle under /Applications
    """
    if os.environ.get("SPSS_NO_SPSS", "0").strip() in ("1", "true", "yes"):
        return None

    install_path = os.environ.get("SPSS_INSTALL_PATH", "").strip()

    # Explicit install path from env
    if install_path:
        for candidate in _mac_candidate_engine_paths(Path(install_path)):
            if candidate.is_file():
                return str(candidate)
    # Auto-detect inside the .app bundle
    found = _find_spss_via_filesystem_darwin()
    if found:
        return found
    return None


def get_spss_python() -> str | None:
    """
    Return path to the SPSS Python launcher used to drive the XD API.

    macOS:   {Contents}/bin/statisticspython3 — a shell launcher that sources
             pythonenv.sh, activates the SPSS-bundled Python 3.13 venv and sets
             the DYLD_* paths before exec'ing the interpreter.
    """
    spss_exe = get_spss_executable()
    if not spss_exe:
        return None

    contents = Path(spss_exe).resolve().parent.parent  # bin -> Contents
    launcher = contents / "bin" / "statisticspython3"
    if launcher.is_file():
        return str(launcher)
    return None


def get_spss_home() -> str | None:
    """Return the SPSS installation root directory.

    macOS:   the Contents directory of IBM SPSS Statistics.app (where bin/ lives).
    """
    spss_exe = get_spss_executable()
    if not spss_exe:
        return None
    return str(Path(spss_exe).resolve().parent.parent)


def get_process_macro_path() -> str | None:
    """Return the trusted local Hayes PROCESS macro definition file.

    The macro path is deliberately configuration-only and is never accepted as
    an MCP tool argument.  This lets the dedicated PROCESS tool load a known
    local macro without weakening the general ``INSERT FILE`` safety rule.
    """
    configured = os.environ.get("SPSS_PROCESS_MACRO_PATH", "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
        return str(path) if path.is_file() and path.suffix.lower() == ".sps" else None

    roots: list[Path] = []
    spss_exe = get_spss_executable()
    if spss_exe:
        # .../<install folder>/SPSS Statistics.app/Contents/bin/spssengine
        roots.append(Path(spss_exe).resolve().parents[3])
    roots.extend((Path("/Applications"), Path.home() / "Applications"))

    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir() or root in seen:
            continue
        seen.add(root)
        patterns = (
            "PROCESS*for SPSS/process.sps",
            "IBM SPSS Statistics*/PROCESS*for SPSS/process.sps",
        )
        for pattern in patterns:
            for candidate in sorted(root.glob(pattern), reverse=True):
                if candidate.is_file():
                    return str(candidate.resolve())
    return None


def get_process_macro_version(path: str | None = None) -> str | None:
    """Read the PROCESS version comment from a macro definition file."""
    macro_path = Path(path or get_process_macro_path() or "")
    if not macro_path.is_file():
        return None
    try:
        header = macro_path.read_text(encoding="windows-1252", errors="replace")[:8192]
    except OSError:
        return None
    match = re.search(r"PROCESS\s+version\s+([0-9.]+)", header, re.IGNORECASE)
    return match.group(1) if match else None


def _get_positive_int_env(name: str, default: int) -> int:
    """Return a positive integer env var value or a default."""
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def get_timeout() -> int:
    """Return SPSS analysis timeout in seconds (default 120)."""
    return _get_positive_int_env("SPSS_TIMEOUT", 120)


def get_startup_timeout() -> int:
    """
    Return SPSS engine startup timeout in seconds.

    Startup is often slower than a normal analysis request because SPSS may need
    to initialize licensing, Python integration, and the persistent XD engine.
    Default to 300 seconds unless explicitly overridden.
    """
    return _get_positive_int_env("SPSS_STARTUP_TIMEOUT", 300)


def get_runtime_config() -> dict:
    """Return the effective runtime configuration used for SPSS execution."""
    return {
        "timeout": get_timeout(),
        "startup_timeout": get_startup_timeout(),
        "temp_dir": str(get_temp_dir()),
        "results_dir": str(get_results_dir()),
        "spss_path": get_spss_executable(),
        "process_macro_path": get_process_macro_path(),
    }


def get_temp_dir() -> Path:
    """Return the directory for temporary SPSS files, creating it if needed."""
    default = Path(tempfile.gettempdir()) / "spss-studio-mcp"
    temp_dir = Path(os.environ.get("SPSS_TEMP_DIR", str(default)))
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def get_results_dir() -> Path:
    """Return directory where persistent SPSS viewer output files (.spv) are saved."""
    default = get_temp_dir() / "results"
    out_dir = Path(os.environ.get("SPSS_RESULTS_DIR", str(default)))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def detect_capabilities() -> dict:
    """
    Detect what capabilities are available on this machine.

    Returns a dict with:
        pyreadstat: bool
        spss: bool
        spss_path: str | None
        pyreadstat_version: str | None
        pandas_version: str | None
    """
    caps: dict = {
        "pyreadstat": False,
        "pyreadstat_version": None,
        "pandas_version": None,
        "spss": False,
        "spss_path": None,
        "process_macro": False,
        "process_macro_path": None,
        "process_macro_version": None,
    }

    try:
        import pyreadstat

        caps["pyreadstat"] = True
        caps["pyreadstat_version"] = getattr(pyreadstat, "__version__", "unknown")
    except ImportError:
        pass

    try:
        import pandas as pd

        caps["pandas_version"] = pd.__version__
    except ImportError:
        pass

    spss_exe = get_spss_executable()
    if spss_exe:
        caps["spss"] = True
        caps["spss_path"] = spss_exe
        # SPSS Python (XD API) launcher — preferred execution method
        caps["spss_python"] = get_spss_python()
    else:
        caps["spss_python"] = None

    process_path = get_process_macro_path()
    if process_path:
        caps["process_macro"] = True
        caps["process_macro_path"] = process_path
        caps["process_macro_version"] = get_process_macro_version(process_path)

    return caps
