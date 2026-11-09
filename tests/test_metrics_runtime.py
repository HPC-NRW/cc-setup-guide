#!/usr/bin/env python3
"""Real v0.8.4 collector lifecycle using only a fresh installer test export.

Requires Linux bubblewrap, the built pinned collector, and tests/installer.py's
private export. Test adaptations: loopback, artificial hostname, 2s sampling,
1s archive worker, 1GiB store. Never accepts an existing real installation.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from test_metrics import tutorial_router


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--collector', type=Path, required=True)
    args = parser.parse_args()
    source, work = args.source.resolve(), args.work.resolve()
    assert (args.installation / '.guide-test-fixture').is_file(), 'only installer test exports are accepted'
    assert not work.exists(), 'choose a fresh private work directory'
    os.umask(0o077)
    work.mkdir(parents=True, mode=0o700)
    instance = work / 'instance'
    shutil.copytree(args.installation, instance)
    evidence = work / 'evidence'
    evidence.mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    token = (instance / 'apikey.txt').read_text().strip()
    config = json.loads((instance / 'config.json').read_text())
    config['main']['addr'] = f'127.0.0.1:{port}'
    config['cron']['commit-job-worker'] = '1s'
    config['metric-store']['memory-cap'] = 1
    write(instance / 'config.json', config)
    cluster_path = instance / 'var/job-archive/demo_cluster/cluster.json'
    cluster = json.loads(cluster_path.read_text())
    cluster['metricConfig'][0]['timestep'] = 2
    known = copy.deepcopy(cluster['metricConfig'][0])
    known['name'] = 'test_known'
    cluster['metricConfig'].append(known)
    write(cluster_path, cluster)
    results, processes, handles = [], [], []

    def record(name, detail):
        results.append({'test': name, 'result': 'PASS', 'detail': detail})
        write(evidence / 'results.json', results)
        print(name + ': PASS', flush=True)

    def request(path, body=None, auth=token):
        payload = None if body is None else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
        req = urllib.request.Request(base + path, data=payload, headers={
            'X-Auth-Token': auth, 'Content-Type': 'text/plain' if isinstance(body, str) else 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                code, raw = response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            code, raw = error.code, error.read().decode()
        try:
            return code, json.loads(raw)
        except json.JSONDecodeError:
            return code, raw

    def launch(command, cwd, name):
        handle = (evidence / (name + '.log')).open('w')
        handles.append(handle)
        process = subprocess.Popen(command, cwd=cwd, stdout=handle, stderr=handle,
                                   env={**os.environ, 'GOMAXPROCS': '4'}, start_new_session=True)
        processes.append(process)
        return process

    def start_backend(cwd, name):
        process = launch([str(cwd / 'cc-backend'), '-server', '-loglevel', 'info'], cwd, name)
        for _ in range(100):
            assert process.poll() is None, 'backend exited: inspect private log'
            try:
                if request('/api/clusters/')[0] == 200:
                    return process
            except OSError:
                pass
            time.sleep(.1)
        raise AssertionError('backend readiness timeout')

    def stop(process):
        if process.poll() is not None:
            return
        if process.args[0] == 'bwrap':
            def descendants(pid):
                try:
                    kids = [int(x) for x in Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
                except FileNotFoundError:
                    return []
                return kids + [child for kid in kids for child in descendants(kid)]
            owned = [pid for pid in descendants(process.pid)
                     if Path(f'/proc/{pid}/comm').read_text().strip() in ('collector', 'cc-metric-colle')]
            assert len(owned) == 1, owned
            os.kill(owned[0], signal.SIGTERM)
        else:
            process.send_signal(signal.SIGTERM)
        process.wait(timeout=20)

    def prepare_collector(mode):
        directory = work / mode
        shutil.copytree(source / 'docs/examples/minimal/cc-metric-collector', directory)
        if mode == 'tutorial':
            write(directory / 'router.json', tutorial_router(source))
        settings = json.loads((directory / 'config.json').read_text())
        settings['main'] = {'interval': '2s', 'duration': '1s'}
        write(directory / 'config.json', settings)
        subprocess.run([sys.executable, str(source / 'docs/scripts/configure-collector.py'),
                        '--directory', str(directory), '--cluster', 'demo_cluster',
                        '--url', base + '/api/write/?cluster=demo_cluster',
                        '--token-file', str(instance / 'apikey.txt')], check=True, capture_output=True)
        # Documented stdout sink alongside HTTP gives an independent value/timestamp oracle.
        sinks = json.loads((directory / 'sinks.json').read_text())
        sinks.update(json.loads((directory / 'sinks_stdout.json').read_text()))
        write(directory / 'sinks.json', sinks)
        return directory

    def start_collector(directory):
        command = ['bwrap', '--unshare-user', '--unshare-pid', '--unshare-uts', '--unshare-ipc',
                   '--hostname', 'node001', '--die-with-parent', '--ro-bind', '/usr', '/usr',
                   '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/lib64', '/lib64',
                   '--symlink', 'usr/lib', '/lib', '--proc', '/proc', '--ro-bind', '/sys', '/sys',
                   '--dev', '/dev', '--tmpfs', '/tmp', '--bind', str(directory), '/work',
                   '--ro-bind', str(args.collector.resolve()), '/collector', '--chdir', '/work',
                   '/collector', '-config', 'config.json']
        return launch(command, directory, directory.name)

    def samples(mode):
        return [(float(value), int(stamp) // 10**9) for value, stamp in
                re.findall(r'cpu_load,[^\n]* value=([\d.]+) (\d+)', (evidence / (mode + '.log')).read_text())]

    def get_job(ident):
        code, job = request(f'/api/jobs/{ident}?all-metrics=true')
        assert code == 200, (code, job)
        return job

    def compare_series(entry, expected, tolerance=0):
        assert entry['timestep'] == 2 and len(entry['series']) == 1
        assert entry['series'][0]['hostname'] == 'node001'
        data = entry['series'][0]['data'][:]
        # Requests may extend beyond the sampling window. Only edge nulls are
        # permitted; an extra inner gap or duplicate must fail the oracle.
        while data and data[0] is None:
            data.pop(0)
        while data and data[-1] is None:
            data.pop()
        assert len(data) == len(expected), (data, expected)
        assert all(actual is not None and abs(actual-value) <= tolerance
                   for actual, (value, _) in zip(data, expected)), (data, expected)

    try:
        server = start_backend(instance, 'backend-before')
        for mode, number, count in [('tutorial', 910001, 18), ('quickstart', 910002, 3)]:
            directory = prepare_collector(mode)
            t0 = int(time.time())
            body = {'jobId': number, 'cluster': 'demo_cluster', 'user': 'synthetic-guide',
                    'project': 'test', 'startTime': t0, 'numNodes': 1, 'numHwthreads': 1,
                    'resources': [{'hostname': 'node001', 'hwthreads': [0]}]}
            code, reply = request('/api/jobs/start_job/', body)
            assert code == 201, (code, reply)
            ident = reply['id'] if isinstance(reply, dict) and 'id' in reply else (1 if mode == 'tutorial' else 2)
            collector = start_collector(directory)
            sent = []
            for index in range(count):
                ts = t0 + index * 2
                delay = ts - time.time()
                if delay > 0:
                    time.sleep(delay)
                assert collector.poll() is None, 'collector exited: inspect private log'
                value = 7 + index
                assert request('/api/write/', f'test_known,cluster=demo_cluster,hostname=node001,type=node value={value} {ts}')[0] == 200
                sent.append((value, ts))
            time.sleep(2.2)
            stop(collector)
            time.sleep(2.1)
            before = get_job(ident)
            write(evidence / (mode + '-before.json'), before)
            assert before['Meta']['jobId'] == number and before['Meta']['startTime'] == t0
            assert before['Meta']['resources'] == body['resources']
            actual = samples(mode)
            assert actual and all(b[1] - a[1] == 2 for a, b in zip(actual, actual[1:])), actual
            for metric, expected in [('test_known', sent), ('cpu_load', actual)]:
                entry = before['Data'][metric]['node']
                compare_series(entry, expected)
                # metricstore.Read clips to the first available sample (v1.5.3).
                # The job API has no per-series start timestamp: assert all values
                # here and the exact absolute timestamps in the checkpoint below.
                assert all(t0 <= stamp < int(time.time()) for _, stamp in expected)
            record(mode + ' first metric and complete ordered running series', {'start': t0, 'collector_samples': actual, 'known_samples': sent})
            if mode == 'tutorial':
                stop(server)
                persisted = {}
                for path in (instance / 'var/checkpoints').rglob('*.json'):
                    checkpoint = json.loads(path.read_text())
                    for metric, values in checkpoint.get('metrics', {}).items():
                        if metric in ('cpu_load', 'test_known'):
                            persisted.setdefault(metric, {}).update({values['start'] + i * values['frequency']: v
                                                                   for i, v in enumerate(values['data']) if v is not None})
                for metric, expected in [('cpu_load', actual), ('test_known', sent)]:
                    got = persisted[metric]
                    assert len(got) == len(expected), (metric, got, expected)
                    for value, stamp in expected:
                        assert stamp in got and abs(got[stamp] - value) <= .051, (metric, stamp, got)
                record('exact checkpoint timestamp/count and documented decimal rounding', persisted)
                server = start_backend(instance, 'backend-restarted')
                after = get_job(ident)
                for metric in ('cpu_load', 'test_known'):
                    a = before['Data'][metric]['node']['series'][0]['data']
                    b = after['Data'][metric]['node']['series'][0]['data']
                    assert len(b) >= len(a)
                    assert all((x is None and y is None) or (x is not None and y is not None and abs(x-y) <= .051)
                               for x, y in zip(a, b)), (metric, a, b)
                record('restart preserves every prior sample in order', {'tolerance': .051, 'checkpoint_format': 'json'})
            end = int(time.time())
            assert request('/api/jobs/stop_job/', {'jobId': number, 'cluster': 'demo_cluster',
                           'startTime': t0, 'stopTime': end, 'jobState': 'completed'})[0] == 200
            if mode == 'tutorial':
                for _ in range(150):
                    archived = get_job(ident)
                    if archived['Meta']['monitoringStatus'] == 3:
                        break
                    time.sleep(.1)
                assert archived['Meta']['monitoringStatus'] == 3, archived['Meta']
                assert archived['Meta']['jobState'] == 'completed'
                assert archived['Data']['test_known']['node']['series'][0]['statistics']['avg'] == 15.5
                compare_series(archived['Data']['cpu_load']['node'], actual, .051)
                compare_series(archived['Data']['test_known']['node'], sent)
                write(evidence / 'archived.json', archived)
                record('job completed and archived status 3', archived['Meta'])
        stop(server)
        inventory = work / 'inventory.json'
        write(inventory, {'paths': [str(instance)]})
        helper = source / 'docs/scripts/cc-offline-backup.py'
        for command in [['backup', '--inventory', str(inventory), '--destination', str(work / 'backup')],
                        ['restore', '--backup', str(work / 'backup'), '--destination', str(work / 'restored')]]:
            run = subprocess.run([sys.executable, str(helper)] + command, capture_output=True, text=True, timeout=120)
            assert run.returncode == 0, run.stderr
        restored = work / 'restored' / str(instance).lstrip('/')
        server = start_backend(restored, 'backend-restored')
        again = get_job(archived['Meta']['id'])
        assert again['Meta'] == archived['Meta'] and again['Data'] == archived['Data']
        record('documented offline backup and separate restore', {'exact_metadata_and_data': True})
        stop(server)
    finally:
        cleanup_errors = []
        for process in reversed(processes):
            try:
                stop(process)
            except Exception as error:
                cleanup_errors.append(str(error))
                if process.poll() is None:
                    # launch() creates a private session for precisely this
                    # owned process tree. Never signal an unrelated process.
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
        for handle in handles:
            handle.close()
        for path in evidence.glob('*.log'):
            text = path.read_text().replace(token, '[REDACTED]')
            path.write_text(re.sub(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', '[REDACTED]', text))
        assert not cleanup_errors, cleanup_errors


if __name__ == '__main__':
    main()
