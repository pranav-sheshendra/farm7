"""Record real local model answers for review; not an agricultural benchmark."""
import json
from pathlib import Path
import time
import requests
ROOT=Path(__file__).resolve().parents[1]
samples=[
 ('en','My tomato leaves are turning yellow. Ask three useful questions before suggesting a cause. Keep it brief.'),
 ('hi','मेरे टमाटर के पत्ते पीले हो रहे हैं। कारण बताने से पहले तीन सवाल पूछें। संक्षिप्त उत्तर दें।'),
 ('te','నా టమాటా ఆకులు పసుపు రంగులోకి మారుతున్నాయి. కారణం చెప్పే ముందు మూడు ప్రశ్నలు అడగండి. చిన్న సమాధానం ఇవ్వండి.'),
]
results=[]
for language,prompt in samples:
    started=time.time()
    r=requests.post('http://127.0.0.1:5000/api/chat',json={'language':language,'messages':[{'role':'user','content':prompt}]},timeout=300)
    r.raise_for_status()
    data=r.json()
    assert data['answer'].strip() and '<think>' not in data['answer']
    if language=='hi': assert any('\u0900'<=c<='\u097f' for c in data['answer'])
    if language=='te': assert any('\u0c00'<=c<='\u0c7f' for c in data['answer'])
    row={'language':language,'prompt':prompt,'answer':data['answer'],'model':data['model'],
         'seconds':round(time.time()-started,1),'scope':'Connectivity and script check; accuracy requires expert review'}
    results.append(row)
    (ROOT/'artifacts/assistant-samples.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(row,ensure_ascii=False),flush=True)
