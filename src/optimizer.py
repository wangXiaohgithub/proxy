"""Original order-preserving dedupe and within-group compaction."""
import ipaddress
COMPACT_DOMAIN_SUFFIX = True
COMPACT_IP_CIDR = True

def deduplicate_rules(rules, stats):
    """
    只删除完全一致的：

    kind + value + outbound

    不会删除策略不同的规则。
    """
    result = []
    seen = set()
    for rule in rules:
        kind, value, outbound = rule
        if kind == 'final':
            result.append(rule)
            continue
        key = (kind, value, outbound)
        if key in seen:
            stats['duplicate'] += 1
            continue
        seen.add(key)
        result.append(rule)
    return result

def domain_suffix_is_covered(domain: str, suffix_set: set) -> bool:
    """
    判断：

    www.google.com

    是否已经被：

    google.com

    覆盖。
    """
    parts = domain.split('.')
    for i in range(1, len(parts)):
        parent = '.'.join(parts[i:])
        if parent in suffix_set:
            return True
    return False

def compact_domain_values(values, stats):
    """
    仅在同一个连续规则组内部做压缩。

    安全示例：

    domain:google.com
    domain:www.google.com

    =>

    domain:google.com

    同一个组策略完全一样，因此不会改变 outbound。
    """
    if not values:
        return values
    values = list(dict.fromkeys(values))
    if not COMPACT_DOMAIN_SUFFIX:
        return values
    suffixes = set()
    for value in values:
        if value.startswith('domain:'):
            domain = value[7:]
            if domain:
                suffixes.add(domain)
    result = []
    for value in values:
        if value.startswith('domain:'):
            domain = value[7:]
            if domain_suffix_is_covered(domain, suffixes):
                stats['domain_compacted'] += 1
                continue
            result.append(value)
            continue
        if value.startswith('full:'):
            domain = value[5:]
            if domain in suffixes or domain_suffix_is_covered(domain, suffixes):
                stats['domain_compacted'] += 1
                continue
            result.append(value)
            continue
        result.append(value)
    return result

def compact_ip_values(values, stats):
    """
    对同一规则组内 CIDR 做安全 collapse。
    """
    values = list(dict.fromkeys(values))
    if not COMPACT_IP_CIDR:
        return values
    ipv4 = []
    ipv6 = []
    special = []
    for value in values:
        if value.lower().startswith('geoip:'):
            special.append(value)
            continue
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            special.append(value)
            continue
        if network.version == 4:
            ipv4.append(network)
        else:
            ipv6.append(network)
    old_network_count = len(ipv4) + len(ipv6)
    ipv4_collapsed = list(ipaddress.collapse_addresses(ipv4))
    ipv6_collapsed = list(ipaddress.collapse_addresses(ipv6))
    new_network_count = len(ipv4_collapsed) + len(ipv6_collapsed)
    if new_network_count < old_network_count:
        stats['ip_compacted'] += old_network_count - new_network_count
    result = []
    result.extend(list(dict.fromkeys(special)))
    result.extend((str(x) for x in ipv4_collapsed))
    result.extend((str(x) for x in ipv6_collapsed))
    return result

def build_groups(rules, stats):
    """
    只把连续的：

    同 kind
    同 outbound

    规则合并。

    这样不会跨策略重排规则。
    """
    groups = []
    current_kind = None
    current_outbound = None
    current_values = []

    def flush():
        nonlocal current_kind
        nonlocal current_outbound
        nonlocal current_values
        if not current_values:
            return
        values = current_values
        if current_kind == 'domain':
            values = compact_domain_values(values, stats)
        elif current_kind == 'ip':
            values = compact_ip_values(values, stats)
        groups.append((current_kind, current_outbound, values))
        current_kind = None
        current_outbound = None
        current_values = []
    for kind, value, outbound in rules:
        if kind == 'final':
            flush()
            groups.append(('final', outbound, []))
            continue
        if current_kind == kind and current_outbound == outbound:
            current_values.append(value)
        else:
            flush()
            current_kind = kind
            current_outbound = outbound
            current_values = [value]
    flush()
    return groups

def collect_txt_lists(rules):
    """
    TXT 保留 Xray domain 表达方式。

    例如：

    domain:google.com
    full:www.google.com
    google
    """
    proxy_domains = []
    block_domains = []
    direct_domains = []
    proxy_ips = []
    for kind, value, outbound in rules:
        if kind == 'domain':
            if outbound == 'proxy':
                proxy_domains.append(value)
            elif outbound == 'block':
                block_domains.append(value)
            elif outbound == 'direct':
                direct_domains.append(value)
        elif kind == 'ip':
            if outbound == 'proxy':
                proxy_ips.append(value)
    return {'proxy_domains': list(dict.fromkeys(proxy_domains)), 'block_domains': list(dict.fromkeys(block_domains)), 'direct_domains': list(dict.fromkeys(direct_domains)), 'proxy_ips': list(dict.fromkeys(proxy_ips))}
