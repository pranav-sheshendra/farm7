"""Production WSGI entrypoint; also works on Windows."""
import os
from waitress import serve
from app import app

if __name__ == '__main__':
    serve(app, host=os.environ.get('HOST', '127.0.0.1'),
          port=int(os.environ.get('PORT', '5000')), threads=8,
          max_request_body_size=10 * 1024 * 1024, channel_timeout=300)
