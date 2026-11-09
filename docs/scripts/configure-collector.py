#!/usr/bin/env python3
"""Insert site identity and a protected raw JWT into existing collector examples."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--cluster', required=True)
    parser.add_argument('--url', required=True, help='HTTPS write URL including ?cluster=NAME')
    parser.add_argument('--token-file', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', args.cluster):
        parser.error('cluster must contain only letters, digits, underscore or hyphen')
    url = urlsplit(args.url)
    if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1')):
        parser.error('use HTTPS, or HTTP only on loopback for a local test')
    if not url.hostname or url.username or url.password or url.path != '/api/write/' or url.fragment:
        parser.error('expected an authenticated backend write URL without embedded credentials')
    if parse_qs(url.query) != {'cluster': [args.cluster]}:
        parser.error('URL cluster must match --cluster')
    try:
        token = args.token_file.read_text().strip()
        if not re.fullmatch(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token):
            parser.error('token file must contain exactly one raw JWT, without CLI output')
        paths = [args.directory / name for name in ('router.json', 'sinks.json')]
        if args.directory.is_symlink() or any(path.is_symlink() or not path.is_file() for path in paths):
            parser.error('expected regular configuration files in a non-symlink directory')
        router = json.loads(paths[0].read_text(), object_pairs_hook=unique_keys)
        sinks = json.loads(paths[1].read_text(), object_pairs_hook=unique_keys)
        cluster_tags = [entry for entry in router.get('add_tags', []) if entry.get('key') == 'cluster']
        http_sinks = [entry for entry in sinks.values() if entry.get('type') == 'http']
        if len(cluster_tags) != 1 or len(http_sinks) != 1:
            parser.error('expected exactly one cluster tag and one HTTP sink')
        cluster_tags[0]['value'] = args.cluster
        http_sinks[0].update(url=args.url, jwt=token)
        os.umask(0o077)
        for name, data in [('router.json', router), ('sinks.json', sinks)]:
            path = args.directory / name
            if path.is_symlink():
                parser.error('refusing a symlink configuration destination')
            # Restrict an existing file before truncation; never print the JWT.
            path.chmod(0o600)
            path.write_text(json.dumps(data, indent=2) + '\n')
    except (OSError, ValueError) as error:
        parser.error(type(error).__name__ + ': could not read or write collector configuration')
    print('Collector identity and HTTP sink configured; verify with the backend before starting the service.')


if __name__ == '__main__':
    main()
