#!/usr/bin/env python3
"""Real installer/manual regression in a prepared disposable Ubuntu rootfs.

Requires bwrap, existing subordinate IDs/newuidmap/newgidmap; never installs host
packages. Rootfs must contain Python3, curl, openssl, systemd and standard tools.
Downloads are replayed from explicitly supplied, unchanged release archives.
Run this file from a trusted checkout; --source selects the workingtree tested.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--work', type=Path, required=True)
p.add_argument('--rootfs', type=Path, required=True)
p.add_argument('--archive153', type=Path, required=True)
p.add_argument('--archive154', type=Path, required=True)
p.add_argument('--old-snapshot', action='store_true', help='Run the same acceptance checks on the old source; nonzero is expected.')
a = p.parse_args()
a.source, a.work, a.rootfs = [x.resolve() for x in (a.source, a.work, a.rootfs)]
assert a.work != a.source and a.rootfs != a.source and a.work not in a.source.parents
assert not a.work.exists(), 'Choose a new work directory to preserve earlier evidence.'
a.work.mkdir(parents=True, mode=0o700)
os.umask(0o077)
records = []
# Only explicit copies into the supplied disposable rootfs; no old audit writes.
assert (a.rootfs/'usr/bin/python3').exists() and (a.rootfs/'etc/os-release').exists()
for name in ('guide', 'bin', 'downloads', 'results'):
    (a.rootfs/'audit'/name).mkdir(parents=True, exist_ok=True)
guide = a.rootfs/'audit/guide'
for name in ('scripts', 'docs'):
    shutil.copytree(a.source/name, guide/name, dirs_exist_ok=True)
if (a.source/'versions.json').exists():
    shutil.copy2(a.source/'versions.json', guide/'versions.json')
for tag, archive in [('1.5.3', a.archive153), ('1.5.4', a.archive154)]:
    shutil.copy2(archive, a.rootfs/f'audit/downloads/backend-{tag}.tar.gz')
wrapper = a.rootfs/'audit/bin/curl'
wrapper.write_text('''#!/usr/bin/python3
import json,os,re,sys,time
from pathlib import Path
args=sys.argv[1:]
url=args[-1]
version='1.5.4' if '1.5.4' in url else '1.5.3'
asset='cc-backend_Linux_x86_64.tar.gz'
mode=os.environ.get('FIX_DOWNLOAD_MODE','valid')
with open('/audit/results/download-calls','a') as log: log.write('call\\n')
if '/releases/tags/' in url or '/releases/latest' in url:
 data={'tag_name':'v'+version,'assets':[{'name':asset,'browser_download_url':'https://github.com/ClusterCockpit/cc-backend/releases/download/v'+version+'/'+asset}]}
 if mode=='invalid-json': print('{bad');sys.exit(0)
 if mode=='empty': sys.exit(0)
 if mode=='no-asset': data['assets']=[]
 if mode=='ambiguous': data['assets']*=2
 if mode=='wrong-url': data['assets'][0]['browser_download_url']='https://untrusted.invalid/file'
 print(json.dumps(data));sys.exit(0)
if mode=='abort': sys.exit(22)
if mode=='slow': time.sleep(30)
if mode=='bad-archive': sys.stdout.buffer.write(b'bad archive');sys.exit(0)
sys.stdout.buffer.write(Path('/audit/downloads/backend-'+version+'.tar.gz').read_bytes())
''')
wrapper.chmod(0o755)
# Only for old source comparison: original installer uses wget after curl.
wget = a.rootfs/'audit/bin/wget'
wget.write_text('#!/bin/sh\ncp /audit/downloads/backend-1.5.3.tar.gz cc-backend.tar.gz\n');wget.chmod(0o755)

def run(name, script, expected=0):
    command=[sys.executable,str(Path(__file__).with_name('installer_namespace.py')),'bwrap',
             '--unshare-pid','--unshare-uts','--unshare-ipc','--unshare-net','--die-with-parent','--new-session',
             '--bind',str(a.rootfs),'/', '--proc','/proc','--dev','/dev','--clearenv',
             '--setenv','PATH','/audit/bin:/usr/sbin:/usr/bin:/sbin:/bin', '--setenv','HOME','/root',
             '--chdir','/audit/guide','/bin/bash','-c',script]
    result=subprocess.run(command,capture_output=True,text=True,timeout=150)
    # Backend stdout is private in this test, but defensively scrub JWT/base64 env.
    output=result.stdout+result.stderr
    output=re.sub(r'[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', '[REDACTED_JWT]',output)
    output=re.sub(r'(?m)^((?:JWT_PRIVATE_KEY|SESSION_KEY)=).*$',r'\1[REDACTED]',output)
    (a.work/(name+'.log')).write_text(output)
    ok=result.returncode==expected if isinstance(expected,int) else result.returncode!=0
    records.append({'test':name,'command':script,'exit':result.returncode,'expected_exit':expected,'pass':ok})
    (a.work/'results.json').write_text(json.dumps(records,indent=2))
    print(name, 'PASS' if ok else 'FAIL', result.returncode, flush=True)
    assert ok, name+'; see '+str(a.work/(name+'.log'))

run('accounts', '''set -e
getent passwd clustercockpit >/dev/null || useradd --system --no-create-home --user-group --shell /usr/sbin/nologin clustercockpit
getent passwd auditreader >/dev/null || useradd --no-create-home --user-group auditreader
getent group ccaltgroup >/dev/null || groupadd --system ccaltgroup
getent passwd ccalternative >/dev/null || useradd --system --no-create-home --gid ccaltgroup ccalternative
''')
for version, target in [('1.5.3','/opt/fix153'),('1.5.4','/srv/fix154')]:
    user='clustercockpit' if version=='1.5.3' else 'ccalternative'
    args='' if a.old_snapshot else ' -v '+version+(' -u ccalternative:ccaltgroup' if version=='1.5.4' else '')
    run('install-'+version, f'umask 022; bash scripts/cc-installation.sh -c demo_cluster -d {target}'+args)
    # Same success criteria for old snapshot and new working tree.
    run('access-'+version, f'''set -e
for secret in .env admin_password.txt apiuser_password.txt apikey.txt; do
 if runuser -u auditreader -- test -r {target}/cc-backend/$secret; then echo 'FAIL foreign user can read a secret'; exit 1; fi
done
runuser -u {user} -- test -r {target}/cc-backend/.env
runuser -u {user} -- test -r {target}/cc-backend/ui-config.json
runuser -u {user} -- test -w {target}/cc-backend/var/job.db
runuser -u {user} -- test -w {target}/cc-backend/var/job-archive
systemd-analyze verify {target}/clustercockpit.service
''')

# Install helper only into the isolated fixture, never into the source under test.
state = r'''import hashlib,json,pathlib,sqlite3,sys
root=pathlib.Path(sys.argv[2]); dest=pathlib.Path('/audit/results/state.json')
if sys.argv[1]=='before':
 db=sqlite3.connect(root/'cc-backend/var/job.db')
 db.execute('CREATE TABLE regression_sentinel(value TEXT)')
 db.execute("INSERT INTO regression_sentinel VALUES ('preserve-me')");db.commit();db.close()
 paths={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
 dest.write_text(json.dumps(paths))
else:
 paths={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
 assert paths==json.loads(dest.read_text()),'rerun mutated installation'
 db=sqlite3.connect('file:'+str(root/'cc-backend/var/job.db')+'?mode=ro',uri=True)
 assert db.execute('select value from regression_sentinel').fetchall()==[('preserve-me',)]
 assert {x[0] for x in db.execute('select username from hpc_user')}=={'admin','apiuser'}
print('State and users preserved')
'''
(guide/'tests_state.py').write_text(state)
for version,target in [('1.5.3','/opt/fix153'),('1.5.4','/srv/fix154')]:
    run('rerun-'+version,f'''set -e
python3 /audit/guide/tests_state.py before {target}
before=$(wc -l < /audit/results/download-calls)
if bash scripts/cc-installation.sh -c demo_cluster -d {target} -v {version}; then exit 1; fi
[ "$(wc -l < /audit/results/download-calls)" = "$before" ]
python3 /audit/guide/tests_state.py after {target}
''')

# Execute the actual documentation blocks, retaining source, template and command paths.
docs=[]
for lang in ('de','en'):
    text=(a.source/f'docs/monitoringserver.{lang}.md').read_text()
    docs.append(re.findall(r'<!-- installer-manual-\d+ -->\n```bash\n(.*?)\n```',text,re.S))
assert len(docs[0])==6 and docs[0]==docs[1], 'Manual DE/EN commands differ or missing'
manual='\n'.join(docs[0]).replace('INSTALL_DIR=/opt/monitoring','INSTALL_DIR=/opt/manual-default')
run('manual-documented-sequence',manual)
run('manual-access', '''set -e
! runuser -u auditreader -- test -r /opt/manual-default/cc-backend/.env
! runuser -u auditreader -- test -r /opt/manual-default/cc-backend/apikey.txt
runuser -u clustercockpit -- test -w /opt/manual-default/cc-backend/var/job.db
runuser -u clustercockpit -- test -r /opt/manual-default/cc-backend/ui-config.json
''')

# Real authenticated API use, under the service account. Only listener address is
# changed to a dynamic loopback port; no config repair or token extraction here.
api=r'''import base64,json,os,pathlib,re,socket,subprocess,sys,time,urllib.request,urllib.error
root=pathlib.Path(sys.argv[1]);os.chdir(root)
user=sys.argv[2] if len(sys.argv)>2 else 'clustercockpit'
p=root/'config.json'; original_config=p.read_bytes(); config=json.loads(original_config)
assert config['ui-file']=='ui-config.json'
assert json.loads((root/config['ui-file']).read_text())==json.loads(pathlib.Path('/audit/guide/docs/examples/minimal/cc-backend/ui-config.json').read_text())
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
config['main']['addr']='127.0.0.1:'+str(port);p.write_text(json.dumps(config))
token=(root/'apikey.txt').read_text().strip()
assert re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',token)
part=token.split('.')[1];claims=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
assert time.time()+364*86400 < claims['exp'] < time.time()+365*86400+60
log=open('/audit/results/server-'+root.parent.name+'.log','w')
proc=subprocess.Popen(['runuser','-u',user,'--','./cc-backend','-server'],stdout=log,stderr=log)
try:
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  try:
   response=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/jobs/',headers={'Authorization':'Bearer '+token}),timeout=2)
   assert response.status==200
   data=json.loads(response.read());assert isinstance(data,(dict,list));break
  except urllib.error.URLError:time.sleep(.1)
 else:raise AssertionError('API not ready/authenticated')
 try:
  urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/jobs/',headers={'Authorization':'Bearer invalid'}),timeout=2)
  raise AssertionError('invalid token accepted')
 except urllib.error.HTTPError as error:assert error.code==401
 print('Raw JWT accepted, invalid JWT rejected; service user starts and reads DB.')
finally:
 proc.terminate()
 try:proc.wait(timeout=15)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log.close()
 p.write_bytes(original_config)
'''
(guide/'tests_api.py').write_text(api)
for target in ('/opt/fix153','/srv/fix154','/opt/manual-default'):
    run('api-'+target.split('/')[-1],f'python3 /audit/guide/tests_api.py {target}/cc-backend'+(' ccalternative' if '154' in target else ''))

# Invalid input must not even call the replay download tool or create a target.
negative=r'''set -e
before=$(wc -l < /audit/results/download-calls)
for cluster in '' '../bad' 'a/b' 'a&b' 'a@b' 'a b' 'a%b' 'a"b' 'a\b' $'a\nb'; do
 if bash scripts/cc-installation.sh -c "$cluster" -d /opt/negative; then exit 1; fi
 test ! -e /opt/negative
done
for path in relative / /opt /opt/../negative /opt/a\ b /opt/a%b /opt/a@b /opt/a\&b /opt/a\\b /opt/a\"b /opt//negative; do
 if bash scripts/cc-installation.sh -c demo_cluster -d "$path"; then exit 1; fi
done
[ "$(wc -l < /audit/results/download-calls)" = "$before" ]
for account in root:root no_such_user 'clustercockpit:clustercockpit:extra' 'clustercockpit:'; do
 if bash scripts/cc-installation.sh -c demo_cluster -d /opt/negative -u "$account"; then exit 1; fi
done
mkdir /opt/partial
printf sentinel > /opt/partial/sentinel
if bash scripts/cc-installation.sh -c demo_cluster -d /opt/partial; then exit 1; fi
[ "$(cat /opt/partial/sentinel)" = sentinel ]
ln -s /srv /opt/link
if bash scripts/cc-installation.sh -c demo_cluster -d /opt/link/negative; then exit 1; fi
test ! -e /srv/negative
'''
run('invalid-input-and-partial',negative)
for template in ['scripts/templates/cc-backend.json.template',
                 'scripts/templates/cluster.json.template',
                 'scripts/templates/clustercockpit.service.template',
                 'docs/examples/minimal/cc-backend/ui-config.json']:
    for kind in ('missing','corrupt'):
        run('template-'+kind+'-'+Path(template).name,f'''set -e
cp {template} /audit/template-save
trap 'cp /audit/template-save {template}' EXIT
{'rm '+template if kind=='missing' else 'printf garbage > '+template}
before=$(wc -l < /audit/results/download-calls)
if bash scripts/cc-installation.sh -c demo_cluster -d /opt/template-negative; then exit 1; fi
test ! -e /opt/template-negative
[ "$(wc -l < /audit/results/download-calls)" = "$before" ]
''')
for mode in ['empty','invalid-json','no-asset','ambiguous','wrong-url','bad-archive','abort']:
    run('download-'+mode,f'''set -e
if FIX_DOWNLOAD_MODE={mode} bash scripts/cc-installation.sh -c demo_cluster -d /opt/download-{mode}; then exit 1; fi
test ! -e /opt/download-{mode}/cc-backend/.env
before=$(wc -l < /audit/results/download-calls)
if bash scripts/cc-installation.sh -c demo_cluster -d /opt/download-{mode}; then exit 1; fi
[ "$(wc -l < /audit/results/download-calls)" = "$before" ]
''')
run('interrupted-installation', '''set -e
set +e
timeout --signal=TERM --kill-after=2 1 env FIX_DOWNLOAD_MODE=slow bash scripts/cc-installation.sh -c demo_cluster -d /opt/interrupted
status=$?
set -e
[ "$status" != 0 ]
test -d /opt/interrupted
test ! -e /opt/interrupted/cc-backend/.env
before=$(wc -l < /audit/results/download-calls)
if bash scripts/cc-installation.sh -c demo_cluster -d /opt/interrupted; then exit 1; fi
[ "$(wc -l < /audit/results/download-calls)" = "$before" ]
''')
run('install-default', 'umask 022; bash scripts/cc-installation.sh -c demo_cluster')
default_version=json.loads((a.source/'versions.json').read_text())['backend']['default']
run('version-defaults', f'''set -e
for target in /opt/monitoring /opt/manual-default; do
 "$target/cc-backend/cc-backend" -version | grep -Eq '^Version:[[:space:]]+{re.escape(default_version)}$'
done
''')
run('api-default', 'python3 /audit/guide/tests_api.py /opt/monitoring/cc-backend')
run('export-fixtures', '''set -e
mkdir -m 0700 /audit/fixture-export
cp -a /opt/fix153/cc-backend /audit/fixture-export/backend153
cp -a /srv/fix154/cc-backend /audit/fixture-export/backend154
chown -R 0:0 /audit/fixture-export
''')
# PRIVATE generated credentials/state: keep the work tree outside the repository
# and never publish export/ with shareable logs. Copies contain no hardlinks.
shutil.copytree(a.rootfs/'audit/fixture-export',a.work/'export')
for name in ('backend153','backend154'):
    (a.work/'export'/name/'.guide-test-fixture').write_text('Synthetic installer regression fixture; never use production data.\n')
print('All installer regression assertions passed. PRIVATE work tree:',a.work)
