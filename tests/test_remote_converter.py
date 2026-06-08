"""Unit tests for remote document converter."""

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from docling_mcp.tools.converters.base import ConversionOutput
from docling_mcp.tools.converters.remote import RemoteDocumentConverter


def configure_service_settings(mock_settings: Any) -> None:
    mock_settings.service_url = "https://test.example.com"
    mock_settings.service_api_key = None
    mock_settings.service_timeout = 123.0
    mock_settings.service_max_retries = 4


def configure_conversion_settings(mock_settings: Any) -> None:
    mock_settings.do_ocr = True
    mock_settings.force_ocr = False
    mock_settings.ocr_preset = "auto"
    mock_settings.do_table_structure = True
    mock_settings.table_mode = "accurate"
    mock_settings.pdf_backend = "docling_parse"
    mock_settings.abort_on_error = False
    mock_settings.include_images = False
    mock_settings.image_export_mode = "placeholder"
    mock_settings.do_code_enrichment = False
    mock_settings.do_formula_enrichment = False
    mock_settings.do_picture_classification = False
    mock_settings.do_picture_description = False


def mock_successful_conversion(mock_client_class: Any) -> Mock:
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_document = Mock()
    mock_document.add_text = Mock(return_value=Mock())
    mock_result = Mock()
    mock_result.document = mock_document
    mock_result.status = Mock(is_error=False)
    mock_client.convert.return_value = mock_result

    return mock_client


def option_value(value: Any) -> Any:
    return getattr(value, "value", value)


