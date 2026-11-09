#!/usr/bin/env python3
"""Real backend1.5.3 energy/footprint contract from current DE/EN documentation.

Only a private installer test export is accepted. Uses two artificial nodes with
2 synthetic GPUs each: 1500W/GPU -> 3000W/node, 60s -> 0.10kWh total. No physical
power/collector measurement. Test adaptations are topology, 2s samples, loopback,
1s commit worker and 1GiB memory cap. No installer/config repair is performed.
"""
import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--installation',type=Path,required=True)
    args=parser.parse_args()
    source,work=args.source.resolve(),args.work.resolve()
    assert not work.exists(), 'Choose a new private work directory.'
    assert (args.installation/'.guide-test-fixture').is_file(), 'Only generated installer fixtures are accepted.'
    os.umask(0o077)
    work.mkdir(parents=True,mode=0o700)
    instance=work/'instance';shutil.copytree(args.installation,instance)
    evidence=work/'evidence';evidence.mkdir()
    documented=[]
    for language in ('de','en'):
        text=(source/f'docs/metric_receive_display.{language}.md').read_text()
        candidates=[]
        for block in re.findall(r'```json\n(.*?)\n```',text,re.S):
            try:value=json.loads(block)
            except json.JSONDecodeError:continue
            if isinstance(value,dict) and value.get('name')=='acc_power' and 'energy' in value:
                candidates.append(value)
        assert len(candidates)==1, 'Missing/ambiguous documented energy example.'
        documented.append(candidates[0])
    assert documented[0]==documented[1], 'DE/EN energy examples differ.'
    metric=copy.deepcopy(documented[0])
    assert metric['unit']=={'base':'W'} and metric['scope']=='accelerator'
    assert metric['aggregation']=='sum' and metric['footprint']=='avg' and metric['energy']=='power'
    metric['timestep']=2
    config_path=instance/'config.json';config=json.loads(config_path.read_text())
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    config['main']['addr']='127.0.0.1:'+str(port)
    config['cron']['commit-job-worker']='1s'
    config['metric-store']['memory-cap']=1
    config_path.write_text(json.dumps(config))
    cluster_path=instance/'var/job-archive/demo_cluster/cluster.json'
    cluster=json.loads(cluster_path.read_text())
    cluster['metricConfig'].append(metric)
    sub=cluster['subClusters'][0];sub['nodes']='node[001-002]'
    sub['topology']['accelerators']=[{'id':'gpu0','type':'test','model':'synthetic'}, {'id':'gpu1','type':'test','model':'synthetic'}]
    cluster_path.write_text(json.dumps(cluster))
    token=(instance/'apikey.txt').read_text().strip()
    version=subprocess.run([str(instance/'cc-backend'),'-version'],cwd=instance,capture_output=True,text=True,check=True)
    assert '1.5.3' in version.stdout+version.stderr, 'This regression is pinned to backend1.5.3.'
    base='http://127.0.0.1:'+str(port)
    def request(path,body=None):
        payload=None if body is None else body.encode() if isinstance(body,str) else json.dumps(body).encode()
        req=urllib.request.Request(base+path,data=payload,headers={'X-Auth-Token':token,'Content-Type':'text/plain' if isinstance(body,str) else 'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=4) as response:code,raw=response.status,response.read()
        except urllib.error.HTTPError as error:code,raw=error.code,error.read()
        try:return code,json.loads(raw)
        except json.JSONDecodeError:return code,raw.decode()
    log=(evidence/'backend.log').open('w')
    process=subprocess.Popen([str(instance/'cc-backend'),'-server'],cwd=instance,stdout=log,stderr=log,env={**os.environ,'GOMAXPROCS':'4'})
    result={'backend':'1.5.3','scope':'synthetic component test, no hardware','documented_metric':documented[0]}
    try:
        for _ in range(100):
            assert process.poll() is None, 'Backend exited; inspect private log.'
            try:
                if request('/api/clusters/')[0]==200:break
            except OSError:pass
            time.sleep(.1)
        else:raise AssertionError('Backend readiness timeout')
        start=(int(time.time())//2)*2-64
        end=start+60
        resources=[{'hostname':host,'hwthreads':[0],'accelerators':['gpu0','gpu1']} for host in ('node001','node002')]
        job={'jobId':920001,'cluster':'demo_cluster','user':'synthetic-energy','project':'regression','startTime':start,'numNodes':2,'numHwthreads':2,'numAcc':4,'resources':resources}
        code,created=request('/api/jobs/start_job/',job);assert code==201,(code,created)
        ident=created.get('id',1) if isinstance(created,dict) else 1
        lines=[]
        for host in ('node001','node002'):
            for stamp in range(start,end,2):
                lines.append(f'cpu_load,cluster=demo_cluster,hostname={host},type=node value=1 {stamp}')
                for gpu in ('gpu0','gpu1'):
                    lines.append(f'acc_power,cluster=demo_cluster,hostname={host},type=accelerator,type-id={gpu} value=1500 {stamp}')
        assert request('/api/write/','\n'.join(lines))[0]==200
        assert request('/api/jobs/stop_job/',{'jobId':920001,'cluster':'demo_cluster','startTime':start,'stopTime':end,'jobState':'completed'})[0]==200
        for _ in range(150):
            code,archived=request(f'/api/jobs/{ident}?all-metrics=true')
            if code==200 and archived.get('Meta',{}).get('monitoringStatus')==3:break
            time.sleep(.1)
        else:raise AssertionError('Job failed to reach archive status3')
        (evidence/'archived.json').write_text(json.dumps(archived,indent=2))
        meta=archived['Meta']
        assert meta['jobId']==920001 and meta['user']=='synthetic-energy' and meta['cluster']=='demo_cluster'
        assert meta['resources']==resources and meta['numNodes']==2 and meta['numAcc']==4
        assert meta['startTime']==start and meta['duration']==60 and meta['jobState']=='completed'
        assert meta['energy']==0.1,meta
        assert meta['footprint']['acc_power_avg']==3000,meta
        aggregate=archived['Data']['acc_power']['node']
        assert aggregate['timestep']==2 and len(aggregate['series'])==2
        assert {entry['hostname'] for entry in aggregate['series']}=={'node001','node002'}
        for entry in aggregate['series']:assert entry['data']==[3000]*30 and entry['statistics']['avg']==3000
        # This REST endpoint leaves energyFootprint null; the persisted SQL field
        # is loaded separately by GraphQL. Verify that actual field, not an
        # invented REST shape. Native accelerator series live in the archive.
        with sqlite3.connect('file:'+str(instance/'var/job.db')+'?mode=ro',uri=True) as database:
            rows=database.execute('select energy_footprint,energy,monitoring_status from job where job_id=920001').fetchall()
        assert len(rows)==1 and rows[0][1:]==(0.1,3)
        energy_footprint=json.loads(rows[0][0]);assert energy_footprint=={'acc_power':0.1}
        native_paths=list((instance/'var/job-archive/demo_cluster/920/001'/str(start)).glob('data.json*'))
        assert len(native_paths)==1
        path=native_paths[0]
        native=json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
        (evidence/'native-archive.json').write_text(json.dumps(native,indent=2))
        series=native['acc_power']['accelerator']['series']
        assert len(series)==4 and native['acc_power']['accelerator']['timestep']==2
        assert {(s['hostname'],s['id']) for s in series}=={(h,g) for h in ('node001','node002') for g in ('gpu0','gpu1')}
        for entry in series:assert entry['data']==[1500]*30 and entry['statistics']['avg']==1500,entry
        result.update({'pass':True,'monitoring_status':3,'duration_seconds':60,'nodes':2,'synthetic_gpu_series':4,'samples_per_series':30,'watts_per_gpu':1500,'expected_energy_kwh':0.1,'actual_energy_kwh':meta['energy'],'energy_footprint':energy_footprint,'footprint':meta['footprint']})
    finally:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
        result['server_stopped']=process.poll() is not None
        (evidence/'results.json').write_text(json.dumps(result,indent=2))
    print('PASS: exact documented power/avg contract, four ordered synthetic series, archived status3, 0.10kWh.')


if __name__=='__main__':main()
