"""
tests/test_api_server.py

Unit tests for api/server.py covering:
  - _verify_razorpay_signature: valid, invalid, missing secret, tampered
  - FastAPI endpoints via TestClient (requires httpx + fastapi):
      POST /api/v1/internal/ingest   → 201 ACCEPTED
      GET  /api/v1/fleet-routing-hazards → 401 without key, 200 with key
      POST /api/v1/webhook/razorpay  → 400 invalid sig, 400 missing fields,
                                       200 valid sig
"""
import sys
import os
import hashlib
import hmac

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from api.server import _verify_razorpay_signature


# ---------------------------------------------------------------------------
# _verify_razorpay_signature
# ---------------------------------------------------------------------------

class TestVerifyRazorpaySignature:

    def _sign(self, order_id: str, payment_id: str, secret: str) -> str:
        msg = f"{order_id}|{payment_id}".encode()
        return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

    def test_valid_signature_returns_true(self):
        secret = "test_secret_abc"
        order_id = "order_12345"
        payment_id = "pay_67890"
        sig = self._sign(order_id, payment_id, secret)
        assert _verify_razorpay_signature(order_id, payment_id, sig, secret) is True

    def test_invalid_signature_returns_false(self):
        assert _verify_razorpay_signature(
            "order_1", "pay_1", "badhex000000000000000000000000000000000000000000000000000000000000",
            "real_secret"
        ) is False

    def test_empty_secret_returns_false(self):
        assert _verify_razorpay_signature("order_1", "pay_1", "anysig", "") is False

    def test_wrong_order_id_fails(self):
        secret = "secret"
        sig = self._sign("order_A", "pay_1", secret)
        assert _verify_razorpay_signature("order_B", "pay_1", sig, secret) is False

    def test_wrong_payment_id_fails(self):
        secret = "secret"
        sig = self._sign("order_1", "pay_A", secret)
        assert _verify_razorpay_signature("order_1", "pay_B", sig, secret) is False

    def test_tampered_signature_single_byte_fails(self):
        secret = "secret_key"
        order_id = "order_x"
        payment_id = "pay_y"
        sig = self._sign(order_id, payment_id, secret)
        # Flip the last hex character
        tampered = sig[:-1] + ("0" if sig[-1] != "0" else "1")
        assert _verify_razorpay_signature(order_id, payment_id, tampered, secret) is False

    def test_signature_is_case_sensitive(self):
        secret = "s3cr3t"
        order_id = "ord_1"
        payment_id = "pay_2"
        sig = self._sign(order_id, payment_id, secret)
        assert _verify_razorpay_signature(order_id, payment_id, sig.upper(), secret) is False


# ---------------------------------------------------------------------------
# FastAPI endpoint tests via TestClient
# ---------------------------------------------------------------------------

try:
    from fastapi.testclient import TestClient
    from api.server import create_app
    FASTAPI_AVAILABLE = True
except (ImportError, Exception):
    FASTAPI_AVAILABLE = False

skip_if_no_fastapi = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="fastapi / httpx not installed"
)


def _make_app(fleet_api_keys="test_key_123", razorpay_secret="razorpay_secret_xyz"):
    """Create a TestClient with patched env vars."""
    import importlib
    import api.server as srv_module

    # Patch the module-level config variables
    original_fleet = srv_module._FLEET_API_KEYS
    original_secret = srv_module._RAZORPAY_SECRET

    srv_module._FLEET_API_KEYS = set(fleet_api_keys.split(",")) if fleet_api_keys else set()
    srv_module._RAZORPAY_SECRET = razorpay_secret

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # Restore original values
    srv_module._FLEET_API_KEYS = original_fleet
    srv_module._RAZORPAY_SECRET = original_secret

    return client, app, razorpay_secret


# --- POST /api/v1/internal/ingest ---

@skip_if_no_fastapi
class TestIngestEndpoint:

    def test_valid_payload_returns_201(self):
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "truck_01",
            "event_type": "vision_detection",
            "hazard_class": "pothole",
            "confidence": 0.87,
            "gps_lat": 13.0827,
            "gps_lon": 80.2707,
            "timestamp": 1700000000.0,
        })
        assert resp.status_code == 201

    def test_response_contains_status_accepted(self):
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "bike_02",
            "event_type": "imu_spike",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ACCEPTED"

    def test_response_echoes_node_id(self):
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "bus_99",
            "event_type": "near_miss",
        })
        assert resp.json()["node_id"] == "bus_99"

    def test_response_echoes_event_type(self):
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "n1",
            "event_type": "pothole_detected",
        })
        assert resp.json()["event_type"] == "pothole_detected"

    def test_missing_node_id_returns_422(self):
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "event_type": "vision_detection",
        })
        assert resp.status_code == 422

    def test_optional_fields_accepted(self):
        """node_id + event_type are mandatory; all others are optional."""
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "n1",
            "event_type": "test",
            # No hazard_class, confidence, gps_lat, gps_lon, timestamp
        })
        assert resp.status_code == 201

    def test_confidence_out_of_range_returns_422(self):
        """confidence must be in [0.0, 1.0]."""
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "n1",
            "event_type": "vision",
            "confidence": 1.5,   # > 1.0
        })
        assert resp.status_code == 422

    def test_response_has_server_epoch_ms(self):
        client, app, _ = _make_app()
        resp = client.post("/api/v1/internal/ingest", json={
            "node_id": "n1",
            "event_type": "x",
        })
        data = resp.json()
        assert "server_epoch_ms" in data
        assert isinstance(data["server_epoch_ms"], int)


