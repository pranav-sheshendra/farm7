"""Use lightweight TFLite on Render; retain original TensorFlow locally."""
import os
from pathlib import Path
import numpy as np

class CropRuntime:
    def __init__(self):
        self.lite = os.environ.get('CROP_RUNTIME') == 'tflite'
        root = Path(__file__).parent
        if self.lite:
            from tflite_runtime.interpreter import Interpreter
            self.model = Interpreter(model_path=str(root/'crop_pred.tflite'), num_threads=1)
            self.model.allocate_tensors()
            self.input = self.model.get_input_details()[0]
            self.output = self.model.get_output_details()[0]
            self.input_shape = tuple(self.input['shape'])
            self.output_shape = tuple(self.output['shape'])
        else:
            import tensorflow as tf
            self.model = tf.keras.models.load_model(root/'crop_pred.keras', compile=False)
            self.input_shape,self.output_shape = self.model.input_shape,self.model.output_shape

    def predict(self, pixels):
        batch = np.expand_dims(pixels,axis=0)
        if self.lite:
            self.model.set_tensor(self.input['index'], batch)
            self.model.invoke()
            return self.model.get_tensor(self.output['index'])[0]
        return self.model(batch,training=False).numpy()[0]
