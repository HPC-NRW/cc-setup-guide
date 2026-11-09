#!/usr/bin/env python3
"""Validation/render helpers for the installer and the separate manual sequence.

This intentionally handles only pinned Linux x86_64 releases, not updates or
arbitrary archives. Commands never print generated secrets.
"""
import base64
import configparser
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import sqlite3
import sys
import tarfile


class InvalidInput(Exception):
    """A safe diagnostic which contains no generated secret values."""


def require(ok, message):
    if not ok:
        raise InvalidInput(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key in input.')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def release(guide, version):
    data = read_json(Path(guide) / 'versions.json')['backend']['releases']
    require(version in data, 'Unsupported backend version; choose a release listed in versions.json.')
    item = data[version]
    require(item['tag'] == 'v' + version, 'Invalid pinned release tag.')
    require(re.fullmatch('[0-9a-f]{64}', item['sha256']), 'Missing pinned SHA256.')
    return item


def default_version(guide):
    version = read_json(Path(guide) / 'versions.json')['backend']['default']
    release(guide, version)
    print(version)


def rendered(guide, directory, cluster, user, group):
    templates = Path(guide) / 'scripts/templates'
    backend = read_json(templates / 'cc-backend.json.template')
    config = read_json(templates / 'cluster.json.template')
    ui = read_json(Path(guide) / 'docs/examples/minimal/cc-backend/ui-config.json')
    require(isinstance(backend, dict) and all(k in backend for k in ('main', 'auth', 'archive', 'metric-store')), 'Incomplete backend template.')
    require(all(isinstance(backend[k], dict) for k in ('main', 'auth', 'archive', 'metric-store')), 'Malformed backend configuration sections.')
    require(isinstance(backend['main'].get('addr'), str) and backend['main']['addr'], 'Missing backend listener address.')
    require(backend['metric-store'].get('checkpoints', {}).get('directory') == './var/checkpoints' and backend['metric-store'].get('cleanup', {}).get('directory') == './var/archive', 'Installer requires runtime paths beneath the new var directory.')
    require(backend['archive'] == {'kind': 'file', 'path': './var/job-archive'}, 'Installer requires the local new job archive.')
    require(backend.get('ui-file') == 'ui-config.json', 'Installer requires ui-file to reference ui-config.json.')
    require(isinstance(ui, dict) and all(isinstance(ui.get(k), dict) for k in ('job-list', 'job-view', 'node-list', 'metric-config', 'plot-configuration')), 'Incomplete UI configuration example.')
    require(config['name'] == '__CLUSTER_NAME__' and config['metricConfig'] and config['subClusters'], 'Incomplete cluster template.')
    config['name'] = ''
    require('__' not in json.dumps(backend) and '__' not in json.dumps(config) and '__' not in json.dumps(ui), 'Unresolved configuration placeholder.')
    config['name'] = cluster
    unit = (templates / 'clustercockpit.service.template').read_text()
    placeholders = {'__INSTALL_DIR__', '__CC_USER__', '__CC_GROUP__'}
    require(set(re.findall(r'__[A-Z_]+__', unit)) == placeholders, 'Unexpected service placeholders.')
    for key, value in [('__INSTALL_DIR__', directory), ('__CC_USER__', user), ('__CC_GROUP__', group)]:
        require(key in unit, 'Missing required service placeholder: ' + key)
        unit = unit.replace(key, value)
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(unit)
    expected = {'User': user, 'Group': group, 'WorkingDirectory': directory + '/cc-backend',
                'EnvironmentFile': directory + '/cc-backend/.env', 'UMask': '0077',
                'Type': 'notify', 'NotifyAccess': 'all', 'Restart': 'on-failure',
                'ExecStart': directory + '/cc-backend/cc-backend -server --config ' + directory + '/cc-backend/config.json'}
    require(all(parser.get('Service', key, fallback='') == value for key, value in expected.items()), 'Invalid required service directives.')
    require(parser.get('Install', 'WantedBy', fallback='') == 'multi-user.target', 'Missing service install target.')
    return backend, config, ui, unit


def preflight(guide, directory, cluster, user, group, version):
    require(sys.version_info >= (3, 9), 'Python 3.9 or newer is required.')
    require(os.geteuid() == 0, 'Run the installer/manual sequence as root.')
    require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}', cluster), 'Unsupported cluster name.')
    for value in (user, group):
        require(re.fullmatch('[a-z_][a-z0-9_-]{0,31}', value), 'Unsupported service user/group name.')
    try:
        account, account_group = pwd.getpwnam(user), grp.getgrnam(group)
    except KeyError:
        raise InvalidInput('Create the requested service user and group before installing.') from None
    require(account.pw_uid != 0 and account_group.gr_gid != 0, 'Use a dedicated non-root service account/group.')
    require(directory.startswith('/') and not directory.endswith('/'), 'Use an absolute directory without a trailing slash.')
    parts = directory.split('/')[1:]
    require(len(parts) >= 2 and all(re.fullmatch('[A-Za-z0-9_.-]+', p) and p not in ('.', '..') for p in parts), 'Unsupported installation path.')
    target = Path(directory)
    require(not os.path.lexists(target), 'Target already exists (including partial installations); no files changed.')
    for parent in target.parents:
        require(parent.is_dir() and not parent.is_symlink(), 'Every parent directory must exist and must not be a symlink.')
        mode = parent.stat()
        require(mode.st_uid == 0 and not mode.st_mode & 0o022, 'Parent directories must be root-owned and not group/other writable.')
    release(guide, version)
    rendered(guide, directory, cluster, user, group)


