"""Verify a release over HTTPS using ADMIN_PASSWORD from the environment."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests
from auth_test_support import authenticated_session

root=Path(__file__).resolve().parents[1]
url=sys.argv[1].rstrip('/')
assert url.startswith('https://')
assert requests.get(url+'/health',timeout=60).status_code==200
for path in ['/api/history','/api/languages','/api/storage/status']:
    assert requests.get(url+path,timeout=30).status_code==401,path
client=authenticated_session(url)
storage=client.get(url+'/api/storage/status',timeout=30)
assert storage.status_code==200 and storage.json()['ready'],storage.status_code
availability=client.get(url+'/api/languages',timeout=30).json()
codes=[code for code,data in availability.items() if data['interface_ready']]
for relative in ['static/app.js','static/app.css',*[f'static/locales/{code}.json' for code in codes]]:
    response=client.get(url+'/'+relative,timeout=30)
    assert response.status_code==200,relative
    # Git's Windows line-ending conversion must not affect comparison.
    normalize=lambda data:data.replace(b'\r\n',b'\n')
    assert hashlib.sha256(normalize(response.content)).digest()==hashlib.sha256(normalize((root/relative).read_bytes())).digest(),relative
with (root/'.venv/test-leaf.jpg').open('rb') as image:
    response=client.post(url+'/predict',files={'image':image},timeout=60)
assert response.status_code==200,response.status_code
prediction=response.json()['predictions'][0]
assert prediction['label']=='Tomato___Late_blight',prediction
report={'url':url,'checked_at':datetime.now(timezone.utc).isoformat(),'sign_in':'passed','anonymous_api_access':'blocked','storage':storage.json(),'deployed_assets_match':True,'interface_languages':codes,'crop_prediction':prediction,'voice_accuracy_verified':False,'native_translation_accuracy_verified':False}
print(json.dumps(report,indent=2))
