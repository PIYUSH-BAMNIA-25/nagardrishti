"""
geo_dashboard.py — Folium Heatmap Dashboard

Generates an interactive Folium map with complaint markers colour-coded
by status:

    🟡 Yellow  — Pending
    🔵 Blue    — In Progress
    🟢 Green   — Resolved

Also renders a heatmap layer to highlight areas with high complaint density.
The map can be saved as an HTML file or rendered inline in Streamlit.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import folium
from folium.plugins import HeatMap

logger = logging.getLogger(__name__)

# ── Status → marker colour mapping ───────────────────────────
STATUS_COLOURS = {
    "Pending": "orange",
    "In Progress": "blue",
    "Resolved": "green",
}

# Default centre (India — Jaipur)
DEFAULT_CENTRE = [26.9124, 75.7873]
DEFAULT_ZOOM = 12


def generate_heatmap(
    complaints: List[Dict[str, Any]],
    centre: Optional[List[float]] = None,
    zoom: int = DEFAULT_ZOOM,
    save_path: Optional[str] = None,
) -> folium.Map:
    """
    Build a Folium map with complaint pins and a heatmap overlay.

    Parameters
    ----------
    complaints : list[dict]
        Each dict must have: latitude, longitude, status.
        Optional: category, severity, description, id.
    centre : [lat, lon], optional
        Map centre. Defaults to Jaipur, India.
    zoom : int
        Initial zoom level.
    save_path : str, optional
        If provided, the map is saved as an HTML file at this path.

    Returns
    -------
    folium.Map
    """
    map_centre = centre or DEFAULT_CENTRE
    m = folium.Map(location=map_centre, zoom_start=zoom, tiles="OpenStreetMap")

    heat_data: List[List[float]] = []

    for c in complaints:
        lat = c.get("latitude")
        lon = c.get("longitude")
        if lat is None or lon is None:
            continue

        status = c.get("status", "Pending")
        colour = STATUS_COLOURS.get(status, "gray")
        severity = c.get("severity", "?")
        category = c.get("category", "Road Issue")

        # Marker with popup
        popup_html = (
            f"<b>{category}</b><br>"
            f"Severity: Level {severity}<br>"
            f"Status: {status}<br>"
            f"<small>{c.get('description', '')[:100]}</small>"
        )
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=colour, icon="info-sign"),
        ).add_to(m)

        # Accumulate heatmap data
        heat_data.append([lat, lon])

    # Add heatmap layer
    if heat_data:
        HeatMap(heat_data, radius=20, blur=15, max_zoom=15).add_to(m)

    # Optionally save to file
    if save_path:
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(out))
        logger.info("Heatmap saved to %s", out)

    return m
