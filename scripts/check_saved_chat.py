"""Real local-model turn, browser reload, isolation, and deletion."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto('http://127.0.0.1:5000')
    page.wait_for_selector('#language option[value="hi"]', state='attached')
    page.locator('#language').select_option('hi')
    page.wait_for_function("document.documentElement.lang==='hi'")
    page.locator('#message').fill('केवल एक छोटा सवाल पूछें: मैं कौन सी फसल उगाता हूँ?')
    page.locator('#send').click()
    page.wait_for_selector('.bubble.assistant', timeout=240000)
    reply = page.locator('.bubble.assistant .message-content').inner_text()
    assert any('\u0900' <= c <= '\u097f' for c in reply)
    page.reload()
    page.wait_for_selector('.bubble.assistant')
    assert page.locator('.bubble.assistant .message-content').inner_text() == reply
    outsider = browser.new_context()
    assert outsider.request.get('http://127.0.0.1:5000/api/history').json() == {'messages': []}
    page.locator('#clearChat').click()
    page.wait_for_function("document.querySelectorAll('.bubble').length===0")
    page.reload()
    page.wait_for_function("document.documentElement.lang==='hi'")
    assert context.request.get('http://127.0.0.1:5000/api/history').json() == {'messages': []}
    report = {'real_model_reply': reply, 'browser_reload': 'passed', 'separate_browser': 'isolated', 'delete_and_reload': 'passed'}
    (root/'artifacts/saved-chat-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    browser.close()
