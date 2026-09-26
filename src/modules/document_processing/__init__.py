"""Módulo `document_processing` — pipeline documental do Dev 1.

Expõe apenas a fachada pública (RF-08); o resto é interno ao módulo.
"""

from .public_api import (
    DocumentProcessingFacade,
    create_default_document_processing,
    create_document_processing,
)

__all__ = [
    "DocumentProcessingFacade",
    "create_document_processing",
    "create_default_document_processing",
]