def release_url(guide, version, response):
    item = release(guide, version)
    data = read_json(response)
    require(isinstance(data, dict) and data.get('tag_name') == item['tag'], 'Release response does not match the pinned tag.')
    assets = data.get('assets')
    require(isinstance(assets, list), 'Release response has no asset array.')
    selected = [x for x in assets if isinstance(x, dict) and x.get('name') == item['asset']]
    require(len(selected) == 1, 'Expected exactly one Linux x86_64 release asset.')
    url = selected[0].get('browser_download_url', '')
    expected = 'https://github.com/ClusterCockpit/cc-backend/releases/download/' + item['tag'] + '/' + item['asset']
    require(url == expected, 'Unexpected release download URL.')
    print(url)


def extract(guide, version, archive, destination):
    expected = release(guide, version)['sha256']
    digest = hashlib.sha256()
    with open(archive, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    require(digest.hexdigest() == expected, 'Release SHA256 mismatch; extraction refused.')
    names = {'LICENSE', 'README.md', 'gen-keypair', 'archive-migration', 'archive-manager', 'cc-backend'}
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers()
        require(len(members) == len(names) and {m.name for m in members} == names and all(m.isfile() for m in members), 'Unexpected release layout: expected six flat regular files.')
        for member in members:
            dest = Path(destination) / member.name
            with dest.open('xb') as output, stream.extractfile(member) as source:
                shutil.copyfileobj(source, output)
            dest.chmod(0o700 if member.name not in ('LICENSE', 'README.md') else 0o600)


def render(guide, directory, cluster, user, group):
    backend, config, ui, unit = rendered(guide, directory, cluster, user, group)
    root = Path(directory)
    archive = root / 'cc-backend/var/job-archive'
    (archive / cluster).mkdir(parents=True, mode=0o700)
    for path, data in [(root / 'cc-backend/config.json', backend),
                       (root / 'cc-backend/ui-config.json', ui),
                       (archive / cluster / 'cluster.json', config)]:
        with path.open('x') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
    with (archive / 'version.txt').open('x') as stream:
        stream.write('3\n')
    with (root / 'clustercockpit.service').open('x') as stream:
        stream.write(unit)


def environment(keyfile, output):
    text = Path(keyfile).read_text()
    values = {}
    for key, size in [('PUBLIC', 32), ('PRIVATE', 64)]:
        matches = re.findall(r'ED25519 ' + key + r'_KEY="([^"\n]+)"', text)
        require(len(matches) == 1, 'Expected exactly one generated ' + key.lower() + ' key.')
        require(len(base64.b64decode(matches[0], validate=True)) == size, 'Invalid generated key length.')
        values[key] = matches[0]
    with Path(output).open('x') as stream:
        stream.write('SESSION_KEY="' + base64.b64encode(secrets.token_bytes(32)).decode() + '"\n')
        for key in ('PRIVATE', 'PUBLIC'):
            stream.write('JWT_' + key + '_KEY="' + values[key] + '"\n')


def token(source, destination):
    matches = re.findall(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?![A-Za-z0-9_-])', Path(source).read_text())
    require(len(matches) == 1, 'Expected exactly one JWT in backend CLI output.')
    parts = matches[0].split('.')
    header, claims = [json.loads(base64.urlsafe_b64decode(x + '=' * (-len(x) % 4))) for x in parts[:2]]
    require(isinstance(header, dict) and header.get('alg') == 'EdDSA' and isinstance(claims, dict), 'Unexpected JWT structure/algorithm.')
    with Path(destination).open('x') as stream:
        stream.write(matches[0] + '\n')


def finish(directory, user, group):
    root = Path(directory)
    backend = root / 'cc-backend'
    uid, gid = pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid
    with sqlite3.connect('file:' + str(backend / 'var/job.db') + '?mode=ro', uri=True) as db:
        require({row[0] for row in db.execute('select username from hpc_user')} >= {'admin', 'apiuser'}, 'Database users missing.')
    for path in (root, backend):
        os.chown(path, 0, gid)
        path.chmod(0o750)
    for path in backend.iterdir():
        if path.is_file():
            os.chown(path, 0, gid)
            path.chmod(0o750 if path.name in ('cc-backend', 'gen-keypair', 'archive-manager', 'archive-migration') else 0o640)
    for name in ('admin_password.txt', 'apiuser_password.txt', 'apikey.txt'):
        (backend / name).chmod(0o600)
    for path in [backend / 'var', *(backend / 'var').rglob('*')]:
        require(not path.is_symlink(), 'Unexpected symlink in new runtime state.')
        os.chown(path, uid, gid)
        path.chmod(0o700 if path.is_dir() else 0o600)
    (root / 'clustercockpit.service').chmod(0o644)


if __name__ == '__main__':
    os.umask(0o077)
    commands = {'default-version': default_version, 'preflight': preflight, 'release-url': release_url, 'extract': extract,
                'render': render, 'environment': environment, 'token': token, 'finish': finish}
    try:
        require(len(sys.argv) > 1 and sys.argv[1] in commands, 'Unknown install support command.')
        commands[sys.argv[1]](*sys.argv[2:])
    except InvalidInput as error:
        print('Installation validation failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, KeyError, TypeError, configparser.Error, tarfile.TarError, sqlite3.Error):
        # Parser/decoder exceptions can contain generated secret values.
        print('Installation validation failed: unreadable/malformed input in ' + (sys.argv[1] if len(sys.argv) > 1 else 'arguments') + '; no secret contents shown.', file=sys.stderr)
        sys.exit(1)
