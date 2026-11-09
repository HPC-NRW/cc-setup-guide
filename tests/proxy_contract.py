#!/usr/bin/env python3
"""Real nginx/backend checks for both documented method policies.

Requires installer_namespace.py, bwrap and an existing subordinate UID mapping.
--rootfs must be an independent disposable rootfs with nginx/OpenSSL/Python
installed and no services running. --backend-instance must be synthetic and
contain the API user selected by --api-user. Inputs are copied, never modified.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def documented_policies(source):
    """Read the shared include and apply each language's actual opt-in line."""
    policies = []
    for language in ['de', 'en']:
        document = (source / ('docs/https_setup.%s.md' % language)).read_text()
        blocks = re.findall(r'```nginx\n(.*?)\n```', document, re.S)
        includes = [re.fullmatch(r'--8<-- "([^"]+)"', block.strip()) for block in blocks]
        includes = [match for match in includes if match]
        if len(includes) != 1:
            raise AssertionError('Expected one shared nginx include: ' + language)
        path = (source / 'docs' / includes[0][1]).resolve()
        if not path.is_relative_to((source / 'docs').resolve()):
            raise AssertionError('nginx include must be inside docs')
        base = path.read_text()
        method_line = r'limit_except ([A-Z ]+) \{'
        base_matches = re.findall(method_line, base)
        if len(base_matches) != 1 or set(base_matches[0].split()) != {'GET', 'POST', 'HEAD'}:
            raise AssertionError('Shared nginx policy must allow GET/POST/HEAD')
        extensions = [block for block in blocks if re.search(method_line, block)]
        if len(extensions) != 1:
            raise AssertionError('Expected one opt-in nginx policy: ' + language)
        extended_methods = re.search(method_line, extensions[0])[1]
        if set(extended_methods.split()) != {'GET', 'POST', 'HEAD', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'}:
            raise AssertionError('Unexpected opt-in methods: ' + language)
        extended, count = re.subn(method_line, 'limit_except ' + extended_methods + ' {', base)
        assert count == 1
        policies.extend([(language, 'restricted', base), (language, 'extended', extended)])
    if policies[0][2] != policies[2][2] or policies[1][2] != policies[3][2]:
        raise AssertionError('DE and EN proxy configurations differ')
    return policies


INNER = r'''
import json,pathlib,re,subprocess,time,urllib.request,urllib.error,ssl
root=pathlib.Path('/operations');directory=root/'backend';binary=root/'cc-backend'
config=json.loads((directory/'config.json').read_text())
config['main']['addr']='127.0.0.1:8443'
for key in ('https-cert-file','https-key-file','redirect-http-to'):
 config['main'].pop(key,None)
(directory/'config.json').write_text(json.dumps(config))
api_user=(root/'api-user').read_text().strip()
issued=subprocess.run([str(binary),'-jwt',api_user],cwd=directory,text=True,capture_output=True,check=True)
match=re.search(r'eyJ[\w-]+\.[\w-]+\.[\w-]+',issued.stdout+issued.stderr)
if match is None:raise RuntimeError('No synthetic API token issued')
token=match[0]
subprocess.run(['openssl','req','-x509','-nodes','-newkey','rsa:2048','-days','1','-subj','/CN=localhost','-keyout','/etc/ssl/proxy-test.key','-out','/etc/ssl/proxy-test.crt'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

opener=urllib.request.build_opener(NoRedirect,urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
results=[]
def request(base,method,path,auth=True):
 headers={'Content-Type':'application/json'}
 if auth:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(base+path,method=method,headers=headers,data=b'{}' if method in ('POST','PUT','PATCH') else None)
 try:
  with opener.open(req,timeout=3) as response:return response.status,dict(response.headers.items())
 except urllib.error.HTTPError as err:return err.code,dict(err.headers.items())

def record(language,policy,test,condition,**details):
 results.append(dict(language=language,policy=policy,test=test,pass_=bool(condition),**details))
 (root/'results.json').write_text(json.dumps(results,indent=2))

stream=(root/'backend.log').open('w')
backend=subprocess.Popen([str(binary),'-server'],cwd=directory,stdout=stream,stderr=subprocess.STDOUT)
try:
 for _ in range(80):
  if backend.poll() is not None:raise RuntimeError('Backend exited')
  try:
   if request('http://127.0.0.1:8443','GET','/api/jobs/')[0]==200:break
  except urllib.error.URLError:pass
  time.sleep(.1)
 else:raise RuntimeError('Backend not ready')
 for fixture in json.loads((root/'configurations.json').read_text()):
  language,policy=fixture['language'],fixture['policy']
  conf=root/fixture['file']
  subprocess.run(['nginx','-t','-c',str(conf)],check=True)
  nginx=subprocess.Popen(['nginx','-c',str(conf),'-g','daemon off;'])
  try:
   for _ in range(50):
    if nginx.poll() is not None:raise RuntimeError('nginx exited')
    try:
     if request('https://127.0.0.1','GET','/api/jobs/')[0]==200:break
    except urllib.error.URLError:pass
    time.sleep(.1)
   else:raise RuntimeError('nginx not ready')
   cases=[('GET','/api/jobs/'),('POST','/api/jobs/start_job/'),('HEAD','/api/jobs/'),('PUT','/api/jobs/start_job/'),('PATCH','/api/jobs/edit_meta/99999999'),('DELETE','/api/jobs/delete_job/99999999'),('OPTIONS','/api/jobs/')]
   for method,path in cases:
    direct=request('http://127.0.0.1:8443',method,path)[0]
    proxied=request('https://127.0.0.1',method,path)[0]
    forwarded=policy=='extended' or method in ('GET','POST','HEAD')
    expected=direct if forwarded else 403
    record(language,policy,method,proxied==expected and (not forwarded or direct!=403),direct=direct,proxy=proxied,expected=expected)
   unauth=request('https://127.0.0.1','GET','/api/jobs/',False)
   record(language,policy,'unauthenticated',unauth[0]==401,status=unauth[0])
   trace=request('https://127.0.0.1','TRACE','/api/jobs/')[0]
   record(language,policy,'TRACE denied',trace in (403,405),status=trace)
   header_cases=[('authenticated',request('https://127.0.0.1','GET','/api/jobs/')),('unauthenticated',unauth),('denied',request('https://127.0.0.1','TRACE','/api/jobs/'))]
   expected_headers={'strict-transport-security':'max-age=31536000','x-content-type-options':'nosniff','referrer-policy':'strict-origin-when-cross-origin','x-frame-options':'DENY'}
   for label,(status,headers) in header_cases:
    headers={key.lower():value for key,value in headers.items()}
    record(language,policy,'security headers '+label,all(headers.get(key)==value for key,value in expected_headers.items()),status=status)
    record(language,policy,'server version hidden '+label,headers.get('server')=='nginx',status=status)
   status,headers=request('http://127.0.0.1','GET','/api/jobs/?cluster=auditcluster',False)
   headers={key.lower():value for key,value in headers.items()}
   record(language,policy,'HTTP redirects to HTTPS',status==301 and headers.get('location')=='https://127.0.0.1/api/jobs/?cluster=auditcluster',status=status)
  finally:
   nginx.terminate()
   try:nginx.wait(timeout=5)
   except subprocess.TimeoutExpired:nginx.kill();nginx.wait()
finally:
 backend.terminate()
 try:backend.wait(timeout=10)
 except subprocess.TimeoutExpired:backend.kill();backend.wait()
 stream.close()
assert all(item['pass_'] for item in results),[item for item in results if not item['pass_']]
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--backend-instance', type=Path, required=True)
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--api-user', default='auditapi')
    args = parser.parse_args()
    args.source, args.work, args.rootfs = [path.resolve() for path in (args.source, args.work, args.rootfs)]
    if args.work.exists():
        parser.error('--work must be new')
    policies = documented_policies(args.source)
    os.umask(0o077)
    args.work.mkdir(parents=True)
    namespace = args.source / 'tests/installer_namespace.py'
    base = [sys.executable, str(namespace)]
    operations = args.rootfs / 'operations'
    subprocess.run(base + ['mkdir', '-m', '0700', str(operations)], check=True)
    subprocess.run(base + ['cp', '-a', str(args.backend_instance.resolve()), str(operations / 'backend')], check=True)
    subprocess.run(base + ['cp', str(args.backend.resolve()), str(operations / 'cc-backend')], check=True)
    configurations = []
    for language, policy, block in policies:
        block = block.replace('__FQDN__', 'localhost').replace('__PEM_FILE__', 'proxy-test.crt').replace('__KEY_FILE__', 'proxy-test.key')
        config = ('pid /operations/nginx.pid;\nerror_log /operations/nginx-error.log;\n'
                  'events {}\nhttp { access_log /operations/nginx-access.log;\n' + block + '\n}\n')
        filename = 'nginx-%s-%s.conf' % (language, policy)
        (operations / filename).write_text(config)
        configurations.append({'language': language, 'policy': policy, 'file': filename})
    (operations / 'configurations.json').write_text(json.dumps(configurations))
    (operations / 'api-user').write_text(args.api_user)
    (operations / 'test.py').write_text(INNER)
    command = base + ['bwrap', '--unshare-pid', '--unshare-uts', '--unshare-ipc', '--unshare-net',
                      '--die-with-parent', '--new-session', '--bind', str(args.rootfs), '/',
                      '--proc', '/proc', '--dev', '/dev', '--clearenv', '--setenv', 'PATH',
                      '/usr/sbin:/usr/bin:/sbin:/bin', '--setenv', 'HOME', '/root',
                      '--chdir', '/operations', 'python3', 'test.py']
    run = subprocess.run(command, text=True, capture_output=True, timeout=120)
    output = re.sub(r'eyJ[\w-]+\.[\w-]+\.[\w-]+', '[JWT REDACTED]', run.stdout + run.stderr)
    (args.work / 'proxy.log').write_text(output)
    for name in ['results.json', 'nginx-error.log', 'nginx-access.log']:
        if (operations / name).exists():
            subprocess.run(base + ['cp', str(operations / name), str(args.work / name)], check=True)
    if run.returncode:
        raise RuntimeError('Proxy regression failed; see ' + str(args.work / 'proxy.log'))
    print((args.work / 'results.json').read_text())


if __name__ == '__main__':
    main()
