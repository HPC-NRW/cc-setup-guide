#!/usr/bin/env python3
"""Build pinned adapter and load actual guide config; no scheduler or host service."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--work', type=Path, required=True)
p.add_argument('--adapter-source', type=Path, required=True)
p.add_argument('--go', type=Path, required=True)
a = p.parse_args()
a.work = a.work.resolve()
if a.work.exists():
    p.error('--work must be NEW')
os.umask(0o077)
a.work.mkdir(parents=True)
copy = a.work / 'adapter'
shutil.copytree(a.adapter_source, copy)
expected = json.loads((a.source / 'versions.json').read_text())['adapter']['commit']
actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=copy, text=True).strip()
assert actual == expected
(copy / 'internal/config/guide_test.go').write_text('''package config
import("os";"testing")
func TestGuideConfig(t *testing.T) {
 Load(os.Getenv("GUIDE_ADAPTER_CONFIG"))
 if Config.SlurmMaxRetries != 5 {t.Fatalf("retry field not decoded: %d",Config.SlurmMaxRetries)}
 if Config.LastRunPath != "/var/lib/cc-slurm-adapter/last_run" {t.Fatal(Config.LastRunPath)}
 if Config.CcRestUrl != "https://cc.example.org" {t.Fatal(Config.CcRestUrl)}
}
''')
env = os.environ.copy()
env.update(GOTOOLCHAIN='local', GOCACHE=str(a.work/'go-build'), GOPATH=str(a.work/'go'),
           GOMODCACHE=str(a.work/'go/pkg/mod'), TMPDIR=str(a.work/'tmp'),
           GUIDE_ADAPTER_CONFIG=str((a.source/'docs/examples/slurm/adapter.json').resolve()))
Path(env['TMPDIR']).mkdir()
commands = [[a.go, 'version'], [a.go, 'build', './cmd/cc-slurm-adapter'], [a.go, 'vet', './...'],
            [a.go, 'test', './internal/config', '-run', 'TestGuideConfig', '-v'],
            [copy/'cc-slurm-adapter', '-debug', '5', '-help']]
for i, command in enumerate(commands):
    r = subprocess.run([str(x) for x in command], cwd=copy, env=env, text=True, capture_output=True)
    (a.work/('command-%d.log'%i)).write_text(r.stdout+r.stderr)
    assert r.returncode == 0, (command,r.stderr)
    if i == 4:
        assert '-debug' in r.stdout+r.stderr and '-daemon' in r.stdout+r.stderr
(a.work/'results.json').write_text(json.dumps({'commit':actual,'build_vet_config_cli':'PASS',
    'scheduler':'NOT_RUN','commands':[[str(x) for x in c] for c in commands]},indent=2))
print('PASS: pinned adapter build/vet, actual guide config, valid -debug CLI; no Slurm runtime.')
