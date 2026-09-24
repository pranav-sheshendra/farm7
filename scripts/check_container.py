"""Smoke-test the temporary Docker app on localhost:5010."""
import json
import time
from pathlib import Path
import requests

root = Path(__file__).resolve().parents[1]
url = 'http://127.0.0.1:5010'
for attempt in range(90):
    try:
        response = requests.get(url+'/health', timeout=2)
        if response.status_code == 200:
            break
    except requests.RequestException:
        pass
    time.sleep(1)
else:
    raise RuntimeError('Container did not become healthy')
assert response.json()['classes'] == 38
assert requests.get(url+'/').status_code == 200
assert requests.get(url+'/api/history').json() == {'messages': []}
with (root/'.venv/test-leaf.jpg').open('rb') as photo:
    prediction = requests.post(url+'/predict', files={'image': photo}, timeout=30)
assert prediction.status_code == 200, prediction.text
assert prediction.json()['predictions'][0]['label'].endswith('___Late_blight')
report = {'container_health': 'passed', 'sqlite_initialization': 'passed', 'crop_prediction': prediction.json()['predictions'][0], 'scope': 'Linux container startup and inference; external domain/HTTPS not provisioned'}
(root/'artifacts/container-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
