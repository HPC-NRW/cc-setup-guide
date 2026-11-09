#!/usr/bin/env python3
"""Check preference-key migration against disposable SQLite databases."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='userconfig-', dir=args.work.resolve()))
    helper = args.source.resolve() / 'docs/scripts/updateUserconfig.pl'
    mapping_path = helper.with_name('configmap_v11.json')
    mapping = json.loads(mapping_path.read_text())
    results = []

    def database(name, version=11, dirty=0):
        path = root / (name + '.db')
        with sqlite3.connect(path) as db:
            db.executescript('''
                CREATE TABLE schema_migrations (version INTEGER, dirty INTEGER);
                CREATE TABLE configuration (
                    username TEXT, confkey TEXT, value TEXT,
                    PRIMARY KEY (username, confkey));
                CREATE TABLE unrelated (value TEXT);
                INSERT INTO unrelated VALUES ('preserve this');
            ''')
            db.execute('INSERT INTO schema_migrations VALUES (?, ?)', (version, dirty))
        return path

    def rows(path):
        with sqlite3.connect(path) as db:
            return db.execute('SELECT username, confkey, value FROM configuration ORDER BY username, confkey').fetchall()

    def run(path, *options, success=True):
        proc = subprocess.run(['perl', str(helper), '--database', str(path), *options],
                              capture_output=True, text=True, timeout=15)
        assert (proc.returncode == 0) == success, proc.stdout + proc.stderr
        return proc

    db = database('all-keys')
    old, expected = [], []
    for item in mapping['confkeys']:
        for suffix in ('', ':demo', ':demo:cpu', ':demo:cpu:extra'):
            value = json.dumps({'text': "quotation ' and unicode ä", 'values': [1, 2]})
            old.append(("test'user", item['old'] + suffix, value))
            expected.append(("test'user", item['new'] + suffix, value))
    preserved = [('another-user', 'unmapped:demo:cpu', '[42]')]
    with sqlite3.connect(db) as conn:
        conn.executemany('INSERT INTO configuration VALUES (?, ?, ?)', old + preserved)
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    preview = run(db, '--mapping', str(mapping_path), '--dry-run')
    assert 'would rename 80' in preview.stdout
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    results.append('dry run preserves database bytes')
    applied = run(db)  # The default mapping is resolved beside the script.
    assert 'renamed 80' in applied.stdout
    assert rows(db) == sorted(expected + preserved)
    assert any(key == 'metricConfig_jobViewPlotMetrics:demo:cpu'
               for _, key, _ in rows(db))
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT value FROM unrelated').fetchone() == ('preserve this',)
    results.append('all 20 mappings preserve suffixes, values, quoted users and other tables')
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    assert 'renamed 0' in run(db).stdout
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    results.append('repeat run leaves migrated database unchanged')

    for name, version, dirty in [('old-schema', 8, 0), ('dirty-schema', 11, 1)]:
        path = database(name, version, dirty)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        run(path, success=False)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        results.append(name + ' refused before changes')

    collision = database('collision')
    before = [('test', 'job_view_selectedMetrics', '["cpu_load"]'),
              ('test', 'metricConfig_jobViewPlotMetrics', '["mem_used"]')]
    with sqlite3.connect(collision) as conn:
        conn.executemany('INSERT INTO configuration VALUES (?, ?, ?)', before)
    run(collision, success=False)
    assert rows(collision) == sorted(before)
    results.append('conflicting existing target preference preserved')

    rollback = database('rollback')
    before = [('test', 'job_view_selectedMetrics', '["cpu_load"]'),
              ('test', 'plot_list_selectedMetrics', '["mem_used"]')]
    with sqlite3.connect(rollback) as conn:
        conn.executemany('INSERT INTO configuration VALUES (?, ?, ?)', before)
        conn.execute('''CREATE TRIGGER reject_update BEFORE UPDATE ON configuration
                        WHEN OLD.confkey = 'plot_list_selectedMetrics'
                        BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END''')
    run(rollback, success=False)
    assert rows(rollback) == sorted(before)
    results.append('SQL failure rolls back every key change')
    absent = root / 'absent.db'
    run(absent, success=False)
    assert not absent.exists()
    results.append('missing database refused without creating a file')
    (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: user preference migration, preview, repeat run, schema checks, conflicts and rollback; evidence: ' + str(root))


if __name__ == '__main__':
    main()
