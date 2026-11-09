#!/usr/bin/env python3
"""Capture guide illustrations from an isolated backend with synthetic data."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--backend-dir', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True,
                        help='New private directory; existing paths are refused')
    parser.add_argument('--browser-executable', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    source, binaries = args.source.resolve(), args.backend_dir.resolve()
    work = args.work.resolve()
    work.mkdir(mode=0o700, parents=True, exist_ok=False)
    instance = work / 'instance'
    instance.mkdir()
    output = work / 'screenshots'
    output.mkdir()
    version = subprocess.run([str(binaries / 'cc-backend'), '-version'], cwd=instance,
                             capture_output=True, text=True, check=True)
    assert '1.5.4' in version.stdout + version.stderr, 'This capture fixture requires backend 1.5.4'

    def write(path, value):
        path.write_text(json.dumps(value, indent=2) + '\n')

    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = 'http://127.0.0.1:' + str(port)
    config = json.loads((source / 'scripts/templates/cc-backend.json.template').read_text())
    config['main'].update(addr='127.0.0.1:' + str(port), **{'api-allowed-ips': ['127.0.0.1']})
    config['cron'].update({'commit-job-worker': '1s', 'duration-worker': '1s'})
    config['metric-store']['memory-cap'] = 1
    archive = instance / 'var/job-archive'
    config['archive']['path'] = str(archive)
    config['metric-store']['checkpoints']['directory'] = str(instance / 'var/checkpoints')
    config['metric-store']['cleanup']['directory'] = str(instance / 'var/archive')
    write(instance / 'config.json', config)
    write(instance / 'ui-config.json', {
        'job-view': {'show-footprint': True, 'show-stat-table': True,
                     'show-polar-plot': False, 'show-roofline': False},
        'metric-config': {'job-list-metrics': ['cpu_load'],
                          'job-view-plot-metrics': ['cpu_load'],
                          'job-view-table-metrics': ['cpu_load']},
    })
    cluster = json.loads((source / 'scripts/templates/cluster.json.template').read_text()
                         .replace('__CLUSTER_NAME__', 'demo_cluster'))
    cluster['subClusters'][0]['processorType'] = 'Demo CPU'
    second = json.loads(json.dumps(cluster['subClusters'][0]))
    second.update(name='second_subcluster', nodes='node002', processorType='Second demo CPU')
    cluster['subClusters'].append(second)
    (archive / 'demo_cluster').mkdir(parents=True)
    (archive / 'version.txt').write_text('3\n')
    write(archive / 'demo_cluster/cluster.json', cluster)

    spec = importlib.util.spec_from_file_location('install_support', source / 'scripts/install_support.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    pair = instance / 'keypair.private'
    pair.write_bytes(subprocess.check_output([str(binaries / 'gen-keypair')], cwd=instance))
    helper.environment(pair, instance / '.env')
    pair.unlink()
    password = secrets.token_urlsafe(24)
    with (instance / 'setup.private.log').open('w') as log:
        for flags in (['-migrate-db'], ['-add-user', 'admin:admin:' + password],
                      ['-add-user', 'apiuser:api:' + secrets.token_urlsafe(24)]):
            subprocess.run([str(binaries / 'cc-backend')] + flags, cwd=instance,
                           stdout=log, stderr=log, check=True)
        raw_token = instance / 'token.private'
        raw_token.write_bytes(subprocess.check_output(
            [str(binaries / 'cc-backend'), '-jwt', 'apiuser'], cwd=instance, stderr=log))
        helper.token(raw_token, instance / 'apikey.private')
        raw_token.unlink()
    token = (instance / 'apikey.private').read_text().strip()

    def request(path, body=None):
        raw = None if body is None else (body.encode() if isinstance(body, str)
                                         else json.dumps(body).encode())
        req = urllib.request.Request(base + path, data=raw, headers={
            'X-Auth-Token': token,
            'Content-Type': 'text/plain' if isinstance(body, str) else 'application/json',
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode()
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass
            return response.status, result

    with (instance / 'backend.private.log').open('w') as log:
        process = subprocess.Popen([str(binaries / 'cc-backend'), '-server', '-loglevel', 'warn'],
                                   cwd=instance, stdout=log, stderr=log)
        try:
            for attempt in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Demo backend stopped; inspect private log')
                try:
                    with urllib.request.urlopen(base + '/login', timeout=1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Demo backend did not start')
            now = 60 * (int(time.time()) // 60)
            ids = {}
            for job_id, start, end in ((1001, now - 7200, now - 3600),
                                       (1002, now - 1800, now)):
                body = {'jobId': job_id, 'cluster': 'demo_cluster', 'user': 'demo-user',
                        'project': 'demo-project', 'metaData': {'jobName': 'Documentation example'},
                        'startTime': start, 'numNodes': 1, 'numHwthreads': 1,
                        'resources': [{'hostname': 'node001', 'hwthreads': [0]}]}
                code, result = request('/api/jobs/start_job/', body)
                assert code == 201
                for attempt in range(100):
                    with sqlite3.connect('file:' + str(instance / 'var/job.db') + '?mode=ro', uri=True) as db:
                        row = db.execute('SELECT id FROM job WHERE job_id = ?', (job_id,)).fetchone()
                    if row:
                        ids[job_id] = row[0]
                        break
                    time.sleep(.1)
                assert job_id in ids, 'Job was not inserted'
                samples = []
                for i, stamp in enumerate(range(start, end, 60)):
                    samples.append('cpu_load,cluster=demo_cluster,hostname=node001,type=node '
                                   + f'value={round(.6 + .18 * math.sin(i / 5), 2)} {stamp}')
                    samples.append('cpu_load,cluster=demo_cluster,hostname=node002,type=node '
                                   + f'value=0.25 {stamp}')
                assert request('/api/write/', '\n'.join(samples))[0] == 200
                if job_id == 1001:
                    assert request('/api/jobs/stop_job/', {
                        'jobId': job_id, 'cluster': 'demo_cluster', 'stopTime': end})[0] == 200
            for attempt in range(100):
                _, archived = request('/api/jobs/' + str(ids[1001]) + '?all-metrics=true')
                if archived['Meta']['monitoringStatus'] == 3:
                    break
                time.sleep(.1)
            assert archived['Meta']['monitoringStatus'] == 3
            _, running = request('/api/jobs/' + str(ids[1002]) + '?all-metrics=true')
            assert running['Meta']['jobState'] == 'running', running['Meta']
            continuous = []
            for i, stamp in enumerate(range(now - 7200, now + 1, 60)):
                for host, value in [('node001', round(.6 + .18 * math.sin(i / 5), 2)),
                                    ('node002', .25)]:
                    continuous.append(f'cpu_load,cluster=demo_cluster,hostname={host},type=node value={value} {stamp}')
            assert request('/api/write/', '\n'.join(continuous))[0] == 200
            assert request('/api/nodestate/', {'cluster': 'demo_cluster', 'nodes': [
                {'hostname': 'node001', 'states': ['allocated'], 'cpusAllocated': 1, 'jobsRunning': 1},
                {'hostname': 'node002', 'states': ['idle'], 'cpusAllocated': 0, 'jobsRunning': 0},
            ]})[0] == 200

            with sync_playwright() as play:
                browser = play.chromium.launch(executable_path=args.browser_executable,
                                               headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                              color_scheme='light', timezone_id='Europe/Berlin')
                context.route('**/*', lambda route: route.continue_()
                              if urllib.parse.urlsplit(route.request.url).hostname == '127.0.0.1'
                              else route.abort())
                page = context.new_page()
                page.goto(base + '/login', wait_until='networkidle')
                page.locator('#username').fill('admin')
                page.locator('#password').fill(password)
                page.locator('button[type=submit]').click()
                page.wait_for_load_state('networkidle')
                captures = [
                    ('node_overview.png', '/monitoring/systems/list/demo_cluster', 'node002'),
                    ('first_metric_overview.png', '/monitoring/node/demo_cluster/node001?startTime=last1h', 'cpu_load'),
                    ('running_job.png', '/monitoring/job/' + str(ids[1002]), '1002'),
                ]
                for name, path, expected in captures:
                    page.set_viewport_size({'width': 1440, 'height': 700 if name == 'first_metric_overview.png' else 1000})
                    response = page.goto(base + path, wait_until='networkidle')
                    assert response.status == 200
                    page.get_by_text(expected, exact=False).first.wait_for()
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(output / name), full_page=name != 'first_metric_overview.png')
                    (work / (name + '.txt')).write_text(page.locator('body').inner_text())
                browser.close()
            write(work / 'evidence.json', {
                'backend': '1.5.4', 'data': 'synthetic only; no Slurm instance',
                'cluster': 'demo_cluster', 'nodes': ['node001', 'node002'],
                'archived_job': {'job_id': 1001, 'database_id': ids[1001], 'monitoring_status': 3},
                'running_job': {'job_id': 1002, 'database_id': ids[1002], 'state': 'running'},
                'screenshots': [item[0] for item in captures],
            })
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    print('PASS: three screenshots from a synthetic loopback demo; backend stopped; output:', output)


if __name__ == '__main__':
    main()
