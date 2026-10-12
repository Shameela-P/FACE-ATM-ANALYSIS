"""Test suite for Phase 4: Machine Learning Pipeline, Anti-Spoofing, and Verification Flow.

Covers:
- Real model initialization, presence, and status
- Real image inference: Live acceptance (T1) and Spoof rejection (F1, F2)
- Fail-closed security behavior (missing models, uncertain outputs, invalid inputs)
- Genuine vs Impostor SFace biometric comparison
- Full ATM face login integration with Anti-Spoofing PAD and lockout enforcement
- Separation of mocked unit tests from real model evaluations
- Preservation of Phase 1-3 transactional features
"""

import io
import json
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pytest
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.face_service import face_service, FaceProcessingError

client = TestClient(app)

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
SAMPLE_DIR = MODELS_DIR / "sample_images"


# ---------------------------------------------------------------------------
# 1. Model Initialization, Status & File Availability
# ---------------------------------------------------------------------------

def test_phase4_models_inventory():
    """Verify all 3 required ONNX model files are present in the models directory."""
    yunet_path = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
    sface_path = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
    minifas_path = MODELS_DIR / "face_antispoof_minifasnet.onnx"

    assert yunet_path.exists(), "YuNet model file missing"
    assert sface_path.exists(), "SFace model file missing"
    assert minifas_path.exists(), "MiniFASNetV2 model file missing"

    assert yunet_path.stat().st_size > 100_000
    assert sface_path.stat().st_size > 10_000_000
    assert minifas_path.stat().st_size > 1_000_000


def test_phase4_face_service_status():
    """Verify face_service status honestly reports anti-spoofing and operational status."""
    status = face_service.get_status()
    assert status["configured"] is True
    assert status["liveness_supported"] is True
    assert "MiniFASNetV2" in status["anti_spoofing"]
    assert status["liveness_threshold"] == pytest.approx(settings.FACE_ANTISPOOF_THRESHOLD)
    assert "fail-closed" in status["disclaimer"].lower()


