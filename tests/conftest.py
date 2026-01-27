"""
Shared pytest fixtures and configuration for tests.
"""
import pytest
import os
from unittest.mock import Mock, MagicMock
from typing import Dict, List


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing without API calls."""
    client = MagicMock()
    
    # Mock chat completion response
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"findings": [], "new_claims": [], "claim_updates": []}'
    mock_response.choices = [MagicMock(message=mock_message)]
    
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def sample_chunk() -> Dict:
    """Sample document chunk for testing."""
    return {
        "text": "Wir werden unsere CO2-Emissionen um 50% reduzieren bis 2030. Dies ist ein wichtiges Ziel.",
        "metadata": {
            "page": 1,
            "source": "test_report.pdf",
            "len": 100,
            "image_path": "/tmp/test_page_1.png"
        }
    }


@pytest.fixture
def sample_chunks() -> List[Dict]:
    """Multiple sample chunks for testing."""
    return [
        {
            "text": "Seite 1: Einleitung zu unserer Nachhaltigkeitsstrategie.",
            "metadata": {"page": 1, "source": "test.pdf", "len": 50, "image_path": "/tmp/p1.png"}
        },
        {
            "text": "Seite 2: Wir sind umweltfreundlich und grün.",
            "metadata": {"page": 2, "source": "test.pdf", "len": 50, "image_path": "/tmp/p2.png"}
        },
        {
            "text": "Seite 3: CO2-Reduktion um 50% ohne Basisjahr.",
            "metadata": {"page": 3, "source": "test.pdf", "len": 50, "image_path": "/tmp/p3.png"}
        }
    ]


@pytest.fixture
def sample_finding() -> Dict:
    """Sample finding for testing."""
    return {
        "page": 2,
        "category": "VAGUE",
        "quote": "umweltfreundlich und grün",
        "reasoning": "Unspezifische Begriffe ohne konkrete Maßnahmen"
    }


@pytest.fixture
def sample_claim() -> Dict:
    """Sample claim for testing."""
    return {
        "id": 1,
        "text": "CO2-Reduktion um 50% bis 2030",
        "context": "Klimaziele",
        "page": 1,
        "status": "OPEN",
        "evidence": None
    }


@pytest.fixture
def sample_claims() -> List[Dict]:
    """Multiple sample claims for testing."""
    return [
        {
            "id": 1,
            "text": "CO2-Reduktion um 50% bis 2030",
            "context": "Klimaziele",
            "page": 1,
            "status": "OPEN",
            "evidence": None
        },
        {
            "id": 2,
            "text": "100% erneuerbare Energien bis 2025",
            "context": "Energiewende",
            "page": 2,
            "status": "POTENTIALLY_VERIFIED",
            "evidence": "Seite 5: Solarpark bereits in Betrieb"
        }
    ]


@pytest.fixture
def temp_pdf_path(tmp_path):
    """Temporary PDF file path for testing."""
    pdf_path = tmp_path / "test_report.pdf"
    # Note: Actual PDF creation would require pypdf or similar
    # For now, return path for mocking purposes
    return str(pdf_path)


@pytest.fixture(autouse=True)
def setup_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")


@pytest.fixture
def mock_progress_callback():
    """Mock progress callback for testing."""
    return Mock()


@pytest.fixture
def mock_rate_limit_error():
    """Mock RateLimitError for testing retry logic."""
    from openai import RateLimitError
    
    # Create RateLimitError with required parameters
    return RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body=None
    )
