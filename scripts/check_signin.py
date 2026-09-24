"""Exercise sign-in, API protection, CSRF, expiry and the browser form."""
import re
import json
import logging
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import app as backend
logging.getLogger('werkzeug').setLevel(logging.ERROR)

test_password='test-password-only-not-a-live-credential'
backend.app.config['ADMIN_PASSWORD_HASH']=generate_password_hash(test_password)
def token(client):
    html=client.get('/login').text
    return re.search(r'name="csrf_token" value="([^"]+)"',html).group(1)

client=backend.app.test_client()
assert client.get('/').status_code==302
assert client.get('/health').status_code==200
for path in ['/api/history','/api/languages','/api/storage/status','/api/speech/voices','/api/assistant/status']:
    assert client.get(path).status_code==401,path
assert client.post('/predict').status_code==401
assert client.post('/api/chat',json={}).status_code==401
assert client.post('/login',data={'email':'admin@mail.com','password':test_password}).status_code==403
csrf=token(client)
assert client.post('/login',data={'csrf_token':csrf,'email':'other@mail.com','password':test_password}).status_code==401
assert client.post('/login',data={'csrf_token':csrf,'email':'admin@mail.com','password':'wrong'}).status_code==401
response=client.post('/login',data={'csrf_token':csrf,'email':'admin@mail.com','password':test_password})
assert response.status_code==302 and response.headers['Location']=='/'
assert client.get('/').status_code==200
with client.session_transaction() as session:
    new_csrf=session['csrf_token']
    assert new_csrf!=csrf and session['owner'].startswith('account:')
assert client.post('/logout').status_code==403
assert client.post('/api/chat',json={}).status_code==403
assert client.post('/api/chat',headers={'X-CSRF-Token':new_csrf},json={}).status_code==400
assert client.post('/logout',data={'csrf_token':new_csrf}).status_code==302
assert client.get('/api/history').status_code==401
csrf=token(client)
client.post('/login',data={'csrf_token':csrf,'email':'admin@mail.com','password':test_password})
with client.session_transaction() as session: session['signed_in_at']=time.time()-9*3600
assert client.get('/api/history').status_code==401
with patch.dict(backend.app.config, {'ADMIN_PASSWORD_HASH':None}):
    csrf=token(client)
    assert client.post('/login',data={'csrf_token':csrf,'email':'admin@mail.com','password':test_password}).status_code==503

server=make_server('127.0.0.1',5011,backend.app,threaded=True)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':390,'height':844})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:5011/')
        page.wait_for_url('**/login')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#email').fill('admin@mail.com');page.locator('#password').fill(test_password)
        page.locator('button[type=submit]').click();page.wait_for_url('http://127.0.0.1:5011/')
        page.locator('#language option[value="hi"]').wait_for(state='attached')
        page.wait_for_function("document.querySelectorAll('#language option:not(:disabled)').length > 3")
        assert page.locator('#language optgroup').count()==0
        codes=page.locator('#language option:not(:disabled)').evaluate_all('(options)=>options.map(option=>option.value)')
        assert codes[:4]==['en','hi','te','mr'],codes
        for code in codes:
            page.locator('#language').select_option(code)
            page.wait_for_function("code=>document.documentElement.lang===code",arg=code)
            strings=json.loads((root/'static/locales'/f'{code}.json').read_text(encoding='utf-8'))
            assert page.locator('#analysisTab').inner_text()==strings['analysis'],code
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(code,page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>[e.tagName,e.id,e.className]).slice(0,15)"))
            assert page.locator('#globalError').inner_text()=='',code
            for width in [360,768,1280]:
                page.set_viewport_size({'width':width,'height':844})
                for tab in ['analysisTab','assistantTab']:
                    page.locator('#'+tab).click()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(code,width,tab,page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>[e.tagName,e.id,e.className]).slice(0,15)"))
            page.set_viewport_size({'width':390,'height':844})
        page.locator('.signout-form button').click();page.wait_for_url('**/login')
        page.reload();assert page.url.endswith('/login')
        assert not errors,errors
        browser.close()
finally: server.shutdown()
(root/'artifacts/signin-checks.json').write_text(json.dumps({'single_account':True,'unauthenticated_api_blocked':True,'csrf_checked':True,'expired_session_blocked':True,'mobile_languages':codes,'viewport_widths':[360,390,768,1280],'dropdown_group_titles':False,'native_translation_accuracy_verified':False},indent=2)+'\n',encoding='utf-8')
print('PASS: single account, password rejection, API gate, CSRF, session rotation/expiry, logout, mobile browser sign-in')
