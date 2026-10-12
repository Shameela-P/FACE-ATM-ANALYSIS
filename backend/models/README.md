# Model Directory & Biometric Pipeline Specifications

This directory contains the machine learning models and ONNX weight files executing the Face ATM Phase 4 biometric verification pipeline.

---

## 1. Pipeline Architecture

The face verification process executes strictly in three stages:

```
Camera Capture (Webcam BGR)
       │
       ▼
[ Stage 1: YuNet ONNX ] ──(No face / Multiple faces / Low confidence)──► REJECT (HTTP 400)
       │ (Face detected, box + landmarks)
       ▼
[ Stage 2: MiniFASNetV2 ONNX ] ──(Spoof / Uncertain / Missing model)──► REJECT & LOCKOUT (HTTP 403 / 503)
       │ (Liveness score >= 0.60)
       ▼
[ Stage 3: SFace ONNX ] ──(Cosine similarity < 0.40)──► REJECT & LOCKOUT (HTTP 401)
       │ (Cosine similarity >= 0.40)
       ▼
ACCESS GRANTED (Short-lived customer ATM session issued)
```

---

## 2. Model Inventory & Licensing

| Component | Model File | Framework | Size | License | Source Repository |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Face Detector** | `face_detection_yunet_2023mar.onnx` | OpenCV DNN / ONNX | 232 KB | MIT License | OpenCV Zoo (`opencv/opencv_zoo`) |
| **Anti-Spoofing (PAD)** | `face_antispoof_minifasnet.onnx` | OpenCV DNN / ONNX | 1.7 MB | Apache-2.0 License | Minivision AI (`minivision-ai/Silent-Face-Anti-Spoofing`) |
| **Face Recognizer** | `face_recognition_sface_2021dec.onnx` | OpenCV DNN / ONNX | 38.6 MB | Apache-2.0 License | OpenCV Zoo (`opencv/opencv_zoo`) |

---

## 3. Operational Requirements & Fail-Closed Guardrails

1. **Anti-Spoofing Preprocessing**:
   - Multi-scale context crops (1.2x and 1.5x of the YuNet face bounding box).
   - Resized to 80x80 BGR image tensor.
   - Forward pass produces 3 class logits: Class 0 (Spoof print), Class 1 (Real live face), Class 2 (Spoof screen replay).
   - Fail-closed threshold: Softmax probability for Class 1 must be `>= 0.60`.
2. **Face Matching Preprocessing**:
   - Landmark alignment via `cv2.FaceRecognizerSF.alignCrop`.
   - Feature extraction generates a 128-dimensional embedding vector normalized with L2 norm to the unit hypersphere.
   - Cosine similarity threshold: `>= 0.40`.
3. **Privacy & Security Constraints**:
   - Biometric data minimization: raw captured customer images are discarded immediately after in-memory inference.
   - Audit logs store only session metadata and boolean verification results. Raw embeddings and customer photos are NEVER logged or stored unencrypted.
