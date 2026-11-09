#!/usr/bin/env python3
"""Record/compare offline 1.4.4 -> 1.5.3 job and metric invariants."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3


def snapshot(database, archive):
    with sqlite3.connect('file:%s?mode=ro' % database, uri=True) as db:
        if db.execute('pragma integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')
        versions = db.execute('select version,dirty from schema_migrations').fetchall()
        if len(versions) != 1 or versions[0][1]:
            raise ValueError('Missing/dirty database migration state')
        jobs = db.execute('select job_id,cluster,hpc_user,project,start_time,duration,resources '
                          'from job order by job_id,cluster,start_time').fetchall()
    result = {'db_version': versions[0][0],
              'archive_version': int((archive / 'version.txt').read_text()),
              'jobs': jobs, 'meta': {}, 'data_sha256': {}}
    for path in sorted(archive.rglob('meta.json')):
        obj = json.loads(path.read_text())
        # Explicitly compare retained identity/resource fields, not fields removed
        # by the documented upstream migration (e.g. legacy footprint summaries).
        row = {key: obj.get(key) for key in ('jobId', 'cluster', 'subCluster', 'user',
                'project', 'jobState', 'partition', 'startTime', 'duration',
                'walltime', 'numNodes', 'numHwthreads', 'numAcc', 'resources')}
        if 'exclusive' in obj:
            row['shared'] = {0: 'multi_user', 1: 'none', 2: 'single_user'}[obj['exclusive']]
        else:
            row['shared'] = obj['shared']
        result['meta'][str(path.relative_to(archive))] = row
    for path in sorted(archive.rglob('data.json')):
        result['data_sha256'][str(path.relative_to(archive))] = hashlib.sha256(path.read_bytes()).hexdigest()
    # JSON canonicalization also converts SQLite resource BLOBs to text.
    return json.loads(json.dumps(result, default=lambda v: v.decode() if isinstance(v, bytes) else str(v)))


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['snapshot', 'verify'])
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--record', type=Path, required=True)
    p.add_argument('--db-version', type=int, required=True)
    p.add_argument('--archive-version', type=int, required=True)
    args = p.parse_args()
    try:
        actual = snapshot(args.database, args.archive)
        if actual['db_version'] != args.db_version or actual['archive_version'] != args.archive_version:
            raise ValueError('Unexpected database/archive version')
        if args.action == 'snapshot':
            with args.record.open('x') as f:
                json.dump(actual, f, indent=2)
        else:
            expected = json.loads(args.record.read_text())
            for key in ('jobs', 'meta', 'data_sha256'):
                if actual[key] != expected[key]:
                    raise ValueError('Migration invariant differs: %s' % key)
        print('Verified %d database jobs, %d archive metadata files, %d metric files; DB%d/archive%d' %
              (len(actual['jobs']), len(actual['meta']), len(actual['data_sha256']),
               actual['db_version'], actual['archive_version']))
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        p.exit(1, 'Migration check failed: %s\n' % exc)


if __name__ == '__main__':
    main()
