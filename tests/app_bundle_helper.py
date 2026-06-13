from __future__ import annotations

import plistlib
from pathlib import Path


def make_minimal_alpha_app(path: Path) -> Path:
    (path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    (path / "Contents" / "Resources" / "Scripts").mkdir(parents=True, exist_ok=True)
    (path / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleName": "Alpha",
                "CFBundlePackageType": "APPL",
                "CFBundleExecutable": "applet",
            }
        )
    )
    applet = path / "Contents" / "MacOS" / "applet"
    applet.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    applet.chmod(0o755)
    (path / "Contents" / "PkgInfo").write_text("APPLaplt", encoding="utf-8")
    (path / "Contents" / "Resources" / "Scripts" / "main.scpt").write_bytes(b"compiled-script-placeholder")
    return path


def make_alpha_launcher_sources(root: Path) -> None:
    output_dir = root / "outputs" / "applications"
    output_dir.mkdir(parents=True, exist_ok=True)
    launcher = f"cd {root}\nALPHA_OPEN_BROWSER=1 scripts/start_alpha_dashboard.sh\n"
    command = f"#!/usr/bin/env bash\ncd {root}\nscripts/start_alpha_dashboard.sh\n"
    (output_dir / "Alpha.applescript").write_text(launcher, encoding="utf-8")
    command_path = output_dir / "Alpha.command"
    command_path.write_text(command, encoding="utf-8")
    command_path.chmod(0o755)
