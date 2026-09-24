"""Execute every notebook cell in an isolated kernel; keep the deployed model intact."""
import json
import os
from pathlib import Path
import sys
import zipfile
import threading
import time
from datetime import datetime, timezone

import nbformat
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "notebook"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["MPLBACKEND"] = "Agg"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["TF_NUM_INTRAOP_THREADS"] = "4"
os.environ["TF_NUM_INTEROP_THREADS"] = "2"
os.environ["KAGGLEHUB_CACHE"] = str(ROOT / '.venv/kaggle')
os.environ["JUPYTER_RUNTIME_DIR"] = str(ROOT / ".venv" / "jupyter-runtime")
os.environ["IPYTHONDIR"] = str(ROOT / ".venv" / "ipython")
kernel_dir = ROOT / ".venv" / "kernels" / "farm-ai"
kernel_dir.mkdir(parents=True, exist_ok=True)
(kernel_dir / "kernel.json").write_text(json.dumps({
    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
    "display_name": "Farm AI Python 3.11", "language": "python"}), encoding="utf-8")
notebook = nbformat.read(ROOT / "crop-disease-prediction.ipynb", as_version=4)
changes = {
    1: "import tensorflow_datasets as tfds\nprint('tensorflow-datasets', tfds.__version__)",
    2: "import google.protobuf\nprint('protobuf', google.protobuf.__version__)\n# Use the TensorFlow-compatible version installed in requirements-notebook.txt.",
    5: "import matplotlib\nprint('matplotlib', matplotlib.__version__)",
}
for i, source in changes.items():
    notebook.cells[i].source = source
# Shuffle individual images before batching to avoid a ~6 GB batch shuffle buffer.
notebook.cells[4].source = notebook.cells[4].source.replace(
    'train.map(pre_process).batch(batch_size).shuffle(1000)',
    'train.map(pre_process).shuffle(1000, seed=42).batch(batch_size)')
notebook.cells[3].source = notebook.cells[3].source.replace(
    "as_supervised=True, with_info=True)",
    "as_supervised=True, with_info=True, data_dir=" + repr(str(ROOT / '.venv' / 'tfds')) + ")")
notebook.cells[3].source = "from tensorflow_datasets.core.utils import gcs_utils\ngcs_utils._is_gcs_disabled = True\n" + notebook.cells[3].source
# The upstream archive's extraction path exceeds Windows MAX_PATH. Reuse its
# verified download in a short local directory; keep the exact TFDS generator.
archives = list((ROOT / '.venv/tfds/downloads/plant_village').glob('*'))
archives = [p for p in archives if p.is_file() and zipfile.is_zipfile(p)]
if archives:
    extracted = ROOT / '.data'
    marker = extracted / '.complete'
    if not marker.exists():
        print('Extracting verified PlantVillage archive into a short path', flush=True)
        with zipfile.ZipFile(archives[0]) as archive:
            for entry in archive.infolist():
                target = (extracted / entry.filename).resolve()
                if not target.is_relative_to(extracted.resolve()):
                    raise ValueError('Unsafe archive path')
                archive.extract(entry, extracted)
        marker.write_text('complete')
    notebook.cells[3].source = notebook.cells[3].source.replace(
        '# loading the crop-image data',
        "from tensorflow_datasets.datasets.plant_village import plant_village_dataset_builder as pv\n"
        "def local_splits(self, dl_manager):\n"
        "    return [tfds.core.SplitGenerator(name=tfds.Split.TRAIN, gen_kwargs={'datapath': " + repr(str(extracted)) + "})]\n"
        "pv.Builder._split_generators = local_splits\n"
        "from pathlib import Path\n"
        "def local_examples(self, datapath):\n"
        "    root = Path(datapath) / 'Plant_leave_diseases_dataset_without_augmentation'\n"
        "    for label in pv._LABELS:\n"
        "        for directory in root.iterdir():\n"
        "            if directory.name.replace(' ', '_').replace(',', '_') != label.replace(' ', '_').replace(',', '_'): continue\n"
        "            for path in sorted(directory.iterdir()):\n"
        "                if path.suffix.lower() == '.jpg':\n"
        "                    yield label + '/' + path.name, {'image': str(path), 'image/filename': path.name, 'label': label}\n"
        "pv.Builder._generate_examples = local_examples\n# loading the crop-image data")
