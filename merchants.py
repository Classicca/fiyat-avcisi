"""Fiyat Avcısı: verified Turkish retailer domains allowed for display.

Only an HTTPS link hosted under one of these exact domain trees can become a
shop offer. Marketplace seller identity and stock are separate questions;
hosting on an approved marketplace does not certify each third-party seller.
"""
from __future__ import annotations

from urllib.parse import urlsplit

# The user-approved platforms. Subdomains are accepted; lookalike hostnames are not.
APPROVED_RETAILERS = (
    ("amazon.com.tr", "Amazon Türkiye"),
    ("trendyol.com", "Trendyol"),
    ("hepsiburada.com", "Hepsiburada"),
    ("n11.com", "n11"),
    ("pazarama.com", "Pazarama"),
    ("idefix.com", "idefix"),
    ("incehesap.com", "İncehesap"),
    ("itopya.com", "İtopya"),
    ("gaming.gen.tr", "Gaming.Gen.TR"),
)


def trusted_retailer(url: str) -> str:
    """Canonical approved platform or empty when the offer link is untrusted.

    Never trust the `source`/store name by itself. SerpApi may return merchant
    names for unrelated pages, comparison sites, or Google redirect links.
    """
    if not isinstance(url, str) or not 0 < len(url) <= 3000:
        return ""
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return ""
        if parsed.username is not None or parsed.password is not None:
            return ""
        if parsed.port not in (None, 443):
            return ""
        host = parsed.hostname.rstrip(".").lower()
    except ValueError:
        return ""
    for domain, title in APPROVED_RETAILERS:
        if host == domain or host.endswith("." + domain):
            return title
    return ""
