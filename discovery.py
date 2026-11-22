"""Rotating Turkish-market gaming peripheral discovery searches.

One general search cannot enumerate Google Shopping. These independent, narrow
search terms improve recall within a strict monthly SerpApi query allowance.
The catalog holds search *queries*, never fabricated prices or product listings.
"""
from __future__ import annotations

DISCOVERY_QUERIES = {
    "mouse": (
        "James Donkey JDM11 PAW3311 gaming mouse",
        "PAW3311 gaming mouse kablosuz",
        "PAW3311 oyuncu mouse kablolu",
        "MageGee Scout PAW3311 gaming mouse",
        "GamePower PAW3311 gaming mouse",
        "PMW3360 gaming mouse fiyat",
        "PAW3315 gaming mouse kablosuz",
        "PAW3395 gaming mouse ucuz",
        "Redragon gaming mouse PAW3311",
        "Attack Shark gaming mouse PAW3395",
        "Ajazz PAW3311 gaming mouse",
        "Fantech Pixart gaming mouse",
        "James Donkey oyuncu mouse sensör",
        "uygun fiyatlı Pixart sensörlü gaming mouse",
    ),
    "keyboard": (
        "James Donkey JDK99 kablosuz gaming klavye",
        "kablosuz mekanik gaming klavye ucuz",
        "kablolu red switch mekanik klavye",
        "gaming klavye membran kablosuz",
        "Aula gaming klavye kablolu",
        "Redragon gaming klavye ucuz",
        "Rampage mekanik oyuncu klavye",
        "Inca gaming klavye uygun fiyat",
        "James Donkey kablosuz oyuncu klavyesi",
        "MageGee kablosuz gaming klavye",
        "GamePower gaming klavye mekanik",
        "TUF key gaming klavye ucuz",
        "uygun fiyatli 2.4ghz oyun klavyesi",
        "ucuz kablolu oyuncu klavyesi",
    ),
}


def choose_discovery_queries(cursor: int, slots: int = 2) -> tuple[tuple[str, str], ...]:
    """Rotates one mouse/one keyboard search per night for ~7 API calls.

    The first run explicitly checks the user-reported omissions: James Donkey
    JDM11 and JDK99. Subsequent runs rotate brand/sensor/model searches.
    """
    cursor = max(0, int(cursor))
    slots = min(2, max(0, int(slots)))
    if not slots:
        return ()
    if slots == 1:
        kind = "mouse" if cursor % 2 == 0 else "keyboard"
        index = cursor // 2
        return ((kind, DISCOVERY_QUERIES[kind][index % len(DISCOVERY_QUERIES[kind])]),)
    return tuple((kind, DISCOVERY_QUERIES[kind][cursor % len(DISCOVERY_QUERIES[kind])])
                 for kind in ("mouse", "keyboard"))
