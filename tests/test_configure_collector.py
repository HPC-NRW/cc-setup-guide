#!/usr/bin/env python3
"""Test site-configuration helper refusals and protected output, without a server."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='configure-', dir=args.work.resolve()))
    os.umask(0o077)
    # Deliberately synthetic, untrusted token: this test checks file handling, not authentication.
    def segment(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    token = segment({'alg': 'HS256'}) + '.' + segment({'sub': 'synthetic-config-test'}) + '.' + segment('invalid-signature')
    tokenfile = root / 'test.jwt'
    tokenfile.write_text(token + '\n')
    outcomes = []
    for case in ('success', 'bad_url', 'duplicate_json', 'sink_symlink'):
        target = root / case
        target.mkdir(mode=0o700)
        for name in ('router.json', 'sinks.json'):
            shutil.copyfile(args.source / 'docs/examples/minimal/cc-metric-collector' / name, target / name)
        if case == 'duplicate_json':
            (target / 'sinks.json').write_text('{"a":1,"a":2}')
        if case == 'sink_symlink':
            (target / 'sinks.json').rename(target / 'external.json')
            (target / 'sinks.json').symlink_to(target / 'external.json')
        before = {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in ('router.json', 'sinks.json')}
        url = 'http://example.org/api/write/?cluster=demo_cluster' if case == 'bad_url' else 'https://example.org/api/write/?cluster=demo_cluster'
        result = subprocess.run([sys.executable, str(args.source / 'docs/scripts/configure-collector.py'),
                                 '--directory', str(target), '--cluster', 'demo_cluster', '--url', url,
                                 '--token-file', str(tokenfile)], capture_output=True, text=True, timeout=10)
        assert token not in result.stdout + result.stderr, 'secret emitted'
        if case == 'success':
            assert result.returncode == 0, result.stderr
            router = json.loads((target / 'router.json').read_text())
            sinks = json.loads((target / 'sinks.json').read_text())
            assert router['add_tags'][0]['value'] == 'demo_cluster'
            assert next(item for item in sinks.values() if item['type'] == 'http')['jwt'] == token
            assert all((target / name).stat().st_mode & 0o777 == 0o600 for name in ('router.json', 'sinks.json'))
        else:
            assert result.returncode != 0, case
            after = {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in before}
            assert before == after, (case, 'configuration changed before refusal')
        outcomes.append({'case': case, 'exit': result.returncode, 'pass': True})
    (args.work / 'configure-results.json').write_text(json.dumps(outcomes, indent=2) + '\n')
    print('PASS: helper config/permissions, invalid URL, duplicate keys, symlink refusal before writes')


if __name__ == '__main__':
    main()
