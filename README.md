# 🌾 Crop Disease Prediction 🦠  

A deep learning-based **crop disease prediction** model with **97% accuracy**, helping farmers detect diseases early using image classification.  

## 📌 Features  
- **High Accuracy (97%)**: Optimized CNN architecture for precise disease detection.  
- **Image-Based Classification**: Uses deep learning to classify diseases from crop images.  
- **Batch Normalization & Dropout**: Improves model stability and reduces overfitting.  
- **Global Average Pooling**: Efficient feature extraction for better performance.  

## 🏗 Model Architecture  
The model is built using **TensorFlow** and **Keras**, featuring multiple **CNN layers**:  

```python
import tensorflow as tf

model = tf.keras.Sequential([
    tf.keras.layers.Conv2D(32, (3,3), activation='relu', input_shape=(128,128,3)),
    tf.keras.layers.MaxPooling2D(2,2),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Conv2D(64, (3,3), activation='relu'),
    tf.keras.layers.MaxPooling2D(2,2),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Conv2D(128, (3,3), activation='relu'),
    tf.keras.layers.MaxPooling2D(2,2),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Conv2D(512, (3,3), activation='relu'),
    tf.keras.layers.MaxPooling2D(2,2),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Conv2D(512, (3,3), activation='relu'),
    tf.keras.layers.MaxPooling2D(2,2),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Dropout(0.4),
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Flatten(),
    
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dense(classes, activation='softmax')
])
```
## 🛠 Installation  

### 1️⃣ Clone the Repository  
```bash
git clone https://github.com/pranav-sheshendra/farm7.git
cd farm7
```

## Run the local prediction app

The web app loads `crop_pred.keras` and uses the notebook's image preprocessing
and PlantVillage class order. It does not retrain or overwrite the saved model.
Use Python 3.11:

