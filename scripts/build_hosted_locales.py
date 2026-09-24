"""Generate static, review-required catalogs from a user-owned Farm AI instance.

Only public interface strings are sent. No API keys or farmer conversations.
Usage: python scripts/build_hosted_locales.py https://your-app.onrender.com
"""
import json
import os
import re
import sys
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from languages import LANGUAGE_MAP

source = json.loads((ROOT/'static/locales/en.json').read_text(encoding='utf-8'))
url = sys.argv[1].rstrip('/')
if os.environ.get('ADMIN_PASSWORD'):
    from auth_test_support import authenticated_session
    client = authenticated_session(url)
else:
    client = requests.Session()  # Initial migration from the pre-sign-in release.
order = ['mr','ta','kn','ml','bn','gu','pa','ur','or','ne','as','sa','gom','mai','doi','brx','ks','sd','mni-Mtei','sat']
out = ROOT/'artifacts/draft-locales'
out.mkdir(parents=True, exist_ok=True)
status_path = ROOT/'artifacts/hosted-translation-status.json'
statuses = {}
last_request = 0

def translate(code, batch):
    global last_request
    text = '\n'.join(f'[{i}] {value}' for i,(_,value) in enumerate(batch))
    for attempt in range(4):
        time.sleep(max(0, 8.0-(time.monotonic()-last_request)))
        last_request = time.monotonic()
        response = client.post(url+'/api/translate', json={'language':code,'text':text}, timeout=90)
        if response.status_code in {429,502,503}:
            print(code, 'provider busy', response.status_code, '; waiting', flush=True)
            time.sleep(30)
            continue
        response.raise_for_status()
        answer = response.json()['text']
        matches = re.findall(r'^\s*\[(\d+)\]\s*(.*?)(?=^\s*\[\d+\]|\Z)', answer, flags=re.M|re.S)
        values = {int(i):value.strip() for i,value in matches}
        if set(values)==set(range(len(batch))) and all(values.values()):
            return {key:values[i] for i,(key,_) in enumerate(batch)}
        if len(batch)>1:
            half=len(batch)//2
            return {**translate(code,batch[:half]),**translate(code,batch[half:])}
        raise ValueError('Translation missing its label ID')
    raise RuntimeError('Provider unavailable after paced retries; resume later')

for code in order:
    path=out/f'{code}.json'
    result=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    batch=[]
    try:
        for key,value in source.items():
            if key in result: continue
            if batch and (sum(len(v)+8 for _,v in batch)+len(value)>600 or len(batch)>=12):
                result.update(translate(code,batch));batch=[]
                path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(code,len(result),'/',len(source),flush=True)
            batch.append((key,value))
        if batch: result.update(translate(code,batch))
        assert set(result)==set(source) and all(isinstance(v,str) and v.strip() for v in result.values())
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        statuses[code]={'status':'draft-complete','native_review':False}
        print(code,'DONE',flush=True)
    except Exception as error:
        statuses[code]={'status':'failed','error_type':type(error).__name__}
        print(code,'FAILED',type(error).__name__,flush=True)
    status_path.write_text(json.dumps(statuses,indent=2),encoding='utf-8')
