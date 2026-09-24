"""Export the existing trained model without retraining or quantization."""
from pathlib import Path
import json
import numpy as np
import tensorflow as tf
from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2

root = Path(__file__).resolve().parents[1]
model = tf.keras.models.load_model(root/'crop_pred.keras', compile=False)
@tf.function(input_signature=[tf.TensorSpec([1,128,128,3], tf.float32)])
def forward(x):
    return model(x, training=False)
frozen = convert_variables_to_constants_v2(forward.get_concrete_function())
converter = tf.lite.TFLiteConverter.from_concrete_functions([frozen])
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
data = converter.convert()
(root/'crop_pred.tflite').write_bytes(data)
lite = tf.lite.Interpreter(model_content=data, num_threads=2)
lite.allocate_tensors()
errors=[]
for image in np.random.default_rng(42).random((8,1,128,128,3),dtype=np.float32):
    expected=model(image,training=False).numpy()
    lite.set_tensor(lite.get_input_details()[0]['index'],image);lite.invoke()
    actual=lite.get_tensor(lite.get_output_details()[0]['index'])
    assert expected.argmax()==actual.argmax()
    errors.append(float(np.max(np.abs(expected-actual))))
assert max(errors)<1e-4,errors
(root/'artifacts/lite-export.json').write_text(json.dumps({'bytes':len(data),'max_absolute_error':max(errors),'samples':8,'quantized':False,'scope':'Numerical conversion check, not an accuracy benchmark'},indent=2))
print('Export and parity checks passed:',len(data),'bytes; max error',max(errors))
