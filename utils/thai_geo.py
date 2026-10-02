import re
from typing import Any, Dict, Optional, Set
import requests
import streamlit as st

GEOJSON_URL = "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/provinces.geojson"

_THAI_CHAR_REGEX = re.compile(r"[\u0e00-\u0e7f]")


def _contains_thai(text: Any) -> bool:
    """Check if a value contains Thai Unicode characters."""
    if isinstance(text, str):
        return bool(_THAI_CHAR_REGEX.search(text))
    return False


@st.cache_data(ttl=86400)
def load_thailand_geojson() -> Optional[Dict[str, Any]]:
    """Fetch Thailand province GeoJSON data from remote repository.

    Returns:
        dict: Parsed GeoJSON dictionary if successful, None on failure.
    """
    try:
        response = requests.get(GEOJSON_URL, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.warning(f"Failed to load Thailand GeoJSON: {e}")
        return None


def detect_name_property(geojson: Dict[str, Any]) -> Optional[str]:
    """Auto-detect which property in GeoJSON features contains Thai province names.

    Checks priority candidate keys first, then falls back to any property containing Thai text.

    Args:
        geojson: GeoJSON FeatureCollection dictionary.

    Returns:
        str or None: Detected property key name, or None if not found.
    """
    if not geojson or "features" not in geojson:
        return None

    features = geojson.get("features", [])
    if not features:
        return None

    candidates = ["pro_th", "name_th", "NAME_TH", "PROV_NAMT", "name", "NAME"]

    # 1. Check priority candidates across sample features
    for candidate in candidates:
        for feature in features:
            props = feature.get("properties", {})
            if candidate in props and _contains_thai(props[candidate]):
                return candidate

    # 2. Fallback: inspect all properties across features for Thai text
    for feature in features:
        props = feature.get("properties", {})
        for key, val in props.items():
            if _contains_thai(val):
                return key

    return None


def get_geojson_province_names(geojson: Dict[str, Any], name_prop: str) -> Set[str]:
    """Extract a set of all province name strings from GeoJSON features.

    Args:
        geojson: GeoJSON FeatureCollection dictionary.
        name_prop: Property key name containing province names.

    Returns:
        set: Set of province name strings found in features.
    """
    if not geojson or "features" not in geojson or not name_prop:
        return set()

    names = set()
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        val = props.get(name_prop)
        if val is not None:
            names.add(str(val).strip())

    return names
