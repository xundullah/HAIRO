"""
meteorologicalAnalysis.py
-------------------------
Heuristic precipitation likelihood estimator based on humidity, temperature,
and wind speed. Returns an integer percentage in [0, 100].
"""

from typing import Union

Number = Union[int, float]

def estimate_precipitation_percent(temp_c: Number, wind_kmh: Number, humidity_pct: Number) -> int:
    """
    Estimate precipitation likelihood as a percentage (0–100%) using gradient-based heuristics.
    This function computes three normalized “scores” (humidity, temperature, wind) in the range [0, 1],
    then combines them via a weighted sum to yield a final precipitation percentage.

    Parameters
    ----------
    temp_c : float
        Air temperature in degrees Celsius.
    wind_kmh : float
        Wind speed in kilometers per hour.
    humidity_pct : float
        Relative humidity as a percentage (0–100). Values outside this range will be clipped.

    Returns
    -------
    int
        Precipitation likelihood as a percentage (0 to 100), clipped and returned as an integer.
    """
    # Defensive clipping of obviously out-of-range humidity values
    if humidity_pct is None:
        raise ValueError("humidity_pct must be provided")
    if temp_c is None:
        raise ValueError("temp_c must be provided")
    if wind_kmh is None:
        raise ValueError("wind_kmh must be provided")

    # 1. Compute humidity_score:
    #    - Below 85% humidity contributes zero.
    #    - Between 85% and 100% maps linearly from 0 to 1.
    humidity_score = max(0.0, min((float(humidity_pct) - 85.0) / 15.0, 1.0))
    #    Explanation:
    #    If humidity_pct = 85 → (85 − 85)/15 = 0 → humidity_score = 0
    #    If humidity_pct = 100 → (100 − 85)/15 = 1 → humidity_score = 1
    #    Values above 100% are clipped to 1; values below 85% are clipped to 0.

    # 2. Compute temp_score:
    #    - Below 24°C begins contributing precipitation likelihood.
    #    - At or below 14°C (24 − 10), this contribution is maximal (1).
    temp_score = max(0.0, min((24.0 - float(temp_c)) / 10.0, 1.0))
    #    Explanation:
    #    If temp_c = 24 → (24 − 24)/10 = 0 → temp_score = 0
    #    If temp_c = 14 → (24 − 14)/10 = 1 → temp_score = 1
    #    Temperatures below 14°C are clipped to 1; above 24°C are clipped to 0.

    # 3. Compute wind_score:
    #    - Below 17 km/h yields zero contribution.
    #    - At or above 37 km/h (17 + 20), contribution is maximal (1).
    wind_score = max(0.0, min((float(wind_kmh) - 17.0) / 20.0, 1.0))
    #    Explanation:
    #    If wind_kmh = 17 → (17 − 17)/20 = 0 → wind_score = 0
    #    If wind_kmh = 37 → (37 − 17)/20 = 1 → wind_score = 1
    #    Speeds below 17 km/h clipped to 0; above 37 km/h clipped to 1.

    # 4. Weighted combination:
    #    - Humidity contributes up to 50% of the final score.
    #    - Temperature contributes up to 30% of the final score.
    #    - Wind contributes up to 20% of the final score.
    weighted_score = (50.0 * humidity_score) + (30.0 * temp_score) + (20.0 * wind_score)

    # 5. Convert to percentage:
    precipitation_pct = int(weighted_score * 1.5)

    # 6. Clip to [0, 100]
    if precipitation_pct < 0:
        precipitation_pct = 0
    elif precipitation_pct > 100:
        precipitation_pct = 100

    return precipitation_pct


__all__ = ["estimate_precipitation_percent"]
