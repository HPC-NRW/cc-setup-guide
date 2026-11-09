#!/usr/bin/env python3
"""Fast stdlib-only installer contracts, no root/network/namespace required.

Example: python3 tests/installer_unit.py --source . --work /tmp/cc-installer-test
The working directory must be new; generated fixture keys are synthetic.
"""
import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--work', type=Path, required=True)
a = parser.parse_args()
a.source, a.work = a.source.resolve(), a.work.resolve()
assert not a.work.exists(), 'Use a new test directory.'
a.work.mkdir(parents=True, mode=0o700)
os.umask(0o077)
spec=importlib.util.spec_from_file_location('install_support',a.source/'scripts/install_support.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
results=[]

def check(name, function):
    function()
    results.append({'test':name,'pass':True})
    (a.work/'results.json').write_text(json.dumps(results,indent=2))
    print(name, 'PASS')


def rejected(function):
    try:function()
    except (support.InvalidInput,ValueError,KeyError,tarfile.TarError):return
    raise AssertionError('invalid fixture accepted')

item=support.release(a.source,'1.5.3')
url='https://github.com/ClusterCockpit/cc-backend/releases/download/'+item['tag']+'/'+item['asset']
response=a.work/'release.json'
valid={'tag_name':item['tag'],'assets':[{'name':item['asset'],'browser_download_url':url}]}
response.write_text(json.dumps(valid))
check('release-valid',lambda:support.release_url(a.source,'1.5.3',response))
for name,value in [('empty',''),('invalid','{x'),('duplicate','{"tag_name":"x","tag_name":"y"}'),('wrong-tag',json.dumps(dict(valid,tag_name='v99'))),('absent',json.dumps(dict(valid,assets=[]))),('multiple',json.dumps(dict(valid,assets=valid['assets']*2))),('foreign-url',json.dumps(dict(valid,assets=[dict(valid['assets'][0],browser_download_url='https://evil.invalid/a')])) )]:
    response.write_text(value)
    check('release-reject-'+name,lambda:rejected(lambda:support.release_url(a.source,'1.5.3',response)))

# All actual command dependencies are checked before any prerequisite/state writes.
required=['python3','curl','openssl','install','id','uname','chown','chmod','mkdir','rm','dirname','getent']
for missing in required:
    directory=a.work/('path-without-'+missing);directory.mkdir()
    for command in required:
        if command!=missing:
            source=shutil.which(command)
            assert source,command
            (directory/command).symlink_to(source)
    def missing_case():
        result=subprocess.run(['/bin/bash',str(a.source/'scripts/cc-installation.sh'),'-c','demo'],env=dict(os.environ,PATH=str(directory)),capture_output=True,text=True)
        assert result.returncode!=0 and 'Missing dependency: '+missing in result.stderr,(missing,result.stderr)
    check('missing-dependency-'+missing,missing_case)

# Archive layout check is independently tested AFTER digest verification, using a
# private synthetic manifest. This never weakens the production pinned manifest.
fixture=a.work/'fixture';shutil.copytree(a.source/'scripts',fixture/'scripts')
manifest=json.loads((a.source/'versions.json').read_text())
def archive_case(name,members,valid_layout=False):
    archive=a.work/(name+'.tar.gz')
    with tarfile.open(archive,'w:gz') as tar:
        for member in members:
            info=tarfile.TarInfo(member)
            if member.endswith('link'):
                info.type=tarfile.SYMTYPE;info.linkname='/tmp/outside';tar.addfile(info)
            else:
                info.size=1;tar.addfile(info,io.BytesIO(b'x'))
    manifest['backend']['releases']['1.5.3']['sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    (fixture/'versions.json').write_text(json.dumps(manifest))
    destination=a.work/('out-'+name);destination.mkdir()
    if valid_layout:
        support.extract(fixture,'1.5.3',archive,destination)
        assert sorted(p.name for p in destination.iterdir())==sorted(members)
    else:
        rejected(lambda:support.extract(fixture,'1.5.3',archive,destination))
        assert not list(destination.iterdir())
flat=['LICENSE','README.md','gen-keypair','archive-migration','archive-manager','cc-backend']
check('archive-flat',lambda:archive_case('flat',flat,True))
for name,members in [('nested',['directory/'+x for x in flat]),('traversal',flat[:-1]+['../cc-backend']),('symlink',flat[:-1]+['backend-link']),('duplicate',flat+[flat[0]]),('missing',flat[:-1])]:
    check('archive-reject-'+name,lambda n=name,m=members:archive_case(n,m))
bad=a.work/'bad.tar.gz';bad.write_bytes(b'bad')
check('archive-reject-hash',lambda:rejected(lambda:support.extract(a.source,'1.5.3',bad,a.work)))

def encoded(value):return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
raw=encoded({'alg':'EdDSA','typ':'JWT'})+'.'+encoded({'sub':'synthetic'})+'.'+base64.urlsafe_b64encode(b'fixture signature').decode().rstrip('=')
token_source=a.work/'token-output';token_dest=a.work/'apikey.txt'
token_source.write_text('CLI prefix: '+raw+'\ncompleted\n')
check('token-extract-one',lambda:support.token(token_source,token_dest))
assert token_dest.read_text()==raw+'\n'
for name,value in [('none','no token'),('two',raw+' '+raw),('bad-header','e30.e30.c2lnbmF0dXJl'),('list-header','W10.e30.c2lnbmF0dXJl')]:
    token_source.write_text(value)
    check('token-reject-'+name,lambda:rejected(lambda:support.token(token_source,a.work/'must-not-exist')))
# Syntax/placeholder validation is independent of allowed literal underscores.
check('render-supported-underscores',lambda:support.rendered(a.source,'/opt/a__b','a__b','cc_user','cc_group'))
check('shell-syntax',lambda:subprocess.run(['bash','-n',str(a.source/'scripts/cc-installation.sh')],check=True))
print('All',len(results),'fast installer checks passed; actual JWT authentication is in installer.py.')