notebook.cells[11].source = notebook.cells[11].source.replace(
    "image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)",
    "if image is None:\n    raise FileNotFoundError('Kaggle sample tomato_early_blight.jpg was not found')\nimage = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)")
# Kaggle's referenced sample endpoint returns HTTP 403 without account access.
# Use an explicitly identified local sample for the same inference procedure.
demo_dir = ROOT / '.data/Plant_leave_diseases_dataset_without_augmentation/Tomato___Early_blight'
demo_images = sorted(demo_dir.glob('*')) if demo_dir.exists() else []
if demo_images:
    notebook.cells[11].source = (
        "# The original Kaggle demo returned HTTP 403. This local demo is not an independent accuracy test.\n"
        "import cv2\n"
        "image = cv2.imread(" + repr(str(demo_images[0])) + ")\n"
        "if image is None: raise FileNotFoundError('Local demo image missing')\n"
        "image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)\n"
        "image = cv2.resize(image, (128,128))\n"
        "image = image.astype(np.float32)/255.0\n"
        "print('Demo ground-truth folder: Tomato___Early_blight; image from the original PlantVillage archive')\nimage")
notebook.cells[10].source = '''import json
from pathlib import Path
class TrainingProgress(tf.keras.callbacks.Callback):
    def on_epoch_begin(self, epoch, logs=None): self.epoch = epoch + 1
    def on_train_batch_end(self, batch, logs=None):
        if batch % 50 == 0:
            Path('training-progress.json').write_text(json.dumps({'epoch':self.epoch,'epochs':20,'batch':batch+1,'metrics':logs}))
    def on_epoch_end(self, epoch, logs=None):
        Path('training-progress.json').write_text(json.dumps({'epoch':epoch+1,'epochs':20,'epoch_complete':True,'metrics':logs}))
model.fit(train_dataset, validation_data=test_dataset, epochs=20, verbose=2,
          callbacks=[TrainingProgress(), tf.keras.callbacks.CSVLogger('training.csv'),
                     tf.keras.callbacks.ModelCheckpoint('training-checkpoint.keras')])
'''
for cell in notebook.cells:
    cell.outputs = []
    cell.execution_count = None
report = {"status": "running", "total_cells": len(notebook.cells), "completed_cells": 0,
          "started": datetime.now(timezone.utc).isoformat(),
          "adaptations": ["Dependency install cells report preinstalled compatible packages; obsolete protobuf pin removed.",
                          "Shuffle images before batching to bound memory usage.",
                          "Dataset cache and output model isolated from deployed model.",
                          "Short extraction paths and pathlib glob replace incompatible Windows TFDS glob; labels and example keys preserved.",
                          "Kaggle demo returns HTTP 403; original archive Tomato Early blight image used for demo only.",
                          "Epoch checkpoints, CSV logs and progress reports added; 20 epochs retained; CPU threads bounded."],
          "training_epochs": 20}

def save():
    nbformat.write(notebook, OUT / "executed.ipynb")
    (OUT / "status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

def heartbeat():
    while report['status'] == 'running':
        time.sleep(15)
        try: save()
        except Exception: pass

client = NotebookClient(notebook, timeout=None, kernel_name="farm-ai",
                        resources={"metadata": {"path": str(OUT)}})
from jupyter_client import KernelManager
client.km = KernelManager(kernel_name="farm-ai", kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_dir.parent)]))
save()
threading.Thread(target=heartbeat, daemon=True).start()
try:
    with client.setup_kernel():
        for index, cell in enumerate(notebook.cells):
            report["active_cell"] = index + 1
            save()
            print(f"Executing cell {index + 1}/{len(notebook.cells)}", flush=True)
            client.execute_cell(cell, index)
            report["completed_cells"] = index + 1
            save()
    report["status"] = "completed"
except Exception as error:
    report["status"] = "failed"
    report["error"] = str(error)
    raise
finally:
    report["updated"] = datetime.now(timezone.utc).isoformat()
    save()
