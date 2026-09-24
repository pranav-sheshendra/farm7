"""Measure saved-model performance against the notebook's TFDS test slice.

This is an in-distribution check, not proof of field performance or independence
from the unknown training history of the supplied saved model.
"""
import json
from pathlib import Path
import sys
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import tensorflow as tf
import tensorflow_datasets as tfds
from tensorflow_datasets.core.utils import gcs_utils
gcs_utils._is_gcs_disabled=True
ROOT=Path(__file__).resolve().parents[1]
builder=tfds.builder('plant_village',data_dir=str(ROOT/'.venv/tfds'))
test=builder.as_dataset(split='train[80%:]',as_supervised=True)
model=tf.keras.models.load_model(ROOT/'crop_pred.keras',compile=False)
labels=builder.info.features['label'].names
matrix=np.zeros((len(labels),len(labels)),dtype=int)
dataset=test.map(lambda image,label:(tf.image.resize(image,(128,128))/255.,label)).batch(32)
for i,(images,targets) in enumerate(dataset):
    pred=np.argmax(model(images,training=False).numpy(),axis=1)
    for expected,actual in zip(targets.numpy(),pred): matrix[expected,actual]+=1
    if i%25==0: print('evaluated',int(matrix.sum()),flush=True)
report={'model':'crop_pred.keras','dataset':'plant_village:1.0.2',
        'split':'train[80%:]','samples':int(matrix.sum()),
        'accuracy':float(np.trace(matrix)/matrix.sum()),
        'labels':labels,'confusion_matrix':matrix.tolist(),
        'per_class_recall':{label:float(matrix[i,i]/matrix[i].sum()) if matrix[i].sum() else None for i,label in enumerate(labels)},
        'limitation':'In-distribution evaluation; saved model training provenance unknown. Not independent field accuracy.'}
(ROOT/'artifacts/model-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in {'labels','confusion_matrix','per_class_recall'}},indent=2))
