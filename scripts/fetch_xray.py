#!/usr/bin/env python3
"""Download pinned official Xray release and verify SHA256 before extraction."""
from pathlib import Path
import argparse
import hashlib
import platform
import subprocess
import zipfile

VERSION = 'v26.3.27'
ASSETS = {
    ('Linux', 'x86_64'): ('Xray-linux-64.zip', '23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae'),
    ('Darwin', 'arm64'): ('Xray-macos-arm64-v8a.zip', '2e93a67e8aa1936ecefb307e120830fcbd4c643ab9b1c46a2d0838d5f8409eaf'),
    ('Darwin', 'x86_64'): ('Xray-macos-64.zip', 'f5b0471d3459eff1b82e48af0aeac186abcc3298210070afbbbd8437a4e8b203'),
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--destination', type=Path, default=Path('.work/xray'))
args = parser.parse_args()
name, digest = ASSETS[(platform.system(), platform.machine())]
args.destination.mkdir(parents=True, exist_ok=True)
archive = args.destination / name
subprocess.run(['curl', '-fLsS', '--retry', '3', '--retry-delay', '2', '--connect-timeout', '15', '--max-time', '180',
                f'https://github.com/XTLS/Xray-core/releases/download/{VERSION}/{name}', '-o', str(archive)], check=True)
if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
    raise ValueError('Xray SHA256 mismatch')
with zipfile.ZipFile(archive) as z:
    for filename in ('xray', 'geoip.dat'):
        if filename in z.namelist():
            (args.destination / filename).write_bytes(z.read(filename))
(args.destination / 'xray').chmod(0o755)
print(f'Verified {VERSION}: {args.destination / "xray"}')
