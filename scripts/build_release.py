"""Build a source release without player saves or generated archives.

Usage: python scripts/build_release.py [--output /tmp/candidate.zip]
The external manifest records every packaged file and the archive checksum.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ROOTS = ['README.md', 'VERSION', 'AGENTS.md', '.gitignore', 'server.py', '启动游戏.bat',
         'game', 'static', 'tests', 'docs', 'scripts', 'artifacts']
EXTERNAL_REPORTS = {
    'artifacts/r4-qa/package-build.json',
    'artifacts/r4-qa/package-smoke.json',
    'artifacts/r4-qa/package-manifest.json',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must contain a numeric release version')
    output = args.output or ROOT / 'dist' / f'guixu-mortal-v{version}.zip'
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ROOTS:
        entry = ROOT / name
        for path in ([entry] if entry.is_file() else entry.rglob('*')):
            if not path.is_file() or path.is_symlink() or path.resolve() == output:
                continue
            relative = path.relative_to(ROOT)
            if '__pycache__' in relative.parts or relative.as_posix() in EXTERNAL_REPORTS:
                continue
            if path.suffix in {'.pyc', '.pyo', '.db', '.sqlite', '.sqlite3', '.zip'}:
                continue
            if any(part in {'.git', 'data', 'backups', 'dist', '.playwright'} for part in relative.parts):
                continue
            if path.name.endswith(('.db-journal', '.db-wal', '.db-shm')):
                continue
            files.append((relative.as_posix(), path))
    manifest = {}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files):
            contents = path.read_bytes()
            archive.writestr(name, contents)
            manifest[name] = hashlib.sha256(contents).hexdigest()
        if archive.testzip() is not None:
            raise ValueError('Archive CRC verification failed')
    report = dict(version=version, archive=output.name, files=len(manifest),
                  bytes=output.stat().st_size,
                  sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  file_sha256=manifest)
    report_path = ROOT / 'artifacts' / 'r4-qa' / 'package-build.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if output.parent == ROOT / 'dist':
        checksums = []
        for archive in sorted(output.parent.glob('*.zip')):
            checksums.append(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
        (output.parent / 'SHA256SUMS').write_text(''.join(checksums))
    print(json.dumps({k: v for k, v in report.items() if k != 'file_sha256'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
