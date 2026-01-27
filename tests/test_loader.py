"""
Unit tests for ReportLoader.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.loader import ReportLoader


class TestReportLoaderInit:
    """Tests for ReportLoader initialization."""
    
    def test_init_with_defaults(self, temp_pdf_path):
        """Test initialization with default parameters."""
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path)
            assert loader.file_path == temp_pdf_path
            assert loader.max_pages == 5
            assert loader.model == "gpt-4o"
            assert loader.api_ready is True
    
    def test_init_with_custom_params(self, temp_pdf_path):
        """Test initialization with custom parameters."""
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path, max_pages=10, vision_model="gpt-4o-mini")
            assert loader.max_pages == 10
            assert loader.model == "gpt-4o-mini"
    
    def test_init_creates_directories(self, temp_pdf_path):
        """Test initialization creates necessary directories."""
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path)
            # Directories should be created
            assert os.path.exists(loader.images_dir)
            assert os.path.exists(loader.highlights_dir)
    
    def test_init_api_failure(self, temp_pdf_path):
        """Test initialization when OpenAI client fails."""
        with patch('src.loader.OpenAI', side_effect=Exception("API Error")):
            loader = ReportLoader(temp_pdf_path)
            assert loader.api_ready is False
            assert loader.client is None


class TestGetHighlightedImage:
    """Tests for get_highlighted_image method."""
    
    @patch('src.loader.fitz.open')
    def test_get_highlighted_image_cache_hit(self, mock_fitz_open, temp_pdf_path):
        """Test get_highlighted_image returns cached image if exists."""
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path)
            
            # Create a fake cached image
            quote = "test quote"
            import hashlib
            quote_hash = hashlib.md5(quote.encode()).hexdigest()[:8]
            cached_path = os.path.join(loader.highlights_dir, f"p1_{quote_hash}.png")
            
            # Mock the file existence
            with patch('os.path.exists', return_value=True):
                result = loader.get_highlighted_image(1, quote)
                assert result == cached_path
                # fitz should not be called for cached images
                assert not mock_fitz_open.called
    
    @patch('src.loader.fitz.open')
    def test_get_highlighted_image_generates_new(self, mock_fitz_open, temp_pdf_path):
        """Test get_highlighted_image generates new highlight."""
        # Mock PDF document and page
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        
        mock_page.search_for.return_value = [MagicMock()]  # Mock found quads
        mock_page.add_highlight_annot.return_value = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 10
        mock_fitz_open.return_value = mock_doc
        
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path)
            
            with patch('os.path.exists', return_value=False):
                result = loader.get_highlighted_image(1, "test quote")
                
                # Should have searched for the quote
                assert mock_page.search_for.called
                # Should have saved the image
                assert mock_pix.save.called
                assert result is not None
    
    @patch('src.loader.fitz.open')
    def test_get_highlighted_image_handles_error(self, mock_fitz_open, temp_pdf_path):
        """Test get_highlighted_image handles errors gracefully."""
        mock_fitz_open.side_effect = Exception("PDF Error")
        
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path)
            result = loader.get_highlighted_image(1, "test")
            assert result is None


class TestGetVisualDescription:
    """Tests for _get_visual_description method."""
    
    def test_visual_description_no_client(self, temp_pdf_path):
        """Test _get_visual_description returns empty string when no client."""
        with patch('src.loader.OpenAI', side_effect=Exception("No API")):
            loader = ReportLoader(temp_pdf_path)
            result = loader._get_visual_description("base64data")
            assert result == ""
    
    def test_visual_description_success(self, temp_pdf_path):
        """Test _get_visual_description with successful API response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Tabelle mit CO2 Daten gefunden"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.loader.OpenAI', return_value=mock_client):
            loader = ReportLoader(temp_pdf_path)
            result = loader._get_visual_description("base64data")
            
            assert result != ""
            assert "VISUELLE DATEN" in result
    
    def test_visual_description_no_relevant_data(self, temp_pdf_path):
        """Test _get_visual_description when LLM finds no relevant data."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "KEINE_RELEVANTEN_DATEN"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.loader.OpenAI', return_value=mock_client):
            loader = ReportLoader(temp_pdf_path)
            result = loader._get_visual_description("base64data")
            assert result == ""
    
    def test_visual_description_rate_limit_retry(self, temp_pdf_path, mock_rate_limit_error):
        """Test _get_visual_description retries on rate limit."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Success after retry"
        mock_response.choices = [mock_choice]
        
        # First call raises RateLimitError, second succeeds
        mock_client.chat.completions.create.side_effect = [
            mock_rate_limit_error,
            mock_response
        ]
        
        with patch('src.loader.OpenAI', return_value=mock_client):
            with patch('time.sleep'):  # Mock sleep to speed up test
                loader = ReportLoader(temp_pdf_path)
                result = loader._get_visual_description("base64data")
                
                # Should retry and succeed
                assert result != ""
                assert mock_client.chat.completions.create.call_count == 2


