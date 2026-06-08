"""Remote document converter using Docling Serve API."""

from pathlib import Path

from docling.datamodel.base_models import OutputFormat
from docling.datamodel.service.options import ConvertDocumentsOptions
from docling.service_client import DoclingServiceClient
from docling.service_client.exceptions import ServiceError
from docling_core.types.doc.document import ContentLayer
from docling_core.types.doc.labels import DocItemLabel

from docling_mcp.docling_cache import get_cache_key
from docling_mcp.logger import setup_logger
from docling_mcp.settings.conversion import settings as conversion_settings
from docling_mcp.settings.service_client import settings as service_settings
from docling_mcp.shared import local_document_cache, local_stack_cache

from .base import ConversionOutput

logger = setup_logger()


class RemoteDocumentConverter:
    """Converter using Docling Serve API."""

    def __init__(self) -> None:
        """Initialize remote converter."""
        if not service_settings.service_url:
            raise ValueError(
                "DOCLING_SERVICE_URL must be set for remote mode. "
                "Set it in the MCP server environment or .env file. Use the "
                "Docling Serve base URL without /v1, and set "
                "DOCLING_SERVICE_API_KEY if the service requires authentication."
            )

        # DoclingServiceClient requires api_key to be str, not Optional[str]
        api_key = (
            service_settings.service_api_key
            if service_settings.service_api_key is not None
            else ""
        )

        self.client = DoclingServiceClient(
            url=service_settings.service_url,
            api_key=api_key,
            job_timeout=service_settings.service_timeout,
            http_read_timeout=service_settings.service_timeout,
            http_retries=service_settings.service_max_retries,
        )
        logger.info(
            f"Initialized remote converter with URL: {service_settings.service_url}"
        )

    def convert_document(self, source: str) -> ConversionOutput:
        """Convert document using remote API."""
        source = source.strip("\"'")
        logger.info(f"Converting document via remote API: {source}")

        cache_key = get_cache_key(source)

        if cache_key in local_document_cache:
            logger.info(f"Document found in cache: {cache_key}")
            return ConversionOutput(True, cache_key)

        options = ConvertDocumentsOptions(
            do_ocr=conversion_settings.do_ocr,
            force_ocr=conversion_settings.force_ocr,
            ocr_preset=conversion_settings.ocr_preset,
            do_table_structure=conversion_settings.do_table_structure,
            table_mode=conversion_settings.table_mode,
            pdf_backend=conversion_settings.pdf_backend,
            abort_on_error=conversion_settings.abort_on_error,
            include_images=conversion_settings.include_images,
            image_export_mode=conversion_settings.image_export_mode,
            do_code_enrichment=conversion_settings.do_code_enrichment,
            do_formula_enrichment=conversion_settings.do_formula_enrichment,
            do_picture_classification=conversion_settings.do_picture_classification,
            do_picture_description=conversion_settings.do_picture_description,
            to_formats=[OutputFormat.JSON],
        )

        candidate_path = Path(source).expanduser()
        if candidate_path.is_file():
            conversion_source: str | Path = candidate_path.resolve()
        else:
            conversion_source = source

        try:
            result = self.client.convert(source=conversion_source, options=options)
        except ServiceError as e:
            raise RuntimeError(self._format_service_error(e)) from e

        # Check for errors
        if hasattr(result, "status") and hasattr(result.status, "is_error"):
            if result.status.is_error:
                raise RuntimeError(
                    "Docling Serve completed the conversion with errors: "
                    f"{result.errors}"
                )

        # Cache the result
        local_document_cache[cache_key] = result.document

        # Add source metadata
        item = result.document.add_text(
            label=DocItemLabel.TEXT,
            text=f"source: {source}",
            content_layer=ContentLayer.FURNITURE,
        )
        local_stack_cache[cache_key] = [item]

        logger.info(f"Successfully converted document: {cache_key}")
        return ConversionOutput(False, cache_key)

    def convert_directory(self, source: str) -> list[ConversionOutput]:
        """Convert all files in a directory using remote API."""
        source = source.strip("\"'")
        directory = Path(source)
        files: list[Path] = [f for f in directory.iterdir() if f.is_file()]
        out: list[ConversionOutput] = []

        logger.info(f"Converting {len(files)} files from directory: {source}")

        for file in files:
            try:
                result = self.convert_document(str(file))
                out.append(result)
            except Exception as e:
                logger.error(f"Failed to convert {file}: {e}")
                # Continue with other files
                continue

        return out

    def is_available(self) -> bool:
        """Check if remote service is available."""
        try:
            health = self.client.health()
            return health.status == "healthy"
        except ServiceError as e:
            logger.warning(f"Remote service health check failed: {self._format_service_error(e)}")
            return False
        except Exception as e:
            logger.warning(f"Remote service health check failed: {e}")
            return False

    def _format_service_error(self, error: ServiceError) -> str:
        """Format Docling Serve errors with MCP-specific configuration hints."""
        if error.status_code in {401, 403}:
            return (
                f"Docling Serve rejected the request with status {error.status_code}. "
                "The MCP server sends DOCLING_SERVICE_API_KEY as the X-Api-Key "
                "header. Verify that DOCLING_SERVICE_API_KEY is set in the MCP "
                "server process environment, not only in your interactive shell; "
                "desktop MCP clients often require env values in their MCP server "
                "configuration."
            )

        if error.status_code is not None:
            return f"Docling Serve request failed: {error}"
        return f"Docling Serve request failed: {error.message}"
