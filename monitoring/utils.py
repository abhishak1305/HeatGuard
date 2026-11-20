"""
Backward-compatible wrapper referencing the comprehensive heat_index module.
"""

from .heat_index import compute_nws_heat_index


def calculate_heat_index(temperature_c, relative_humidity):
    """
    Wrapper returning tuple (heat_index_c, risk_level, notes).
    """
    res = compute_nws_heat_index(temperature_c, relative_humidity)
    return (res['heat_index_c'], res['risk']['category'], res['risk']['description'])
