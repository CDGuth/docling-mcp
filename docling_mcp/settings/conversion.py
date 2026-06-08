"""Settings for document conversion tools."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from docling.datamodel.pipeline_options import PdfBackend, TableFormerMode
from docling_core.types.doc.base import ImageRefMode

OcrPreset = Literal["auto", "easyocr", "tesseract", "rapidocr"]


class ConversionSettings(BaseSettings):
    """Settings for document conversion tools."""

    model_config = SettingsConfigDict(
        env_prefix="DOCLING_MCP_",
        env_file=".env",
        extra="ignore",  # Ignore extra env vars like DOCLING_SERVICE_URL
    )

    keep_images: bool = False
    do_ocr: bool = True
    force_ocr: bool = False
    ocr_preset: OcrPreset = "auto"
    do_table_structure: bool = True
    table_mode: TableFormerMode = TableFormerMode.ACCURATE
    pdf_backend: PdfBackend = PdfBackend.DOCLING_PARSE
    abort_on_error: bool = False
    include_images: bool = False
    image_export_mode: ImageRefMode = ImageRefMode.PLACEHOLDER
    do_code_enrichment: bool = False
    do_formula_enrichment: bool = False
    do_picture_classification: bool = False
    do_picture_description: bool = False


settings = ConversionSettings()
