"""Fingerprint extraction using AcoustID/pyacoustid."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FingerprintReader:
    """Extracts audio fingerprints using pyacoustid.

    Provides reliable fingerprint extraction with error handling and caching.
    """

    def __init__(self, acoustid_api_key: Optional[str] = None):
        """Initialize fingerprint reader.

        Args:
            acoustid_api_key: AcoustID API key (optional, for future API calls)
        """
        self.acoustid_api_key = acoustid_api_key
        self._pyacoustid: Optional[Any] = None

    def read_fingerprint(self, audio_path: Path) -> Optional[str]:
        """Extract fingerprint from audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Fingerprint string, or None if extraction fails
        """
        if not audio_path.exists():
            logger.debug("Audio file does not exist: %s", audio_path)
            return None

        try:
            # Lazy import to handle cases where pyacoustid isn't available
            if self._pyacoustid is None:
                # Note: pyacoustid 1.3.0+ uses 'acoustid' as the module name
                try:
                    import acoustid as pyacoustid_module
                except ImportError:
                    # Fallback for older versions
                    import pyacoustid as pyacoustid_module
                self._pyacoustid = pyacoustid_module

            # Extract fingerprint and duration
            duration, fingerprint = self._pyacoustid.fingerprint_file(str(audio_path))

            if not fingerprint:
                logger.debug("No fingerprint extracted from: %s", audio_path)
                return None

            # Validate fingerprint format (should be base64-like string)
            if not isinstance(fingerprint, str) or len(fingerprint) < 10:
                logger.warning("Invalid fingerprint format from: %s", audio_path)
                return None

            logger.debug("Extracted fingerprint from %s (duration: %ds)", audio_path, duration)
            return fingerprint

        except ImportError:
            logger.warning("pyacoustid not available, cannot extract fingerprints")
            return None

        except self._pyacoustid.NoBackendError as e:  # type: ignore
            logger.warning("No audio backend available for fingerprinting: %s", e)
            return None

        except self._pyacoustid.FingerprintGenerationError as e:  # type: ignore
            logger.debug("Fingerprint generation failed for %s: %s", audio_path, e)
            return None

        except OSError as e:
            logger.debug("File access error for %s: %s", audio_path, e)
            return None

        except Exception as e:
            logger.warning("Unexpected error extracting fingerprint from %s: %s", audio_path, e)
            return None

    def read_duration(self, audio_path: Path) -> Optional[int]:
        """Extract duration from audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds, or None if extraction fails
        """
        if not audio_path.exists():
            return None

        try:
            if self._pyacoustid is None:
                # Note: pyacoustid 1.3.0+ uses 'acoustid' as the module name
                try:
                    import acoustid as pyacoustid_module
                except ImportError:
                    # Fallback for older versions
                    import pyacoustid as pyacoustid_module
                self._pyacoustid = pyacoustid_module

            duration, _ = self._pyacoustid.fingerprint_file(str(audio_path))

            # Round to nearest second for deterministic behavior
            return int(duration + 0.5)

        except (ImportError, AttributeError):
            # Fallback: try to get duration without fingerprint
            # This is a simplified fallback - in practice you'd use mutagen or similar
            logger.debug("Cannot extract duration from %s", audio_path)
            return None

        except Exception as e:
            logger.debug("Error extracting duration from %s: %s", audio_path, e)
            return None
