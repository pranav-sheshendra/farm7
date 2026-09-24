"""HTTP and real-browser checks; no mocked disease predictions or model replies."""
import json
from pathlib import Path
import requests
import time
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:5000'
report={}
for attempt in range(30):
    try:
        if requests.get(URL+'/health',timeout=1).status_code==200: break
    except requests.RequestException: pass
    time.sleep(1)
assert requests.get(URL+'/health',timeout=10).json()['classes']==38
assert requests.post(URL+'/predict',timeout=10).status_code==400
assert requests.post(URL+'/api/chat',json={'messages':[{'role':'system','content':'bad'}]},timeout=10).status_code==400
assert requests.post(URL+'/api/chat',json={'language':{},'messages':[]},timeout=10).status_code==400
assert requests.post(URL+'/api/chat',json={'messages':[{'role':{},'content':'bad'}]},timeout=10).status_code==400
r=requests.post(URL+'/api/speech/measure',json={'reference':'the leaf is yellow','transcript':'the leaf was yellow'},timeout=10)
assert r.status_code==200 and r.json()['wer']==0.25
r=requests.post(URL+'/api/speech/measure',json={'reference':'पत्ता पीला है','transcript':'पत्ता पीला है'},timeout=10)
assert r.json()['wer']==0 and r.json()['cer']==0
report['api_checks']='passed'
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL)
    page.wait_for_function("document.querySelector('#analyze').textContent === 'Analyze disease'")
    assert page.locator('#assistantPanel').is_visible()
    page.locator('#analysisTab').click()
    page.locator('#image').set_input_files(str(ROOT/'.venv/test-leaf.jpg'))
    page.locator('#analyze').click()
    page.locator('#result').wait_for(state='visible',timeout=30000)
    report['disease_result']=page.locator('#disease').inner_text()
    assert report['disease_result'].casefold()=='late blight',report['disease_result']
    page.locator('#language').select_option('hi')
    page.wait_for_function("document.documentElement.lang === 'hi'")
    assert page.locator('#disease').inner_text()=='पछेती झुलसा'
    page.locator('#discuss').click()
    assert page.locator('#assistantPanel').is_visible()
    assert 'पछेती झुलसा' in page.locator('#message').input_value()
    page.wait_for_selector('#voices option[value="edge:hi-IN-SwaraNeural"]',state='attached')
    page.locator('#language').select_option('te')
    page.wait_for_function("document.documentElement.lang === 'te'")
    assert page.locator('#assistantTab').inner_text()=='సహాయకుడు'
    page.locator('#language').select_option('en')
    page.wait_for_function("document.documentElement.lang === 'en'")
    report['voices']=page.evaluate("speechSynthesis.getVoices().map(v=>({name:v.name,lang:v.lang,local:v.localService}))")
    report['recognition_api']=page.evaluate("!!(window.SpeechRecognition||window.webkitSpeechRecognition)")
    page.screenshot(path=str(ROOT/'artifacts/assistant-desktop.png'),full_page=True)
    page.locator('#analysisTab').click()
    page.screenshot(path=str(ROOT/'artifacts/analysis-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.locator('#assistantTab').click()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(ROOT/'artifacts/assistant-mobile.png'),full_page=True)
    assert not errors,errors
    report['browser_checks']='passed: upload, inference, language changes, disease handoff, tabs, mobile layout'
    report['javascript_errors']=errors
    browser.close()
report['voice_accuracy']='Not measured: real microphone samples and native-speaker review required.'
remote=requests.get(URL+'/api/speech/voices',timeout=10).json()['voices']
report['online_indian_voices']=[v for v in remote if v['lang'].endswith('-IN')]
audio=requests.post(URL+'/api/speech/speak',json={'voice':'hi-IN-SwaraNeural','text':'कृपया पत्ते की साफ तस्वीर भेजें।'},timeout=60)
assert audio.status_code==200 and audio.headers['Content-Type'].startswith('audio/mpeg') and len(audio.content)>1000
(ROOT/'artifacts/voice-hindi-test.mp3').write_bytes(audio.content)
report['online_speech_test']={'voice':'hi-IN-SwaraNeural','audio_bytes':len(audio.content),'status':'audio generated; listening-quality review pending'}
(ROOT/'artifacts/app-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
