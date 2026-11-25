"""Explicit local setup. No downloads, automatic activation, or audio rerouting."""

import json
import os
import secrets
import shutil
import tempfile
from pathlib import Path

from .bridge_client import config_path, read_config

ROOT = Path(__file__).resolve().parent.parent


def default_user_library():
    if os.name == "nt":
        from win32com.shell import shell, shellcon
        documents = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)
        return Path(documents) / "Ableton/User Library"
    return Path.home() / "Music/Ableton/User Library"


def setup(user_library=None, *, config=None, source=None, check_cancel=lambda: None):
    library = Path(user_library) if user_library is not None else default_user_library()
    source = Path(source) if source is not None else ROOT / "remote_script/OctetBridge"
    config = Path(config) if config is not None else config_path()
    target = library / "Remote Scripts/OctetBridge"
    if target.is_symlink():
        raise ValueError(
            "Refusing to replace a symlinked OctetBridge. Review its target first."
        )
    check_cancel()
    config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if config.exists() or config.is_symlink():
        read_config(config)  # Keep the existing token, including on updates.
    else:
        value = {"protocol": 1, "port": 9878, "token": secrets.token_hex(32)}
        if os.name == "nt":
            from .windows_config import write_private_config
            write_private_config(config, value)
        else:
            with open(config, "x", opener=lambda p, f: os.open(p, f, 0o600)) as handle:
                json.dump(value, handle)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Stage first, keep the previous script as a backup, then replace it.
    staging = Path(tempfile.mkdtemp(prefix=".octet-stage-", dir=target.parent))
    backup = None
    try:
        shutil.copytree(
            source,
            staging / "OctetBridge",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        check_cancel()
        if target.exists():
            # Live scans every directory in Remote Scripts, even dotted backups.
            backups = config.parent / "script-backups"
            backups.mkdir(exist_ok=True, mode=0o700)
            backup = backups / ("OctetBridge.backup-" + secrets.token_hex(4))
            target.rename(backup)
        try:
            (staging / "OctetBridge").rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    finally:
        shutil.rmtree(staging)
    return {
        "installed": str(target),
        "backup": str(backup) if backup else None,
        "next": "Restart Live, then Settings > Link, Tempo & MIDI > Control Surface: OctetBridge. Leave Input/Output as None. Run /ableton status.",
    }
