"""Copy the public CBOM core into an existing NegoLog CBOM integration.

Run from any directory: python tools/sync_negolog.py ../NegoLogV2 [--check].
Only the explicitly listed source files are managed. Builds and adapter code
are never overwritten. This tool needs no installed CBOM or NegoLog package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--check", action="store_true", help="compare without writing")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.repository.resolve() / "agents" / "CBOM"
    if not (args.repository / "nenv" / "Agent.py").is_file():
        parser.error("target must be a NegoLog checkout containing nenv/Agent.py")
    files: dict[str, Path] = {}
    for path in (source / "src" / "cbom").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".typed"}:
            files[f"_vendor/cbom/{path.relative_to(source / 'src/cbom').as_posix()}"] = path
    for path in (source / "java").rglob("*"):
        relative = path.relative_to(source / "java")
        if (path.is_file() and (path.suffix in {".java", ".py", ".md", ".json", ".jsonl"}
                               or path.name in {"LICENSE", "NOTICE", "PSF-LICENSE"})
                and not set(relative.parts) & {"build", "__pycache__"}):
            files[f"java/{relative.as_posix()}"] = path
    for name in ["LICENSE", "NOTICE", "CITATION.bib", "CITATION.cff"]:
        files[f"_vendor/{name}"] = source / name
    version = re.search(r'__version__ = "([^"]+)"', (source / "src/cbom/__init__.py").read_text())[1]
    manifest = {
        "source": "https://github.com/monurkeskin/CBOM",
        "version": version,
        "license": "GPL-3.0-only",
        "files": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for name, path in sorted(files.items())},
    }
    expected_manifest = (json.dumps(manifest, indent=2) + "\n").encode()
    expected = {name: path.read_bytes() for name, path in files.items()}
    expected["vendor-manifest.json"] = expected_manifest
    differences = []
    for name, content in expected.items():
        dest = target / name
        if not dest.is_file() or dest.read_bytes() != content:
            differences.append(name)
            if not args.check:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
    if args.check and differences:
        print("CBOM sources differ: " + ", ".join(differences))
        return 1
    verb = "Verified" if args.check else "Synchronized"
    print(f"{verb} {len(files)} public CBOM {version} files in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
