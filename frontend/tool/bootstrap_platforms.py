#!/usr/bin/env python3
"""Generate Flutter platform wrappers without overwriting application source."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd or FRONTEND, check=True)


def patch_android() -> None:
    manifest = FRONTEND / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    if 'android.permission.INTERNET' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.INTERNET"/>\n    <application', 1)
    if "usesCleartextTraffic" not in text:
        text = text.replace(
            "<application",
            '<application android:usesCleartextTraffic="true"',
            1,
        )
    manifest.write_text(text, encoding="utf-8")


def patch_ios() -> None:
    plist = FRONTEND / "ios" / "Runner" / "Info.plist"
    text = plist.read_text(encoding="utf-8")
    if "NSLocalNetworkUsageDescription" not in text:
        text = text.replace('</dict>\n</plist>', '<key>NSLocalNetworkUsageDescription</key>\n<string>Connect to your local research backend.</string>\n</dict>\n</plist>')
    if "NSAllowsLocalNetworking" not in text:
        marker = "</dict>\n</plist>"
        addition = (
            "\t<key>NSAppTransportSecurity</key>\n"
            "\t<dict>\n"
            "\t\t<key>NSAllowsLocalNetworking</key>\n"
            "\t\t<true/>\n"
            "\t</dict>\n"
        )
        text = text.replace(marker, addition + marker, 1)
        plist.write_text(text, encoding="utf-8")


def patch_web() -> None:
    index = FRONTEND / "web" / "index.html"
    text = index.read_text(encoding="utf-8")
    text = text.replace("sectors_duel_app", "Duel Intelligence")
    index.write_text(text, encoding="utf-8")


def main() -> None:
    flutter = shutil.which("flutter")
    if flutter is None:
        raise SystemExit(
            "Flutter was not found in PATH. Install Flutter, reopen the terminal, "
            "then rerun: python tool/bootstrap_platforms.py"
        )

    with tempfile.TemporaryDirectory(prefix="sectors-duel-flutter-") as temp:
        scaffold = Path(temp) / "scaffold"
        run(
            flutter,
            "create",
            "--platforms=android,ios,web",
            "--project-name=sectors_duel_app",
            "--org=app.sectorsduel",
            str(scaffold),
            cwd=Path(temp),
        )
        for name in ("android", "ios", "web"):
            shutil.copytree(scaffold / name, FRONTEND / name, dirs_exist_ok=True)
        shutil.copy2(scaffold / ".metadata", FRONTEND / ".metadata")

    patch_android()
    patch_ios()
    patch_web()
    run(flutter, "pub", "get")
    print("\nPlatform wrappers are ready. Next: flutter analyze && flutter test")


if __name__ == "__main__":
    main()
