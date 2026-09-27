#!/usr/bin/env python3
"""Shadowrocket -> v2rayN / v2rayNG reproducible distribution builder."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from src.downloader import Downloader
from src.parser import parse
from src.optimizer import deduplicate_rules, build_groups, collect_txt_lists
from src.dat_builder import build
from src.qr import generate
from src.validate import output as validate_output

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/sr_top500_banlist_ad.conf'

def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

def convert(text: str, download, directory: Path) -> dict:
    stats = Counter()
    parsed = parse(text, download, stats)
    unique = deduplicate_rules(parsed, stats)
    groups = build_groups(unique, stats)
    for name in ('v2rayn', 'v2rayng', 'debug'):
        (directory / name).mkdir(parents=True)
    n = []
    for kind, outbound, values in groups:
        rule = {'outboundTag': outbound, 'enabled': True}
        rule['port' if kind == 'final' else kind] = '0-65535' if kind == 'final' else values
        n.append(rule)
    dump(directory / 'v2rayn/routing.json', n)
    ng = build(groups, directory / 'v2rayng')
    dump(directory / 'v2rayng/routing.json', ng)
    qr_ok = generate(directory / 'v2rayng/routing.png', (directory / 'v2rayng/routing.json').read_text())
    for name, values in collect_txt_lists(unique).items():
        (directory / f'debug/{name}.txt').write_text('\n'.join(values) + ('\n' if values else ''))
    validation = validate_output(directory)
    repo = os.environ.get('GITHUB_REPOSITORY', '<owner>/<repo>')
    branch = os.environ.get('RULES_BRANCH', 'main')
    links = ['# 本次分发链接', '', '资源与路由请使用同一提交版本。', '']
    for file in ('v2rayn/routing.json', 'v2rayng/routing.json', 'v2rayng/g.dat', 'v2rayng/i.dat', 'v2rayng/routing.png'):
        if (directory / file).exists():
            url = f'https://raw.githubusercontent.com/{repo}/{branch}/output/{file}'
            links.append(f'- {file}: `{url}`')
    links.extend(['', 'QR: ' + ('OK，已反向解码验证。' if qr_ok else 'TOO LARGE，请复制 routing.json 正文，通过剪贴板导入。'), ''])
    (directory / 'README.md').write_text('\n'.join(links), encoding='utf-8')
    report = dict(stats)
    for key in ('duplicate', 'domain_compacted', 'ip_compacted'):
        report.setdefault(key, 0)
    report.update(validation)
    report['qr'] = 'OK' if qr_ok else 'TOO LARGE'
    report['ng_bytes_without_enabled'] = len(json.dumps([{k:v for k,v in r.items() if k != 'enabled'} for r in ng], ensure_ascii=False, separators=(',', ':')).encode())
    report['files'] = {str(p.relative_to(directory)): p.stat().st_size for p in sorted(directory.rglob('*')) if p.is_file()}
    report['sources'] = {url: hashlib.sha256(content.encode()).hexdigest() for url, content in sorted(getattr(download, 'cache', {}).items())}
    report['source_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    dump(directory / 'stats.json', report)
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-file', type=Path, help='Local main config; RULE-SET still downloads')
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    if args.validate_only:
        print(validate_output(args.output)); return 0
    downloader = Downloader()
    text = args.source_file.read_text(encoding='utf-8-sig') if args.source_file else downloader(SOURCE)
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.build-', dir=args.output.parent) as temp:
        staged = Path(temp)
        report = convert(text, downloader, staged)
        # Replace only owned filenames; preserve unrelated files in output directories.
        for file in sorted(staged.rglob('*')):
            if file.is_file():
                target = args.output / file.relative_to(staged)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(file, target)
        for optional in ('routing.png', 'g.dat', 'i.dat', 'sr_geosite.dat', 'sr_geoip.dat'):
            relative = 'v2rayng/' + optional
            if relative not in report['files']:
                (args.output / relative).unlink(missing_ok=True)
    print('=' * 60 + '\nShadowrocket -> v2rayN / v2rayNG\n' + '=' * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    repo = os.environ.get('GITHUB_REPOSITORY', '<owner>/<repo>')
    branch = os.environ.get('RULES_BRANCH', 'main')
    print('\nGitHub:')
    for name in ('v2rayn/routing.json', 'v2rayng/routing.json', 'v2rayng/g.dat', 'v2rayng/i.dat'):
        if (args.output / name).exists():
            print(f'  https://raw.githubusercontent.com/{repo}/{branch}/output/{name}')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'构建失败，未发布新产物：{exc}', file=sys.stderr)
        sys.exit(1)
