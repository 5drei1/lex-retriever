"""Case law provider registry."""

from .base import CaseProvider
from .rechtsprechung_im_internet import RechtsprechungImInternetProvider

__all__ = ["CaseProvider", "RechtsprechungImInternetProvider"]
