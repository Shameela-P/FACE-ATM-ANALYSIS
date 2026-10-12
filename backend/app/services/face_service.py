"""Biometric face detection, quality assessment, and embedding extraction service.

Uses OpenCV YuNet (MIT license) for face detection and OpenCV SFace (Apache-2.0 license)
for 128-dimensional normalized facial embedding generation.
Enforces strict biometric data minimization: raw customer images are never stored.
"""

import io
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from PIL import Image, ImageOps
import cv2

from app.core.config import settings

logger = logging.getLogger("face_atm.face_service")


class FaceProcessingError(Exception):
    """Custom exception for face processing and validation errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FaceBiometricService:
    """Biometric facial detection and feature embedding engine."""

    def __init__(self):
        self._models_dir = settings.resolve_face_models_dir()
        self._detector_path = self._models_dir / "face_detection_yunet_2023mar.onnx"
        self._recognizer_path = self._models_dir / "face_recognition_sface_2021dec.onnx"
        self._antispoof_path = self._models_dir / "face_antispoof_minifasnet.onnx"
        self._detector: Optional[cv2.FaceDetectorYN] = None
        self._recognizer: Optional[cv2.FaceRecognizerSF] = None
        self._antispoof_net: Optional[cv2.dnn.Net] = None
        self._init_error: Optional[str] = None
        self._antispoof_error: Optional[str] = None
        self._initialize_models()

    def _initialize_models(self):
        """Lazily initialize ONNX models if available on disk."""
        if not self._detector_path.exists():
            self._init_error = f"Detection model file not found at: {self._detector_path.name}"
            logger.warning("Face detector model missing: %s", self._detector_path)
            return

        if not self._recognizer_path.exists():
            self._init_error = f"Recognition model file not found at: {self._recognizer_path.name}"
            logger.warning("Face recognizer model missing: %s", self._recognizer_path)
            return

        try:
            # YuNet face detector initialization with default (320, 320) buffer
            self._detector = cv2.FaceDetectorYN.create(
                model=str(self._detector_path),
                config="",
                input_size=(320, 320),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000,
            )

            # SFace face embedding model initialization
            self._recognizer = cv2.FaceRecognizerSF.create(
                model=str(self._recognizer_path),
                config="",
            )
            self._init_error = None
            logger.info("Face detector (YuNet) and recognizer (SFace) successfully initialized.")
        except Exception as exc:
            self._init_error = f"Failed to initialize face models: {exc}"
            logger.error("%s", self._init_error)
            self._detector = None
            self._recognizer = None

        # MiniFASNetV2 anti-spoofing model initialization
        if self._antispoof_path.exists():
            try:
                self._antispoof_net = cv2.dnn.readNetFromONNX(str(self._antispoof_path))
                self._antispoof_error = None
                logger.info("Anti-spoofing model (MiniFASNetV2) successfully initialized.")
            except Exception as exc:
                self._antispoof_error = f"Failed to initialize anti-spoofing model: {exc}"
                logger.error("%s", self._antispoof_error)
                self._antispoof_net = None
        else:
            self._antispoof_error = f"Anti-spoofing model file not found at: {self._antispoof_path.name}"
            self._antispoof_net = None
            logger.warning("Anti-spoofing model missing: %s", self._antispoof_path)

    @property
    def is_configured(self) -> bool:
        """Check if both detector and recognizer models are properly loaded."""
        return self._detector is not None and self._recognizer is not None

    @property
    def is_liveness_configured(self) -> bool:
        """Check if anti-spoofing model is loaded and available."""
        return self._antispoof_net is not None

    def get_status(self) -> Dict[str, Any]:
        """Safe non-sensitive status report for health and monitoring endpoints."""
        return {
            "configured": self.is_configured and self.is_liveness_configured,
            "detector": "YuNet (ONNX)",
            "recognizer": "SFace (128-dim ONNX)",
            "anti_spoofing": "MiniFASNetV2 (ONNX)" if self.is_liveness_configured else "Not loaded",
            "models_directory": str(self._models_dir),
            "status_detail": "operational" if (self.is_configured and self.is_liveness_configured) else (
                self._init_error or self._antispoof_error or "Models not loaded"
            ),
            "liveness_supported": self.is_liveness_configured,
            "liveness_threshold": settings.FACE_ANTISPOOF_THRESHOLD,
            "disclaimer": "Webcam RGB presentation attack detection (PAD) is enabled. Mitigates common 2D print and screen replay attacks. Complies with fail-closed security policy.",
        }

    def decode_image_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Decode image bytes (JPEG, PNG, WebP) into BGR numpy array with EXIF orientation correction."""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            # Correct orientation according to EXIF metadata (essential for smartphone & webcam portraits)
            image = ImageOps.exif_transpose(image)
            # Convert to RGB mode if RGBA or Grayscale
            if image.mode != "RGB":
                image = image.convert("RGB")
            # Convert RGB PIL image to BGR numpy array for OpenCV
            rgb_arr = np.array(image)
            bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
            return bgr_arr
        except Exception as exc:
            logger.warning("Image decoding failed: %s", exc)
            raise FaceProcessingError("Invalid image file format. Please submit a valid JPEG, PNG, or WebP photo.", 400)

    def detect_face_presence(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Fast lightweight face presence check using existing YuNet detector.
        Provides instant camera feedback when face is hidden, obscured, or turned away.
        Does not extract embedding or verify identity.
        """
        if not self.is_configured:
            self._initialize_models()

        if not self.is_configured:
            return {
                "recognizable": False,
                "message": "Face Not Recognizable — Please show your full face to the camera.",
            }

        try:
            img = self.decode_image_bytes(image_bytes)
            height, width = img.shape[:2]
            if width < 120 or height < 120:
                return {
                    "recognizable": False,
                    "message": "Face Not Recognizable — Please show your full face to the camera.",
                }

            self._detector.setInputSize((width, height))
            _, faces = self._detector.detect(img)

            if faces is None or len(faces) == 0:
                return {
                    "recognizable": False,
                    "message": "Face Not Recognizable — Please show your full face to the camera.",
                }

            if len(faces) > 1:
                return {
                    "recognizable": False,
                    "message": "Face Not Recognizable — Multiple faces detected in frame.",
                }

            face_data = faces[0]
            w, h = int(face_data[2]), int(face_data[3])
            confidence = float(face_data[-1])

            if confidence < 0.65 or w < 50 or h < 50:
                return {
                    "recognizable": False,
                    "message": "Face Not Recognizable — Please show your full face to the camera.",
                }

            return {
                "recognizable": True,
                "confidence": round(confidence, 4),
                "message": "Face detected — Please look directly at the camera.",
            }
        except Exception:
            return {
                "recognizable": False,
                "message": "Face Not Recognizable — Please show your full face to the camera.",
            }

    def predict_liveness(
        self,
        img_bgr: np.ndarray,
        face_box: Tuple[int, int, int, int] | List[int] | np.ndarray,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Anti-spoofing presentation attack detection using MiniFASNetV2.

        Evaluates contextual face crops across multiple bounding box expansion scales
        (1.2x and 1.5x) to detect screen replay, printed photographs, and physical presentation attacks.
        Returns live probability score and fail-closed determination.
        """
        if self._antispoof_net is None:
            self._initialize_models()

        if self._antispoof_net is None:
            detail = self._antispoof_error or "Anti-spoofing model weights are not loaded."
            logger.error("Anti-spoofing model unavailable: %s", detail)
            raise FaceProcessingError(
                f"Biometric anti-spoofing service unavailable: {detail}. Access denied (fail-closed).",
                503,
            )

        try:
            x, y, w, h = int(face_box[0]), int(face_box[1]), int(face_box[2]), int(face_box[3])
            img_h, img_w = img_bgr.shape[:2]

            if w <= 0 or h <= 0 or x >= img_w or y >= img_h:
                raise FaceProcessingError("Invalid facial bounding box geometry for liveness verification.", 400)

            # Evaluate multi-scale crops (1.2x and 1.5x context)
            scale_scores = []
            for scale in (1.2, 1.5):
                cx, cy = x + w / 2.0, y + h / 2.0
                nw, nh = w * scale, h * scale
                x1 = max(0, int(cx - nw / 2.0))
                y1 = max(0, int(cy - nh / 2.0))
                x2 = min(img_w, int(cx + nw / 2.0))
                y2 = min(img_h, int(cy + nh / 2.0))

                crop = img_bgr[y1:y2, x1:x2]
                if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
                    continue

                # MiniFASNet expects input blob (1, 3, 80, 80) in BGR [0, 255]
                blob = cv2.dnn.blobFromImage(
                    crop,
                    scalefactor=1.0,
                    size=(80, 80),
                    mean=(0, 0, 0),
                    swapRB=False,
                )
                self._antispoof_net.setInput(blob)
                logits = self._antispoof_net.forward()

                # Softmax across 3 classes: [Class 0: Spoof, Class 1: Real/Live, Class 2: Spoof]
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / np.sum(exp_logits)
                live_prob = float(probs[0][1])
                scale_scores.append(live_prob)

            if not scale_scores:
                raise FaceProcessingError("Failed to extract valid face crop for liveness verification.", 400)

            avg_liveness_score = float(np.mean(scale_scores))
            effective_threshold = float(
                threshold if threshold is not None else settings.FACE_ANTISPOOF_THRESHOLD
            )

            is_live = bool(avg_liveness_score >= effective_threshold)
            spoof_score = round(1.0 - avg_liveness_score, 4)

            return {
                "is_live": is_live,
                "liveness_score": round(avg_liveness_score, 4),
                "spoof_score": spoof_score,
                "threshold": effective_threshold,
                "scale_scores": [round(s, 4) for s in scale_scores],
                "model": "MiniFASNetV2-ONNX",
            }
        except FaceProcessingError:
            raise
        except Exception as exc:
            logger.error("Anti-spoofing inference error: %s", exc)
            raise FaceProcessingError(f"Liveness verification engine encountered an error: {exc}", 500)

    def verify_liveness_and_extract_embedding(
        self,
        image_bytes: bytes,
        consent_obtained: bool,
        liveness_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute full Phase 4 biometric verification pipeline in strict sequence:
        1. Verify explicit customer consent.
        2. Detect single face using YuNet ONNX.
        3. Execute Anti-Spoofing PAD check using MiniFASNetV2 (fail-closed).
        4. If liveness passes, extract 128-dim facial feature embedding using SFace ONNX.
        5. Return validated embedding and liveness metadata.
        """
        return self.process_and_extract_embedding(
            image_bytes=image_bytes,
            consent_obtained=consent_obtained,
            check_liveness=True,
            liveness_threshold=liveness_threshold,
        )

    def process_and_extract_embedding(
        self,
        image_bytes: bytes,
        consent_obtained: bool,
        check_liveness: bool = False,
        liveness_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Validate explicit consent, detect face, evaluate quality, optionally verify liveness,
        and extract 128-dim embedding.
        Raw image is immediately discarded and NEVER stored in persistent storage.
        """
        if not consent_obtained:
            raise FaceProcessingError(
                "Explicit customer consent is legally required before capturing or processing biometric face data.",
                400,
            )

        if not self.is_configured:
            # Re-attempt initialization in case models were downloaded recently
            self._initialize_models()

        if not self.is_configured:
            detail = self._init_error or "Face detection model is not configured."
            raise FaceProcessingError(
                f"Biometric processing service unavailable: {detail}. Please ensure model files are configured.",
                503,
            )

        # Decode image
        img = self.decode_image_bytes(image_bytes)
        height, width = img.shape[:2]

        if width < 120 or height < 120:
            raise FaceProcessingError("Image resolution is too low. Please capture a clear image of at least 160x160 pixels.", 400)

        # Configure detector with current image dimensions
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(img)

        if faces is None or len(faces) == 0:
            raise FaceProcessingError(
                "Face Not Recognizable — Please show your full face to the camera. No face detected in the captured image.",
                400,
            )

        if len(faces) > 1:
            raise FaceProcessingError(
                f"Face Not Recognizable — Multiple faces detected ({len(faces)}). Please ensure only the customer is visible in the camera frame.",
                400,
            )

        face_data = faces[0]
        # face_data format: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
        x, y, w, h = int(face_data[0]), int(face_data[1]), int(face_data[2]), int(face_data[3])
        confidence = float(face_data[-1])

        if confidence < 0.65:
            raise FaceProcessingError(
                f"Face Not Recognizable — Please show your full face to the camera. Face detection confidence ({confidence:.2f}) is too low.",
                400,
            )

        if w < 50 or h < 50:
            raise FaceProcessingError(
                "Face Not Recognizable — Please show your full face to the camera. Face is too small or obscured in the frame.",
                400,
            )

        # Pipeline Step 2: Anti-spoofing verification if requested
        liveness_result: Optional[Dict[str, Any]] = None
        if check_liveness:
            liveness_result = self.predict_liveness(
                img_bgr=img,
                face_box=(x, y, w, h),
                threshold=liveness_threshold,
            )
            if not liveness_result.get("is_live"):
                score = liveness_result.get("liveness_score", 0.0)
                thresh = liveness_result.get("threshold", 0.60)
                logger.warning("Spoof presentation attack rejected (score=%.4f, threshold=%.4f)", score, thresh)
                raise FaceProcessingError(
                    f"Biometric liveness verification failed (liveness score: {score:.2f} < {thresh:.2f}). Presentation attack (photo, screen replay, or paper print) detected.",
                    403,
                )

        # Pipeline Step 3: Align and crop face using facial landmarks
        try:
            aligned_face = self._recognizer.alignCrop(img, face_data)
            raw_feature = self._recognizer.feature(aligned_face)
            # Normalize embedding vector to unit length (L2 norm)
            vector = raw_feature[0]
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            embedding_list: List[float] = [round(float(v), 6) for v in vector]
        except Exception as exc:
            logger.error("Embedding extraction failed: %s", exc)
            raise FaceProcessingError("Failed to extract biometric features from face. Please capture another image.", 500)

        result_payload = {
            "embedding": embedding_list,
            "dimensions": len(embedding_list),
            "confidence": round(confidence, 4),
            "bounding_box": {"x": x, "y": y, "width": w, "height": h},
            "model": "SFace-v1-ONNX",
            "detector": "YuNet-v1-ONNX",
            "consent_obtained": True,
            "consent_timestamp": datetime.now(timezone.utc).isoformat(),
            "liveness_checked": bool(check_liveness),
        }
        if liveness_result:
            result_payload["liveness"] = liveness_result

        return result_payload

    def compare_embeddings(
        self,
        embedding1: List[float],
        embedding2: List[float],
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compare two 128-dimensional face embedding vectors using Cosine Similarity.
        
        SFace embeddings are normalized feature representations on a unit hypersphere.
        The cosine similarity is computed as the dot product: cos(theta) = v1 . v2 / (||v1|| * ||v2||).
        Higher similarity indicates a closer biometric match (range -1.0 to 1.0).
        OpenCV SFace recommended verification threshold is 0.363 - 0.40.
        Default configurable threshold is 0.40 (settings.FACE_MATCH_THRESHOLD).
        
        Returns:
            Dict containing matched (bool), similarity (float), and threshold (float).
        """
        if not embedding1 or not embedding2:
            raise FaceProcessingError("Both embeddings are required for biometric comparison.", 400)

        if len(embedding1) != 128 or len(embedding2) != 128:
            raise FaceProcessingError(
                f"Embedding vector dimension mismatch: expected 128 dimensions, "
                f"received ({len(embedding1)}, {len(embedding2)}).",
                400,
            )

        v1 = np.array(embedding1, dtype=np.float32)
        v2 = np.array(embedding2, dtype=np.float32)

        norm1 = float(np.linalg.norm(v1))
        norm2 = float(np.linalg.norm(v2))

        if norm1 <= 1e-7 or norm2 <= 1e-7:
            raise FaceProcessingError("Invalid zero-magnitude biometric embedding vector.", 400)

        v1 = v1 / norm1
        v2 = v2 / norm2

        similarity = float(np.dot(v1, v2))
        effective_threshold = float(
            threshold if threshold is not None else settings.FACE_MATCH_THRESHOLD
        )
        is_match = similarity >= effective_threshold

        return {
            "matched": bool(is_match),
            "similarity": round(similarity, 6),
            "threshold": effective_threshold,
            "metric": "cosine_similarity",
        }


# Global singleton face service instance
face_service = FaceBiometricService()

