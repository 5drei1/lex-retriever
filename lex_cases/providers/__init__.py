"""Case law provider registry."""

from .base import CaseProvider
from .neuris_cases_provider import NeurisCasesProvider
from .rechtsprechung_im_internet import RechtsprechungImInternetProvider

__all__ = ["CaseProvider", "NeurisCasesProvider", "RechtsprechungImInternetProvider"]