```powershell
python -m venv .app-venv
.\.app-venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.app-venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000 and upload a JPG, PNG or WebP leaf photo (up to 10 MB).
The app shows the three highest model scores. Images are processed in memory.
Predictions are not confirmed diagnoses; unrelated images also receive a class.

The original notebook includes dataset downloads and model training. Launching
the app only requires the saved model, not the training dataset or Jupyter.

## Assistant, languages and voices

The app has Crop Analysis and Assistant tabs. A disease result can be copied into
the chat composer for review before sending. The app requires the administrator
account (`admin@mail.com`) and a server-configured `ADMIN_PASSWORD`. Chat is saved
in SQLite locally or MongoDB on Render and shared between signed-in browsers for
that account. Delete chat removes the stored conversation. The local assistant
uses Ollama; the Render assistant uses Groq.

The default assistant is **Qwen3.5 4B**, served by Ollama. The earlier DeepSeek-R1
1.5B test produced poor farming guidance, so it is not the default. Set
`ASSISTANT_MODEL` to another installed Ollama model, or `OLLAMA_URL` for an
alternative local Ollama endpoint. The app does not invent a reply if the model
is unavailable. Small local model answers require agricultural expert review.

```powershell
ollama pull qwen3.5:4b
./scripts/start-app.ps1
```

This workspace also has a portable Ollama installation in `.venv/ollama`.
Its models are stored in `.venv/ollama-models`. The start script uses it when
available. The default URL is http://127.0.0.1:5000.

Language scope is English plus India's 22 scheduled languages, not every Indian
language or dialect. Complete static catalogs enable their language option;
incomplete options are disabled. The dropdown lists individual languages without
group headings. `scripts/check_locales.py` checks complete keys and expected
scripts, and `scripts/check_signin.py` checks language switching and mobile layout.
See `artifacts/locale-checks.json` for the checked catalogs. These checks do not
establish translation accuracy. All generated translations need native-speaker
review, particularly disease terminology and the low-resource languages.
`scripts/build_hosted_locales.py` generates resumable drafts using the deployed
assistant; it sends only public interface labels and is subject to free quotas.
Existing conversation text stays in its original language. New replies use the
selected language. Changing the interface no longer queues translations of every
old message, which could delay new replies.

Voice input uses the browser's SpeechRecognition implementation. Its underlying
recognition model/version is not exposed; language availability and microphone
permission must be tested in the actual browser. Dictation is editable and is
never automatically sent to the assistant. Recording uses continuous mode and
resumes after browser silence boundaries. Partial text stays in a preview; tap
Stop to commit finalized speech to the composer, review it, then send. Select the
spoken language first; automatic language detection is not implemented.

Voice output lists actual browser voices and Microsoft Edge online voices, with
their names, language and local/online status. Edge speech uses no paid API key,
but requires internet and sends the reply text to Microsoft. It is an unofficial
adapter to the online service, so availability can change. Browser recognition
may send microphone audio to its provider. Do not describe this as fully offline.
The observed Edge catalog supports Bengali, Gujarati, Hindi, Kannada, Malayalam,
Marathi, Nepali, Tamil, Telugu and Urdu; **it does not cover all 22 languages**.
See `artifacts/edge-voices.json` for the fetched inventory.

The voice test panel compares a user's spoken transcript with a reference phrase,
reports word/character error rates and exports the samples. Scores are for those
samples only. No farmer-speech accuracy or native-speaker quality score has been
established. Missing voices are shown explicitly instead of substituting English.

## Verification and notebook execution

The notebook has **14 code cells**. `116` is its last historical execution number,
not a cell count. The local full runner executes them in order with documented
Windows/dependency adjustments. It keeps `crop_pred.keras` intact and writes any
new trained model under `artifacts/notebook/` for separate evaluation.

```powershell
.\.venv\Scripts\uv.exe pip install --python .app-venv\Scripts\python.exe -r requirements-notebook.txt
.\.app-venv\Scripts\python.exe scripts/run_notebook.py
.\.app-venv\Scripts\python.exe scripts/evaluate_model.py
```

Full training is 20 epochs on 43,442 images and can take hours on this CPU.
`artifacts/notebook/status.json` records the completed-cell count and active cell;
`artifacts/notebook/executed.ipynb` contains real outputs and is updated during
execution. A running training cell is not a completed notebook run.
The original final Kaggle demo request returned HTTP 403. The adapted run uses
an explicitly labeled Tomato Early blight image from the downloaded PlantVillage
archive for that demo, with the same image preprocessing. It is not an independent
accuracy test. Epoch checkpoints, CSV logs and a training progress JSON prevent
losing an entire long run to a later demo failure.

The supplied model scored **97.1089% on 10,861 examples** from the notebook's
`plant_village:1.0.2` `train[80%:]` slice. This is an in-distribution check; the
saved model's training provenance is unknown, so it is not an independent field
benchmark. Per-class recall and the confusion matrix are in
`artifacts/model-evaluation.json`. A softmax score is not measured accuracy, and
the classifier can confidently misclassify unrelated images or unsupported crops.

Checks and evidence:

- `scripts/check_app.py`: real browser upload/inference, tabs, disease-to-chat
  handoff, Hindi/Telugu switching, mobile layout and input validation.
- `artifacts/app-checks.json`: browser results and observed installed voice names.
- `scripts/check_assistant.py` and `artifacts/assistant-samples.json`: real local
  model responses in English, Hindi and Telugu; connectivity/script checks only.
- `artifacts/translation-status.json`: language draft status and quality blockers.

Browser checks require `playwright` and an installed Chrome browser. Training,
translation generation and chat share this machine's CPU; running them together
increases response times. Do not replace the deployed model merely because a
training run finishes; compare its evaluation before promotion.

## Deployment and chat storage

**Free hosting:** follow [FREE_DEPLOYMENT.md](FREE_DEPLOYMENT.md). The supplied
`render.yaml` selects Render's Free plan, MongoDB Atlas stores chats, and Groq's
Free API handles assistant requests. A 12.5 MB TFLite export runs disease inference
without loading TensorFlow on the free web service. Cloud credentials must be
configured privately before live deployment. Free services have sleep/quota limits.

Use `python serve.py` for the local Waitress server. Local chats are stored under
`instance/` (ignored by Git); Render uses MongoDB Atlas for persistent history.
See [FREE_DEPLOYMENT.md](FREE_DEPLOYMENT.md) for the hosted setup. Keep the
production session secret stable and configure `ADMIN_PASSWORD` privately.
There is no registration; the one administrator account is the only allowed login.

`scripts/check_chat_changes.py` verifies database isolation, persistence, deletion,
cross-site rejection and simulated recognition lifecycle behavior. It does not
measure recognition accuracy from a real microphone.
