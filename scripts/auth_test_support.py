"""Authentication helpers for local verification scripts."""
import os
import re
import requests
from werkzeug.security import generate_password_hash


def flask_sign_in(app, client):
    password='isolated-test-password-not-used-in-deployment'
    app.config['ADMIN_PASSWORD_HASH']=generate_password_hash(password)
    token=re.search(r'name="csrf_token" value="([^"]+)"',client.get('/login').text).group(1)
    assert client.post('/login',data={'email':'admin@mail.com','password':password,'csrf_token':token}).status_code==302
    with client.session_transaction() as session:
        client.environ_base['HTTP_X_CSRF_TOKEN']=session['csrf_token']


def browser_sign_in(page, url):
    password=os.environ.get('ADMIN_PASSWORD')
    if not password: raise RuntimeError('Set ADMIN_PASSWORD to the local test server password before running browser checks.')
    page.goto(url+'/login')
    page.locator('#email').fill('admin@mail.com')
    page.locator('#password').fill(password)
    page.locator('button[type=submit]').click()
    page.wait_for_url(url+'/')


def authenticated_session(url):
    password=os.environ.get('ADMIN_PASSWORD')
    if not password: raise RuntimeError('Set ADMIN_PASSWORD to the local test server password before running API checks.')
    client=requests.Session()
    html=client.get(url+'/login',timeout=10).text
    token=re.search(r'name="csrf_token" value="([^"]+)"',html).group(1)
    response=client.post(url+'/login',data={'email':'admin@mail.com','password':password,'csrf_token':token},timeout=10)
    response.raise_for_status()
    token=re.search(r'name="csrf-token" content="([^"]+)"',response.text).group(1)
    client.headers['X-CSRF-Token']=token
    return client
