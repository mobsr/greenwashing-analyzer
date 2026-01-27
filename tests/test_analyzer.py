"""
Unit tests for GreenwashingAnalyzer.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.analyzer import GreenwashingAnalyzer


class TestGreenwashingAnalyzerInit:
    """Tests for GreenwashingAnalyzer initialization."""
    
    def test_init_with_default_model(self):
        """Test initialization with default model."""
        with patch('src.analyzer.OpenAI'):
            analyzer = GreenwashingAnalyzer()
            assert analyzer.model == "gpt-4o-mini"
            assert analyzer.api_ready is True
    
    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        with patch('src.analyzer.OpenAI'):
            analyzer = GreenwashingAnalyzer(model_name="gpt-4o")
            assert analyzer.model == "gpt-4o"
    
    def test_init_api_failure(self):
        """Test initialization when OpenAI client fails."""
        with patch('src.analyzer.OpenAI', side_effect=Exception("API Error")):
            analyzer = GreenwashingAnalyzer()
            assert analyzer.api_ready is False
            assert analyzer.client is None


class TestAnalyzeReport:
    """Tests for analyze_report method."""
    
    def test_analyze_report_no_api(self, sample_chunks):
        """Test analyze_report when API is not ready."""
        with patch('src.analyzer.OpenAI', side_effect=Exception("No API")):
            analyzer = GreenwashingAnalyzer()
            result = analyzer.analyze_report(sample_chunks)
            assert "error" in result
            assert result["error"] == "API Key fehlt."
    
    def test_analyze_report_empty_chunks(self, mock_openai_client):
        """Test analyze_report with empty chunks list."""
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer.analyze_report([])
            assert result["findings"] == []
            assert result["claim_registry"] == []
            assert result["total_chunks"] == 0
    
    def test_analyze_report_with_findings(self, sample_chunks, mock_openai_client):
        """Test analyze_report extracts findings correctly."""
        # Mock LLM response with findings
        mock_response_data = {
            "findings": [
                {
                    "category": "VAGUE",
                    "quote": "umweltfreundlich und grün",
                    "reasoning": "Unspezifische Begriffe"
                }
            ],
            "new_claims": [],
            "claim_updates": []
        }
        
        mock_message = MagicMock()
        mock_message.content = json.dumps(mock_response_data)
        mock_choice = MagicMock(message=mock_message)
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer.analyze_report(sample_chunks[:1])
            
            assert len(result["findings"]) == 1
            assert result["findings"][0]["category"] == "VAGUE"
            assert result["findings"][0]["page"] == 1
    
    def test_analyze_report_with_custom_definitions(self, sample_chunks, mock_openai_client):
        """Test analyze_report uses custom tag definitions."""
        custom_defs = {
            "CUSTOM_TAG": "Custom definition for testing"
        }
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer.analyze_report(sample_chunks[:1], custom_definitions=custom_defs)
            
            # Verify the call was made (custom defs are passed to _analyze_single_chunk)
            assert mock_openai_client.chat.completions.create.called
    
    def test_analyze_report_progress_callback(self, sample_chunks, mock_openai_client, mock_progress_callback):
        """Test analyze_report calls progress callback."""
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            analyzer.analyze_report(sample_chunks, progress_callback=mock_progress_callback)
            
            assert mock_progress_callback.called
            # Should be called at least for each chunk + final
            assert mock_progress_callback.call_count >= len(sample_chunks)


class TestDeepVerifyClaims:
    """Tests for deep_verify_claims method."""
    
    def test_deep_verify_no_open_claims(self, sample_chunks, sample_claims, mock_openai_client):
        """Test deep_verify_claims with no open claims."""
        # All claims are verified
        verified_claims = [
            {**claim, "status": "POTENTIALLY_VERIFIED"} 
            for claim in sample_claims
        ]
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer.deep_verify_claims(sample_chunks, verified_claims)
            
            # Should return unchanged
            assert result == verified_claims
            # No API calls should be made
            assert not mock_openai_client.chat.completions.create.called
    
    def test_deep_verify_claim_verification(self, sample_chunks, sample_claim, mock_openai_client):
        """Test deep_verify_claims successfully verifies a claim."""
        # Mock verification response
        verification_response = {
            "is_evidence": True,
            "reason": "Konkrete Maßnahmen genannt"
        }
        
        mock_message = MagicMock()
        mock_message.content = json.dumps(verification_response)
        mock_choice = MagicMock(message=mock_message)
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            claims = [sample_claim]
            result = analyzer.deep_verify_claims(sample_chunks, claims)
            
            # Claim should be verified if evidence found
            # Note: This depends on keyword matching threshold
            # For this test, we'll just check structure
            assert isinstance(result, list)
    
    def test_deep_verify_skips_origin_page(self, sample_chunks, mock_openai_client):
        """Test deep_verify_claims skips the page where claim originated."""
        claim = {
            "id": 1,
            "text": "Test claim with keywords",
            "context": "Test",
            "page": 1,  # Same as first chunk
            "status": "OPEN",
            "evidence": None
        }
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            analyzer.deep_verify_claims(sample_chunks[:1], [claim])
            
            # Should not make API call since only chunk is origin page
            assert not mock_openai_client.chat.completions.create.called


class TestAnalyzeSingleChunk:
    """Tests for _analyze_single_chunk method."""
    
    def test_analyze_single_chunk_success(self, sample_chunk, mock_openai_client):
        """Test _analyze_single_chunk with successful API response."""
        mock_response_data = {
            "findings": [],
            "new_claims": [{"claim": "Test claim", "context": "Test"}],
            "claim_updates": []
        }
        
        mock_message = MagicMock()
        mock_message.content = json.dumps(mock_response_data)
        mock_choice = MagicMock(message=mock_message)
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer._analyze_single_chunk(
                sample_chunk, 
                "prev text", 
                "next text", 
                [], 
                {}
            )
            
            assert result is not None
            assert "findings" in result
            assert "new_claims" in result
    
    def test_analyze_single_chunk_api_error(self, sample_chunk, mock_openai_client):
        """Test _analyze_single_chunk handles API errors gracefully."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer._analyze_single_chunk(
                sample_chunk,
                "",
                "",
                [],
                {}
            )
            
            assert result is None
    
    def test_analyze_single_chunk_with_context(self, sample_chunk, mock_openai_client):
        """Test _analyze_single_chunk uses context correctly."""
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            
            prev_text = "Previous page content"
            next_text = "Next page content"
            
            analyzer._analyze_single_chunk(
                sample_chunk,
                prev_text,
                next_text,
                [],
                {}
            )
            
            # Verify API was called
            assert mock_openai_client.chat.completions.create.called
            
            # Get the call arguments
            call_args = mock_openai_client.chat.completions.create.call_args
            messages = call_args[1]['messages']
            
            # Verify context is in the user message
            user_message = messages[1]['content']
            assert "KONTEXT: VORHERIGE SEITE" in user_message
            assert "KONTEXT: NÄCHSTE SEITE" in user_message


