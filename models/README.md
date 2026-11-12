# Model

`best.onnx` is the coconut-tree detector used by the inference service.

| | |
|---|---|
| Architecture | [YOLO11n](https://docs.ultralytics.com/models/yolo11/) (Ultralytics) |
| Task | Object detection, one class: `coconut_tree` |
| Input | 1 × 3 × 640 × 640, RGB, scaled to 0–1 |
| Output | 1 × 5 × 8400 (box centre x, y, width, height, confidence) |
| Format | ONNX (FP32, static batch 1, exported without NMS) |
| Trained with | Ultralytics 8.3.121 |

The service runs it with onnxruntime (`src/utils/detector.py`), which
reproduces Ultralytics' pre- and post-processing (confidence 0.25, NMS IoU 0.7).

## License

YOLO11 and its pretrained weights are released by Ultralytics under the
**GNU Affero General Public License v3.0 (AGPL-3.0)**, and this model was trained
from them. The weights in this directory are therefore licensed under
**AGPL-3.0**; the full text is in [LICENSE](LICENSE). The model file's own
metadata records the same license.

This applies only to the model weights. The rest of the repository is MIT
licensed (see the root [LICENSE](../LICENSE)).

Using these weights in a network service, as Cocolit does, means offering that
service's corresponding source under AGPL-3.0 terms; this repository is public
for that reason. For use without AGPL-3.0 obligations, Ultralytics offers an
[Enterprise License](https://www.ultralytics.com/license).