class TestRemoteDocumentConverter:
    """Test suite for RemoteDocumentConverter."""

    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_init_without_service_url_raises_error(self, mock_settings: Any) -> None:
        """Test that initialization fails without service URL."""
        mock_settings.service_url = None

        with pytest.raises(ValueError, match="DOCLING_SERVICE_URL must be set"):
            RemoteDocumentConverter()

    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_init_passes_service_client_settings(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test initialization passes service client configuration."""
        mock_settings.service_url = "https://test.example.com"
        mock_settings.service_api_key = "test-key"
        mock_settings.service_timeout = 3600.0
        mock_settings.service_max_retries = 3

        converter = RemoteDocumentConverter()

        assert converter is not None
        mock_client_class.assert_called_once_with(
            url="https://test.example.com",
            api_key="test-key",
            job_timeout=3600.0,
            http_read_timeout=3600.0,
            http_retries=3,
        )

    @patch("docling_mcp.tools.converters.remote.local_document_cache", {})
    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_convert_document_from_cache(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test document conversion when document is in cache."""
        configure_service_settings(mock_settings)
        mock_client = mock_successful_conversion(mock_client_class)

        # Setup cache
        cache_key = "test_key"
        with patch(
            "docling_mcp.tools.converters.remote.get_cache_key", return_value=cache_key
        ):
            with patch(
                "docling_mcp.tools.converters.remote.local_document_cache",
                {cache_key: Mock()},
            ):
                converter = RemoteDocumentConverter()
                result = converter.convert_document("test.pdf")

        assert isinstance(result, ConversionOutput)
        assert result.from_cache is True
        assert result.document_key == cache_key
        mock_client.convert.assert_not_called()

    @patch("docling_mcp.tools.converters.remote.local_stack_cache", {})
    @patch("docling_mcp.tools.converters.remote.local_document_cache", {})
    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_convert_document_success(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test successful document conversion via remote API."""
        configure_service_settings(mock_settings)
        mock_client = mock_successful_conversion(mock_client_class)

        cache_key = "test_key"
        with patch(
            "docling_mcp.tools.converters.remote.get_cache_key", return_value=cache_key
        ):
            converter = RemoteDocumentConverter()
            result = converter.convert_document("test.pdf")

        assert isinstance(result, ConversionOutput)
        assert result.from_cache is False
        assert result.document_key == cache_key
        mock_client.convert.assert_called_once()

    @patch("docling_mcp.tools.converters.remote.local_stack_cache", {})
    @patch("docling_mcp.tools.converters.remote.local_document_cache", {})
    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_convert_url_source_passed_as_string(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test URL sources remain strings for Docling Serve to fetch."""
        configure_service_settings(mock_settings)
        mock_client = mock_successful_conversion(mock_client_class)
        url = "https://arxiv.org/pdf/2501.17887"

        converter = RemoteDocumentConverter()
        converter.convert_document(url)

        source = mock_client.convert.call_args.kwargs["source"]
        assert source == url
        assert isinstance(source, str)

    @patch("docling_mcp.tools.converters.remote.local_stack_cache", {})
    @patch("docling_mcp.tools.converters.remote.local_document_cache", {})
    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_convert_existing_local_file_passed_as_resolved_path(
        self, mock_settings: Any, mock_client_class: Any, tmp_path: Path
    ) -> None:
        """Test existing local files are uploaded via resolved Path objects."""
        configure_service_settings(mock_settings)
        mock_client = mock_successful_conversion(mock_client_class)
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")

        converter = RemoteDocumentConverter()
        converter.convert_document(str(file_path))

        source = mock_client.convert.call_args.kwargs["source"]
        assert source == file_path.resolve()
        assert isinstance(source, Path)

    @patch("docling_mcp.tools.converters.remote.local_stack_cache", {})
    @patch("docling_mcp.tools.converters.remote.local_document_cache", {})
    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_convert_missing_local_file_remains_string(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test nonexistent local-looking sources are not converted to Path."""
        configure_service_settings(mock_settings)
        mock_client = mock_successful_conversion(mock_client_class)

        converter = RemoteDocumentConverter()
        converter.convert_document("missing.pdf")

        source = mock_client.convert.call_args.kwargs["source"]
        assert source == "missing.pdf"
        assert isinstance(source, str)

    @patch("docling_mcp.tools.converters.remote.local_stack_cache", {})
    @patch("docling_mcp.tools.converters.remote.local_document_cache", {})
    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.conversion_settings")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_convert_forwards_conversion_options(
        self,
        mock_service_settings: Any,
        mock_conversion_settings: Any,
        mock_client_class: Any,
    ) -> None:
        """Test configured conversion options are forwarded to Docling Serve."""
        configure_service_settings(mock_service_settings)
        configure_conversion_settings(mock_conversion_settings)
        mock_conversion_settings.do_ocr = False
        mock_conversion_settings.force_ocr = True
        mock_conversion_settings.ocr_preset = "rapidocr"
        mock_conversion_settings.do_table_structure = False
        mock_conversion_settings.table_mode = "fast"
        mock_conversion_settings.pdf_backend = "pypdfium2"
        mock_conversion_settings.abort_on_error = True
        mock_conversion_settings.include_images = True
        mock_conversion_settings.image_export_mode = "referenced"
        mock_conversion_settings.do_code_enrichment = True
        mock_conversion_settings.do_formula_enrichment = True
        mock_conversion_settings.do_picture_classification = True
        mock_conversion_settings.do_picture_description = True
        mock_client = mock_successful_conversion(mock_client_class)

        converter = RemoteDocumentConverter()
        converter.convert_document("missing.pdf")

        options = mock_client.convert.call_args.kwargs["options"]
        assert options.do_ocr is False
        assert options.force_ocr is True
        assert options.ocr_preset == "rapidocr"
        assert options.do_table_structure is False
        assert option_value(options.table_mode) == "fast"
        assert option_value(options.pdf_backend) == "pypdfium2"
        assert options.abort_on_error is True
        assert options.include_images is True
        assert option_value(options.image_export_mode) == "referenced"
        assert options.do_code_enrichment is True
        assert options.do_formula_enrichment is True
        assert options.do_picture_classification is True
        assert options.do_picture_description is True

    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_is_available_healthy(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test is_available returns True when service is healthy."""
        configure_service_settings(mock_settings)

        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_health = Mock(status="healthy")
        mock_client.health.return_value = mock_health

        converter = RemoteDocumentConverter()
        assert converter.is_available() is True

    @patch("docling_mcp.tools.converters.remote.DoclingServiceClient")
    @patch("docling_mcp.tools.converters.remote.service_settings")
    def test_is_available_unhealthy(
        self, mock_settings: Any, mock_client_class: Any
    ) -> None:
        """Test is_available returns False when service is unhealthy."""
        configure_service_settings(mock_settings)

        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.health.side_effect = Exception("Service unavailable")

        converter = RemoteDocumentConverter()
        assert converter.is_available() is False
