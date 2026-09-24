"""Local crop-image inference using the model exported by the notebook."""
import io
import os
import json
import asyncio
import secrets
import time
from collections import deque
from datetime import timedelta
from pathlib import Path
from threading import Lock, BoundedSemaphore

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import cv2
import numpy as np
from crop_runtime import CropRuntime
from flask import Flask, jsonify, render_template, request, Response, session
from PIL import Image, UnidentifiedImageError
import requests
import assistant_service
import speech_service
from languages import LANGUAGE_MAP
from chat_store import ChatStore, MongoChatStore, StorageUnavailable

# Exact TFDS PlantVillage class order used by the notebook (not alphabetical).
# https://github.com/tensorflow/datasets/blob/v4.9.7/tensorflow_datasets/datasets/plant_village/plant_village_dataset_builder.py
LABELS = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust",
    "Apple___healthy", "Blueberry___healthy", "Cherry___healthy",
    "Cherry___Powdery_mildew", "Corn___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___Common_rust", "Corn___healthy", "Corn___Northern_Leaf_Blight",
    "Grape___Black_rot", "Grape___Esca_(Black_Measles)", "Grape___healthy",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot",
    "Peach___healthy", "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy",
    "Potato___Early_blight", "Potato___healthy", "Potato___Late_blight",
    "Raspberry___healthy", "Soybean___healthy", "Squash___Powdery_mildew",
    "Strawberry___healthy", "Strawberry___Leaf_scorch", "Tomato___Bacterial_spot",
    "Tomato___Early_blight", "Tomato___healthy", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_mosaic_virus", "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
]

app = Flask(__name__)
production = os.environ.get('APP_ENV') == 'production'
secret = os.environ.get('SECRET_KEY')
if production and (not secret or len(secret) < 32):
    raise RuntimeError('Production requires a persistent SECRET_KEY of at least 32 characters.')
data_dir = Path(os.environ.get('DATA_DIR', Path(__file__).parent / 'instance'))
data_dir.mkdir(parents=True, exist_ok=True)
if not secret:
    secret_file = data_dir / '.session-key'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding='ascii')
    secret = secret_file.read_text(encoding='ascii').strip()
app.config.update(SECRET_KEY=secret, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=production,
                  PERMANENT_SESSION_LIFETIME=timedelta(days=30))
if os.environ.get('RENDER') and not os.environ.get('MONGODB_URI'):
    raise RuntimeError('Render requires MONGODB_URI; SQLite would lose saved chats on restart.')
store = MongoChatStore(os.environ['MONGODB_URI']) if os.environ.get('MONGODB_URI') else ChatStore(data_dir / 'chats.sqlite3')
chat_slots = BoundedSemaphore(1)
request_times = deque()
request_times_lock = Lock()
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
model = CropRuntime()
if model.input_shape[1:] != (128, 128, 3) or model.output_shape[-1] != len(LABELS):
    raise RuntimeError("Saved model does not match notebook input or class labels.")
inference_lock = Lock()
prediction_slots = BoundedSemaphore(1)


@app.before_request
def protect_requests():
    # Browser cross-site writes are rejected; no CORS is enabled.
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = request.headers.get('Origin')
        expected = os.environ.get('PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL') or request.host_url.rstrip('/')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin != expected):
            return jsonify(error='invalid_request'), 403
        if request.path in {'/api/chat', '/api/translate', '/api/speech/speak', '/predict'}:
            with request_times_lock:
                now = time.monotonic()
                while request_times and request_times[0] < now - 60:
                    request_times.popleft()
                if len(request_times) >= 30:
                    return jsonify(error='assistantBusy'), 429, {'Retry-After': '60'}
                request_times.append(now)
    if 'owner' not in session:
        session['owner'] = secrets.token_urlsafe(32)
        session.permanent = True


@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'microphone=(self)'
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.route('/api/history', methods=['GET', 'DELETE'])
def chat_history():
    if request.method == 'DELETE':
        store.clear(session['owner'])
    return jsonify(messages=store.history(session['owner']))


@app.get("/")
def index():
    return render_template("index.html", languages=LANGUAGE_MAP)


@app.get('/api/assistant/status')
def assistant_status():
    return jsonify(assistant_service.status())


@app.errorhandler(StorageUnavailable)
def storage_unavailable(error):
    app.logger.warning('MongoDB unavailable (%s). Check Atlas network access, cluster status, TLS and database credentials.',
                       type(error.__cause__).__name__)
    return jsonify(error='storageError'), 503


@app.get('/api/storage/status')
def storage_status():
    store.check_connection()
    return jsonify(ready=True, provider='MongoDB' if isinstance(store, MongoChatStore) else 'SQLite')


@app.get('/api/languages')
def language_status():
    root=Path(__file__).parent/'static/locales'
    required=set(json.loads((root/'en.json').read_text(encoding='utf-8')))
    result={}
    for code, language in LANGUAGE_MAP.items():
        try:
            strings=json.loads((root/(code+'.json')).read_text(encoding='utf-8'))
            ready=set(strings)==required and all(isinstance(v,str) and v for v in strings.values())
        except (OSError,ValueError): ready=False
        result[code]={**language,'interface_ready':ready,'native_review':code=='en'}
    return jsonify(result)


