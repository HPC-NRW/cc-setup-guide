#!/usr/bin/env python3
"""Check documented counter arithmetic without accessing performance counters."""
import argparse
import ast
import json
import pathlib
import re
import os
import shutil
import subprocess
import sys
import tempfile


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'Duplicate JSON key: ' + key
        result[key] = value
    return result


def calculate(expression, values):
    tree = ast.parse(expression, mode='eval')
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.UAdd, ast.USub, ast.Load, ast.Name, ast.Constant)
    assert all(isinstance(node, allowed) for node in ast.walk(tree)), expression
    return eval(compile(tree, '<metric formula>', 'eval'), {'__builtins__': {}}, values)


def check_zen4_bandwidth(label, eventsets, globalmetrics, write_slot, results):
    """Exercise every channel independently, then combine distinct read/write values."""
    metrics = {}
    for eventset in eventsets:
        for metric in eventset['metrics']:
            if metric['name'] in ('mem_read', 'mem_write'):
                assert metric['name'] not in metrics, (label, 'duplicate intermediate metric')
                metrics[metric['name']] = (eventset, metric)
    assert set(metrics) == {'mem_read', 'mem_write'}, (label, 'missing memory intermediate')
    totals = [m for m in globalmetrics if m['name'] == 'mem_bw']
    assert len(totals) == 1, (label, 'missing or duplicate mem_bw')
    total_metric = totals[0]
    assert total_metric['unit'] == 'GBytes/s' and total_metric['publish'] is True, (label, total_metric)
    assert total_metric['type'] == 'socket', (label, total_metric)
    for name, slot, event in (('mem_read', 0, 'CAS_CMD_RD'),
                              ('mem_write', write_slot, 'CAS_CMD_WR')):
        eventset, metric = metrics[name]
        assert metric['publish'] is False and metric['type'] == 'socket', (label, metric)
        for channel in range(12):
            assert eventset['events'][f'UMC{channel}C{slot}'] == event, (label, name, channel)

    cases = []
    for kind in ('read', 'write'):
        for channel in range(12):
            reads, writes = [0] * 12, [0] * 12
            (reads if kind == 'read' else writes)[channel] = 1e9
            cases.append((reads, writes, 2))
    cases.append(([1e6 * (i + 1) for i in range(12)],
                  [2e6 * (i + 2) for i in range(12)], 3))
    for reads, writes, seconds in cases:
        actual = {}
        for name, byte_values, slot in (('mem_read', reads, 0), ('mem_write', writes, write_slot)):
            eventset, metric = metrics[name]
            values = dict.fromkeys(eventset['events'], 0)
            values['time'] = seconds
            values.update({f'UMC{i}C{slot}': byte_values[i] / 64 for i in range(12)})
            actual[name] = calculate(metric['calc'], values)
            expected = sum(byte_values) / seconds / 1e9
            assert abs(actual[name] - expected) < 1e-12, (label, name, actual, expected)
        total = calculate(total_metric['calc'], actual)
        expected_total = (sum(reads) + sum(writes)) / seconds / 1e9
        assert abs(total - expected_total) < 1e-12, (label, total, expected_total)
        results.append({'source': label, 'read_bytes': reads, 'write_bytes': writes,
                        'seconds': seconds, 'mem_bw_GB_s': total})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=pathlib.Path, required=True)
    parser.add_argument('--work', type=pathlib.Path, required=True)
    parser.add_argument('--collector-source', type=pathlib.Path, help='Optional pinned collector checkout for real converter tests; requires --likwid-source')
    parser.add_argument('--likwid-source', type=pathlib.Path,
                        help='Optional unpacked LIKWID v5.5.1 source for event availability checks')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    results = []
    converter_outputs = {}
    if args.collector_source:
        assert args.likwid_source, '--collector-source also needs --likwid-source'
        layout = pathlib.Path(tempfile.mkdtemp(prefix='likwid-layout-', dir=args.work.resolve()))
        (layout / 'bin').mkdir()
        sentinel = layout / 'bin/likwid-topology'
        sentinel.write_text('#!/bin/sh\nexit 99\n')
        sentinel.chmod(0o755)
        for arch, group in (('zen4', 'MEMREAD'), ('zen4', 'MEMWRITE'), ('SPR', 'MEM')):
            dest = layout / 'share/likwid/perfgroups' / arch
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.likwid_source / 'groups' / arch / (group + '.txt'), dest / (group + '.txt'))
            command = [sys.executable, str(args.collector_source / 'scripts/likwid_perfgroup_to_cc_config.py'), arch, group]
            execution = subprocess.run(command, env=dict(os.environ, PATH=str(layout / 'bin'), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True, timeout=15)
            assert execution.returncode == 0, execution.stderr + execution.stdout
            converter_outputs[arch, group] = json.loads(execution.stdout)
            (args.work / (arch + '-' + group + '-converter.json')).write_text(execution.stdout)

    # The published site profile is one Zen4 CPU configuration. Historical
    # CPU/GPU/Zen5 variants are no longer guide inputs and must not be fabricated.
    name = 'docs/examples/rub/cc-metric-collector/collectors.json'
    profile = json.loads((args.source / name).read_text(), object_pairs_hook=unique_pairs)
    assert not {'cpustat', 'numastats', 'iostat', 'nfs4stat'} & set(profile), (name, 'collector has no registered metric')
    assert profile['lustrestat']['send_diff_values'] is False, (name, 'interval counters must remain disabled')
    config = profile['likwid']
    unit_contract = {'clock': 'MHz', 'ipc': 'IPC', 'core_power': 'W',
                     'flops_any': 'GFlops/s', 'mem_bw': 'GBytes/s'}
    all_metrics = config['globalmetrics'] + [m for eventset in config['eventsets'] for m in eventset['metrics']]
    named_metrics = {m['name']: m for m in all_metrics}
    assert len(named_metrics) == len(all_metrics), (name, 'duplicate metric name')
    assert set(unit_contract) <= set(named_metrics), (name, 'missing published metric')
    for metric_name, unit in unit_contract.items():
        metric = named_metrics[metric_name]
        assert metric['unit'] == unit and metric['publish'] is True, (name, metric)
    for eventset in config['eventsets']:
        for metric in eventset['metrics']:
            names = {n.id for n in ast.walk(ast.parse(metric['calc'], mode='eval')) if isinstance(n, ast.Name)}
            assert names <= set(eventset['events']) | {'time', 'inverseClock'}, (name, metric)
        if args.likwid_source:
            event_definitions = (args.likwid_source / 'src/includes/perfmon_zen4_events.txt').read_text()
            for event in eventset['events'].values():
                assert re.search(r'\b(?:EVENT|UMASK)_' + re.escape(event) + r'\b', event_definitions), (name, event)
    for metric in config['globalmetrics']:
        names = {n.id for n in ast.walk(ast.parse(metric['calc'], mode='eval')) if isinstance(n, ast.Name)}
        local_names = {m['name'] for eventset in config['eventsets'] for m in eventset['metrics']}
        assert names <= local_names, (name, metric, 'undefined global input')
    for metric_name, counters, expected, events in (
            ('clock', {'FIXC1': 4e9, 'time': 2}, 2000,
             {'FIXC1': 'ACTUAL_CPU_CLOCK'}),
            ('ipc', {'PMC0': 6e9, 'PMC1': 3e9}, 2,
             {'PMC0': 'RETIRED_INSTRUCTIONS', 'PMC1': 'CPU_CLOCKS_UNHALTED'}),
            ('core_power', {'PWR0': 600, 'time': 3}, 200,
             {'PWR0': 'RAPL_CORE_ENERGY'}),
            ('flops_any', {'PMC2': 8e9, 'time': 2}, 4,
             {'PMC2': 'RETIRED_SSE_AVX_FLOPS_ALL', 'PMC3': 'MERGE'})):
        eventset = next(es for es in config['eventsets'] if named_metrics[metric_name] in es['metrics'])
        assert all(eventset['events'][key] == value for key, value in events.items()), (name, metric_name)
        metric = named_metrics[metric_name]
        assert metric['type'] == 'hwthread', (name, metric)
        actual = calculate(metric['calc'], counters)
        assert abs(actual - expected) < 1e-12, (name, metric_name, actual, expected)
        results.append({'source': name, 'metric': metric_name, 'inputs': counters, 'value': actual})
    check_zen4_bandwidth(name, config['eventsets'], config['globalmetrics'], 1, results)
    for language in ('de', 'en'):
        text = (args.source / f'docs/likwid_metrics.{language}.md').read_text()
        blocks = re.findall(r'```json\s*(.*?)```', text, re.S)
        if converter_outputs:
            complete = []
            for block in blocks:
                try:
                    complete.append(json.loads(block, object_pairs_hook=unique_pairs))
                except json.JSONDecodeError:
                    pass  # Declared tutorial fragments are checked through their complete examples.
            for key, expected in converter_outputs.items():
                assert expected in complete, (language, key, 'documented converter output differs from release')
        # The documented Zen4 selection uses separate read/write eventsets,
        # each with its own C0 slots, plus a published global sum.
        zen4 = json.loads('[' + next(b for b in blocks if '"name": "mem_read"' in b) + ']',
                         object_pairs_hook=unique_pairs)
        globalmetrics = json.loads('{' + next(b for b in blocks if b.lstrip().startswith('"globalmetrics"')) + '}',
                                   object_pairs_hook=unique_pairs)['globalmetrics']
        check_zen4_bandwidth(f'likwid_metrics.{language}.md:zen4', zen4, globalmetrics, 0, results)
        spr = json.loads([b for b in blocks if 'MBOX0C0' in b][-1], object_pairs_hook=unique_pairs)
        metric = next(m for m in spr['metrics'] if m['name'] == 'mem_bw')
        assert metric['unit'] == 'GBytes/s', metric
        for read_bytes, write_bytes, seconds in ((1e9, 0, 1), (0, 3e9, 2), (1e9, 3e9, 2)):
            values = dict.fromkeys(spr['events'], 0)
            values.update(time=seconds, MBOX0C0=read_bytes / 64, MBOX11C1=write_bytes / 64)
            actual = calculate(metric['calc'], values)
            assert abs(actual - (read_bytes + write_bytes) / seconds / 1e9) < 1e-12
            results.append({'language': language, 'bytes': [read_bytes, write_bytes],
                            'seconds': seconds, 'mem_bw_GB_s': actual})
    cluster = json.loads((args.source / 'docs/examples/rub/job-archive/cluster.json').read_text(), object_pairs_hook=unique_pairs)
    for subcluster in cluster['subClusters']:
        topology = subcluster['topology']
        expected_count = subcluster['socketsPerNode'] * subcluster['coresPerSocket'] * subcluster['threadsPerCore']
        assert len(topology['node']) == len(set(topology['node'])) == expected_count
        for key in ('socket', 'memoryDomain', 'core'):
            ids = [value for group in topology[key] for value in group]
            assert len(ids) == len(set(ids)) == expected_count
            assert set(ids) == set(topology['node'])
    (args.work / 'hardware-results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(f'PASS: {len(results)} arithmetic cases, current RUB Zen4 profile, DE/EN Zen4 and SPR examples, all RUB topologies'
          + (', LIKWID event definitions' if args.likwid_source else '')
          + (', 3 real converter outputs match DE/EN' if converter_outputs else ''))


if __name__ == '__main__':
    main()
