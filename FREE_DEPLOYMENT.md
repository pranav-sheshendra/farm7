# Free deployment: Render + MongoDB Atlas + Groq

This is the default hosted setup. There is no paid VM, local Ollama server,
persistent Render disk, or paid database in `render.yaml`.

| Component | Free service | Purpose |
| --- | --- | --- |
| Website + API | Render Free web service | Hosts the complete Flask application over HTTPS |
| Crop inference | TFLite in the Render service | Runs the original trained model with float32 weights |
| Chat history | MongoDB Atlas Free (M0) | Survives Render sleeps, restarts and deployments |
| Assistant | Groq Free API | Qwen `qwen/qwen3.8-27b`, subject to account quotas |
| Speech | Browser recognition + Edge TTS | Existing selected-language dictation and voice output |

## Deploy

1. Create a **Free/M0** cluster at MongoDB Atlas. Do not select Flex, Dedicated,
   or a paid trial. Create a database user with read/write permission limited to
   `farm_ai`. Copy its Python driver `mongodb+srv://...` connection string,
   replacing the password placeholder with a URL-encoded password.
2. Create a Groq API key in a **Free** account. Do not upgrade to Developer or
   enable paid billing. Confirm `qwen/qwen3.8-27b` is available in your account;
   it is a preview model and may change. `ASSISTANT_MODEL` is configurable.
3. Push the application changes to your own GitHub repository. Include
   `crop_pred.tflite` (12.5 MB), `render.yaml`, `Dockerfile.render`,
   `requirements-render.txt`, application Python files, `static/` and `templates/`.
   Do not commit `.env`, database files, keys or virtual environments. Conversion
   already ran locally; TensorFlow/training is not needed on Render.
4. In Render choose **New → Blueprint**, connect this repository, and select
   the branch containing `render.yaml`. Verify the service plan says **Free**.
   Enter `MONGODB_URI` and `GROQ_API_KEY` into the private secret fields.
   Render generates a stable SECRET_KEY. Keep it across redeployments.
5. In the Render service's **Connect / Outbound** information, find its outbound
   IP ranges and add those to Atlas **Network Access**. An initial deployment
   may fail until this is configured; redeploy after adding the ranges. Do not
   expose MongoDB without authentication or disable TLS verification.
6. Open the generated `https://farm-ai-....onrender.com` link. No custom domain
   purchase is needed. `/health` checks crop-model startup. Send a real assistant
   message to verify the API key/model/quota, reload to check saved history,
   upload a leaf, and test the microphone on your actual device.

If you create a Web Service manually instead of using Blueprint: select Docker,
Dockerfile path `./Dockerfile.render`, Free plan, and copy the environment settings
from `render.yaml`. Also set APP_ENV=production and a random SECRET_KEY of at least
32 characters. Render supplies PORT and RENDER_EXTERNAL_URL automatically.

## What is and isn't verified

The conversion preserves the original float32 model and preprocessing. Local
evidence is recorded in `artifacts/lite-export.json`; synthetic numerical parity
is not a new disease accuracy measurement. Free deployment has a 5-megapixel
image cap and admits one prediction at a time to bound RAM use.

The Linux image passed startup and a real crop-photo inference test with a
512 MB memory cap and 0.5 CPU limit. Observed peak memory was 90,316,800 bytes
(about 86 MiB); this smoke test used local SQLite, not Atlas. See
`artifacts/render-free-checks.json`. This is not a concurrency or cloud-load benchmark.

Groq credentials and an Atlas cluster are required for a live end-to-end cloud
check. Status checks model availability; only a real chat verifies remaining quota. This workspace
cannot create your accounts or promise a live URL without access to them.

Chats are sent to Groq; saved conversations are stored in Atlas. Explain this
to users. The database keeps the latest 100 messages per anonymous browser and
expires a conversation after 30 days without a successful chat. It is not account
login or cross-device synchronization. Existing local SQLite history is not
automatically copied into Atlas. Changing SECRET_KEY invalidates browser ownership.
Deleting chat removes the Atlas document. Atlas TTL cleanup is asynchronous.

## Staying free

- Render Free sleeps after 15 idle minutes; waking can take about a minute.
  Free hours, bandwidth and build limits apply. Use one web service, avoid paid
  add-ons, and do not add a payment method if you want usage exhaustion to suspend
  services instead of incur overage charges. Check the billing dashboard.
- Atlas Free has a 512 MB database storage limit; monitor usage and stay on M0.
- Groq Free has request/token limits, not unlimited inference. Exhaustion returns
  an error; this app does not switch to another paid service. Preview model
  availability and farming-language quality must be rechecked before launch.
- These are free demo services with cold starts and quotas, not an always-on SLA.
- Native speech accuracy and complete coverage of all Indian languages have not
  been established by deploying the app.

## Why Render here, rather than Vercel?

The app is one Flask service with image uploads, native inference dependencies,
and chat requests. Render runs that service directly and provides HTTPS without
splitting the frontend/backend. This configuration targets Render only; it does
not claim Vercel is incapable of running Python. A Vercel deployment would need
its own function packaging, upload, execution-duration and memory validation.

Sources: [Render Free](https://render.com/docs/free),
[Atlas Free limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/),
[Groq Free limits](https://console.groq.com/docs/rate-limits),
[Qwen on Groq](https://console.groq.com/docs/model/qwen/qwen3.8-27b).
