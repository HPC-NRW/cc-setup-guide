#!/usr/bin/env python3
"""Run the real topology helper with controlled subprocesses; no hardware access."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

TOPOLOGY = '''CPU name:,Fixture CPU "quoted"
CPU type:,Fixture
Sockets:,2
Cores per socket:,2
Threads per core:,2
NUMA domains:,4
Socket 0,0,1,4,5
Socket 1,2,3,6,7
STRUCT,NUMA Topology 0
Processors,0,4
STRUCT,NUMA Topology 1
Processors,1,5
STRUCT,NUMA Topology 2
Processors,2,6
STRUCT,NUMA Topology 3
Processors,3,7
STRUCT,Cache Topology L1
Cache groups,0 4,1 5,2 6,3 7
GPU count:,{gpu}
'''
GPU = '''ID:,0
Name:,Nvidia fixture "GPU"
PCI bus:,0x26
PCI domain:,0x00000000
PCI device:,0x00
PCI function:,0x01
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=pathlib.Path, required=True)
    parser.add_argument('--work', type=pathlib.Path, required=True)
    args = parser.parse_args()
    perl = shutil.which('perl')
    assert perl, 'Perl and JSON::PP are required'
    check = subprocess.run([perl, '-MJSON::PP', '-e', '1'], capture_output=True, text=True)
    assert check.returncode == 0, 'Install JSON::PP (or provide a local PERL5LIB): ' + check.stderr
    args.work.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix='subcluster-', dir=args.work.resolve()))
    helper = (args.source / 'docs/scripts/generate-subcluster.pl').resolve()
    outcomes = []
    for case in ('cpu', 'gpu', 'gpu_no_function', 'missing_topology', 'missing_bench', 'failed_topology',
                 'failed_memory', 'failed_scalar', 'failed_simd', 'bad_number',
                 'empty_topology', 'incomplete_gpu', 'duplicate_thread'):
        directory = work / case
        directory.mkdir()
        topology = TOPOLOGY.format(gpu=int(case in ('gpu', 'gpu_no_function', 'incomplete_gpu')))
        if case in ('gpu', 'gpu_no_function'):
            topology += GPU.replace('PCI function:,0x01\n', '') if case == 'gpu_no_function' else GPU
        if case == 'empty_topology':
            topology = ''
        if case == 'duplicate_thread':
            topology = topology.replace('Socket 0,0,1,4,5', 'Socket 0,0,1,4,4')
        if case != 'missing_topology':
            program = directory / 'likwid-topology'
            program.write_text(f'#!{sys.executable}\nimport sys\nprint({topology!r})\nsys.exit({7 if case == "failed_topology" else 0})\n')
            program.chmod(0o755)
        if case != 'missing_bench':
            program = directory / 'likwid-bench'
            program.write_text(f'''#!{sys.executable}
import sys
case = {case!r}
variant = sys.argv[sys.argv.index('-t')+1]
if (case == 'failed_memory' and variant == 'clload') or (case == 'failed_scalar' and variant == 'peakflops') or (case == 'failed_simd' and variant != 'clload' and sys.argv[-1].startswith('N:500kB:')):
    sys.exit(7)
if case == 'bad_number':
    print('MByte/s: nan')
elif variant == 'clload':
    print('MByte/s: 123456')
elif sys.argv[-1].startswith('N:24kB:'):
    print('MFlops/s: 45678')
else:
    print('MFlops/s: 987654')
''')
            program.chmod(0o755)
        env = dict(os.environ, PATH=str(directory))
        result = subprocess.run([perl, str(helper)], env=env, capture_output=True, text=True, timeout=15)
        (directory / 'stdout.log').write_text(result.stdout)
        (directory / 'stderr.log').write_text(result.stderr)
        if case in ('cpu', 'gpu', 'gpu_no_function'):
            assert result.returncode == 0, (case, result.stderr)
            data = json.loads(result.stdout)  # The entire stdout must be exactly JSON.
            assert data['topology']['node'] == list(range(8))
            assert all(isinstance(x, int) for x in data['topology']['node'])
            assert data['processorType'] == 'Fixture CPU "quoted"'
            for kind in ('socket', 'memoryDomain', 'core'):
                assert sorted(x for group in data['topology'][kind] for x in group) == list(range(8))
            assert [data[key]['value'] for key in ('flopRateScalar', 'flopRateSimd', 'memoryBandwidth')] == [46, 988, 123]
            if case in ('gpu', 'gpu_no_function'):
                assert data['topology']['accelerators'] == [{'id': '00000000:26:00.' + ('1' if case == 'gpu' else '0'), 'type': 'Nvidia GPU', 'model': 'Nvidia fixture "GPU"'}]
            else:
                assert 'accelerators' not in data['topology']
        else:
            assert result.returncode != 0, (case, 'failure reported as success')
            assert result.stdout == '', (case, 'partial configuration emitted')
            assert result.stderr.strip(), (case, 'missing explanation')
        outcomes.append({'case': case, 'exit': result.returncode, 'passed': True})
    (args.work / 'subcluster-results.json').write_text(json.dumps(outcomes, indent=2) + '\n')
    print(f'PASS: {len(outcomes)} CPU/GPU/child-failure/topology cases; logs: {work}')


if __name__ == '__main__':
    main()
