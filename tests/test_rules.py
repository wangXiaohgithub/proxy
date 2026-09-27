import json
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from convert import convert
from src.parser import parse_line, parse
from src.optimizer import deduplicate_rules, build_groups, compact_domain_values, compact_ip_values
from src.dat_builder import read_dat
from src.qr import generate, verify
from src.validate import output, rules

class RulesTest(unittest.TestCase):
    def test_types_policies(self):
        cases = [
            ('DOMAIN,WWW.Example.com,Proxy', ('domain', 'full:www.example.com', 'proxy')),
            ('DOMAIN-SUFFIX,example.com,Reject', ('domain', 'domain:example.com', 'block')),
            ('DOMAIN-KEYWORD,abc,Direct', ('domain', 'abc', 'direct')),
            ('IP-CIDR,192.0.2.1/24,Proxy', ('ip', '192.0.2.0/24', 'proxy')),
            ('IP-CIDR6,2001:db8::/32,Direct', ('ip', '2001:db8::/32', 'direct')),
            ('IP-CIDR,2001:db8::/32,Proxy', ('ip', '2001:db8::/32', 'proxy')),
            ('GEOIP,CN,Direct', ('ip', 'geoip:cn', 'direct')),
            ('FINAL,Direct', ('final', None, 'direct')),
            ('MATCH,Proxy', ('final', None, 'proxy')),
        ]
        for text, expected in cases:
            with self.subTest(text=text): self.assertEqual(tuple(parse_line(text)), expected)

    def test_ruleset_expansion_policy_and_count(self):
        c = Counter()
        r = parse('[Rule]\nRULE-SET,https://one,Proxy\nFINAL,Direct',
                  lambda _: "payload:\n- 'DOMAIN,a,Reject'\nDOMAIN-SUFFIX,b", c)
        self.assertEqual([x.outbound for x in r], ['proxy', 'proxy', 'direct'])
        self.assertEqual(c['parsed'], 3)

    def test_ruleset_failure_cycle_empty(self):
        text = '[Rule]\nRULE-SET,https://one,Proxy\nFINAL,Direct'
        for downloader in [lambda _: '', lambda _: 'RULE-SET,https://one', lambda _: 'UNKNOWN,x']:
            with self.assertRaises(ValueError): parse(text, downloader, Counter())
        with self.assertRaises(OSError):
            parse(text, lambda _: (_ for _ in ()).throw(OSError('download failed')), Counter())

    def test_final_invalid(self):
        for text in ('[Rule]\nDOMAIN,a,Proxy', '[Rule]\nFINAL,Direct\nDOMAIN,a,Proxy', '[Rule]\nFINAL,Proxy\nFINAL,Direct'):
            with self.assertRaises(ValueError): parse(text, lambda _: '', Counter())

    def test_unknown_fail_closed(self):
        for line in ('DOMAIN,a,unknown', 'URL-REGEX,a,Proxy', 'DOMAIN,,Proxy', 'IP-CIDR,bad,Proxy', 'IP-CIDR,192.0.2.0/24,Proxy,no-resolve'):
            with self.assertRaises(ValueError): parse_line(line)

    def test_suffix_compaction(self):
        c = Counter()
        self.assertEqual(compact_domain_values(['domain:google.com', 'domain:www.google.com', 'full:google.com', 'domain:notgoogle.com', 'keyword'], c),
                         ['domain:google.com', 'domain:notgoogle.com', 'keyword'])
        self.assertEqual(c['domain_compacted'], 2)

    def test_cidr_compaction(self):
        c = Counter()
        self.assertEqual(compact_ip_values(['192.0.2.0/25', '192.0.2.128/25', '2001:db8::/32', 'geoip:cn'], c),
                         ['geoip:cn', '192.0.2.0/24', '2001:db8::/32'])
        self.assertEqual(c['ip_compacted'], 1)

    def test_order_no_cross_group_compaction(self):
        data = [('domain', 'domain:www.a.com', 'block'), ('domain', 'full:www.a.com', 'proxy'), ('domain', 'domain:a.com', 'block')]
        groups = build_groups(data, Counter())
        self.assertEqual([x[1] for x in groups], ['block', 'proxy', 'block'])
        self.assertEqual(groups[0][2], ['domain:www.a.com'])

    def test_exact_dedupe(self):
        data = [('domain', 'full:a', 'block'), ('domain', 'full:a', 'proxy'), ('domain', 'full:a', 'block')]
        c = Counter(); self.assertEqual(deduplicate_rules(data, c), data[:2]); self.assertEqual(c['duplicate'], 1)

    def test_real_products_and_tag_tamper(self):
        text = '[Rule]\nDOMAIN,a,Reject\nIP-CIDR6,2001:db8::/32,Proxy\nGEOIP,CN,Direct\nDOMAIN-SUFFIX,b,Reject\nFINAL,Direct'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); convert(text, lambda _: '', path)
            self.assertEqual(output(path)['groups'], 5)
            self.assertEqual(read_dat(path / 'v2rayng/i.dat')['1'], ['2001:db8::/32'])
            file = path / 'v2rayng/routing.json'
            data = json.loads(file.read_text());data[0]['domain'] = ['ext:g.dat:MISSING'];file.write_text(json.dumps(data))
            with self.assertRaises(ValueError): output(path)

    def test_no_empty_geoip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp);convert('[Rule]\nDOMAIN,a,Proxy\nFINAL,Direct', lambda _: '', path)
            self.assertFalse((path / 'v2rayng/i.dat').exists())

    def test_qr_roundtrip_unicode_overflow_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'routing.png'
            self.assertTrue(generate(path, '[{"备注":"测试"}]'))
            verify(path, '[{"备注":"测试"}]')
            with self.assertRaises(ValueError): verify(path, 'wrong')
            self.assertFalse(generate(path, 'a' * 2954));self.assertFalse(path.exists())
            with patch('src.qr.verify', side_effect=ValueError('bad decode')):
                with self.assertRaises(ValueError): generate(path, '[]')

    def test_structure_invalid(self):
        for data in ({}, [], [{'outboundTag': 'other', 'enabled': True, 'port': '0-65535'}],
                     [{'outboundTag': 'proxy', 'enabled': True}]):
            with self.assertRaises(ValueError): rules(data)

    def test_failed_build_preserves_existing_output(self):
        from convert import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'output'
            path.mkdir()
            sentinel = path / 'routing.json'
            sentinel.write_text('old production')
            def download(url):
                if url.endswith('.conf'):
                    return '[Rule]\nRULE-SET,https://missing,Proxy\nFINAL,Direct'
                raise OSError('missing ruleset')
            with patch('sys.argv', ['convert.py', '--output', str(path)]), patch('convert.Downloader', return_value=download):
                with self.assertRaises(OSError): main()
            self.assertEqual(sentinel.read_text(), 'old production')
            self.assertEqual(list(path.iterdir()), [sentinel])

    def test_match_order_equivalence(self):
        # Exhaust overlapping exact/suffix matches before and after optimization.
        data = [('domain', 'full:www.a.com', 'proxy'), ('domain', 'domain:a.com', 'block'),
                ('domain', 'domain:sub.a.com', 'block'), ('domain', 'full:www.a.com', 'proxy'),
                ('domain', 'domain:com', 'direct')]
        def matches(value, host):
            if value.startswith('full:'): return host == value[5:]
            if value.startswith('domain:'): return host == value[7:] or host.endswith('.' + value[7:])
            return value in host
        def route(items, host):
            return next((out for _, val, out in items if matches(val, host)), None)
        c = Counter()
        groups = build_groups(deduplicate_rules(data, c), c)
        optimized = [(kind, value, out) for kind, out, values in groups for value in values]
        for host in ('a.com', 'www.a.com', 'sub.a.com', 'www.sub.a.com', 'b.com', 'x.org'):
            self.assertEqual(route(data, host), route(optimized, host))

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            text = '[Rule]\nDOMAIN,a,Reject\nIP-CIDR,192.0.2.0/24,Proxy\nFINAL,Direct'
            convert(text, lambda _: '', a);convert(text, lambda _: '', b)
            self.assertEqual({p.relative_to(a): p.read_bytes() for p in a.rglob('*') if p.is_file()},
                             {p.relative_to(b): p.read_bytes() for p in b.rglob('*') if p.is_file()})

if __name__ == '__main__': unittest.main()
