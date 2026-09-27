#!/usr/bin/env python3
"""Load both products through a real Xray binary, without starting listeners."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xray', type=Path, required=True)
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'output')
parser.add_argument('--geoip', type=Path, help='geoip.dat for sources containing GEOIP rules')
args = parser.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    assets = Path(tmp)
    for file in (args.output / 'v2rayng').glob('*.dat'):
        (assets / file.name).write_bytes(file.read_bytes())
    if args.geoip:
        (assets / 'geoip.dat').write_bytes(args.geoip.read_bytes())
    for product in ('v2rayn', 'v2rayng'):
        data = json.loads((args.output / product / 'routing.json').read_text())
        rules = [{k: v for k, v in rule.items() if k in ('domain', 'ip', 'port', 'outboundTag')} | {'type': 'field'} for rule in data]
        config = {'log': {'loglevel': 'warning'}, 'inbounds': [], 'outbounds': [
            {'protocol': 'freedom', 'tag': 'proxy'}, {'protocol': 'freedom', 'tag': 'direct'},
            {'protocol': 'blackhole', 'tag': 'block'}],
            'routing': {'domainStrategy': 'AsIs', 'rules': rules}}
        path = assets / 'config.json'
        path.write_text(json.dumps(config))
        subprocess.run([str(args.xray.resolve()), 'run', '-test', '-config', str(path)],
                       env=os.environ | {'XRAY_LOCATION_ASSET': str(assets)}, check=True)
        print(f'{product}: Xray configuration test OK')
