"""Use descriptors compiled from unmodified official Xray protobuf schema."""
from pathlib import Path
import ipaddress
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

pool = descriptor_pool.DescriptorPool()
descriptors = descriptor_pb2.FileDescriptorSet.FromString(
    (Path(__file__).resolve().parents[1] / 'vendor/xray/router.desc').read_bytes())
for descriptor in descriptors.file:
    pool.Add(descriptor)
GeoSiteList = message_factory.GetMessageClass(pool.FindMessageTypeByName('xray.app.router.GeoSiteList'))
GeoIPList = message_factory.GetMessageClass(pool.FindMessageTypeByName('xray.app.router.GeoIPList'))

def short_tag(index: int) -> str:
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if index < 36:
        return alphabet[index]
    return short_tag(index // 36) + alphabet[index % 36]

def build(groups: list, directory: Path) -> list[dict]:
    sites, ips = GeoSiteList(), GeoIPList()
    rules = []
    for index, (kind, outbound, values) in enumerate(groups, 1):
        rule = {'outboundTag': outbound} # RulesetItem has a no-arg constructor; enabled defaults true.
        tag = short_tag(index - 1) # Xray uppercases lookups; use uppercase base36.
        if kind == 'final':
            rule['port'] = '0-65535'
        elif kind == 'domain':
            entry = sites.entry.add(country_code=tag)
            for value in values:
                prefix, sep, rest = value.partition(':')
                typ = {'domain': 2, 'full': 3}.get(prefix) if sep else None
                entry.domain.add(type=typ if typ is not None else 0, value=rest if typ is not None else value)
            rule['domain'] = [f'ext:g.dat:{tag}']
        elif kind == 'ip':
            cidrs = [v for v in values if not v.startswith('geoip:')]
            rule['ip'] = [v for v in values if v.startswith('geoip:')]
            if cidrs:
                entry = ips.entry.add(country_code=tag)
                for value in cidrs:
                    net = ipaddress.ip_network(value)
                    entry.cidr.add(ip=net.network_address.packed, prefix=net.prefixlen)
                rule['ip'].append(f'ext:i.dat:{tag}')
        else:
            raise ValueError(f'Unknown group: {kind}')
        rules.append(rule)
    for filename, data in [('g.dat', sites), ('i.dat', ips)]:
        if data.entry:
            (directory / filename).write_bytes(data.SerializeToString(deterministic=True))
    return rules

def read_dat(path: Path):
    cls = {'g.dat': GeoSiteList, 'i.dat': GeoIPList}[path.name]
    if not path.read_bytes():
        raise ValueError(f'Empty dat: {path}')
    data = cls.FromString(path.read_bytes())
    entries = {}
    for entry in data.entry:
        if not entry.country_code or entry.country_code != entry.country_code.upper() or entry.country_code in entries:
            raise ValueError('Empty, duplicated or non-uppercase tag')
        values = []
        if path.name == 'g.dat':
            for domain in entry.domain:
                if domain.type not in (0, 2, 3) or not domain.value:
                    raise ValueError('Invalid domain entry')
                values.append({0: '', 2: 'domain:', 3: 'full:'}[domain.type] + domain.value)
        else:
            for cidr in entry.cidr:
                address = ipaddress.ip_address(cidr.ip)
                values.append(str(ipaddress.ip_network(f'{address}/{cidr.prefix}', strict=True)))
        if not values:
            raise ValueError('Empty tag data')
        entries[entry.country_code] = values
    if not entries:
        raise ValueError('Empty dat entry list')
    return entries
