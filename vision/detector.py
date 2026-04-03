"""
NagarDrishti — Vision Engine
detector.py — v3 (Threaded Inference — Zero Lag)

Architecture:
    Main thread   → reads camera + displays frames at full FPS (no blocking)
    Worker thread → runs YOLO inference in background, updates shared result

This eliminates ALL display lag regardless of how slow inference is.
"""

import cv2
import time
import base64
import os
import glob
import threading
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from huggingface_hub import snapshot_download
from ultralytics import YOLO


# ── Constants ─────────────────────────────────────────────────────────────────
MODEL_REPO                   = "aarmstrkk/Road_Cracks_Pothole_Detection"
POTHOLE_HIGH_ALERT_THRESHOLD = 0.40
CLASS_NAMES                  = {0: "crack", 1: "pothole"}
INFERENCE_SIZE               = 320    # smaller = faster inference on CPU

SEVERITY_MAP = {
    1: {"label": "Safe",       "color": (0, 200, 0)},
    2: {"label": "Risky",      "color": (0, 165, 255)},
    3: {"label": "High Alert", "color": (0, 0, 255)},
}


# ── Camera Source Config ──────────────────────────────────────────────────────
class CameraSource:
    @staticmethod
    def local(index: int = 0) -> dict:
        return {"type": "local", "source": index}

    @staticmethod
    def remote(url: str) -> dict:
        return {"type": "remote", "source": url}

    @staticmethod
    def select_from_terminal() -> dict:
        print("\n" + "=" * 50)
        print("  NagarDrishti — Camera Setup")
        print("=" * 50)
        print("  [1] Local Webcam (default laptop/USB cam)")
        print("  [2] Remote Camera (mobile/CCTV/IP cam)")
        print("=" * 50)

        choice = input("  Select mode (1 or 2): ").strip()

        if choice == "2":
            print("\n  Supported URLs:")
            print("  Android IP Webcam  → http://<phone-ip>:8080/video")
            print("  DroidCam           → http://<phone-ip>:4747/video")
            print("  RTSP CCTV          → rtsp://user:pass@<ip>:554/stream")
            url = input("\n  Enter stream URL: ").strip()
            return CameraSource.remote(url)
        else:
            idx = input("  Camera index (press Enter for 0): ").strip()
            return CameraSource.local(int(idx) if idx.isdigit() else 0)


# ── Result Container ──────────────────────────────────────────────────────────
@dataclass
class DetectionResult:
    severity_level : int
    severity_label : str
    severity_color : Tuple[int, int, int]
    confidence     : float
    pothole_count  : int
    crack_count    : int
    coverage_ratio : float
    annotated_frame: np.ndarray
    camera_source  : str = "unknown"
    raw_detections : List[dict] = field(default_factory=list)
    snapshot_b64   : Optional[str] = None


# ── Model Loader ──────────────────────────────────────────────────────────────
def load_model_from_hf() -> YOLO:
    print("[NagarDrishti] Loading model from HuggingFace cache...")
    local_dir  = snapshot_download(repo_id=MODEL_REPO)
    onnx_files = glob.glob(os.path.join(local_dir, "**/*.onnx"), recursive=True)
    if not onnx_files:
        raise FileNotFoundError(f"No .onnx file in {local_dir}")
    onnx_path = onnx_files[0]
    print(f"[NagarDrishti] Model ready: {os.path.basename(onnx_path)} ✓")
    return YOLO(onnx_path, task="detect")


# ── Severity Classifier ───────────────────────────────────────────────────────
def classify_severity(detections: List[dict]) -> Tuple[int, str, Tuple]:
    potholes = [d for d in detections if d["class"] == "pothole"]
    if not potholes:
        level = 1
    else:
        max_cov = max(d["coverage"] for d in potholes)
        level   = 3 if max_cov >= POTHOLE_HIGH_ALERT_THRESHOLD else 2
    s = SEVERITY_MAP[level]
    return level, s["label"], s["color"]


