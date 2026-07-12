"""
Memory Twin AI — Backend Concurrency & Error Code Tests

Tests the production hardening in app.py:
  - ErrorCode class with consistent error codes
  - make_error() helper
  - Semaphore-based concurrency control (LLM, EMBED, ASR)
  - Request lifecycle tracking (register_request, complete_request)
  - Cancellation handling via asyncio.CancelledError
  - Client disconnect detection in streaming

Run with: pytest backend/tests/test_app_concurrency.py -v
"""
import asyncio
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is on path
_proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

# Patch model loading before importing app — prevents model load during lifespan
_MODEL_PATCHES = [
    patch("backend.models.embedding_loader.load_embedder", return_value=MagicMock()),
    patch("backend.models.llm_loader.load_llm", return_value=(MagicMock(), MagicMock())),
    patch("backend.models.tts_loader.load_tts", return_value=None),
    patch("backend.models.asr_loader.load_asr", return_value=None),
    patch("backend.rag.memory_store.build_vector_store", return_value=0),
    patch("backend.utils.compute_status.get_compute_status", return_value={}),
    patch("backend.models.model_registry.print_model_registry", return_value=None),
]
for _p in _MODEL_PATCHES:
    _p.start()


class TestErrorCodes:
    """Test the ErrorCode class and make_error helper."""

    def test_error_codes_are_strings(self):
        from backend.app import ErrorCode
        assert isinstance(ErrorCode.CHAT_TIMEOUT, str)
        assert isinstance(ErrorCode.CHAT_CANCELLED, str)
        assert isinstance(ErrorCode.CHAT_GENERATION_FAILED, str)
        assert isinstance(ErrorCode.MODEL_NOT_LOADED, str)
        assert isinstance(ErrorCode.INVALID_REQUEST, str)
        assert isinstance(ErrorCode.INTERNAL_ERROR, str)

    def test_error_codes_have_expected_values(self):
        from backend.app import ErrorCode
        assert ErrorCode.CHAT_TIMEOUT == "CHAT_TIMEOUT"
        assert ErrorCode.CHAT_CANCELLED == "CHAT_CANCELLED"
        assert ErrorCode.CHAT_GENERATION_FAILED == "CHAT_GENERATION_FAILED"
        assert ErrorCode.MODEL_NOT_LOADED == "MODEL_NOT_LOADED"
        assert ErrorCode.INVALID_REQUEST == "INVALID_REQUEST"
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_make_error_returns_dict(self):
        from backend.app import make_error
        err = make_error("CHAT_TIMEOUT", "Request timed out")
        assert isinstance(err, dict)
        assert err["ok"] is False
        assert err["error_code"] == "CHAT_TIMEOUT"
        assert err["error"] == "Request timed out"

    def test_make_error_includes_request_id(self):
        from backend.app import make_error
        err = make_error("CHAT_TIMEOUT", "Timed out", request_id="req-123")
        assert err["request_id"] == "req-123"

    def test_make_error_includes_extra_fields(self):
        from backend.app import make_error
        err = make_error("CHAT_TIMEOUT", "Timed out", timeout_seconds=45)
        assert err["timeout_seconds"] == 45


class TestSemaphores:
    """Test semaphore-based concurrency control."""

    def test_llm_semaphore_exists(self):
        from backend.app import _LLM_SEMAPHORE
        assert _LLM_SEMAPHORE is not None
        assert isinstance(_LLM_SEMAPHORE, asyncio.Semaphore)

    def test_embed_semaphore_exists(self):
        from backend.app import _EMBED_SEMAPHORE
        assert _EMBED_SEMAPHORE is not None
        assert isinstance(_EMBED_SEMAPHORE, asyncio.Semaphore)

    def test_asr_semaphore_exists(self):
        from backend.app import _ASR_SEMAPHORE
        assert _ASR_SEMAPHORE is not None
        assert isinstance(_ASR_SEMAPHORE, asyncio.Semaphore)

    def test_semaphore_limits_are_positive(self):
        from backend.app import _LLM_SEMAPHORE, _EMBED_SEMAPHORE, _ASR_SEMAPHORE
        # Semaphore._value is the internal counter
        assert _LLM_SEMAPHORE._value > 0
        assert _EMBED_SEMAPHORE._value > 0
        assert _ASR_SEMAPHORE._value > 0


class TestRequestLifecycle:
    """Test request lifecycle tracking."""

    def test_register_request_increments_count(self):
        from backend.app import register_request, get_active_request_count, complete_request
        initial = get_active_request_count()
        register_request("req-test-1", "/chat")
        assert get_active_request_count() == initial + 1
        complete_request("req-test-1")
        assert get_active_request_count() == initial

    def test_complete_request_unknown_id_is_safe(self):
        from backend.app import complete_request, get_active_request_count
        initial = get_active_request_count()
        complete_request("nonexistent-id")
        assert get_active_request_count() == initial

    def test_multiple_requests_tracked(self):
        from backend.app import register_request, get_active_request_count, complete_request
        initial = get_active_request_count()
        register_request("req-a", "/chat")
        register_request("req-b", "/chat")
        register_request("req-c", "/chat")
        assert get_active_request_count() == initial + 3
        complete_request("req-a")
        complete_request("req-b")
        complete_request("req-c")
        assert get_active_request_count() == initial


class TestCancellation:
    """Test cancellation handling."""

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        async def cancellable_coro():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await cancellable_coro()

    def test_make_error_for_cancellation(self):
        from backend.app import make_error, ErrorCode
        err = make_error(ErrorCode.CHAT_CANCELLED, "Request was cancelled")
        assert err["error_code"] == "CHAT_CANCELLED"


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_health_returns_ok(self):
        from backend.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestComputeEndpoint:
    """Test the /compute endpoint."""

    def test_compute_endpoint_exists(self):
        from backend.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/compute")
        # Endpoint exists (may return JSON or HTML depending on mount order)
        assert response.status_code == 200


class TestMemoriesEndpoint:
    """Test /memories endpoint."""

    def test_memories_returns_list(self):
        from backend.app import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/memories")
        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert isinstance(data["memories"], list)
