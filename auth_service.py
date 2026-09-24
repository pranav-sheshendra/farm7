"""Single-account authentication; passwords stay in server configuration."""
import hashlib
import os
import secrets
import time
from collections import deque
from threading import Lock
from flask import jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ADMIN_EMAIL = 'admin@mail.com'


def install_auth(app):
    password = os.environ.get('ADMIN_PASSWORD', '')
    app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(password) if password else None
    # Rotated at startup; existing sessions must sign in after redeployment.
    epoch = secrets.token_urlsafe(32)
    attempts, lock = deque(), Lock()

    def signed_in():
        return (session.get('admin') == ADMIN_EMAIL and session.get('auth_epoch') == epoch
                and time.time() - session.get('signed_in_at', 0) < 8 * 3600)

    @app.before_request
    def require_sign_in():
        if request.endpoint in {'static', 'login', 'health'}:
            return None
        if not signed_in():
            if request.path.startswith('/api/') or request.path == '/predict':
                return jsonify(error='signInRequired'), 401
            return redirect(url_for('login'))
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
            if not supplied or not secrets.compare_digest(supplied, session.get('csrf_token', '')):
                return jsonify(error='invalid_request'), 403

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if signed_in():
            return redirect(url_for('index'))
        session.setdefault('csrf_token', secrets.token_urlsafe(32))
        error, status = '', 200
        if request.method == 'POST':
            token = request.form.get('csrf_token', '')
            if not token or not secrets.compare_digest(token, session['csrf_token']):
                error, status = 'Your sign-in form expired. Please try again.', 403
            elif not app.config['ADMIN_PASSWORD_HASH']:
                error, status = 'Sign-in is not configured. Set ADMIN_PASSWORD in the server environment.', 503
            else:
                with lock:
                    now = time.monotonic()
                    while attempts and attempts[0] < now - 60:
                        attempts.popleft()
                    limited = len(attempts) >= 10
                    if not limited:
                        attempts.append(now)
                if limited:
                    error, status = 'Too many attempts. Please wait one minute and try again.', 429
                else:
                    candidate = request.form.get('password', '')
                    valid = len(candidate) <= 1024 and check_password_hash(app.config['ADMIN_PASSWORD_HASH'], candidate)
                    if request.form.get('email', '').strip().lower() == ADMIN_EMAIL and valid:
                        session.clear()
                        session.update(admin=ADMIN_EMAIL, auth_epoch=epoch, signed_in_at=time.time(),
                                       csrf_token=secrets.token_urlsafe(32),
                                       owner='account:'+hashlib.sha256(ADMIN_EMAIL.encode()).hexdigest())
                        session.permanent = True
                        return redirect(url_for('index'))
                    error, status = 'Incorrect email or password.', 401
        return render_template('login.html', error=error, csrf_token=session['csrf_token']), status

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))
