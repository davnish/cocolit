"""YOLO detection with onnxruntime only (no ultralytics / torch).

Reproduces ultralytics' predict() for a 640x640 detect model exported with
nms=False: BGR->RGB, /255, CHW; then confidence filter + NMS on the raw
[1, 4 + classes, anchors] output. Inputs are already 640x640 patches, so the
letterbox step is a no-op and box coordinates need no rescaling.
"""

from dataclasses import dataclass
import os

import numpy as np
import onnxruntime as ort


@dataclass
class Detections:
    xywh: np.ndarray  # (n, 4) box centre/size in input pixels
    conf: np.ndarray  # (n,)
    cls: np.ndarray  # (n,)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> np.ndarray:
    """Greedy NMS on xyxy boxes; returns kept indices, highest score first."""
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        rest = order[1:]
        w = np.clip(np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]), 0, None)
        h = np.clip(np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]), 0, None)
        inter = w * h
        iou = inter / (areas[i] + areas[rest] - inter + 1e-9)
        order = rest[iou <= iou_threshold]
    return np.asarray(keep, dtype=np.int64)


class OnnxDetector:
    def __init__(
        self,
        model_path: str,
        conf: float = 0.25,
        iou: float = 0.7,
        max_det: int = 300,
        threads: int | None = None,
    ) -> None:
        opts = ort.SessionOptions()
        threads = threads or int(os.environ.get("ORT_THREADS", 0))
        if threads:
            opts.intra_op_num_threads = threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.size = inp.shape[2]
        self.conf = conf
        self.iou = iou
        self.max_det = max_det

    def preprocess(self, bgr: np.ndarray) -> np.ndarray:
        # HxWx3 uint8 BGR -> 1x3xHxW float32 RGB in [0, 1]
        rgb = bgr[..., ::-1].transpose(2, 0, 1)
        return np.ascontiguousarray(rgb, dtype=np.float32)[None] / 255.0

    def postprocess(self, output: np.ndarray) -> Detections:
        pred = output[0].T  # (anchors, 4 + classes)
        scores_all = pred[:, 4:]
        cls = scores_all.argmax(1)
        scores = scores_all[np.arange(len(pred)), cls]
        mask = scores > self.conf
        xywh, scores, cls = pred[mask, :4], scores[mask], cls[mask]
        if not len(scores):
            return Detections(np.empty((0, 4), np.float32), np.empty(0, np.float32), np.empty(0, np.int64))
        xyxy = np.concatenate([xywh[:, :2] - xywh[:, 2:] / 2, xywh[:, :2] + xywh[:, 2:] / 2], 1)
        # Offset boxes per class so NMS never suppresses across classes.
        offset = cls[:, None] * 7680.0
        keep = nms(xyxy + offset, scores, self.iou)[: self.max_det]
        # Like ultralytics' scale_boxes: clip to the image, then recompute centres.
        xyxy = np.clip(xyxy[keep], 0, self.size)
        xywh = np.concatenate([(xyxy[:, :2] + xyxy[:, 2:]) / 2, xyxy[:, 2:] - xyxy[:, :2]], 1)
        return Detections(xywh, scores[keep], cls[keep])

    def __call__(self, bgr: np.ndarray) -> Detections:
        output = self.session.run(None, {self.input_name: self.preprocess(bgr)})[0]
        return self.postprocess(output)
