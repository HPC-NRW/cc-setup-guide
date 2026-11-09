#!/usr/bin/env python3
"""Exercise upstream unit schemas and real router -> backend -> archived API values.

Requires a stopped, newly generated installer fixture containing .guide-test-fixture.
All state is copied to a new private directory; no original installation is modified.
"""
import argparse
import base64
import copy
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from test_metrics import check_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--router-binary', type=Path, required=True)
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--browser-executable')
    args = parser.parse_args()
    source, installation = args.source.resolve(), args.installation.resolve()
    assert (installation / '.guide-test-fixture').is_file(), 'Only explicitly marked disposable fixtures are accepted'
    assert not any(path.is_symlink() for path in installation.rglob('*')), 'External symlink targets are not copied'
    os.umask(0o077)
    args.work.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='backend-units-', dir=args.work.resolve()))
    version_output = subprocess.run([str(installation / 'cc-backend'), '-version'],
                                    capture_output=True, text=True, check=True).stdout
    version = {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
               for line in version_output.splitlines()
               if line.startswith(('Version:', 'Git hash:', 'SQL db version:', 'Job archive version:'))}
    report = {'schema': check_schema(source), 'backend_version': version,
              'work': str(work), 'cases': [], 'hardware_test': False}
    token = (installation / 'apikey.txt').read_text().strip()
    payload = token.split('.')[1]
    token_subject = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))['sub']
    assert isinstance(token_subject, str) and token_subject, 'fixture JWT subject required for owned-job queries'
    password = (installation / 'admin_password.txt').read_text().strip()
    rub = json.loads((source / 'docs/examples/rub/job-archive/cluster.json').read_text())
    original = json.loads((installation / 'var/job-archive/demo_cluster/cluster.json').read_text())

    def record(name, **details):
        report['cases'].append({'test': name, **details})
        text = json.dumps(report, indent=2)
        assert token not in text and password not in text, 'credential would enter report'
        (args.work / 'backend-units-results.json').write_text(text + '\n')

    for mode in ('minimal-validated', 'rub-validated', 'rub-archive-validation', 'rub-sparse', 'rub-runtime'):
        instance = work / mode
        shutil.copytree(installation, instance)
        cluster = copy.deepcopy(original if mode == 'minimal-validated' else rub)
        cluster['name'] = 'demo_cluster'  # Test identity, not a schema repair.
        if mode in ('rub-runtime', 'rub-sparse', 'rub-archive-validation'):
            subcluster = copy.deepcopy(original['subClusters'][0])
            subcluster.update(name='synthetic', nodes='cpu001', socketsPerNode=2, coresPerSocket=1, threadsPerCore=1)
            subcluster['topology'] = {'node': [0, 1], 'socket': [[0], [1]], 'memoryDomain': [[0], [1]],
                                     'core': [[0], [1]], 'accelerators': [{'id': 'gpu0', 'type': 'Nvidia GPU', 'model': 'synthetic'}]}
            cluster['subClusters'] = [subcluster]
            for metric in cluster['metricConfig']:
                metric['timestep'] = 2  # Documented shorter synthetic test interval.
        (instance / 'var/job-archive/demo_cluster/cluster.json').write_text(json.dumps(cluster))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        config = json.loads((instance / 'config.json').read_text())
        config['main'].update(addr=f'127.0.0.1:{port}')
        if mode in ('minimal-validated', 'rub-validated', 'rub-archive-validation'):
            config['main']['validate'] = True
        else:
            config['main'].pop('validate', None)  # Unmodified upstream runtime default.
        (instance / 'config.json').write_text(json.dumps(config))
        logpath = instance / 'backend.log'
        log = logpath.open('w')
        process = subprocess.Popen([str(instance / 'cc-backend'), '-server', '-loglevel', 'info'], cwd=instance,
                                   stdout=log, stderr=log)

        def request(path, body=None):
            raw = None if body is None else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
            headers = {'X-Auth-Token': token, 'Content-Type': 'text/plain' if isinstance(body, str) else 'application/json'}
            try:
                with urllib.request.urlopen(urllib.request.Request(base + path, data=raw, headers=headers), timeout=5) as response:
                    code, data = response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                code, data = error.code, error.read().decode()
            try:
                return code, json.loads(data)
            except json.JSONDecodeError:
                return code, data

        try:
            clusters = None
            for attempt in range(80):
                if process.poll() is not None:
                    break
                try:
                    code, data = request('/api/clusters/')
                    if code == 200:
                        clusters = data.get('clusters') or []
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.1)
            assert clusters and clusters[0]['name'] == 'demo_cluster', 'Cluster not available after startup'
            actual_metrics = {metric['name']: metric for metric in clusters[0]['metricConfig']}
            expected_metrics = {metric['name']: metric for metric in cluster['metricConfig']}
            for name, metric in expected_metrics.items():
                assert all(actual_metrics[name]['unit'].get(key, '') == metric['unit'].get(key, '') for key in ('base', 'prefix')), (mode, name, 'unit base/prefix changed')
            if mode in ('minimal-validated', 'rub-validated'):
                record(mode, passed=True, cluster='demo_cluster', validate=True,
                       metric_count=len(actual_metrics), subcluster_count=len(cluster['subClusters']))
                continue
            record(mode + ': configured units preserved', passed=True,
                   validate=config['main'].get('validate', 'upstream default'),
                   units={name: metric['unit'] for name, metric in actual_metrics.items()})
            # Use the actual published router. Only artificial topology/identities differ.
            specs = [
                ('load_one', '', 2, 'node', None, 'cpu_load', 2),
                ('mem_used', 'Bytes', 1e9, 'memoryDomain', '0', 'mem_used', 1),
                ('mem_used', 'kB', 1048576, 'memoryDomain', '1', 'mem_used', 1.073741824),
                ('mem_bw', 'GBytes/s', 2, 'socket', '0', 'mem_bw', 2),
                ('mem_bw', 'GBytes/s', 3, 'socket', '1', 'mem_bw', 3),
                ('net_bytes_in_bw', 'Bytes/s', 1e6, 'node', None, 'net_bytes_in', 1),
                ('nv_fb_mem_used', 'MiBytes', 1024, 'accelerator', 'gpu0', 'acc_mem_used', 1.073741824),
                ('clock', 'MHz', 2000, 'hwthread', '0', 'clock', 2000),
                ('clock', 'MHz', 3000, 'hwthread', '1', 'clock', 3000),
                ('flops_any', 'GFlops/s', 64, 'hwthread', '0', 'flops_any', 64),
                ('flops_any', 'GFlops/s', 128, 'hwthread', '1', 'flops_any', 128),
            ]
            if mode == 'rub-sparse':
                specs = [spec for spec in specs if spec[0] == 'load_one' or
                         spec[0] in ('clock', 'mem_bw', 'mem_used') and spec[4] == '1']
            inputs = [{'name': name, 'unit': unit, 'value': value,
                       'tags': {'hostname': 'cpu001', 'type': scope, **({'type-id': index} if index is not None else {})}}
                      for name, unit, value, scope, index, _, _ in specs]
            excluded = [
                {'name': 'cpu_user', 'unit': '%', 'value': 75, 'tags': {'hostname': 'cpu001', 'type': 'hwthread', 'type-id': '0'}},
                {'name': 'nv_util', 'unit': '%', 'value': 50, 'tags': {'hostname': 'cpu001', 'type': 'accelerator', 'type-id': 'gpu0'}},
                {'name': 'io_reads', 'unit': '', 'value': 8, 'tags': {'hostname': 'cpu001', 'type': 'node', 'device': 'nvme0n1p4'}},
                {'name': 'ib_recv_pkts_bw', 'unit': 'packets/s', 'value': 6, 'tags': {'hostname': 'cpu001', 'type': 'node'}},
                {'name': 'numastats_numa_hit_rate', 'unit': '', 'value': 10, 'tags': {'hostname': 'cpu001', 'type': 'memoryDomain', 'type-id': '0'}},
            ]
            processor = json.loads((source / 'docs/examples/rub/cc-metric-collector/router.json').read_text())['process_messages']
            router = subprocess.run([str(args.router_binary.resolve())], input=json.dumps({'router': processor, 'metrics': inputs + excluded}),
                                    capture_output=True, text=True, timeout=20)
            assert router.returncode == 0, router.stderr
            routed = json.loads(router.stdout)
            assert len(routed) == len(specs) + len(excluded), 'router lost input records'
            assert all(item['dropped'] and not item.get('error') for item in routed[len(specs):]), 'unsupported unit metrics reached the backend route'
            record(mode + ': unsupported unit metrics dropped', passed=True,
                   dropped_inputs=[item['name'] for item in excluded])
            routed = routed[:len(specs)]
            for item, spec in zip(routed, specs):
                assert not item['dropped'] and not item.get('error') and item['name'] == spec[-2], item
                assert abs(item['value'] - spec[-1]) < 1e-8, (item, spec[-1])
            start = 2 * (int(time.time()) // 2) - 64
            stamps = list(range(start, start + 62, 2))
            jobid = 910005
            job = {'jobId': jobid, 'cluster': 'demo_cluster', 'user': token_subject, 'project': 'guide-test',
                   'startTime': start, 'numNodes': 1, 'numHwthreads': 2, 'numAcc': 1,
                   'resources': [{'hostname': 'cpu001', 'hwthreads': [0, 1], 'accelerators': ['gpu0']}]}
            assert request('/api/jobs/start_job/', job)[0] == 201
            lines = []
            for item, spec in zip(routed, specs):
                scope, index = spec[3:5]
                tags = f'cluster=demo_cluster,hostname=cpu001,type={scope}'
                if index is not None:
                    tags += ',type-id=' + index
                for stamp in stamps:
                    lines.append(f'{item["name"]},{tags} value={item["value"]} {stamp}')
            assert request('/api/write/', '\n'.join(lines))[0] == 200
            assert request('/api/jobs/stop_job/', {'jobId': jobid, 'cluster': 'demo_cluster', 'startTime': start,
                                                'stopTime': start + 62, 'jobState': 'completed'})[0] == 200
            if mode == 'rub-archive-validation':
                # main.validate also validates archived metadata written by the backend.
                # Its upstream schema currently rejects some of those records even
                # when the cluster and metric units validated at startup.
                with sqlite3.connect('file:' + str(instance / 'var/job.db') + '?mode=ro', uri=True) as database:
                    for attempt in range(80):
                        row = database.execute('SELECT id, monitoring_status FROM job WHERE job_id = ?', (jobid,)).fetchone()
                        if row and row[1] == 3:
                            break
                        time.sleep(0.1)
                assert row and row[1] == 3, 'Archive validation probe did not reach archived status'
                detail_code, detail_response = request('/api/jobs/' + str(row[0]) + '?all-metrics=true')
                assert not detail_response, 'Pinned backend unexpectedly returned a validated archived dataset'
                code, response = request('/api/jobs/')
                error = json.dumps(response)
                assert code >= 400 and 'job-meta.schema.json' in error and 'jsonschema' in error, (code, response)
                metadata_paths = list((instance / 'var/job-archive').rglob('meta.json'))
                assert len(metadata_paths) == 1
                metadata = json.loads(metadata_paths[0].read_text())
                assert 'cpu_user' not in metadata['statistics'], 'Probe must use the unmodified supported metric selection'
                log.flush()
                assert 'job-data.schema.json' in logpath.read_text(), 'Missing upstream archived-data schema failure'
                record('upstream archived metadata and data validation limitation', passed=True, expected_limitation=True,
                       validate=True, monitoring_status=3, response_status=code, error=response,
                       job_detail_status=detail_code, job_detail_empty=not detail_response,
                       absent_required_statistic='cpu_user',
                       null_metadata_fields=sorted(key for key, value in metadata.items() if value is None),
                       schema_or_product_patched=False)
                continue
            archived = None
            for attempt in range(80):
                jobs = request('/api/jobs/')[1].get('jobs', [])
                archived = next((job for job in jobs if job['jobId'] == jobid and job['monitoringStatus'] == 3), None)
                if archived:
                    break
                time.sleep(0.1)
            assert archived, 'Job did not reach actual archived monitoringStatus3'
            dbid = archived['id']
            data = request('/api/jobs/' + str(dbid) + '?all-metrics=true')[1]
            assert data['Meta']['jobId'] == jobid and data['Meta']['resources'][0]['hostname'] == 'cpu001'
            # The ordinary single-node job endpoint requests core scope. Request native scopes explicitly.
            query = urllib.parse.urlencode([('metric', name) for name in sorted({spec[-2] for spec in specs})] +
                                           [('scope', scope) for scope in ('hwthread', 'memoryDomain', 'socket', 'accelerator', 'node')])
            code, native = request('/api/jobs/metrics/' + str(dbid) + '?' + query)
            assert code == 200 and not native.get('error') and native.get('data'), native
            data['Data'] = {}
            for item in native['data']['jobMetrics']:
                data['Data'].setdefault(item['name'], {})[item['scope']] = item['metric']
            archives = list((instance / 'var/job-archive').rglob('data.json.gz'))
            assert len(archives) == 1, archives
            stored = json.loads(gzip.decompress(archives[0].read_bytes()))
            for spec in specs:
                assert data['Data'][spec[-2]][spec[3]] == stored[spec[-2]][spec[3]], (spec[-2], 'archive differs from native API')
            (args.work / (mode + '-job-api.json')).write_text(json.dumps(data, indent=2) + '\n')
            if mode == 'rub-sparse':
                sparse_ids = {}
                for name, scope, expected_value in [('clock', 'hwthread', 3000), ('mem_bw', 'socket', 3),
                                                     ('mem_used', 'memoryDomain', 1.07)]:
                    series = data['Data'][name][scope]['series']
                    assert len(series) == 1 and str(series[0]['id']) in ('0', '1'), (name, series)
                    assert series[0]['data'] == [expected_value] * len(stamps), (name, series)
                    sparse_ids[name] = {'sent_id': '1', 'returned_id': series[0]['id'], 'value': expected_value,
                                       'samples': len(series[0]['data']), 'incorrect_id': str(series[0]['id']) != '1'}
                # HWthread query order follows job resources [0,1]; socket/NUMA query order uses Go maps.
                assert sparse_ids['clock']['returned_id'] == '0', sparse_ids
                record('sparse native scope upstream limitation reproduced', expected_limitation=True,
                       monitoring_status=3, observations=sparse_ids,
                       mechanism='FetchData drops missing selectors; LoadScopedData assigns IDs by compressed row index')
                continue
            values = {}
            for item, spec in zip(routed, specs):
                name, expected = spec[-2:]
                metric = data['Data'][name][spec[3]]
                assert metric['timestep'] == 2, (name, 'unexpected stored sampling interval')
                assert all(metric['unit'].get(key, '') == expected_metrics[name]['unit'].get(key, '') for key in ('base', 'prefix')), (name, 'API unit changed')
                series = next(series for series in metric['series'] if series['hostname'] == 'cpu001'
                              and (spec[4] is None or str(series.get('id')) == spec[4]))
                points = series['data']
                assert len(points) == len(stamps), (name, len(points), len(stamps))
                # Upstream schema.Series serializes float32-valued samples with exactly 2 decimal places.
                archived_expected = float(format(struct.unpack('f', struct.pack('f', expected))[0], '.2f'))
                assert all(isinstance(value, (int, float)) and math.isfinite(value) and value == archived_expected
                           for value in points), (name, points, archived_expected)
                values.setdefault(name, []).append({'scope': spec[3], 'index': spec[4], 'unit': metric['unit'],
                                'router_value': expected, 'archived_value': archived_expected,
                                'samples': len(points), 'timestep': metric['timestep']})
            (args.work / 'unit-job-api.json').write_text(json.dumps(data, indent=2) + '\n')
            record('real RUB router to archived backend API', passed=True, job_id=jobid, database_id=dbid,
                   monitoring_status=3, values=values, timestamps=stamps,
                   precision='router values checked before archival; archive/API samples equal float32 rounded to2 decimals',
                   adaptations='artificial host/topology and identities; all stored metric timesteps2s; no unit/schema/formula repairs')
            if args.browser:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as play:
                    options = {'headless': True, 'args': ['--no-sandbox']}
                    if args.browser_executable:
                        options['executable_path'] = args.browser_executable
                    browser = play.chromium.launch(**options)
                    context = browser.new_context(viewport={'width': 1600, 'height': 1100})
                    context.route('**/*', lambda route: route.continue_()
                                  if urllib.parse.urlsplit(route.request.url).hostname == '127.0.0.1' else route.abort())
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base + '/monitoring/job/' + str(dbid), wait_until='networkidle')
                    page.locator('#username').fill('admin')
                    page.locator('#password').fill(password)
                    page.locator('button[type=submit]').click()
                    page.wait_for_load_state('networkidle')
                    page.goto(base + '/monitoring/job/' + str(dbid), wait_until='networkidle')
                    for index in (0, 1):
                        page.get_by_role('button', name='Select Metrics').nth(index).click()
                        modal = page.locator('.modal.show')
                        modal.locator('input[type=checkbox]').first.wait_for(state='visible')
                        for checkbox in modal.locator('input[type=checkbox]').all():
                            checkbox.set_checked(checkbox.input_value() in values)
                        modal.get_by_role('button', name='Close & Apply').click()
                        page.wait_for_timeout(300)
                    page.wait_for_function("document.body.innerText.includes('Statistics Table')")
                    text = page.locator('body').inner_text()
                    assert str(jobid) in text and 'cpu001' in text
                    assert all(name in text for name in values), 'metric missing from browser'
                    visible_units = ['GB', 'GB/s', 'MB/s', 'MHz', 'GF/s']
                    assert all(unit in text for unit in visible_units), 'configured upstream units missing'
                    assert not errors, errors
                    page.screenshot(path=str(args.work / 'unit-job-browser.png'), full_page=True)
                    record('browser units', passed=True, version=browser.version, visible_units=visible_units, errors=errors)
                    browser.close()
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log.close()
            text = logpath.read_text().replace(token, '[REDACTED]').replace(password, '[REDACTED]')
            logpath.write_text(text)
    print('PASS: minimal and complete RUB profiles validate, preserved units, router/archive/API' + (' and browser' if args.browser else ''))


if __name__ == '__main__':
    main()