# --- GET /api/v1/fleet-routing-hazards ---

@skip_if_no_fastapi
class TestFleetRoutingEndpoint:

    def test_no_api_key_returns_401(self):
        client, app, _ = _make_app()
        resp = client.get("/api/v1/fleet-routing-hazards")
        assert resp.status_code == 401

    def test_wrong_api_key_returns_401(self):
        client, app, _ = _make_app(fleet_api_keys="valid_key")
        resp = client.get(
            "/api/v1/fleet-routing-hazards",
            headers={"X-API-Key": "wrong_key"},
        )
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        import api.server as srv
        original = srv._FLEET_API_KEYS
        srv._FLEET_API_KEYS = {"valid_key"}
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/fleet-routing-hazards",
                headers={"X-API-Key": "valid_key"},
            )
        finally:
            srv._FLEET_API_KEYS = original
        assert resp.status_code == 200

    def test_valid_key_response_has_hazards_list(self):
        import api.server as srv
        original = srv._FLEET_API_KEYS
        srv._FLEET_API_KEYS = {"the_key"}
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/api/v1/fleet-routing-hazards",
                headers={"X-API-Key": "the_key"},
            )
        finally:
            srv._FLEET_API_KEYS = original
        assert "hazards" in resp.json()


# --- POST /api/v1/webhook/razorpay ---

@skip_if_no_fastapi
class TestRazorpayWebhookEndpoint:

    def _sign(self, order_id: str, payment_id: str, secret: str) -> str:
        msg = f"{order_id}|{payment_id}".encode()
        return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

    def test_valid_signature_returns_200(self):
        secret = "razorpay_secret_xyz"
        import api.server as srv
        original = srv._RAZORPAY_SECRET
        srv._RAZORPAY_SECRET = secret
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            order_id = "order_abc"
            payment_id = "pay_def"
            sig = self._sign(order_id, payment_id, secret)
            resp = client.post("/api/v1/webhook/razorpay", json={
                "razorpay_payment_id": payment_id,
                "razorpay_order_id": order_id,
                "razorpay_signature": sig,
            })
        finally:
            srv._RAZORPAY_SECRET = original
        assert resp.status_code == 200

    def test_valid_signature_response_has_payment_verified(self):
        secret = "secret_abc"
        import api.server as srv
        original = srv._RAZORPAY_SECRET
        srv._RAZORPAY_SECRET = secret
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            order_id = "order_1"
            payment_id = "pay_1"
            sig = self._sign(order_id, payment_id, secret)
            resp = client.post("/api/v1/webhook/razorpay", json={
                "razorpay_payment_id": payment_id,
                "razorpay_order_id": order_id,
                "razorpay_signature": sig,
            })
        finally:
            srv._RAZORPAY_SECRET = original
        assert resp.json()["status"] == "PAYMENT_VERIFIED"

    def test_invalid_signature_returns_400(self):
        import api.server as srv
        original = srv._RAZORPAY_SECRET
        srv._RAZORPAY_SECRET = "real_secret"
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/v1/webhook/razorpay", json={
                "razorpay_payment_id": "pay_1",
                "razorpay_order_id": "order_1",
                "razorpay_signature": "0" * 64,  # wrong sig
            })
        finally:
            srv._RAZORPAY_SECRET = original
        assert resp.status_code == 400

    def test_missing_payment_id_returns_400(self):
        import api.server as srv
        original = srv._RAZORPAY_SECRET
        srv._RAZORPAY_SECRET = "secret"
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/v1/webhook/razorpay", json={
                "razorpay_order_id": "order_1",
                "razorpay_signature": "sig",
            })
        finally:
            srv._RAZORPAY_SECRET = original
        assert resp.status_code in (400, 422)

    def test_missing_order_id_returns_400(self):
        import api.server as srv
        original = srv._RAZORPAY_SECRET
        srv._RAZORPAY_SECRET = "secret"
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/v1/webhook/razorpay", json={
                "razorpay_payment_id": "pay_1",
                "razorpay_signature": "sig",
            })
        finally:
            srv._RAZORPAY_SECRET = original
        assert resp.status_code in (400, 422)

    def test_missing_signature_field_returns_400(self):
        import api.server as srv
        original = srv._RAZORPAY_SECRET
        srv._RAZORPAY_SECRET = "secret"
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/v1/webhook/razorpay", json={
                "razorpay_payment_id": "pay_1",
                "razorpay_order_id": "order_1",
                # No razorpay_signature
            })
        finally:
            srv._RAZORPAY_SECRET = original
        assert resp.status_code == 400