class TestLoad:
    """Tests for load method."""
    
    def test_load_from_cache(self, temp_pdf_path):
        """Test load returns cached data when available."""
        cached_data = [
            {"text": "cached text", "metadata": {"page": 1}}
        ]
        
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path)
            
            # Mock cache file exists
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data='[{"text": "cached", "metadata": {"page": 1}}]')):
                    result = loader.load(use_cache=True)
                    assert isinstance(result, list)
    
    @patch('src.loader.fitz.open')
    @patch('src.loader.pymupdf4llm')
    def test_load_process_new_pdf(self, mock_pymupdf4llm, mock_fitz_open, temp_pdf_path, mock_progress_callback):
        """Test load processes new PDF when cache not available."""
        # Mock PDF document
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"fake_image_data"
        mock_page.get_pixmap.return_value = mock_pix
        
        mock_doc.__len__.return_value = 2
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz_open.return_value = mock_doc
        
        # Mock pymupdf4llm
        mock_pymupdf4llm.to_markdown.return_value = [
            {"text": "Page 1 text"},
            {"text": "Page 2 text"}
        ]
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Vision description"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.loader.OpenAI', return_value=mock_client):
            loader = ReportLoader(temp_pdf_path, max_pages=2)
            
            # Mock cache doesn't exist
            with patch('os.path.exists', return_value=False):
                with patch('builtins.open', mock_open()):
                    with patch('json.dump'):
                        result = loader.load(use_cache=False, progress_callback=mock_progress_callback)
                        
                        # Should return list of chunks
                        assert isinstance(result, list)
                        # Progress callback should be called
                        assert mock_progress_callback.called
    
    def test_load_respects_max_pages(self, temp_pdf_path):
        """Test load respects max_pages parameter."""
        # This would be a more complex integration test
        # For now, we verify the parameter is stored
        with patch('src.loader.OpenAI'):
            loader = ReportLoader(temp_pdf_path, max_pages=3)
            assert loader.max_pages == 3


class TestProcessPageVision:
    """Tests for _process_page_vision method."""
    
    def test_process_page_vision_no_api(self, temp_pdf_path):
        """Test _process_page_vision when API not ready."""
        with patch('src.loader.OpenAI', side_effect=Exception("No API")):
            loader = ReportLoader(temp_pdf_path)
            img_data = {
                'page_num': 1,
                'base64': 'base64data',
                'text_content': 'text',
                'img_path': '/tmp/img.png'
            }
            result = loader._process_page_vision(img_data)
            assert result == ""
    
    def test_process_page_vision_success(self, temp_pdf_path):
        """Test _process_page_vision with successful API call."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Vision data"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.loader.OpenAI', return_value=mock_client):
            with patch('time.sleep'):  # Mock sleep
                loader = ReportLoader(temp_pdf_path)
                img_data = {
                    'page_num': 1,
                    'base64': 'base64data',
                    'text_content': 'text',
                    'img_path': '/tmp/img.png'
                }
                result = loader._process_page_vision(img_data)
                
                # Should have delay for rate limiting
                assert isinstance(result, str)
    
    def test_process_page_vision_rate_limit_retry(self, temp_pdf_path, mock_rate_limit_error):
        """Test _process_page_vision retries on rate limit."""
        mock_client = MagicMock()
        
        # Mock _get_visual_description to raise then succeed
        with patch('src.loader.OpenAI', return_value=mock_client):
            with patch('time.sleep'):
                loader = ReportLoader(temp_pdf_path)
                
                # Mock the _get_visual_description method
                with patch.object(loader, '_get_visual_description', side_effect=[
                    mock_rate_limit_error,
                    "Success"
                ]):
                    img_data = {'page_num': 1, 'base64': 'data', 'text_content': '', 'img_path': ''}
                    result = loader._process_page_vision(img_data)
                    assert result == "Success"


@pytest.mark.integration
class TestLoaderIntegration:
    """Integration tests for ReportLoader."""
    
    @patch('src.loader.fitz.open')
    @patch('src.loader.pymupdf4llm')
    def test_full_loading_pipeline(self, mock_pymupdf4llm, mock_fitz_open, temp_pdf_path):
        """Test complete PDF loading and processing pipeline."""
        # Setup mocks
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"fake_image"
        mock_page.get_pixmap.return_value = mock_pix
        
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz_open.return_value = mock_doc
        
        mock_pymupdf4llm.to_markdown.return_value = [{"text": "Test page"}]
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "KEINE_RELEVANTEN_DATEN"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.loader.OpenAI', return_value=mock_client):
            with patch('builtins.open', mock_open()):
                with patch('json.dump'):
                    with patch('time.sleep'):
                        loader = ReportLoader(temp_pdf_path, max_pages=1)
                        result = loader.load(use_cache=False)
                        
                        assert isinstance(result, list)
                        assert len(result) > 0
                        assert "text" in result[0]
                        assert "metadata" in result[0]
