"""Structure, external resource references, and reconstructed rule equality."""
from pathlib import Path
import ipaddress
import json
from .dat_builder import read_dat
from .qr import verify, MAX_BYTES

def rules(data, *, default_enabled: bool = False) -> None:
    if not isinstance(data, list) or not data:
        raise ValueError('Routing must be a nonempty array')
    for index, rule in enumerate(data):
        if not isinstance(rule, dict) or rule.get('outboundTag') not in ('proxy', 'direct', 'block'):
            raise ValueError('Invalid outbound/rule')
        if rule.get('enabled', default_enabled) is not True:
            raise ValueError('Generated rules must be enabled')
        fields = [k for k in ('domain', 'ip', 'port') if k in rule]
        if len(fields) != 1:
            raise ValueError('Each generated rule must have exactly one match field')
        field = fields[0]; values = rule[field]
        if field == 'port':
            if values != '0-65535' or index != len(data) - 1:
                raise ValueError('FINAL must be last')
        elif not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            raise ValueError('Invalid match list')
        elif field == 'ip':
            for value in values:
                if not value.startswith(('geoip:', 'ext:')):
                    ipaddress.ip_network(value, strict=True)
    if data[-1].get('port') != '0-65535':
        raise ValueError('Missing FINAL')

def output(directory: Path) -> dict:
    n = json.loads((directory / 'v2rayn/routing.json').read_text())
    ngpath = directory / 'v2rayng'
    ng = json.loads((ngpath / 'routing.json').read_text())
    rules(n); rules(ng, default_enabled=True)
    if len(n) != len(ng):
        raise ValueError('Group counts differ')
    resources = {p.name: read_dat(p) for p in ngpath.glob('*.dat')}
    used = {name: set() for name in resources}
    for left, right in zip(n, ng):
        if left['outboundTag'] != right['outboundTag']:
            raise ValueError('Outbound order differs')
        field = next(k for k in ('domain', 'ip', 'port') if k in left)
        if field not in right:
            raise ValueError('Group type differs')
        if field == 'port':
            continue
        expanded = []
        for value in right[field]:
            if value.startswith('ext:'):
                _, filename, tag = value.split(':')
                expected = 'g.dat' if field == 'domain' else 'i.dat'
                if filename != expected or not tag or tag not in resources.get(filename, {}):
                    raise ValueError(f'Missing or invalid ext resource: {value}')
                used[filename].add(tag)
                expanded.extend(resources[filename][tag])
            else:
                expanded.append(value)
        # OR values in a single group commute; group order must remain exact.
        if set(expanded) != set(left[field]):
            raise ValueError('External data changed group semantics')
    if any(used[name] != set(tags) for name, tags in resources.items()):
        raise ValueError('Unreferenced dat tags')
    text = (ngpath / 'routing.json').read_text()
    if len(text.encode()) <= MAX_BYTES:
        verify(ngpath / 'routing.png', text)
    elif (ngpath / 'routing.png').exists():
        raise ValueError('Stale QR for oversized JSON')
    return {'groups': len(n), 'resources': {k: len(v) for k, v in resources.items()}}
