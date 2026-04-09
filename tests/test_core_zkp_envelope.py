"""
tests/test_core_zkp_envelope.py

Unit tests for core/zkp_envelope.py covering:
  - _coarsen: basic snapping, negative coords, exact boundaries, precision
  - _commitment_hash: format, determinism, salt sensitivity, length
  - coarsen_coordinate: tuple output, symmetry, rounding
  - wrap_event: gps_lat/gps_lon coarsened, commitment attached, auto-salt,
                explicit salt, in-place mutation, returns same object
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hashlib
import math
import pytest
from unittest.mock import MagicMock

from core.zkp_envelope import (
    _coarsen,
    _commitment_hash,
    wrap_event,
    coarsen_coordinate,
    _GRID_DEG,
    _SALT_BYTES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event():
    """Return a minimal mock object that mimics NearMissEvent GPS fields."""
    ev = MagicMock()
    ev.gps_lat = None
    ev.gps_lon = None
    return ev


# ---------------------------------------------------------------------------
# _coarsen
# ---------------------------------------------------------------------------

class TestCoarsen:

    def test_snaps_to_grid_floor(self):
        # 12.9245 / 0.005 = 2584.9 → floor = 2584 → 2584 * 0.005 = 12.920
        result = _coarsen(12.9245)
        assert math.isclose(result, 12.920, abs_tol=1e-9)

    def test_snaps_exact_grid_boundary(self):
        # 12.920 is exactly on the 0.005 grid
        result = _coarsen(12.920)
        assert math.isclose(result, 12.920, abs_tol=1e-9)

    def test_snaps_just_below_boundary(self):
        result = _coarsen(12.9249)
        assert math.isclose(result, 12.920, abs_tol=1e-9)

    def test_negative_coordinate(self):
        # -12.9245 → floor(-12.9245 / 0.005) * 0.005 = floor(-2584.9) * 0.005
        result = _coarsen(-12.9245)
        expected = math.floor(-12.9245 / _GRID_DEG) * _GRID_DEG
        assert math.isclose(result, expected, abs_tol=1e-9)

    def test_zero_coordinate(self):
        assert _coarsen(0.0) == 0.0

    def test_custom_grid(self):
        # With grid=0.1: 12.97 → floor(12.97 / 0.1) * 0.1 = 12.9
        result = _coarsen(12.97, grid=0.1)
        assert math.isclose(result, 12.9, abs_tol=1e-9)

    def test_large_coordinate(self):
        # Longitude 80.2301
        result = _coarsen(80.2301)
        expected = math.floor(80.2301 / _GRID_DEG) * _GRID_DEG
        assert math.isclose(result, expected, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# _commitment_hash
# ---------------------------------------------------------------------------

class TestCommitmentHash:

    def test_starts_with_sha3_prefix(self):
        salt = b"\x00" * 16
        h = _commitment_hash(12.9245, 80.2301, salt)
        assert h.startswith("sha3:")

    def test_hex_part_is_64_chars(self):
        salt = b"\x00" * 16
        h = _commitment_hash(12.9245, 80.2301, salt)
        hex_part = h[len("sha3:"):]
        assert len(hex_part) == 64

    def test_deterministic_same_inputs(self):
        salt = b"\xde\xad\xbe\xef" * 4
        h1 = _commitment_hash(12.9245, 80.2301, salt)
        h2 = _commitment_hash(12.9245, 80.2301, salt)
        assert h1 == h2

    def test_different_salt_different_hash(self):
        salt1 = b"\x01" * 16
        salt2 = b"\x02" * 16
        h1 = _commitment_hash(12.9245, 80.2301, salt1)
        h2 = _commitment_hash(12.9245, 80.2301, salt2)
        assert h1 != h2

    def test_different_lat_different_hash(self):
        salt = b"\x00" * 16
        h1 = _commitment_hash(12.9245, 80.2301, salt)
        h2 = _commitment_hash(12.9999, 80.2301, salt)
        assert h1 != h2

    def test_different_lon_different_hash(self):
        salt = b"\x00" * 16
        h1 = _commitment_hash(12.9245, 80.2301, salt)
        h2 = _commitment_hash(12.9245, 80.9999, salt)
        assert h1 != h2

    def test_verifiable_by_recomputation(self):
        """A verifier can reproduce the hash given raw_lat, raw_lon, and salt."""
        raw_lat, raw_lon = 12.924500, 80.230100
        salt = b"test_salt_value!"
        expected_payload = salt + f"{raw_lat:.6f},{raw_lon:.6f}".encode("utf-8")
        expected = "sha3:" + hashlib.sha3_256(expected_payload).hexdigest()
        assert _commitment_hash(raw_lat, raw_lon, salt) == expected


# ---------------------------------------------------------------------------
# coarsen_coordinate
# ---------------------------------------------------------------------------

class TestCoarsenCoordinate:

    def test_returns_tuple(self):
        result = coarsen_coordinate(12.9245, 80.2301)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_lat_coarsened(self):
        lat, lon = coarsen_coordinate(12.9245, 80.2301)
        assert lat == round(math.floor(12.9245 / _GRID_DEG) * _GRID_DEG, 3)

    def test_lon_coarsened(self):
        lat, lon = coarsen_coordinate(12.9245, 80.2301)
        assert lon == round(math.floor(80.2301 / _GRID_DEG) * _GRID_DEG, 3)

    def test_output_has_3_decimal_places(self):
        lat, lon = coarsen_coordinate(12.9245, 80.2301)
        # round() to 3 dp: result can be expressed as X.XXX
        assert abs(lat - round(lat, 3)) < 1e-10
        assert abs(lon - round(lon, 3)) < 1e-10

    def test_zero_coordinate(self):
        lat, lon = coarsen_coordinate(0.0, 0.0)
        assert lat == 0.0
        assert lon == 0.0

    def test_precision_example_from_docstring(self):
        # (12.9245, 80.2301) → lat: floor(12.9245/0.005)*0.005 = 12.920
        lat, lon = coarsen_coordinate(12.9245, 80.2301)
        assert math.isclose(lat, 12.920, abs_tol=1e-3)


# ---------------------------------------------------------------------------
# wrap_event
# ---------------------------------------------------------------------------

class TestWrapEvent:

    def test_returns_same_event_object(self):
        ev = _make_event()
        result = wrap_event(ev, 12.9245, 80.2301)
        assert result is ev

    def test_gps_lat_set_to_coarsened_value(self):
        ev = _make_event()
        wrap_event(ev, 12.9245, 80.2301)
        expected_lat = round(math.floor(12.9245 / _GRID_DEG) * _GRID_DEG, 3)
        assert math.isclose(ev.gps_lat, expected_lat, abs_tol=1e-3)

    def test_gps_lon_set_to_coarsened_value(self):
        ev = _make_event()
        wrap_event(ev, 12.9245, 80.2301)
        expected_lon = round(math.floor(80.2301 / _GRID_DEG) * _GRID_DEG, 3)
        assert math.isclose(ev.gps_lon, expected_lon, abs_tol=1e-3)

    def test_commitment_attached(self):
        ev = _make_event()
        wrap_event(ev, 12.9245, 80.2301)
        assert hasattr(ev, "_gps_commitment")
        assert ev._gps_commitment.startswith("sha3:")

    def test_auto_salt_generates_different_commitments(self):
        """Two calls without explicit salt must produce different commitments
        (because os.urandom generates a new salt each time)."""
        ev1 = _make_event()
        ev2 = _make_event()
        wrap_event(ev1, 12.9245, 80.2301)
        wrap_event(ev2, 12.9245, 80.2301)
        # It's astronomically unlikely that two random 16-byte salts collide
        assert ev1._gps_commitment != ev2._gps_commitment

    def test_explicit_salt_produces_same_commitment(self):
        """Same explicit salt + same coordinates → same commitment."""
        salt = b"\xab\xcd\xef" * 5 + b"\x00"
        ev1 = _make_event()
        ev2 = _make_event()
        wrap_event(ev1, 12.9245, 80.2301, device_salt=salt)
        wrap_event(ev2, 12.9245, 80.2301, device_salt=salt)
        assert ev1._gps_commitment == ev2._gps_commitment

    def test_gps_lat_rounded_to_3dp(self):
        ev = _make_event()
        wrap_event(ev, 12.9245, 80.2301)
        # Verify it is rounded to 3 dp
        assert abs(ev.gps_lat - round(ev.gps_lat, 3)) < 1e-10

    def test_gps_lon_rounded_to_3dp(self):
        ev = _make_event()
        wrap_event(ev, 12.9245, 80.2301)
        assert abs(ev.gps_lon - round(ev.gps_lon, 3)) < 1e-10

    def test_coarsened_coords_differ_from_raw(self):
        """Coarsened coordinates must differ from raw (high-precision) coordinates."""
        raw_lat, raw_lon = 12.924567, 80.230189
        ev = _make_event()
        wrap_event(ev, raw_lat, raw_lon)
        # Coarsened ≠ raw (unless raw happened to be on exact grid cell)
        assert ev.gps_lat != raw_lat or ev.gps_lon != raw_lon
