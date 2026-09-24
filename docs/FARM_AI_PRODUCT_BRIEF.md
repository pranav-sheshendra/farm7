# Farm AI
## Product & Technology Brief

**Release:** 24 September 2026 · **App:** https://farm-ai-ksm7.onrender.com/

### 1. Product overview

Farm AI helps farmers analyze a leaf photograph and discuss crop care through a multilingual, voice-enabled assistant. Two primary tabs—**Crop Analysis** and **Assistant**—keep diagnosis and conversation accessible in one application. Access is restricted to one administrator account.

### 2. Features, models & connections

| Feature | Technology / model | API & connection |
| --- | --- | --- |
| **Crop disease prediction** | Custom TensorFlow/Keras CNN trained on PlantVillage; 38 classes across 14 crop types. The saved `crop_pred.keras` model is exported to float32 `crop_pred.tflite`; production uses TFLite Runtime 2.14.0. Pillow, OpenCV and NumPy prepare 128 × 128 RGB images normalized to 0–1. | Browser uploads to `POST /predict` → inference inside the Render service → top three predictions and model scores. Leaf images are processed in memory and are not saved by the app. |
| **Text assistant** | Qwen model `qwen/qwen3.8-27b`, hosted by Groq. A farming-focused system prompt requests concise answers in the selected language and uses conversation context. | Browser → `POST /api/chat` → Groq's `https://api.groq.com/openai/v1/chat/completions` → response saved in MongoDB → browser. Authentication uses a server-side `GROQ_API_KEY`. |
| **Voice input** | Browser Web Speech API: `SpeechRecognition` / `webkitSpeechRecognition`. The browser/provider controls the recognition model; its exact name/version is not exposed. Continuous listening and interim transcripts support dictation until Stop. | Microphone → browser recognition service → editable text in the chat composer. The farmer reviews and sends it through the same text-assistant API. Audio may be sent to the browser's provider. |
| **Voice output** | Browser `speechSynthesis` voices, plus Microsoft Edge online neural voices through `edge-tts` 7.2.8. Example voice IDs: `hi-IN-SwaraNeural`, `te-IN-ShrutiNeural`, `en-IN-NeerjaNeural`. | Browser voices are listed locally; `GET /api/speech/voices` lists online voices. `POST /api/speech/speak` → Edge TTS → MP3 playback. Online speech sends reply text to Microsoft; no speech API key is configured. |
| **Language switching & translation** | UTF-8 JSON interface catalogs and JavaScript update labels, buttons and disease names. The user selects the language for dictation and new assistant replies. | Static catalogs load from `/static/locales/`; `/api/languages` reports availability. A backend translation utility uses `POST /api/translate` with the same Groq model. Saved messages retain their original language when the interface changes. |
| **Saved conversations** | MongoDB Atlas, accessed through PyMongo over certificate-verified TLS. History is shared across signed-in browsers for the administrator. | `GET /api/history` loads chats; `DELETE /api/history` clears them. The latest 100 messages are retained; a TTL index expires conversations after 30 days without a new saved turn. |
| **Sign-in & protection** | Flask sessions, Werkzeug password hashing, CSRF tokens, sign-in attempt limits and eight-hour session expiry. Production cookies use Secure, HttpOnly and SameSite settings. | `/login` and `/logout` manage access. The app and its APIs require sign-in; `/health` and static assets remain public. The password and session secret stay in server environment variables. |
| **Voice accuracy testing** | Word Error Rate (WER) and Character Error Rate (CER), calculated using edit distance against a user-provided reference phrase. | `POST /api/speech/measure` returns sample-level metrics; the browser exports results as JSON. These are per-recording measurements, not overall language-accuracy claims. |

### 3. Platform & deployment

- **Frontend:** HTML, CSS, vanilla JavaScript and Jinja2 templates; responsive layouts, icons and CSS motion.
- **Backend:** Python 3.11, Flask and Waitress 3.0.2, packaged with Docker.
- **Hosting:** Render Free web service; GitHub repository `pranav-sheshendra/farm7` supplies deployments. MongoDB Atlas stores chats; Groq supplies the language model. Free-tier quotas and cold starts apply.
- **Private configuration:** `GROQ_API_KEY`, `MONGODB_URI`, `ADMIN_PASSWORD`, `SECRET_KEY`. Model selection uses `ASSISTANT_PROVIDER` and `ASSISTANT_MODEL`; no credentials belong in frontend code or documents.
- **Local development:** Ollama serves `qwen3.5:4b` through `http://127.0.0.1:11434/api/chat`; SQLite stores chats; TensorFlow loads the original Keras model.

### 4. Current coverage & product boundaries

**Ten enabled interface languages:** English, Hindi, Telugu, Marathi, Tamil, Kannada, Malayalam, Bengali, Gujarati and Punjabi.

Voice availability depends on the browser, device and online voice inventory; interface availability does not guarantee matching speech support. Language selection is manual. Edge TTS is an unofficial online-service adapter. Interface translations need native-speaker review, and disease scores are not independently validated field accuracy or confirmed diagnoses.

**Release verification:** Administrator sign-in, blocked anonymous API access, MongoDB connectivity, deployed UI assets and a crop-image prediction passed live checks. Both tabs were checked at phone, tablet and desktop widths. Native speech accuracy has not been independently established.
