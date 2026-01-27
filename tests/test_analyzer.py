"""
Unit Tests für den Greenwashing Analyzer.

Diese Tests validieren die Kernfunktionalität der Analyse-Logik.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.analyzer import GreenwashingAnalyzer


class TestGreenwashingAnalyzer:
    """Test Suite für GreenwashingAnalyzer Klasse."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock für OpenAI Client."""
        with patch('src.analyzer.OpenAI') as mock:
            yield mock
    
    @pytest.fixture
    def analyzer(self, mock_openai_client):
        """Fixture für Analyzer-Instanz."""
        return GreenwashingAnalyzer(model_name="gpt-4o-mini")
    
    def test_analyzer_initialization(self, analyzer):
        """Test: Analyzer wird korrekt initialisiert."""
        assert analyzer.model == "gpt-4o-mini"
        assert analyzer.api_ready is True
    
    def test_analyzer_without_api_key(self):
        """Test: Analyzer behandelt fehlenden API Key korrekt."""
        with patch('src.analyzer.OpenAI', side_effect=Exception("No API key")):
            analyzer = GreenwashingAnalyzer()
            assert analyzer.api_ready is False
            assert analyzer.client is None
    
    def test_analyze_report_without_api(self, mock_openai_client):
        """Test: analyze_report gibt Fehler bei fehlender API zurück."""
        with patch('src.analyzer.OpenAI', side_effect=Exception("No API")):
            analyzer = GreenwashingAnalyzer()
            result = analyzer.analyze_report([])
            assert "error" in result
            assert result["error"] == "API Key fehlt."
    
    def test_analyze_report_empty_chunks(self, analyzer):
        """Test: Leere Chunk-Liste wird korrekt behandelt."""
        with patch.object(analyzer, 'client') as mock_client:
            result = analyzer.analyze_report([])
            assert result["findings"] == []
            assert result["claim_registry"] == []
            assert result["total_chunks"] == 0
    
    def test_custom_definitions(self, analyzer):
        """Test: Benutzerdefinierte Tag-Definitionen werden verwendet."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"findings": [], "new_claims": [], "claim_updates": []}'
        
        custom_defs = {
            "CUSTOM_TAG": "Test Definition"
        }
        
        chunks = [{"text": "Test", "metadata": {"page": 1}}]
        
        with patch.object(analyzer.client.chat.completions, 'create', return_value=mock_response) as mock_create:
            analyzer.analyze_report(chunks, custom_definitions=custom_defs)
            
            # Verify custom definitions were included in prompt
            call_args = mock_create.call_args
            system_message = call_args[1]['messages'][0]['content']
            assert "CUSTOM_TAG" in system_message
            assert "Test Definition" in system_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
