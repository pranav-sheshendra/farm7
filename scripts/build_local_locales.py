"""Generate offline translation drafts with the local multilingual model.

These drafts require native-speaker review, especially low-resource languages.
No network translation provider or user chat is involved.
"""
import json
from pathlib import Path
import sys
import time
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from languages import LANGUAGE_MAP
from assistant_service import MODEL, OLLAMA_URL
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'static/locales'
DIR = ROOT / 'artifacts/draft-locales'
DIR.mkdir(parents=True,exist_ok=True)
source = json.loads((SOURCE/'en.json').read_text(encoding='utf-8'))
status_file = ROOT/'artifacts/translation-status.json'
statuses = {}
for code, language in LANGUAGE_MAP.items():
    path = DIR/(code+'.json')
    existing = SOURCE/(code+'.json') if (SOURCE/(code+'.json')).exists() else path
    if existing.exists() and set(json.loads(existing.read_text(encoding='utf-8'))) == set(source):
        statuses[code] = {'status':'complete-draft', 'native_review':False}
        continue
    result = {}
    statuses[code] = {'status':'running', 'native_review':False}
    status_file.write_text(json.dumps(statuses,indent=2),encoding='utf-8')
    try:
        items = list(source.items())
        for offset in range(0,len(items),12):
            batch = dict(items[offset:offset+12])
            schema = {'type':'object','properties':{k:{'type':'string'} for k in batch},
                      'required':list(batch),'additionalProperties':False}
            prompt = (f'Translate every JSON value into {language["english"]} ({language["name"]}) in its native script. '
                      'These are farmer-facing app interface labels, explanations and crop disease names. '
                      'Keep keys EXACTLY unchanged. Translate ALL values, preserve numbers, and do not summarize. '
                      'Return only the translated JSON object.\n' + json.dumps(batch,ensure_ascii=False))
            response = requests.post(OLLAMA_URL+'/api/chat',json={'model':MODEL,
                'messages':[{'role':'user','content':prompt}], 'stream':False,'think':False,
                'format':schema,'options':{'temperature':0,'num_ctx':4096,'num_predict':3000}},timeout=600)
            response.raise_for_status()
            translated = json.loads(response.json()['message']['content'])
            if set(translated)!=set(batch) or any(not isinstance(v,str) or not v.strip() for v in translated.values()):
                raise ValueError('Incomplete translation batch')
            result.update(translated)
            print(code,len(result),'/',len(source),flush=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        statuses[code]={'status':'draft-only-not-enabled','model':MODEL,'native_review':False}
    except Exception as error:
        statuses[code]={'status':'failed','error':str(error),'native_review':False}
        print(code,'FAILED',str(error),flush=True)
    status_file.write_text(json.dumps(statuses,indent=2),encoding='utf-8')
