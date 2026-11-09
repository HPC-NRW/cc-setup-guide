#!/usr/bin/env python3
"""Check current examples, schemas and optionally real cc-lib router semantics."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'duplicate JSON key: ' + key
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=unique)


def blocks(source, path):
    text = (source / path).read_text()
    def include(match):
        return (source / 'docs' / match[1]).read_text().rstrip()
    text = re.sub(r'--8<--\s+"([^"]+)"', include, text)
    return re.findall(r'```json\n(.*?)\n```', text, re.S)


def fragment(text):
    try:
        return loads(text)
    except json.JSONDecodeError:
        return loads('{' + text.strip().rstrip(',') + '}')


def tutorial_router(source, lang='en'):
    return next(loads(b) for b in blocks(source, f'docs/metrics.{lang}.md')
                if 'rename_messages' in b)


def messages():
    specs = [
        ('load_one', '', 2, {}, 'cpu_load', 2),
        ('load_five', '', 4, {}, None, None),
        ('mem_used', 'Bytes', 1e9, {}, 'mem_used', 1),
        ('mem_used', 'kB', 1048576, {}, 'mem_used', 1.073741824),
        ('net_bytes_in_bw', 'Bytes/s', 1e6, {}, 'net_bytes_in', 1),
        ('ib_recv_bw', 'Bytes/s', 2e6, {}, 'ib_recv', 2),
        ('nv_util', '%', 50, {'type': 'accelerator'}, None, None),
        ('nv_fb_mem_used', 'MiBytes', 1024, {'type': 'accelerator'}, 'acc_mem_used', 1.073741824),
        ('io_reads', '', 8, {'device': 'nvme0n1p4'}, None, None),
        ('io_writes', '', 9, {'device': '/dev/nvme0n1p4'}, None, None),
        ('io_reads', '', 99, {'device': 'wrongdisk'}, None, None),
        ('disk_free', 'Bytes', 1e9, {'device': '/dev/nvme0n1p4'}, 'disk_free', 1),
        ('nfsio_nread_bw', 'Bytes/s', 1e6, {'stypeid': 'home:/home'}, 'nfsio_nread', 1),
        ('numastats_numa_hit_rate', '', 20, {'type': 'memoryDomain', 'typeid': '1'}, None, None),
        ('nfs4_open', '', 10, {}, None, None),
        ('lustre_open_diff', '', 12, {}, None, None),
        ('clock', 'MHz', 2000, {'type': 'hwthread', 'typeid': '0'}, 'clock', 2000),
        ('flops_any', 'GFlops/s', 64, {'type': 'hwthread', 'typeid': '0'}, 'flops_any', 64),
        ('ipc', 'IPC', 1.5, {'type': 'hwthread', 'typeid': '0'}, 'ipc', 1.5),
        ('core_power', 'W', 200, {'type': 'hwthread', 'typeid': '0'}, 'core_power', 200),
        # Unsupported optional units and unregistered names must never leave the profile.
        ('cpu_user', '%', 75, {'type': 'hwthread', 'typeid': '0'}, None, None),
        ('net_pkts_in_bw', 'packets/s', 2, {}, None, None),
        ('net_pkts_out_bw', 'packets/s', 3, {}, None, None),
        ('ib_recv_pkts_bw', 'packets/s', 4, {}, None, None),
        ('ib_xmit_pkts_bw', 'packets/s', 5, {}, None, None),
        ('nv_mem_util', '%', 40, {'type': 'accelerator'}, None, None),
        ('nv_compute_processes', '', 2, {'type': 'accelerator'}, None, None),
        ('lustre_close_diff', '', 6, {}, None, None),
        ('lustre_statfs_diff', '', 7, {}, None, None),
        ('nfs4_close', '', 8, {}, None, None),
        ('numastats_interleave_hit_rate', '', 9, {'type': 'memoryDomain'}, None, None),
        ('numastats_local_node_rate', '', 10, {'type': 'memoryDomain'}, None, None),
        ('numastats_numa_foreign_rate', '', 11, {'type': 'memoryDomain'}, None, None),
        ('numastats_numa_miss_rate', '', 12, {'type': 'memoryDomain'}, None, None),
        ('numastats_other_node_rate', '', 13, {'type': 'memoryDomain'}, None, None),
        ('nread', 'Bytes/s', 1000, {}, None, None),
        ('nwrite', 'Bytes/s', 2000, {}, None, None),
        ('unregistered_metric', '', 42, {}, None, None),
    ]
    return [({'name': name, 'unit': unit, 'value': value,
              'tags': {'type': 'node', 'hostname': 'cpu001', **tags}}, expected, result)
            for name, unit, value, tags, expected, result in specs]


def process(binary, processor, items):
    run = subprocess.run([str(binary)], input=json.dumps({'router': processor, 'metrics': items}),
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    result = loads(run.stdout)
    assert all(not item.get('error') for item in result), result
    return result


def check_schema(source):
    contract = loads((source / 'tests/schema-contract.json').read_text())
    schemas = source / contract['schema_directory']
    for name, digest in contract['schema_sha256'].items():
        assert hashlib.sha256((schemas / name).read_bytes()).hexdigest() == digest, 'upstream schema was modified'
    cluster_schema = loads((schemas / 'cluster.schema.json').read_text())
    unit_schema = loads((schemas / 'unit.schema.json').read_text())
    registry = Registry().with_resource('embedfs://unit.schema.json', Resource(contents=unit_schema, specification=DRAFT202012))
    validator = Draft202012Validator(cluster_schema, registry=registry)
    for relative in contract['cluster_files']:
        cluster = loads((source / relative).read_text().replace('__CLUSTER_NAME__', 'demo_cluster'))
        errors = list(validator.iter_errors(cluster))
        assert not errors, (relative, [error.message for error in errors])
    cluster = loads((source / 'docs/examples/rub/job-archive/cluster.json').read_text())
    units = {metric['name']: metric['unit'] for metric in cluster['metricConfig']}
    assert len(units) == len(cluster['metricConfig']), 'duplicate registered metric'
    assert units == contract['rub_metric_units'], 'published metrics or units changed'
    assert all(set(unit) <= {'base', 'prefix'} for unit in units.values()), 'unsupported unit field'
    backend = loads((source / 'docs/examples/rub/cc-backend/config.json').read_text())
    assert 'validate' not in backend['main'], 'use the upstream default for global runtime validation'
    router = loads((source / 'docs/examples/rub/cc-metric-collector/router.json').read_text())
    allowlist = next(rule for rule in router['process_messages']['drop_messages_if']
                     if rule.startswith("messagetype == 'metric'"))
    allowed = set(re.findall("'([^']+)'", allowlist)) - {'metric'}
    assert allowed == set(units), 'router must export exactly the registered metric names'
    ui = loads((source / 'docs/examples/rub/cc-backend/ui-config.json').read_text())
    def check_ui(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith('-metrics'):
                    assert set(child) <= set(units), (key, child)
                else:
                    check_ui(child)
        elif isinstance(value, list):
            for child in value:
                check_ui(child)
    check_ui(ui)
    return {'minimal': 'PASS', 'rub': 'PASS', 'schema_sha256': contract['schema_sha256'],
            'rub_metric_count': len(units)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--router-binary', type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    report = {'schema': check_schema(source), 'json_files': [], 'router_cases': []}
    for path in sorted((source / 'docs/examples').rglob('*.json')):
        loads(path.read_text())
        report['json_files'].append(str(path.relative_to(source)))
    for profile in ['minimal', 'rub']:
        config = loads((source / f'docs/examples/{profile}/cc-metric-collector/config.json').read_text())
        assert config['main'] == {'interval': '60s', 'duration': '10s'}
        assert set(config) == {'main', 'collectors-file', 'router-file', 'sinks-file', 'receivers-file'}
    for lang in ['de', 'en']:
        process_config = tutorial_router(source, lang)['process_messages']
        order = process_config['stage_order']
        assert order.index('rename') < order.index('drop_if') < order.index('add_meta') < order.index('change_unit_prefix')
        assert '"scope": "hwthread"' not in (source / f'docs/more_metrics.{lang}.md').read_text()
        if args.router_binary:
            first = process(args.router_binary, process_config, [x[0] for x in messages()[:2]])
            assert first[0]['name'] == 'cpu_load' and first[0]['value'] == 2 and first[1]['dropped']
            # Reconstruct every documented intermediate processor by the documented merge rules.
            cumulative = copy.deepcopy(process_config)
            for index, text in enumerate(blocks(source, f'docs/more_metrics.{lang}.md')):
                piece = fragment(text)
                piece = piece.get('process_messages', piece)
                if not any(key in piece for key in ('rename_messages', 'drop_messages_if', 'change_unit_prefix')):
                    continue
                for key in ('rename_messages', 'change_unit_prefix'):
                    cumulative.setdefault(key, {}).update(piece.get(key, {}))
                for key in ('stage_order', 'drop_messages_if', 'add_meta_if'):
                    if key in piece:
                        cumulative[key] = piece[key]
                result = process(args.router_binary, cumulative, [x[0] for x in messages()])
                assert result[0]['name'] == 'cpu_load', (lang, index, result[0])
                whitelist = next(x for x in cumulative['drop_messages_if'] if 'name in [' in x and x.startswith('!'))
                for item, (_, expected_name, value) in zip(result, messages()):
                    if expected_name and "'" + expected_name + "'" in whitelist:
                        assert not item['dropped'] and item['name'] == expected_name, (lang, index, item)
                        assert abs(item['value'] - value) <= 1e-8, (lang, index, item, value)
                    else:
                        assert item['dropped'], (lang, index, item)
                report['router_cases'].append({'language': lang, 'intermediate': index, 'pass': True})
    if args.router_binary:
        router = loads((source / 'docs/examples/rub/cc-metric-collector/router.json').read_text())
        result = process(args.router_binary, router['process_messages'], [x[0] for x in messages()])
        for item, (_, name, value) in zip(result, messages()):
            if name is None:
                assert item['dropped'], item
            else:
                assert item['name'] == name and abs(item['value'] - value) <= 1e-8, (item, name, value)
        report['rub_router'] = result
        # Check representative node groups, both collector tag spellings,
        # and rejection of devices outside the selected filesystem.
        device_cases = [
            ('tvis001', 'md126', 'md125'),
            ('th200gpu001', 'nvme0n1p1', 'sda4'),
            ('tl40sgpu001', 'nvme0n1p1', 'nvme1n1p1'),
            ('tl40sgpu123', 'nvme0n1p1', 'nvme1n1p1'),
        ]
        inputs, expectations = [], []
        for hostname, selected, rejected in device_cases:
            for name, unit, raw, scaled in [('disk_free', 'Bytes', 1e9, 1)]:
                for device, keep in [(selected, True), (rejected, False)]:
                    for prefix in ['', '/dev/']:
                        inputs.append({'name': name, 'unit': unit, 'value': raw,
                                       'tags': {'type': 'node', 'hostname': hostname, 'device': prefix + device}})
                        expectations.append((keep, scaled))
        for export, keep in [('home:/home', True), ('other:/scratch', False)]:
            inputs.append({'name': 'nfsio_nread_bw', 'unit': 'Bytes/s', 'value': 1e6,
                           'tags': {'type': 'node', 'hostname': 'cpu001', 'stypeid': export}})
            expectations.append((keep, 1))
        selected = process(args.router_binary, router['process_messages'], inputs)
        for item, (keep, value) in zip(selected, expectations):
            assert item['dropped'] != keep, item
            if keep:
                assert abs(item['value'] - value) <= 1e-8, (item, value)
        report['rub_device_and_export_cases'] = len(selected)
    (args.work / 'metrics-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Metric examples, exact schemas and requested real router cases PASS')


if __name__ == '__main__':
    main()
