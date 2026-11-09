#!/usr/bin/env python3
"""Real pinned collector memstat -> current RUB router, using fake /proc/meminfo.

Requires Linux bubblewrap with user/mount/PID/UTS/network namespaces, Python3 and
an independently built collector v0.8.4. No hardware counters or privileged host
operations. --source is read-only; --work must be a new private directory.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--collector',type=Path,required=True)
    args=parser.parse_args()
    source,work,collector=args.source.resolve(),args.work.resolve(),args.collector.resolve()
    assert not work.exists(), 'Use a new private work directory.'
    assert collector.is_file(), 'Pass the independently built pinned collector.'
    os.umask(0o077)
    work.mkdir(parents=True,mode=0o700)
    router=source/'docs/examples/rub/cc-metric-collector/router.json'
    shutil.copyfile(router,work/'router.json')
    # Deliberately isolated memstat configuration: only this actual collector runs.
    for name,value in {
        'config.json':{'main':{'interval':'1s','duration':'100ms'},'collectors-file':'./collectors.json','router-file':'./router.json','sinks-file':'./sinks.json','receivers-file':'./receivers.json'},
        'collectors.json':{'memstat':{'node_stats':True,'numa_stats':False}},
        'sinks.json':{'stdout':{'type':'stdout','meta_as_tags':['unit']}},
        'receivers.json':{}
    }.items():
        (work/name).write_text(json.dumps(value,indent=2)+'\n')
    fixture='''MemTotal:        2097152 kB
MemFree:         1048576 kB
MemAvailable:    1048576 kB
Buffers:              0 kB
Cached:               0 kB
Shmem:                0 kB
SwapTotal:            0 kB
SwapFree:             0 kB
SReclaimable:         0 kB
Slab:                 0 kB
'''
    (work/'meminfo').write_text(fixture)
    command=['bwrap','--unshare-user','--unshare-pid','--unshare-uts','--unshare-ipc','--unshare-net',
        '--hostname','memstat-fixture','--die-with-parent','--new-session',
        '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',
        '--symlink','usr/lib64','/lib64','--symlink','usr/lib','/lib',
        '--proc','/proc','--ro-bind',str(work/'meminfo'),'/proc/meminfo',
        '--dir','/sys','--dev','/dev','--tmpfs','/tmp',
        '--bind',str(work),'/work','--ro-bind',str(collector),'/collector',
        '--chdir','/work','/collector','-config','config.json','-once']
    result=subprocess.run(command,capture_output=True,text=True,timeout=20,
                          env={**os.environ,'GOMAXPROCS':'2'})
    (work/'collector.stdout').write_text(result.stdout)
    (work/'collector.stderr').write_text(result.stderr)
    matches=re.findall(r'mem_used,([^\s]+) value=([-+0-9.eE]+) (\d+)',result.stdout)
    parsed=[]
    for tags,value,timestamp in matches:
        parsed.append({'tags':dict(x.split('=',1) for x in tags.split(',')),
                       'value':value,'timestamp_ns':int(timestamp)})
    success=result.returncode==0 and len(parsed)==1
    success=success and parsed[0]['tags'].get('unit')=='GB' and Decimal(parsed[0]['value'])==Decimal('1.073741824')
    record={'pass':bool(success),'command':command,'exit':result.returncode,
        'collector_expected_version':'v0.8.4','collector_sha256':hashlib.sha256(collector.read_bytes()).hexdigest(),
        'router_sha256':hashlib.sha256(router.read_bytes()).hexdigest(),
        'fixture_memtotal_kb':2097152,'fixture_memfree_kb':1048576,
        'linux_reported_mem_used_kb':1048576,'physical_unit':'KiB',
        'expected_gb':'1.073741824','observed':parsed,
        'scope':'Actual memstat code, fake read-only /proc/meminfo, unchanged current RUB router; no hardware/NUMA measurement.'}
    (work/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    assert success, 'Wrong memstat value/unit or collector failure; inspect '+str(work/'results.json')
    print('PASS: real memstat 1048576 Linux kB -> router KiB -> exactly 1.073741824 GB.')


if __name__=='__main__':main()
