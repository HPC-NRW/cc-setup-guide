#!/usr/bin/env python3
"""Portable component regressions for operations, sync and offline migration.

Requires Python>=3.9, requests2.32.5, git and GNU tar.
All --work state is NEW and artificial. Never pass an existing installation.
Backend144/gen-keypair, backend153, backend154 and archive-migration must be
the versions in versions.json. --sync-source is read-only; the unchanged source
is copied to verify its documented incompatibility with backend154.
"""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--sync-source', type=Path, required=True)
    parser.add_argument('--backend144', type=Path, required=True)
    parser.add_argument('--backend153', type=Path, required=True)
    parser.add_argument('--backend154', type=Path, required=True)
    parser.add_argument('--migration-tool', type=Path, required=True)
    args = parser.parse_args()
    source, work = args.source.resolve(), args.work.resolve()
    if work.exists():
        parser.error('--work must be a NEW directory')
    os.umask(0o077)
    work.mkdir(parents=True, mode=0o700)
    evidence = work / 'evidence'
    evidence.mkdir()
    results = []

    def record(name, condition, detail=None):
        results.append({'test': name, 'pass': bool(condition), 'detail': detail})
        (evidence / 'results.json').write_text(json.dumps(results, indent=2))
        if not condition:
            raise AssertionError(name + ': ' + str(detail))

    def run(name, command, cwd=work, stdin=None, expected=0, env=None):
        proc = subprocess.run([str(x) for x in command], cwd=cwd, input=stdin,
                              text=True, capture_output=True, timeout=90, env=env)
        output = re.sub(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', '[JWT REDACTED]', proc.stdout + proc.stderr)
        (evidence / (name + '.log')).write_text(output)
        record(name, proc.returncode == expected, {'exit': proc.returncode})
        return proc

    versions = json.loads((source / 'versions.json').read_text())
    sync_copy = work / 'sync'
    shutil.copytree(args.sync_source, sync_copy)
    ref = run('sync-commit', ['git', 'rev-parse', 'HEAD'], cwd=sync_copy).stdout.strip()
    record('pinned-sync-source', ref == versions['sync']['commit'])
    run('unchanged-sync-source', ['git', 'diff', '--exit-code', 'HEAD', '--'], cwd=sync_copy)
    record('sync-explicitly-unsupported', versions['sync']['supported'] is False
           and versions['sync']['incompatible_with_backend'] == '1.5.4')
    module = load(sync_copy / 'slurm-clusercockpit-sync.py', 'upstream_sync')

    # Real old instance, three synthetic completed archive jobs.
    old, new, tool = args.backend144.resolve(), args.backend153.resolve(), args.migration_tool.resolve()
    src = work / 'old144'
    src.mkdir()
    run('old-init', [old, '-init'], src)
    generated = subprocess.run([str(old.parent / 'gen-keypair')], capture_output=True, text=True, check=True).stdout
    public = re.search(r'PUBLIC_KEY="([^"]+)"', generated)[1]
    private = re.search(r'PRIVATE_KEY="([^"]+)"', generated)[1]
    (src / '.env').write_text('JWT_PUBLIC_KEY="%s"\nJWT_PRIVATE_KEY="%s"\nSESSION_KEY="%s"\n' %
                              (public, private, secrets.token_hex(32)))
    old_config = json.loads((src / 'config.json').read_text())
    old_config['clusters'][0]['name'] = 'auditcluster'
    old_config['clusters'][0]['metricDataRepository']['url'] = 'http://127.0.0.1:1'
    (src / 'config.json').write_text(json.dumps(old_config))
    archive = src / 'var/job-archive'
    (archive / 'auditcluster').mkdir(parents=True)
    (archive / 'version.txt').write_text('2\n')
    cluster = {'name': 'auditcluster', 'metricConfig': [{'name': 'cpu_load', 'unit': {'base': 'load'},
        'scope': 'node', 'aggregation': 'avg', 'timestep': 10, 'normal': 1, 'peak': 2}],
        'subClusters': [{'name': 'main', 'nodes': 'auditgpu[01-02]', 'processorType': 'synthetic',
                        'socketsPerNode': 2, 'coresPerSocket': 4, 'threadsPerCore': 1,
                        'topology': {'node': list(range(8)), 'socket': [[0,1,2,3], [4,5,6,7]],
                                     'memoryDomain': [[0,1,2,3], [4,5,6,7]], 'core': [[i] for i in range(8)]}}]}
    (archive / 'auditcluster/cluster.json').write_text(json.dumps(cluster))
    for identifier in [101, 102, 103]:
        directory = archive / ('auditcluster/0/%03d/1700000000' % identifier)
        directory.mkdir(parents=True)
        metadata = {'jobId': identifier, 'cluster': 'auditcluster', 'subCluster': 'main', 'partition': 'test',
                    'project': 'auditproject', 'user': 'audituser', 'jobState': 'completed', 'numNodes': 1,
                    'numHwthreads': 2, 'exclusive': identifier - 101, 'startTime': 1700000000,
                    'duration': 30, 'walltime': 60, 'resources': [{'hostname': 'auditgpu01', 'hwthreads': [0, 1]}],
                    'metaData': {'jobName': 'synthetic-%d' % identifier},
                    'statistics': {'cpu_load': {'avg': 2, 'min': 1, 'max': 3, 'unit': {'base': 'load'}}}}
        (directory / 'meta.json').write_text(json.dumps(metadata))
        (directory / 'data.json').write_text(json.dumps({'cpu_load': {'node': {'unit': {'base': 'load'}, 'timestep': 10,
            'series': [{'hostname': 'auditgpu01', 'data': [1,2,3], 'statistics': {'avg': 2, 'min': 1, 'max': 3}}]}}}))
    run('old-import', [old, '-init-db'], src)
    external = work / 'external-store'
    external.mkdir()
    (external / 'checkpoint.json').write_text('{"artificial":true}')
    (src / 'external-store-link').symlink_to('../external-store')
    backup_helper = source / 'docs/scripts/cc-offline-backup.py'
    migration_check = source / 'docs/scripts/cc-migration-check.py'
    inv = work / 'inventory.json'
    inv.write_text(json.dumps({'paths': [str(src)]}))
    run('backup-reject-unlisted-target', ['python3', backup_helper, 'backup', '--inventory', inv,
                                        '--destination', work / 'invalid-backup'], expected=1)
    record('failed-backup-no-output', not (work / 'invalid-backup').exists())
    inv.write_text(json.dumps({'paths': [str(src), str(external)]}))
    before_record = work / 'before.json'
    run('migration-before', ['python3', migration_check, 'snapshot', '--database', src / 'var/job.db',
                            '--archive', archive, '--record', before_record, '--db-version', '8', '--archive-version', '2'])
    backup = work / 'offline-backup'
    run('documented-backup', ['python3', backup_helper, 'backup', '--inventory', inv, '--destination', backup])
    original_checksums = (backup / 'SHA256SUMS').read_text()
    for case, contents in [('empty', ''), ('truncated', original_checksums.splitlines()[1] + '\n'),
                           ('duplicate', original_checksums + original_checksums), ('invalid', 'not-a-hash  offline.tar\n')]:
        bad = work / ('bad-backup-' + case)
        shutil.copytree(backup, bad)
        (bad / 'SHA256SUMS').write_text(contents)
        destination = work / ('bad-restore-' + case)
        run('reject-checksums-' + case, ['python3', backup_helper, 'restore', '--backup', bad,
                                       '--destination', destination], expected=1)
        record('reject-checksums-no-output-' + case, not destination.exists())
    for action in ['backup', 'restore']:
        destination = work / ('dangling-' + action)
        target_missing = work / ('must-not-create-' + action)
        destination.symlink_to(target_missing)
        params = ['--inventory', inv] if action == 'backup' else ['--backup', backup]
        run('reject-dangling-' + action, ['python3', backup_helper, action, *params,
                                        '--destination', destination], expected=1)
        record('reject-dangling-no-output-' + action, destination.is_symlink() and not target_missing.exists())
    staging = work / 'restore'
    run('documented-restore', ['python3', backup_helper, 'restore', '--backup', backup, '--destination', staging])
    restored = staging / src.relative_to('/')
    record('external-target-restored', (staging / external.relative_to('/') / 'checkpoint.json').read_text() == '{"artificial":true}')
    record('symlink-preserved', (restored / 'external-store-link').is_symlink())
    record('secret-preserved-private', (restored / '.env').read_bytes() == (src / '.env').read_bytes()
           and (restored / '.env').stat().st_mode & 0o077 == 0 and backup.stat().st_mode & 0o077 == 0)
    run('restore-verified', ['python3', migration_check, 'verify', '--database', restored / 'var/job.db',
                           '--archive', restored / 'var/job-archive', '--record', before_record,
                           '--db-version', '8', '--archive-version', '2'])
    # Migrated target derives from the documented restored set, not a hidden backup.
    target = work / 'target153'
    shutil.copytree(restored, target, symlinks=True)
    config153 = json.loads((source / 'scripts/templates/cc-backend.json.template').read_text())
    config153['main']['addr'] = '127.0.0.1:18093'
    config153['archive']['path'] = './var/job-archive'
    config153['metric-store']['memory-cap'] = 100
    config153['cron']['commit-job-worker'] = '1s'
    (target / 'config.json').write_text(json.dumps(config153))
    shutil.copyfile(source / 'docs/examples/minimal/cc-backend/ui-config.json', target / 'ui-config.json')
    run('migration-db', [new, '-migrate-db'], target)
    run('migration-archive', [tool, '-archive', target / 'var/job-archive'], target, stdin='y\n')
    run('migration-invariants', ['python3', migration_check, 'verify', '--database', target / 'var/job.db',
                                '--archive', target / 'var/job-archive', '--record', before_record,
                                '--db-version', '11', '--archive-version', '3'])
    run('migration-optimize', [new, '-optimize-db'], target)
    broken = work / 'broken-archive'
    shutil.copytree(restored / 'var/job-archive', broken)
    next(broken.rglob('meta.json')).write_text('{broken')
    run('broken-migration-fails', [tool, '-archive', broken], stdin='y\n', expected=1)
    record('broken-marker-remains-two', (broken / 'version.txt').read_text().strip() == '2')
    run('broken-invariants-fail', ['python3', migration_check, 'verify', '--database', target / 'var/job.db',
                                 '--archive', broken, '--record', before_record,
                                 '--db-version', '11', '--archive-version', '3'], expected=1)

    @contextlib.contextmanager
    def backend(label, directory, binary, nested):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        config = json.loads((directory / 'config.json').read_text())
        main_config = config['main'] if nested else config
        main_config['addr'] = '127.0.0.1:%d' % port
        (directory / 'config.json').write_text(json.dumps(config))
        run(label + '-api-user', [binary, '-add-user', 'auditapi:api:' + secrets.token_hex(16)], directory)
        issued = subprocess.run([str(binary), '-jwt', 'auditapi'], cwd=directory,
                                text=True, capture_output=True, check=True)
        match = re.search(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', issued.stdout + issued.stderr)
        if not match:
            raise RuntimeError('No API token')
        token = match[0]
        address = 'http://127.0.0.1:%d' % port
        def request(path, method='GET', data=None, authorize=True):
            headers = {'Content-Type': 'application/json'}
            if authorize:
                headers['Authorization'] = 'Bearer ' + token
            req = urllib.request.Request(address + path, headers=headers, method=method,
                                         data=None if data is None else json.dumps(data).encode())
            try:
                with urllib.request.urlopen(req, timeout=4) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read().decode()
        stream = (evidence / (label + '-server.log')).open('w')
        process = subprocess.Popen([str(binary), '-server'], cwd=directory, stdout=stream, stderr=subprocess.STDOUT)
        try:
            for _ in range(80):
                if process.poll() is not None:
                    raise RuntimeError('Backend exited: ' + label)
                try:
                    status, listing = request('/api/jobs/?cluster=auditcluster')
                    if status == 200:
                        break
                except urllib.error.URLError:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError('Backend readiness: ' + label)
            yield request, address, token
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            stream.close()

    def metric_series(data):
        if isinstance(data, dict):
            if data.get('data') == [1,2,3]:
                return True
            return any(metric_series(v) for v in data.values())
        return isinstance(data, list) and any(metric_series(v) for v in data)

    target154 = work / 'target154'
    shutil.copytree(target, target154, symlinks=True)
    current = args.backend154.resolve()
    version154 = run('backend154-version', [current, '-version'])
    record('backend154-release', '1.5.4' in version154.stdout + version154.stderr)

    for label, directory, binary, nested in [('before144', src, old, False), ('restored144', restored, old, False),
                                              ('after153', target, new, True)]:
        with backend(label, directory, binary, nested) as (request, address, token):
            status, data = request('/api/jobs/1?all-metrics=true')
            record(label + '-api-known-series', status == 200 and metric_series(data))
            (evidence / (label + '-job.json')).write_text(json.dumps(data, indent=2))
            record(label + '-unauthenticated', request('/api/jobs/', authorize=False)[0] == 401)
            if nested:
                # Actual decoder with the optional DE/EN LDAP fragments.
                # The RUB example uses local user accounts and JWTs.
                for language in ['de', 'en']:
                    document = (source / ('docs/operation.%s.md' % language)).read_text()
                    fragment = json.loads(re.search(r'```json\n(.*?)\n```', document, re.S)[1])
                    ldap_config = copy.deepcopy(config153)
                    ldap_config['auth']['ldap'] = fragment['auth']['ldap']
                    ldap_config['auth']['ldap']['url'] = 'ldap://127.0.0.1:1'
                    path = target / ('ldap-%s.json' % language)
                    path.write_text(json.dumps(ldap_config))
                    proc = run('ldap-decode-' + language, [new, '-config', path], target)
                    record('ldap-no-decode-error-' + language, 'unknown field' not in proc.stderr + proc.stdout
                           and '[ERROR]' not in proc.stderr + proc.stdout)
    # Negative compatibility check: original upstream methods and real HTTP.
    # Only Slurm command output is synthetic; no product patch or payload repair.
    with backend('unpatched-sync154', target154, current, True) as (request, address, token):
        cfg = {
            'clustername': 'auditcluster', 'node_regex': '^auditgpu01$',
            'nodes': {'sockets': 2, 'cores_per_socket': 4}, 'accelerators': {},
            'slurm': {'squeue': 'squeue', 'sacct': 'sacct', 'scontrol': 'scontrol',
                      'state_save_location': str(work / 'slurm-state')},
            'cc-backend': {'host': address, 'apikey': token},
        }
        sync = module.SlurmSync(cfg)
        sync._exec = lambda cmd: 'auditgpu01' if 'show hostname' in cmd else 'Synthetic job details'
        number = lambda value: {'set': True, 'number': value, 'infinite': False}
        job = {
            'job_id': 900101, 'user_name': 'audituser', 'partition': 'test',
            'name': 'unpatched-compatibility-test', 'shared': 'none',
            'node_count': number(1), 'cpus': number(1),
            'start_time': number(int(time.time()) - 120), 'time_limit': number(5),
            'account': 'auditproject', 'array_job_id': number(0), 'gres_detail': [],
            'job_resources': {'nodes': 'auditgpu01', 'allocated_nodes': [
                {'sockets': {'0': {'cores': {'0': 'allocated'}}}}]},
            'admin_comment': '', 'job_state': ['RUNNING'], 'end_time': number(0),
        }
        responses = []
        original_post = module.requests.post

        def observe_post(*positional, **keywords):
            response = original_post(*positional, **keywords)
            responses.append({'status': response.status_code, 'body': response.text,
                              'payload': copy.deepcopy(keywords.get('json'))})
            return response

        module.requests.post = observe_post
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                sync._ccStartJob(job)
        finally:
            module.requests.post = original_post
        record('unpatched-sync-real-http', len(responses) == 1)
        response = responses[0]
        record('unpatched-sync-legacy-field', 'exclusive' in response['payload']
               and 'shared' not in response['payload'])
        record('unpatched-sync154-rejected', response['status'] == 400
               and 'unknown field "exclusive"' in json.loads(response['body'])['error'],
               {'status': response['status'], 'body': response['body']})
        status, listing = request('/api/jobs/?cluster=auditcluster')
        record('unpatched-sync154-no-job', status == 200
               and all(item['jobId'] != job['job_id'] for item in listing['jobs']))
        record('backend154-known-series', metric_series(request('/api/jobs/1?all-metrics=true')[1]))

    proxy_source = (source / 'docs/examples/nginx/clustercockpit.conf').read_text()
    main_allowed = re.findall(r'limit_except ([A-Z ]+) \{', proxy_source)
    record('proxy-main-methods', len(main_allowed) == 1
           and set(main_allowed[0].split()) == {'GET', 'POST', 'HEAD'})
    for language in ['de', 'en']:
        document = (source / ('docs/https_setup.%s.md' % language)).read_text()
        record('proxy-shared-source-' + language,
               '--8<-- "examples/nginx/clustercockpit.conf"' in document)
        expansions = re.findall(r'limit_except ([A-Z ]+) \{', document)
        record('proxy-opt-in-methods-' + language, len(expansions) == 1
               and set(expansions[0].split()) == {'GET', 'POST', 'HEAD', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'})
    print(json.dumps({'passed': len(results), 'evidence': str(evidence)}, indent=2))


if __name__ == '__main__':
    main()