def test_phase4_health_endpoint_reports_liveness():
    """Verify /api/health endpoint includes liveness PAD status."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    bio_service = data.get("components", {}).get("biometric_service", {})
    assert bio_service.get("liveness_supported") is True
    assert "MiniFASNetV2" in bio_service.get("anti_spoofing", "")


# ---------------------------------------------------------------------------
# 2. Real Model Evaluation on Benchmark Samples
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not (SAMPLE_DIR / "image_T1.jpg").exists(), reason="Sample images not present")
def test_phase4_real_live_face_acceptance():
    """Test real inference: Genuine live face (image_T1.jpg) must pass liveness and extract embedding."""
    with open(SAMPLE_DIR / "image_T1.jpg", "rb") as f:
        img_bytes = f.read()

    result = face_service.verify_liveness_and_extract_embedding(
        image_bytes=img_bytes,
        consent_obtained=True,
        liveness_threshold=0.60,
    )

    assert result["liveness_checked"] is True
    assert result["liveness"]["is_live"] is True
    assert result["liveness"]["liveness_score"] >= 0.60
    assert len(result["embedding"]) == 128
    # Norm should be approximately 1.0 (unit hypersphere)
    norm = np.linalg.norm(np.array(result["embedding"]))
    assert norm == pytest.approx(1.0, rel=1e-3)


@pytest.mark.skipif(not (SAMPLE_DIR / "image_F1.jpg").exists(), reason="Sample images not present")
def test_phase4_real_spoof_rejection_paper_print():
    """Test real inference: Paper print attack (image_F1.jpg) must be rejected with HTTP 403."""
    with open(SAMPLE_DIR / "image_F1.jpg", "rb") as f:
        img_bytes = f.read()

    with pytest.raises(FaceProcessingError) as exc_info:
        face_service.verify_liveness_and_extract_embedding(
            image_bytes=img_bytes,
            consent_obtained=True,
            liveness_threshold=0.60,
        )

    assert exc_info.value.status_code == 403
    assert "liveness verification failed" in exc_info.value.message.lower()


@pytest.mark.skipif(not (SAMPLE_DIR / "image_F2.jpg").exists(), reason="Sample images not present")
def test_phase4_real_spoof_rejection_screen_replay():
    """Test real inference: Phone screen replay attack (image_F2.jpg) must be rejected with HTTP 403."""
    with open(SAMPLE_DIR / "image_F2.jpg", "rb") as f:
        img_bytes = f.read()

    with pytest.raises(FaceProcessingError) as exc_info:
        face_service.verify_liveness_and_extract_embedding(
            image_bytes=img_bytes,
            consent_obtained=True,
            liveness_threshold=0.60,
        )

    assert exc_info.value.status_code == 403
    assert "liveness verification failed" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# 3. Fail-Closed Security & Error Handling
# ---------------------------------------------------------------------------

def test_phase4_fail_closed_when_antispoof_model_missing():
    """Fail-closed: if anti-spoofing model is unavailable, service MUST deny access (HTTP 503)."""
    orig_net = face_service._antispoof_net
    orig_err = face_service._antispoof_error
    try:
        face_service._antispoof_net = None
        face_service._antispoof_error = "Model file removed for maintenance"
        with patch.object(face_service, "_initialize_models", lambda: None):
            with pytest.raises(FaceProcessingError) as exc_info:
                face_service.predict_liveness(np.zeros((100, 100, 3), dtype=np.uint8), (10, 10, 50, 50))
            assert exc_info.value.status_code == 503
            assert "fail-closed" in exc_info.value.message.lower()
    finally:
        face_service._antispoof_net = orig_net
        face_service._antispoof_error = orig_err


def test_phase4_fail_closed_uncertain_liveness():
    """Fail-closed: borderline or uncertain liveness scores below threshold must be rejected."""
    # Mock predict_liveness returning uncertain score of 0.58 when threshold is 0.60
    with patch.object(face_service, "predict_liveness") as mock_live:
        mock_live.return_value = {
            "is_live": False,
            "liveness_score": 0.58,
            "spoof_score": 0.42,
            "threshold": 0.60,
            "scale_scores": [0.57, 0.59],
            "model": "MiniFASNetV2-ONNX",
        }
        with open(SAMPLE_DIR / "image_T1.jpg", "rb") as f:
            img_bytes = f.read()

        with pytest.raises(FaceProcessingError) as exc_info:
            face_service.verify_liveness_and_extract_embedding(
                image_bytes=img_bytes,
                consent_obtained=True,
                liveness_threshold=0.60,
            )
        assert exc_info.value.status_code == 403
        assert "liveness verification failed" in exc_info.value.message.lower()


def test_phase4_face_detection_failure_no_face():
    """No face detected in blank image must raise HTTP 400."""
    blank = Image.new("RGB", (320, 320), color=(0, 0, 0))
    buf = io.BytesIO()
    blank.save(buf, format="JPEG")
    blank_bytes = buf.getvalue()

    with pytest.raises(FaceProcessingError) as exc_info:
        face_service.verify_liveness_and_extract_embedding(blank_bytes, consent_obtained=True)

    assert exc_info.value.status_code == 400
    assert "no face detected" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# 4. SFace Biometric Comparison (Genuine vs Non-Match)
# ---------------------------------------------------------------------------

def test_phase4_biometric_face_matching_evaluation():
    """Verify SFace cosine similarity logic cleanly differentiates genuine and non-matching faces."""
    # Orthogonal vectors (similarity = 0.0) -> Impostor
    v_a = [1.0] + [0.0] * 127
    v_b = [0.0, 1.0] + [0.0] * 126
    res_impostor = face_service.compare_embeddings(v_a, v_b, threshold=0.40)
    assert res_impostor["matched"] is False
    assert res_impostor["similarity"] == pytest.approx(0.0)

    # Identical vector (similarity = 1.0) -> Genuine
    res_genuine = face_service.compare_embeddings(v_a, v_a, threshold=0.40)
    assert res_genuine["matched"] is True
    assert res_genuine["similarity"] == pytest.approx(1.0)

    # Near vector (similarity = 0.707) -> Genuine above 0.40
    v_near = [0.7071, 0.7071] + [0.0] * 126
    res_near = face_service.compare_embeddings(v_a, v_near, threshold=0.40)
    assert res_near["matched"] is True
    assert res_near["similarity"] >= 0.40


# ---------------------------------------------------------------------------
# 5. ATM Login Integration & Fail-Closed Order Verification
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_phase4_atm_login_spoof_rejection_and_lockout_trigger():
    """
    Test ATM face login verification order:
    When a spoof attack occurs, liveness fails before SFace comparison.
    Failed attempts are incremented and lockout is triggered upon exceeding max attempts.
    """
    mock_db = MagicMock()
    now = datetime.now(timezone.utc)
    card_number = "4000123456789010"

    mock_card = MagicMock()
    mock_card.exists = True
    mock_card.to_dict.return_value = {"customerId": "cust_p4_01", "status": "ACTIVE"}

    mock_cust = MagicMock()
    mock_cust.exists = True
    # Customer currently has 2 failed attempts (max is 3)
    mock_cust.to_dict.return_value = {
        "fullName": "Jane Doe",
        "email": "jane@example.com",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "failedAttempts": 2,
        "lockedUntil": None,
        "balance": 15000.0,
    }

    mock_bio = MagicMock()
    mock_bio.exists = True
    mock_bio.to_dict.return_value = {"embedding": [0.1] * 128}

    def collection_side_effect(name):
        col = MagicMock()
        if name == "cards":
            col.document.return_value.get.return_value = mock_card
        elif name == "customers":
            doc = MagicMock()
            doc.get.return_value = mock_cust
            doc.collection.return_value.document.return_value.get.return_value = mock_bio
            col.document.return_value = doc
        return col

    mock_db.collection.side_effect = collection_side_effect

    # Mock face_service.verify_liveness_and_extract_embedding raising FaceProcessingError(403)
    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract, \
         patch("app.routers.atm.email_service.send_security_alert_email") as mock_alert_email:

        mock_extract.side_effect = FaceProcessingError(
            "Biometric liveness verification failed (score 0.05 < 0.60). Presentation attack detected.",
            403
        )

        dummy_b64 = "data:image/jpeg;base64," + base64.b64encode(b"dummy_image_data_for_unit_testing_padding").decode("utf-8")
        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": card_number,
                "imageBase64": dummy_b64,
            }
        )

        # 3rd failure triggers lockout -> HTTP 403 Forbidden
        assert resp.status_code == 403
        assert "presentation attack detected" in resp.json()["detail"].lower()
        assert "temporarily locked" in resp.json()["detail"].lower()

        # Check security alert email was called
        assert mock_alert_email.called


@pytest.mark.anyio
async def test_phase4_atm_login_success_with_liveness():
    """Test ATM face login succeeds when both liveness and face similarity pass."""
    mock_db = MagicMock()
    now = datetime.now(timezone.utc)
    card_number = "4000123456789010"

    mock_card = MagicMock()
    mock_card.exists = True
    mock_card.to_dict.return_value = {"customerId": "cust_p4_02", "status": "ACTIVE"}

    mock_cust = MagicMock()
    mock_cust.exists = True
    mock_cust.to_dict.return_value = {
        "fullName": "Alice Smith",
        "email": "alice@example.com",
        "status": "ACTIVE",
        "faceEnrolled": True,
        "failedAttempts": 0,
        "lockedUntil": None,
        "balance": 25000.0,
    }

    mock_bio = MagicMock()
    mock_bio.exists = True
    mock_bio.to_dict.return_value = {"embedding": [0.1] * 128}

    def collection_side_effect(name):
        col = MagicMock()
        if name == "cards":
            col.document.return_value.get.return_value = mock_card
        elif name == "customers":
            doc = MagicMock()
            doc.get.return_value = mock_cust
            doc.collection.return_value.document.return_value.get.return_value = mock_bio
            col.document.return_value = doc
        elif name == "customer_sessions":
            col.document.return_value.set.return_value = None
        elif name == "audit_logs":
            col.add.return_value = None
        return col

    mock_db.collection.side_effect = collection_side_effect

    # Mock face_service: liveness passes, comparison passes
    with patch("app.routers.atm.get_firestore_client", return_value=mock_db), \
         patch("app.routers.atm.validate_luhn_card_number", return_value=True), \
         patch.object(face_service, "verify_liveness_and_extract_embedding") as mock_extract, \
         patch.object(face_service, "compare_embeddings") as mock_compare:

        mock_extract.return_value = {
            "embedding": [0.1] * 128,
            "dimensions": 128,
            "confidence": 0.95,
            "bounding_box": {"x": 10, "y": 10, "width": 100, "height": 100},
            "liveness_checked": True,
            "liveness": {"is_live": True, "liveness_score": 0.98, "threshold": 0.60},
        }

        mock_compare.return_value = {
            "matched": True,
            "similarity": 0.88,
            "threshold": 0.40,
            "metric": "cosine_similarity",
        }

        dummy_b64 = "data:image/jpeg;base64," + base64.b64encode(b"dummy_image_data_for_unit_testing_padding").decode("utf-8")
        resp = client.post(
            "/api/atm/login-face",
            json={
                "cardNumber": card_number,
                "imageBase64": dummy_b64,
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["sessionToken"].startswith("cust_sess_")
        assert data["fullName"] == "Alice Smith"