@app.get('/api/speech/voices')
def speech_voices():
    try:
        voices=asyncio.run(speech_service.available_voices())
        return jsonify(voices=[{'name':v['ShortName'],'lang':v['Locale'],'gender':v['Gender'],
                                'voiceURI':'edge:'+v['ShortName'],'localService':False,'provider':'Microsoft Edge online'} for v in voices])
    except Exception:
        return jsonify(voices=[],error='voiceError'),503


@app.post('/api/speech/speak')
def speech_speak():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify(error='invalid_request'),400
    text,voice=data.get('text'),data.get('voice')
    if not isinstance(text,str) or not 1<=len(text)<=6000 or not isinstance(voice,str):
        return jsonify(error='invalid_request'),400
    try:
        audio=asyncio.run(speech_service.synthesize(text,voice))
        return Response(audio,mimetype='audio/mpeg',headers={'Cache-Control':'no-store'})
    except ValueError:
        return jsonify(error='voiceError'),400
    except Exception:
        app.logger.exception('Speech service failed')
        return jsonify(error='voiceError'),502


@app.post('/api/chat')
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return jsonify(error='invalid_request'), 400
    language = data.get('language', 'en')
    messages = data.get('messages')
    if not isinstance(language, str) or language not in LANGUAGE_MAP or not isinstance(messages, list) or not 1 <= len(messages) <= 24:
        return jsonify(error='invalid_request'), 400
    if any(not isinstance(m, dict) or not isinstance(m.get('role'),str) or m.get('role') not in {'user', 'assistant'}
           or not isinstance(m.get('content'), str) or not 1 <= len(m['content']) <= 6000 for m in messages):
        return jsonify(error='invalid_request'), 400
    if sum(len(m['content']) for m in messages) > 18000 or messages[-1]['role'] != 'user':
        return jsonify(error='invalid_request'), 400
    store.check_connection()
    if not assistant_service.status()['ready']: return jsonify(error='offline'), 503
    if not chat_slots.acquire(blocking=False): return jsonify(error='assistantBusy'), 429
    try:
        answer = assistant_service.complete(messages, language)
        store.append_turn(session['owner'], messages[-1]['content'], answer, language)
        return jsonify(answer=answer, model=assistant_service.MODEL, language=language)
    except (requests.RequestException, ValueError, KeyError):
        app.logger.exception('Assistant request failed')
        return jsonify(error='chatError'), 502
    finally:
        chat_slots.release()


@app.post('/api/translate')
def translate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('language'),str) or data.get('language') not in LANGUAGE_MAP:
        return jsonify(error='invalid_request'), 400
    text = data.get('text')
    if not isinstance(text, str) or not 1 <= len(text) <= 6000:
        return jsonify(error='invalid_request'), 400
    if not chat_slots.acquire(blocking=False): return jsonify(error='assistantBusy'), 429
    try:
        return jsonify(text=assistant_service.complete([{'role':'user','content':text}], data['language'], translate=True))
    except (requests.RequestException, ValueError, KeyError):
        return jsonify(error='translationError'), 502
    finally:
        chat_slots.release()


@app.post('/api/speech/measure')
def measure_speech():
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return jsonify(error='invalid_request'), 400
    reference, transcript = data.get('reference'), data.get('transcript')
    if any(not isinstance(v, str) or len(v) > 2000 for v in (reference, transcript)):
        return jsonify(error='invalid_request'), 400
    try:
        return jsonify(assistant_service.speech_metrics(reference, transcript))
    except ValueError:
        return jsonify(error='noTest'), 400


@app.get("/health")
def health():
    return jsonify(status="ready", classes=len(LABELS))


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Please choose an image smaller than 10 MB."), 413


@app.post("/predict")
def predict():
    if not prediction_slots.acquire(blocking=False):
        return jsonify(error='assistantBusy'), 429
    try:
        return predict_image()
    finally:
        prediction_slots.release()


def predict_image():
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return jsonify(error="Choose a leaf image first."), 400
    raw = upload.read()
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                return jsonify(error="Please upload a JPG, PNG or WebP image."), 400
            limit = 5_000_000 if model.lite else 20_000_000
            if image.width * image.height > limit:
                return jsonify(error=f"Please use an image with at most {limit//1_000_000} million pixels."), 400
            image.verify()
        # Match notebook cell 11: OpenCV BGR -> RGB, linear resize, float32 / 255.
        decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("Image could not be decoded")
        rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        pixels = cv2.resize(rgb, (128, 128)).astype(np.float32) / 255.0
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return jsonify(error="That file could not be read. Choose a valid leaf photo."), 400
    with inference_lock:
        scores = model.predict(pixels)
    if not np.isfinite(scores).all():
        return jsonify(error="Prediction failed. Please try another image."), 500
    results = []
    for class_index in np.argsort(scores)[-3:][::-1]:
        label = LABELS[int(class_index)]
        crop, condition = label.split("___")
        results.append({"label": label, "crop": crop.replace("_", " "),
                        "condition": condition.replace("_", " "),
                        "confidence": float(scores[class_index])})
    ordered = np.sort(scores)
    uncertain = bool(ordered[-1] < 0.70 or ordered[-1] - ordered[-2] < 0.20)
    return jsonify(predictions=results, uncertain=uncertain,
                   accuracy_verified=False, model='crop_pred.tflite' if model.lite else 'crop_pred.keras')


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
