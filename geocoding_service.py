"""
Simple Geocoding Service for US Cities
Provides latitude/longitude coordinates for major US cities
"""

from typing import Optional, Tuple, Dict

# Dictionary of major US cities with their coordinates
# Format: "city, state_abbr": (latitude, longitude)
CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    # Ohio
    "cincinnati, oh": (39.1031, -84.5120),
    "cleveland, oh": (41.4993, -81.6944),
    "columbus, oh": (39.9612, -82.9988),
    "toledo, oh": (41.6528, -83.5379),
    "akron, oh": (41.0814, -81.5190),
    "dayton, oh": (39.7589, -84.1916),

    # New York
    "new york, ny": (40.7128, -74.0060),
    "nyc, ny": (40.7128, -74.0060),
    "buffalo, ny": (42.8864, -78.8784),
    "rochester, ny": (43.1566, -77.6088),
    "syracuse, ny": (43.0481, -76.1474),
    "albany, ny": (42.6526, -73.7562),
    "yonkers, ny": (40.9312, -73.8987),

    # California
    "los angeles, ca": (34.0522, -118.2437),
    "san francisco, ca": (37.7749, -122.4194),
    "san diego, ca": (32.7157, -117.1611),
    "sacramento, ca": (38.5816, -121.4944),
    "san jose, ca": (37.3382, -121.8863),
    "fresno, ca": (36.7378, -119.7871),
    "oakland, ca": (37.8044, -122.2712),

    # Texas
    "houston, tx": (29.7604, -95.3698),
    "dallas, tx": (32.7767, -96.7970),
    "austin, tx": (30.2672, -97.7431),
    "san antonio, tx": (29.4241, -98.4936),
    "fort worth, tx": (32.7555, -97.3308),
    "el paso, tx": (31.7619, -106.4850),

    # Florida
    "miami, fl": (25.7617, -80.1918),
    "orlando, fl": (28.5383, -81.3792),
    "tampa, fl": (27.9506, -82.4572),
    "jacksonville, fl": (30.3322, -81.6557),
    "fort lauderdale, fl": (26.1224, -80.1373),
    "tallahassee, fl": (30.4383, -84.2807),

    # Illinois
    "chicago, il": (41.8781, -87.6298),
    "springfield, il": (39.7817, -89.6501),
    "peoria, il": (40.6936, -89.5890),
    "rockford, il": (42.2711, -89.0940),

    # Pennsylvania
    "philadelphia, pa": (39.9526, -75.1652),
    "pittsburgh, pa": (40.4406, -79.9959),
    "harrisburg, pa": (40.2732, -76.8867),
    "allentown, pa": (40.6084, -75.4902),

    # Arizona
    "phoenix, az": (33.4484, -112.0740),
    "tucson, az": (32.2226, -110.9747),
    "mesa, az": (33.4152, -111.8315),
    "scottsdale, az": (33.4942, -111.9261),

    # Michigan
    "detroit, mi": (42.3314, -83.0458),
    "grand rapids, mi": (42.9634, -85.6681),
    "lansing, mi": (42.7325, -84.5555),

    # Massachusetts
    "boston, ma": (42.3601, -71.0589),
    "worcester, ma": (42.2626, -71.8023),
    "cambridge, ma": (42.3736, -71.1097),

    # Washington
    "seattle, wa": (47.6062, -122.3321),
    "spokane, wa": (47.6588, -117.4260),
    "tacoma, wa": (47.2529, -122.4443),

    # Georgia
    "atlanta, ga": (33.7490, -84.3880),
    "savannah, ga": (32.0809, -81.0912),
    "augusta, ga": (33.4735, -82.0105),

    # North Carolina
    "charlotte, nc": (35.2271, -80.8431),
    "raleigh, nc": (35.7796, -78.6382),
    "greensboro, nc": (36.0726, -79.7920),

    # Tennessee
    "nashville, tn": (36.1627, -86.7816),
    "memphis, tn": (35.1495, -90.0490),
    "knoxville, tn": (35.9606, -83.9207),

    # Missouri
    "kansas city, mo": (39.0997, -94.5786),
    "st louis, mo": (38.6270, -90.1994),
    "st. louis, mo": (38.6270, -90.1994),
    "springfield, mo": (37.2090, -93.2923),

    # Wisconsin
    "milwaukee, wi": (43.0389, -87.9065),
    "madison, wi": (43.0731, -89.4012),

    # Colorado
    "denver, co": (39.7392, -104.9903),
    "colorado springs, co": (38.8339, -104.8214),
    "aurora, co": (39.7294, -104.8319),

    # Nevada
    "las vegas, nv": (36.1699, -115.1398),
    "reno, nv": (39.5296, -119.8138),

    # Oregon
    "portland, or": (45.5152, -122.6784),
    "salem, or": (44.9429, -123.0351),
    "eugene, or": (44.0521, -123.0868),

    # Louisiana
    "new orleans, la": (29.9511, -90.0715),
    "baton rouge, la": (30.4515, -91.1871),

    # Indiana
    "indianapolis, in": (39.7684, -86.1581),
    "fort wayne, in": (41.0793, -85.1394),

    # Virginia
    "virginia beach, va": (36.8529, -75.9780),
    "richmond, va": (37.5407, -77.4360),

    # Minnesota
    "minneapolis, mn": (44.9778, -93.2650),
    "st paul, mn": (44.9537, -93.0900),
    "st. paul, mn": (44.9537, -93.0900),

    # Maryland
    "baltimore, md": (39.2904, -76.6122),

    # Connecticut
    "hartford, ct": (41.7658, -72.6734),

    # Alabama
    "birmingham, al": (33.5186, -86.8104),
    "montgomery, al": (32.3668, -86.3000),

    # South Carolina
    "charleston, sc": (32.7765, -79.9311),
    "columbia, sc": (34.0007, -81.0348),

    # Kentucky
    "louisville, ky": (38.2527, -85.7585),
    "lexington, ky": (38.0406, -84.5037),
}


class GeocodingService:
    """Simple geocoding service for US cities"""

    def __init__(self):
        self.coordinates = CITY_COORDINATES

    def geocode(self, city: str, state: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """
        Get latitude and longitude for a city

        Args:
            city: City name (e.g., "Cincinnati", "New York")
            state: State abbreviation (e.g., "OH", "NY")

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        if not city:
            return None

        # Normalize input
        city_lower = city.lower().strip()
        state_lower = state.lower().strip() if state else None

        # Try exact match with state
        if state_lower:
            key = f"{city_lower}, {state_lower}"
            if key in self.coordinates:
                return self.coordinates[key]

        # Try to find city in any state
        for key, coords in self.coordinates.items():
            if key.startswith(f"{city_lower},"):
                return coords

        return None

    def get_city_info(self, city: str, state: Optional[str] = None) -> Optional[Dict[str, any]]:
        """
        Get detailed city information including coordinates

        Args:
            city: City name
            state: State abbreviation

        Returns:
            Dictionary with city info or None
        """
        coords = self.geocode(city, state)

        if coords:
            return {
                "city": city,
                "state": state,
                "latitude": coords[0],
                "longitude": coords[1]
            }

        return None
