"""Strict Shadowrocket parsing; unsupported active rules fail the build."""
from dataclasses import dataclass
from collections import Counter
from collections.abc import Callable
import ipaddress

@dataclass(frozen=True)
class Rule:
    kind: str
    value: str | None
    outbound: str

    def __iter__(self):
        return iter((self.kind, self.value, self.outbound))

POLICIES = {
    **dict.fromkeys(('proxy', 'proxied'), 'proxy'),
    **dict.fromkeys(('reject', 'reject-drop', 'reject-tinygif', 'reject-no-drop'), 'block'),
    **dict.fromkeys(('direct', 'bypass'), 'direct'),
}

def parse_line(line: str, forced_policy: str | None = None) -> Rule | None:
    line = line.strip()
    if not line or line.startswith(('#', ';')):
        return None
    parts = [x.strip() for x in line.split(',')]
    kind = parts[0].upper()
    final = kind in ('FINAL', 'MATCH')
    if len(parts) < (2 if final or forced_policy else 3):
        raise ValueError(f'Malformed rule: {line}')
    outbound = forced_policy or POLICIES.get(parts[1 if final else 2].lower())
    if outbound not in ('block', 'direct', 'proxy'):
        raise ValueError(f'Unknown policy: {line}')
    flags = parts[2 if final else (2 if forced_policy else 3):]
    # A forced ruleset policy overrides an optional per-line policy.
    if forced_policy and flags and flags[0].lower() in POLICIES:
        flags = flags[1:]
    if flags:
        raise ValueError(f'Unsupported rule options: {line}')
    if final:
        return Rule('final', None, outbound)
    value = parts[1]
    if not value:
        raise ValueError(f'Empty rule: {line}')
    if kind == 'RULE-SET':
        return Rule('ruleset', value, outbound)
    if kind in ('DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD'):
        value = value.lower().rstrip('.') if kind != 'DOMAIN-KEYWORD' else value.lower()
        if not value or (kind == 'DOMAIN-KEYWORD' and ':' in value):
            raise ValueError(f'Unrepresentable domain: {line}')
        prefix = {'DOMAIN': 'full:', 'DOMAIN-SUFFIX': 'domain:', 'DOMAIN-KEYWORD': ''}[kind]
        return Rule('domain', prefix + value, outbound)
    if kind in ('IP-CIDR', 'IP-CIDR6'):
        network = ipaddress.ip_network(value, strict=False)
        if kind == 'IP-CIDR6' and network.version != 6:
            raise ValueError(f'IP family mismatch: {line}')
        return Rule('ip', str(network), outbound)
    if kind == 'GEOIP':
        return Rule('ip', 'geoip:' + value.lower(), outbound)
    raise ValueError(f'Unsupported rule type: {line}')

def parse(text: str, download: Callable[[str], str], stats: Counter) -> list[Rule]:
    stats['source_lines'] = len(text.splitlines())
    def expand(lines, forced=None, stack=()):
        out = []
        for line in lines:
            line = line.strip()
            if forced and line == 'payload:':
                continue
            if forced and line.startswith('- '):
                line = line[2:].strip()
                if len(line) > 1 and line[0] in "\"'" and line[-1] == line[0]:
                    line = line[1:-1]
            rule = parse_line(line, forced)
            if rule is None:
                continue
            if rule.kind == 'ruleset':
                if rule.value in stack or len(stack) >= 5:
                    raise ValueError(f'RULE-SET cycle/depth: {rule.value}')
                stats['rulesets'] += 1
                children = expand(download(rule.value).splitlines(), rule.outbound, (*stack, rule.value))
                if not children:
                    raise ValueError(f'Empty RULE-SET: {rule.value}')
                out.extend(children)
            else:
                if forced and rule.kind == 'final':
                    raise ValueError('FINAL inside RULE-SET is not supported')
                stats['parsed'] += 1
                out.append(rule)
        return out
    lines = []; inside = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower() == '[rule]':
            inside = True
        elif inside and line.startswith('[') and line.endswith(']'):
            break
        elif inside:
            lines.append(raw)
    rules = expand(lines)
    if not rules or rules[-1].kind != 'final' or sum(r.kind == 'final' for r in rules) != 1:
        raise ValueError('Exactly one FINAL/MATCH must be the last rule')
    return rules
