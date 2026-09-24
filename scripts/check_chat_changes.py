"""Persistence/security checks and simulated browser speech lifecycle regression."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chat_store import ChatStore
import app as backend
from playwright.sync_api import sync_playwright
from auth_test_support import flask_sign_in, browser_sign_in

report = {}
with tempfile.TemporaryDirectory() as folder:
    db = ChatStore(Path(folder) / 'test.sqlite3')
    with patch.object(backend, 'store', db), patch.object(backend.assistant_service, 'status', return_value={'ready': True}), patch.object(backend.assistant_service, 'complete', return_value='नमस्ते किसान'):
        a, b = backend.app.test_client(), backend.app.test_client()
        flask_sign_in(backend.app, a)
        assert a.get('/api/history').json == {'messages': []}
        payload = {'language': 'hi', 'messages': [{'role': 'user', 'content': 'नमस्ते'}]}
        assert a.post('/api/chat', json=payload).status_code == 200
        assert len(a.get('/api/history').json['messages']) == 2
        assert b.get('/api/history').status_code == 401
        reopened = ChatStore(Path(folder) / 'test.sqlite3')
        with a.session_transaction() as session:
            assert len(reopened.history(session['owner'])) == 2
        assert a.delete('/api/history', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert len(a.get('/api/history').json['messages']) == 2
        assert a.delete('/api/history').json == {'messages': []}
        backend.chat_slots.acquire()
        try:
            assert a.post('/api/chat', json=payload).status_code == 429
        finally:
            backend.chat_slots.release()
        with patch.object(backend.assistant_service, 'complete', side_effect=ValueError('empty')):
            assert a.post('/api/chat', json=payload).status_code == 502
        assert a.get('/api/history').json['messages'] == []
report['database'] = 'passed: saved turn, reopen, isolation, deletion, failed-turn rollback, cross-site rejection, busy response'

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('''
      window.SpeechRecognition=class {
        constructor(){window.rec=this;this.starts=0;}
        start(){this.starts++;this.onstart?.();}
        stop(){this.emit('अंतिम शब्द',true);this.onend?.();}
        abort(){this.onend?.();}
        emit(text,final){const r=[{transcript:text}];r.isFinal=final;this.onresult({resultIndex:0,results:[r]});}
      };
    ''')
    browser_sign_in(page,'http://127.0.0.1:5000')
    page.wait_for_function("document.querySelector('#language').options.length===23")
    page.locator('#language').select_option('hi')
    page.wait_for_function("document.documentElement.lang==='hi'")
    page.locator('#message').fill('पहले')
    page.locator('#voice').click()
    assert page.evaluate('rec.continuous && rec.lang === "hi-IN"')
    page.evaluate("rec.emit('अधूरा',false)")
    assert page.locator('#message').input_value() == 'पहले'
    assert page.locator('#send').is_disabled()
    page.evaluate("rec.emit('मेरे पौधे',true);rec.onend()")
    page.wait_for_function('rec.starts===2')
    page.locator('#stopVoice').click()
    assert page.locator('#message').input_value() == 'पहले मेरे पौधे अंतिम शब्द'
    assert not page.locator('#message').get_attribute('readonly')
    assert page.locator('#messages article').count() == 0
    page.locator('#voice').click()
    page.evaluate("rec.onerror({error:'language-not-supported'});rec.onend()")
    assert page.locator('#speechStatus').inner_text()
    assert page.locator('#stopVoice').is_hidden()
    assert not errors, errors
    report['speech_lifecycle'] = 'passed with simulated recognition: interim separation, selected Hindi, silence restart, final result after Stop, no auto-send, unsupported language error'
    report['microphone_accuracy'] = 'Not measured; simulated recognition does not validate browser/provider speech accuracy.'
    browser.close()
(ROOT/'artifacts/chat-change-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
