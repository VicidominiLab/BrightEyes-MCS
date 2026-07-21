"""Persistence adapters for legacy configuration and acquisition files."""

from .legacy_config import LegacyConfigurationCodec, LegacyConfigurationTranslator
from .h5_schema import DATA_FORMAT_VERSION, H5_METADATA_GROUPS

__all__ = ["DATA_FORMAT_VERSION", "H5_METADATA_GROUPS", "LegacyConfigurationCodec", "LegacyConfigurationTranslator"]