# ── Frame Annotator ───────────────────────────────────────────────────────────
def annotate_frame(frame, detections, level, label, color, cam_label="", fps=0) -> np.ndarray:
    out  = frame.copy()
    h, w = out.shape[:2]

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        c = (0, 180, 0) if det["class"] == "crack" else color
        cv2.rectangle(out, (x1, y1), (x2, y2), c, 2)
        cv2.putText(out, f"{det['class']} {det['conf']:.0%}",
                    (x1, max(y1 - 8, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2)

    # Top badge
    cv2.rectangle(out, (0, 0), (w, 42), color, -1)
    fps_txt = f"  {fps:.0f} FPS" if fps > 0 else ""
    cv2.putText(out, f"  LEVEL {level}  |  {label}  |  NagarDrishti{fps_txt}",
                (8, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    # Bottom stats
    pcount = sum(1 for d in detections if d["class"] == "pothole")
    ccount = sum(1 for d in detections if d["class"] == "crack")
    cov    = max((d["coverage"] for d in detections), default=0.0)
    for i, txt in enumerate([f"Coverage: {cov:.1%}", f"Potholes: {pcount}  Cracks: {ccount}"]):
        cv2.putText(out, txt, (10, h - 12 - i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return out


# ── Core Detector ─────────────────────────────────────────────────────────────
class PotholeDetector:

    def __init__(self, conf_threshold: float = 0.35):
        self.model = load_model_from_hf()
        self.conf  = conf_threshold

        # Shared state between main thread and inference thread
        self._lock          = threading.Lock()
        self._latest_frame  = None          # newest frame for inference
        self._latest_dets   = []            # most recent detection results
        self._latest_level  = 1
        self._latest_label  = "Safe"
        self._latest_color  = (0, 200, 0)
        self._running       = False

    def _open_camera(self, camera_config: dict) -> Tuple[cv2.VideoCapture, str]:
        source   = camera_config["source"]
        cam_type = camera_config["type"]
        print(f"[NagarDrishti] Connecting to {cam_type} camera: {source}")
        cap = cv2.VideoCapture(source)
        if cam_type == "local":
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not cap.isOpened():
            raise RuntimeError(
                f"Cannot open camera: {source}\n"
                "Remote camera tips:\n"
                "  - Phone and PC must be on same WiFi\n"
                "  - IP Webcam app must be running\n"
                "  - Check URL format: http://<ip>:8080/video"
            )
        label = f"[{source}]" if cam_type == "remote" else "[WEBCAM]"
        print(f"[NagarDrishti] Connected {label} ✓")
        return cap, label

    # ── Background inference thread ───────────────────────────────────────────

    def _inference_loop(self):
        """Runs in a background thread. Grabs the latest frame, runs YOLO,
        and stores results. The main thread never waits for this."""
        while self._running:
            # Grab the latest frame
            with self._lock:
                frame = self._latest_frame
            if frame is None:
                time.sleep(0.01)
                continue

            # Run inference on a small copy
            h, w = frame.shape[:2]
            scale = INFERENCE_SIZE / max(w, h)
            small = cv2.resize(frame, (int(w * scale), int(h * scale)))
            inf_h, inf_w = small.shape[:2]
            inf_area = inf_h * inf_w

            results = self.model(small, conf=self.conf, verbose=False)
            boxes   = results[0].boxes
            dets    = []

            if boxes is not None and len(boxes):
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf_val   = float(box.conf[0])
                    class_idx  = int(box.cls[0])
                    class_name = CLASS_NAMES.get(class_idx, f"cls_{class_idx}")
                    coverage   = ((x2 - x1) * (y2 - y1)) / inf_area

                    # Scale boxes back to original frame coords
                    inv = 1.0 / scale
                    dets.append({
                        "class": class_name, "conf": conf_val,
                        "bbox": (int(x1 * inv), int(y1 * inv),
                                 int(x2 * inv), int(y2 * inv)),
                        "coverage": coverage,
                    })

            level, label, color = classify_severity(dets)

            # Store results (main thread reads these)
            with self._lock:
                self._latest_dets  = dets
                self._latest_level = level
                self._latest_label = label
                self._latest_color = color

            # Small sleep to avoid burning CPU between inferences
            time.sleep(0.02)

    # ── Single frame analysis (for Streamlit / non-live use) ──────────────────

    def analyze_frame(
        self,
        frame: np.ndarray,
        capture_snapshot: bool = False,
        cam_label: str = "",
    ) -> DetectionResult:
        """Synchronous single-frame analysis (used by Streamlit tab)."""
        h, w = frame.shape[:2]
        scale = INFERENCE_SIZE / max(w, h)
        small = cv2.resize(frame, (int(w * scale), int(h * scale)))
        inf_h, inf_w = small.shape[:2]
        inf_area = inf_h * inf_w

        results    = self.model(small, conf=self.conf, verbose=False)
        boxes      = results[0].boxes
        detections = []

        if boxes is not None and len(boxes):
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf_val   = float(box.conf[0])
                class_idx  = int(box.cls[0])
                class_name = CLASS_NAMES.get(class_idx, f"cls_{class_idx}")
                coverage   = ((x2 - x1) * (y2 - y1)) / inf_area
                inv = 1.0 / scale
                detections.append({
                    "class": class_name, "conf": conf_val,
                    "bbox": (int(x1 * inv), int(y1 * inv),
                             int(x2 * inv), int(y2 * inv)),
                    "coverage": coverage,
                })

        level, label, color = classify_severity(detections)
        annotated = annotate_frame(frame, detections, level, label, color, cam_label)
        best_conf = max((d["conf"] for d in detections), default=0.0)

        result = DetectionResult(
            severity_level  = level,
            severity_label  = label,
            severity_color  = color,
            confidence      = best_conf,
            pothole_count   = sum(1 for d in detections if d["class"] == "pothole"),
            crack_count     = sum(1 for d in detections if d["class"] == "crack"),
            coverage_ratio  = max((d["coverage"] for d in detections), default=0.0),
            annotated_frame = annotated,
            camera_source   = cam_label,
            raw_detections  = detections,
        )

        if capture_snapshot and detections:
            _, buf = cv2.imencode(".jpg", annotated)
            result.snapshot_b64 = base64.b64encode(buf).decode("utf-8")

        return result

    # ── Live loop (main thread — never blocks) ────────────────────────────────

    def run_live(
        self,
        camera: dict = None,
        snapshot_callback=None,
        alert_cooldown: int = 10,
    ):
        if camera is None:
            camera = CameraSource.local(index=0)

        cap, cam_label = self._open_camera(camera)
        print("[NagarDrishti] 📷 Live — Q: quit | S: snapshot")
        print("[NagarDrishti] ⚡ Threaded inference — display runs at full FPS")

        # Start background inference thread
        self._running = True
        worker = threading.Thread(target=self._inference_loop, daemon=True)
        worker.start()

        last_alert_time = 0
        fps_timer       = time.time()
        fps_count       = 0
        display_fps     = 0.0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                # Feed frame to inference thread (non-blocking)
                with self._lock:
                    self._latest_frame = frame.copy()
                    dets  = list(self._latest_dets)
                    level = self._latest_level
                    label = self._latest_label
                    color = self._latest_color

                # FPS counter
                fps_count += 1
                now = time.time()
                if now - fps_timer >= 1.0:
                    display_fps = fps_count / (now - fps_timer)
                    fps_count   = 0
                    fps_timer   = now

                # Annotate current frame with latest detections (instant)
                display = annotate_frame(frame, dets, level, label, color,
                                         cam_label, fps=display_fps)
                cv2.imshow("NagarDrishti Vision Engine", display)

                # Auto-trigger agents on Level 2/3
                if level >= 2 and snapshot_callback:
                    if (now - last_alert_time) > alert_cooldown:
                        snap = self.analyze_frame(frame, capture_snapshot=True,
                                                  cam_label=cam_label)
                        print(f"[NagarDrishti] 🚨 Level {snap.severity_level} "
                              f"| {snap.severity_label}")
                        snapshot_callback(snap)
                        last_alert_time = now

                key = cv2.waitKey(1) & 0xFF
                if key == ord("s"):
                    snap = self.analyze_frame(frame, capture_snapshot=True,
                                              cam_label=cam_label)
                    print(f"[NagarDrishti] 📸 Level {snap.severity_level} | "
                          f"Potholes: {snap.pothole_count} | "
                          f"Cracks: {snap.crack_count}")
                    if snapshot_callback:
                        snapshot_callback(snap)

                if key == ord("q"):
                    break
                # Safe check for window X button on Windows
                try:
                    if cv2.getWindowProperty("NagarDrishti Vision Engine",
                                             cv2.WND_PROP_VISIBLE) < 1:
                        break
                except cv2.error:
                    break

        except KeyboardInterrupt:
            print("\n[NagarDrishti] Stopped by user.")
        finally:
            self._running = False
            worker.join(timeout=2)
            cap.release()
            cv2.destroyAllWindows()
            print("[NagarDrishti] Closed ✓")


# ── Quick Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    def mock_agent_callback(r: DetectionResult):
        print("\n" + "=" * 48)
        print(f"  Camera    : {r.camera_source}")
        print(f"  Severity  : Level {r.severity_level} — {r.severity_label}")
        print(f"  Potholes  : {r.pothole_count}")
        print(f"  Cracks    : {r.crack_count}")
        print(f"  Confidence: {r.confidence:.0%}")
        print(f"  Coverage  : {r.coverage_ratio:.1%}")
        print(f"  Snapshot  : {'✓ Ready' if r.snapshot_b64 else 'None'}")
        print("=" * 48 + "\n")

    camera   = CameraSource.select_from_terminal()
    detector = PotholeDetector(conf_threshold=0.35)
    detector.run_live(camera=camera, snapshot_callback=mock_agent_callback)