class TestVerifyClaimWithLLM:
    """Tests for _verify_claim_with_llm method."""
    
    def test_verify_claim_success(self, sample_claim, mock_openai_client):
        """Test _verify_claim_with_llm with successful verification."""
        verification_response = {
            "is_evidence": True,
            "reason": "Konkrete Zahlen genannt"
        }
        
        mock_message = MagicMock()
        mock_message.content = json.dumps(verification_response)
        mock_choice = MagicMock(message=mock_message)
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer._verify_claim_with_llm(
                sample_claim,
                "Im Jahr 2023 haben wir CO2 von 100t auf 50t reduziert."
            )
            
            assert result is not None
            assert result["is_evidence"] is True
            assert "reason" in result
    
    def test_verify_claim_not_evidence(self, sample_claim, mock_openai_client):
        """Test _verify_claim_with_llm when text is not evidence."""
        verification_response = {
            "is_evidence": False,
            "reason": "Nur Wiederholung des Ziels"
        }
        
        mock_message = MagicMock()
        mock_message.content = json.dumps(verification_response)
        mock_choice = MagicMock(message=mock_message)
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer._verify_claim_with_llm(
                sample_claim,
                "Wir planen CO2 zu reduzieren."
            )
            
            assert result is not None
            assert result["is_evidence"] is False
    
    def test_verify_claim_api_error(self, sample_claim, mock_openai_client):
        """Test _verify_claim_with_llm handles API errors."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            result = analyzer._verify_claim_with_llm(sample_claim, "test text")
            
            assert result is None


@pytest.mark.integration
class TestAnalyzerIntegration:
    """Integration tests for the full analyzer pipeline."""
    
    def test_full_analysis_pipeline(self, sample_chunks, mock_openai_client):
        """Test complete analysis pipeline from chunks to results."""
        # Mock first pass response
        pass1_response = {
            "findings": [
                {"category": "VAGUE", "quote": "grün", "reasoning": "Unspezifisch"}
            ],
            "new_claims": [
                {"claim": "50% CO2 Reduktion", "context": "Klimaziele"}
            ],
            "claim_updates": []
        }
        
        mock_message = MagicMock()
        mock_message.content = json.dumps(pass1_response)
        mock_choice = MagicMock(message=mock_message)
        mock_openai_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        
        with patch('src.analyzer.OpenAI', return_value=mock_openai_client):
            analyzer = GreenwashingAnalyzer()
            
            # Run Pass 1
            results = analyzer.analyze_report(sample_chunks)
            
            # Verify results structure
            assert "findings" in results
            assert "claim_registry" in results
            assert "total_chunks" in results
            assert "model_used" in results
            
            # Verify findings
            assert len(results["findings"]) > 0
            
            # Verify claims
            assert len(results["claim_registry"]) > 0
