"""
Database Service for Healthcare Staffing Intelligence
Handles PostgreSQL connections and queries
"""

import asyncpg
from typing import Optional, Dict, Any, List
import os
import math


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the distance between two points using the Haversine formula.

    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point

    Returns:
        Distance in miles
    """
    # Radius of Earth in miles
    R = 3959.0

    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))

    distance = R * c
    return distance


class DatabaseService:
    """Service for interacting with PostgreSQL database"""

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 5432):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.pool: Optional[asyncpg.Pool] = None

    def _get_profession_filter(self, profession: Optional[str]) -> str:
        """Generate SQL WHERE clause for profession filtering"""
        if profession:
            return f' AND "newProfession" = \'{profession}\''
        return ''

    def _normalize_specialty_for_query(self, specialty: str) -> str:
        """
        Normalize specialty to handle variations in database.

        For example, CRNA can appear as:
        - "APRN - CRNA" (Advanced Practice RN)
        - "Certified Nurse Anesthetist (CRNA)" (CRNA subprofession)

        Returns a regex pattern that matches all variations.
        Uses word boundaries to prevent false matches (e.g., ICU shouldn't match NICU)
        """
        specialty_upper = specialty.upper().strip()

        # Special handling for CRNA - match both variations
        if specialty_upper == "CRNA":
            # Match "APRN - CRNA" OR "Certified Nurse Anesthetist" OR just "CRNA"
            return "(APRN - CRNA|Certified Nurse Anesthetist|\\bCRNA\\b)"

        # For other specialties, use word boundaries to prevent substring matches
        # Example: "ICU" should match "RN - ICU" but NOT "RN - NICU"
        # Pattern: (^|\\s|-)specialty($|\\s|-)
        # This matches specialty at word boundaries (start/end of string, space, or dash)
        return f"(^|\\s|-){specialty}($|\\s|-)"

    async def connect(self):
        """Establish database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            print(f"✅ Database pool created: {self.database}@{self.host}")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            print("Database pool closed")

    async def execute_query(self, query: str, *args) -> List[Dict]:
        """Execute a SELECT query and return results"""
        if not self.pool:
            raise Exception("Database pool not initialized")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute_one(self, query: str, *args) -> Optional[Dict]:
        """Execute a SELECT query and return single result"""
        if not self.pool:
            raise Exception("Database pool not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def get_rate_recommendation(self, parameters) -> Optional[Dict[str, Any]]:
        """
        Get rate recommendation based on specialty and location

        This is a stub implementation. Replace with your actual database schema.
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized - cannot query rates")
                return None

            specialty = getattr(parameters, 'specialty', None)
            location = getattr(parameters, 'location', None)
            city = getattr(parameters, 'city', None)
            state = getattr(parameters, 'state', None)
            rate_type = getattr(parameters, 'rate_type', None)
            profession = getattr(parameters, 'profession', None)

            # Map rate_type to appropriate column
            if rate_type == 'hourly_pay':
                rate_column = '"hourlyPay"'
                rate_label = 'hourly pay'
            elif rate_type == 'weekly_pay':
                rate_column = '"weeklyPay"'
                rate_label = 'weekly pay'
            else:
                # Default to billRate
                rate_column = '"billRate"'
                rate_label = 'bill rate'

            # Build profession filter clause
            profession_filter = self._get_profession_filter(profession)
            if profession:
                print(f"🎯 Profession filter active: {profession}")

            # Normalize specialty to handle database variations (e.g., CRNA)
            normalized_specialty = self._normalize_specialty_for_query(specialty) if specialty else None

            print(f"🔍 Database query: specialty='{specialty}' (normalized: '{normalized_specialty}'), city='{city}', state='{state}', location='{location}', rate_type='{rate_column}'")

            if not specialty:
                return None

            # Query using actual table name: vmsrawscrape_prod
            # Using ILIKE for fuzzy matching to handle "RN - ICU" format
            # Filter by startDate for recent assignments (last 90 days)

            # Build query dynamically to avoid parameter type issues
            # Include all rate metrics from database
            # Recommended range is ±2.5% of average
            # Competitive floor: 35th percentile for nurse pay (weekly/hourly), 25th percentile for bill rate

            result = None

            # Use higher percentile for nurse pay (weekly/hourly) to set more realistic competitive floor
            # 35th percentile for nurse pay, 25th percentile for bill rate
            floor_percentile = 0.35 if rate_type in ['weekly_pay', 'hourly_pay'] else 0.25

            # Try city + state first (most specific)
            if city and state:
                print(f"  Trying city-level query: {city}, {state}")
                query = f"""
                    SELECT
                        "newSpecialty" as specialty,
                        city,
                        state as location,
                        AVG({rate_column}) * 0.975 as recommended_min,
                        AVG({rate_column}) * 1.025 as recommended_max,
                        PERCENTILE_CONT({floor_percentile}) WITHIN GROUP (ORDER BY {rate_column}) as competitive_floor,
                        AVG({rate_column}) as market_average,
                        AVG("weeklyPay") as avg_weekly_pay,
                        AVG("hourlyPay") as avg_hourly_pay,
                        AVG("billRate") as avg_bill_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE "newSpecialty" ~ $1
                        AND LOWER(city) = LOWER($2)
                        AND LOWER(state) = LOWER($3)
                        AND {rate_column} IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        {profession_filter}
                    GROUP BY "newSpecialty", city, state
                    HAVING COUNT(*) >= 5
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                """
                result = await self.execute_one(query, normalized_specialty, city, state)

                if result:
                    print(f"  ✅ Found {result.get('sample_size')} records for {city}, {state}")
                else:
                    print(f"  ⚠️ Not enough data for {city}, falling back to state-level")

            # Fall back to state only if city didn't work or wasn't specified
            if not result and (state or location):
                state_code = state or location
                print(f"  Trying state-level query: {state_code}")
                query = f"""
                    SELECT
                        "newSpecialty" as specialty,
                        state as location,
                        AVG({rate_column}) * 0.975 as recommended_min,
                        AVG({rate_column}) * 1.025 as recommended_max,
                        PERCENTILE_CONT({floor_percentile}) WITHIN GROUP (ORDER BY {rate_column}) as competitive_floor,
                        AVG({rate_column}) as market_average,
                        AVG("weeklyPay") as avg_weekly_pay,
                        AVG("hourlyPay") as avg_hourly_pay,
                        AVG("billRate") as avg_bill_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE "newSpecialty" ~ $1
                        AND LOWER(state) = LOWER($2)
                        AND {rate_column} IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        {profession_filter}
                    GROUP BY "newSpecialty", state
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                """
                result = await self.execute_one(query, normalized_specialty, state_code)

                if result:
                    print(f"  ✅ Found {result.get('sample_size')} records for state {state_code}")

            # If still no result, try national (aggregate across ALL states)
            if not result:
                print(f"  Trying national-level query (all states aggregated)")
                query = f"""
                    SELECT
                        "newSpecialty" as specialty,
                        'National' as location,
                        AVG({rate_column}) * 0.975 as recommended_min,
                        AVG({rate_column}) * 1.025 as recommended_max,
                        PERCENTILE_CONT({floor_percentile}) WITHIN GROUP (ORDER BY {rate_column}) as competitive_floor,
                        AVG({rate_column}) as market_average,
                        AVG("weeklyPay") as avg_weekly_pay,
                        AVG("hourlyPay") as avg_hourly_pay,
                        AVG("billRate") as avg_bill_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE "newSpecialty" ~ $1
                        AND {rate_column} IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        {profession_filter}
                    GROUP BY "newSpecialty"
                    HAVING COUNT(*) >= 5
                """
                result = await self.execute_one(query, normalized_specialty)

                if result:
                    print(f"  ✅ Found {result.get('sample_size')} records nationally")

            print(f"📊 Query result: {result}")

            if result:
                return {
                    "specialty": result.get('specialty', specialty),
                    "location": result.get('location', location or 'National'),
                    "recommended_min": float(result.get('recommended_min', 0)),
                    "recommended_max": float(result.get('recommended_max', 0)),
                    "competitive_floor": float(result.get('competitive_floor', 0)),
                    "market_average": float(result.get('market_average', 0)),
                    "avg_weekly_pay": float(result.get('avg_weekly_pay', 0)) if result.get('avg_weekly_pay') else None,
                    "avg_hourly_pay": float(result.get('avg_hourly_pay', 0)) if result.get('avg_hourly_pay') else None,
                    "avg_bill_rate": float(result.get('avg_bill_rate', 0)) if result.get('avg_bill_rate') else None,
                    "rate_type": rate_label,
                    "sample_size": int(result.get('sample_size', 0))
                }

            return None

        except Exception as e:
            print(f"Error getting rate recommendation: {e}")
            return None

    async def get_lead_opportunities(self, parameters) -> Optional[Dict[str, Any]]:
        """
        Get lead generation opportunities

        This is a stub implementation. Replace with your actual database schema.
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized - cannot query leads")
                return None

            specialty = getattr(parameters, 'specialty', None)
            location = getattr(parameters, 'location', None)

            print(f"🔍 Lead query: specialty='{specialty}', location='{location}'")

            # Query using actual table name: vmsrawscrape_prod
            # Get top opportunities by bill rate with fuzzy matching
            # Filter by startDate for recent opportunities (last 30 days)

            # Build query dynamically
            if specialty and location:
                query = """
                    SELECT
                        "clientName" as facility_name,
                        specialty,
                        state,
                        "billRate" as bill_rate,
                        1 as open_positions,
                        "billRate" as urgency_score
                    FROM vmsrawscrape_prod
                    WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                        AND LOWER(state) = LOWER($2)
                        AND "billRate" IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    ORDER BY "billRate" DESC, "startDate" DESC
                    LIMIT 10
                """
                results = await self.execute_query(query, specialty, location)
            elif specialty:
                query = """
                    SELECT
                        "clientName" as facility_name,
                        specialty,
                        state,
                        "billRate" as bill_rate,
                        1 as open_positions,
                        "billRate" as urgency_score
                    FROM vmsrawscrape_prod
                    WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                        AND "billRate" IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    ORDER BY "billRate" DESC, "startDate" DESC
                    LIMIT 10
                """
                results = await self.execute_query(query, specialty)
            elif location:
                query = """
                    SELECT
                        "clientName" as facility_name,
                        specialty,
                        state,
                        "billRate" as bill_rate,
                        1 as open_positions,
                        "billRate" as urgency_score
                    FROM vmsrawscrape_prod
                    WHERE LOWER(state) = LOWER($1)
                        AND "billRate" IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    ORDER BY "billRate" DESC, "startDate" DESC
                    LIMIT 10
                """
                results = await self.execute_query(query, location)
            else:
                query = """
                    SELECT
                        "clientName" as facility_name,
                        specialty,
                        state,
                        "billRate" as bill_rate,
                        1 as open_positions,
                        "billRate" as urgency_score
                    FROM vmsrawscrape_prod
                    WHERE "billRate" IS NOT NULL
                    AND "billRate" BETWEEN 30 AND 800
                    AND "weeklyPay" BETWEEN 1200 AND 15000
                    AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    ORDER BY "billRate" DESC, "startDate" DESC
                    LIMIT 10
                """
                results = await self.execute_query(query)

            if results:
                opportunities = []
                total_value = 0

                for row in results:
                    opp = {
                        "facility": row.get('facility_name', 'Unknown'),
                        "specialty": row.get('specialty', ''),
                        "location": row.get('state', ''),
                        "rate": float(row.get('bill_rate', 0)),
                        "positions": int(row.get('open_positions', 0)),
                        "urgency": row.get('urgency_score', 0)
                    }
                    opportunities.append(opp)

                    # Calculate estimated value (rate * positions * 13 weeks)
                    total_value += opp['rate'] * opp['positions'] * 40 * 13

                return {
                    "opportunities": opportunities,
                    "total_opportunities": len(opportunities),
                    "estimated_value": total_value
                }

            return None

        except Exception as e:
            print(f"Error getting lead opportunities: {e}")
            return None

    async def get_clients_by_rate(self, parameters, target_rate: float = None, rate_tolerance: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Get clients/facilities by rate (highest, lowest, or similar to target)

        Args:
            parameters: Query parameters with specialty, location, rate_type, rate_filter
            target_rate: Target rate to match (for "similar" filter)
            rate_tolerance: Percentage tolerance for rate matching (default 10%)
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized - cannot query clients")
                return None

            specialty = getattr(parameters, 'specialty', None)
            location = getattr(parameters, 'location', None)
            rate_type = getattr(parameters, 'rate_type', None)
            rate_filter = getattr(parameters, 'rate_filter', 'highest')

            # Determine which rate column to use based on rate_type
            if rate_type == 'hourly_pay':
                rate_column = '"hourlyPay"'
                rate_label = 'Hourly Pay ($/hr)'
            elif rate_type == 'weekly_pay':
                rate_column = '"weeklyPay"'
                rate_label = 'Weekly Pay ($/week)'
            else:
                # Default to bill_rate for business queries
                rate_column = '"billRate"'
                rate_label = 'Bill Rate ($/hr)'

            print(f"🔍 Client search: specialty='{specialty}', location='{location}', rate_column={rate_column}, filter='{rate_filter}', target_rate={target_rate}")

            # Handle different rate filters
            if rate_filter == 'highest' or rate_filter == 'lowest':
                # Query for highest or lowest paying clients
                order_direction = "DESC" if rate_filter == 'highest' else "ASC"

                if specialty and location:
                    query = f"""
                        SELECT DISTINCT
                            "clientName" as client_name,
                            city,
                            state,
                            specialty,
                            AVG({rate_column}) as avg_rate,
                            COUNT(*) as assignment_count,
                            MAX("startDate") as most_recent
                        FROM vmsrawscrape_prod
                        WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                            AND LOWER(state) = LOWER($2)
                            AND {rate_column} IS NOT NULL
                            AND "billRate" BETWEEN 30 AND 800
                            AND "weeklyPay" BETWEEN 1200 AND 15000
                            AND "hourlyPay" BETWEEN 10 AND 250
                            AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                            AND "clientName" IS NOT NULL
                        GROUP BY "clientName", city, state, specialty
                        ORDER BY avg_rate {order_direction}
                        LIMIT 15
                    """
                    results = await self.execute_query(query, specialty, location)
                elif specialty:
                    query = f"""
                        SELECT DISTINCT
                            "clientName" as client_name,
                            city,
                            state,
                            specialty,
                            AVG({rate_column}) as avg_rate,
                            COUNT(*) as assignment_count,
                            MAX("startDate") as most_recent
                        FROM vmsrawscrape_prod
                        WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                            AND {rate_column} IS NOT NULL
                            AND "billRate" BETWEEN 30 AND 800
                            AND "weeklyPay" BETWEEN 1200 AND 15000
                            AND "hourlyPay" BETWEEN 10 AND 250
                            AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                            AND "clientName" IS NOT NULL
                        GROUP BY "clientName", city, state, specialty
                        ORDER BY avg_rate {order_direction}
                        LIMIT 15
                    """
                    results = await self.execute_query(query, specialty)
                elif location:
                    query = f"""
                        SELECT DISTINCT
                            "clientName" as client_name,
                            city,
                            state,
                            specialty,
                            AVG({rate_column}) as avg_rate,
                            COUNT(*) as assignment_count,
                            MAX("startDate") as most_recent
                        FROM vmsrawscrape_prod
                        WHERE LOWER(state) = LOWER($1)
                            AND {rate_column} IS NOT NULL
                            AND "billRate" BETWEEN 30 AND 800
                            AND "weeklyPay" BETWEEN 1200 AND 15000
                            AND "hourlyPay" BETWEEN 10 AND 250
                            AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                            AND "clientName" IS NOT NULL
                        GROUP BY "clientName", city, state, specialty
                        ORDER BY avg_rate {order_direction}
                        LIMIT 15
                    """
                    results = await self.execute_query(query, location)
                else:
                    return None

            else:
                # Handle "similar" filter - need a target rate
                if target_rate is None:
                    # Get market average as target
                    avg_query = f"""
                        SELECT AVG({rate_column}) as avg_rate
                        FROM vmsrawscrape_prod
                        WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                            AND {rate_column} IS NOT NULL
                            AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    """
                    if location:
                        avg_query += " AND LOWER(state) = LOWER($2)"
                        avg_result = await self.execute_one(avg_query, specialty, location)
                    else:
                        avg_result = await self.execute_one(avg_query, specialty)

                    if avg_result and avg_result.get('avg_rate'):
                        target_rate = float(avg_result['avg_rate'])
                    else:
                        return None

                # Calculate rate range
                min_rate = target_rate * (1 - rate_tolerance / 100)
                max_rate = target_rate * (1 + rate_tolerance / 100)

                # Build client search query for similar rates
                if specialty and location:
                    query = f"""
                        SELECT DISTINCT
                            "clientName" as client_name,
                            city,
                            state,
                            specialty,
                            AVG({rate_column}) as avg_rate,
                            COUNT(*) as assignment_count,
                            MAX("startDate") as most_recent
                        FROM vmsrawscrape_prod
                        WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                            AND LOWER(state) = LOWER($2)
                            AND {rate_column} BETWEEN $3 AND $4
                            AND {rate_column} IS NOT NULL
                            AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                            AND "clientName" IS NOT NULL
                        GROUP BY "clientName", city, state, specialty
                        ORDER BY assignment_count DESC, avg_rate DESC
                        LIMIT 15
                    """
                    results = await self.execute_query(query, specialty, location, min_rate, max_rate)
                elif specialty:
                    query = f"""
                        SELECT DISTINCT
                            "clientName" as client_name,
                            city,
                            state,
                            specialty,
                            AVG({rate_column}) as avg_rate,
                            COUNT(*) as assignment_count,
                            MAX("startDate") as most_recent
                        FROM vmsrawscrape_prod
                        WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                            AND {rate_column} BETWEEN $2 AND $3
                            AND {rate_column} IS NOT NULL
                            AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                            AND "clientName" IS NOT NULL
                        GROUP BY "clientName", city, state, specialty
                        ORDER BY assignment_count DESC, avg_rate DESC
                        LIMIT 15
                    """
                    results = await self.execute_query(query, specialty, min_rate, max_rate)
                else:
                    return None

            if results:
                clients = []
                for row in results:
                    most_recent = row.get('most_recent')
                    client = {
                        "client_name": row.get('client_name', 'Unknown'),
                        "city": row.get('city', ''),
                        "state": row.get('state', ''),
                        "specialty": row.get('specialty', ''),
                        "avg_rate": float(row.get('avg_rate', 0)),
                        "assignment_count": int(row.get('assignment_count', 0)),
                        "most_recent": most_recent.isoformat() if most_recent else None
                    }
                    clients.append(client)

                response = {
                    "clients": clients,
                    "total_clients": len(clients),
                    "specialty": specialty,
                    "location": location,
                    "rate_filter": rate_filter,
                    "rate_type_label": rate_label,
                    "rate_column_queried": rate_column.strip('"')
                }

                # Add target_rate and rate_range only for "similar" queries
                if rate_filter == 'similar' and target_rate:
                    response["target_rate"] = target_rate
                    response["rate_range"] = {"min": min_rate, "max": max_rate}

                return response

            return None

        except Exception as e:
            print(f"Error getting clients by rate: {e}")
            return None

    async def get_comparable_jobs(self, parameters, target_rate: float = None, rate_range: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Get comparable job positions with similar pay packages in the same location

        Args:
            parameters: Query parameters with specialty, city, state, rate_type
            target_rate: Target rate to find similar positions around
            rate_range: Tuple of (min_rate, max_rate) to search within
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized")
                return None

            specialty = getattr(parameters, 'specialty', None)
            city = getattr(parameters, 'city', None)
            state = getattr(parameters, 'state', None)
            location = getattr(parameters, 'location', None)
            rate_type = getattr(parameters, 'rate_type', None)

            # Map rate_type to column
            if rate_type == 'hourly_pay':
                rate_column = '"hourlyPay"'
                rate_label = 'hourly pay'
            elif rate_type == 'weekly_pay':
                rate_column = '"weeklyPay"'
                rate_label = 'weekly pay'
            else:
                rate_column = '"billRate"'
                rate_label = 'bill rate'

            print(f"🔍 Looking for comparable jobs: specialty='{specialty}', city='{city}', state='{state}', rate_type='{rate_column}'")

            # If rate_range is provided, use it; otherwise calculate from target_rate
            if rate_range:
                min_rate, max_rate = rate_range
            elif target_rate:
                # ±10% range for comparable positions
                min_rate = target_rate * 0.9
                max_rate = target_rate * 1.1
            else:
                # No rate context provided
                return None

            # Build query based on location specificity
            if city and state:
                # City-specific search
                query = f"""
                    SELECT
                        specialty,
                        "clientName" as client_name,
                        city,
                        state,
                        {rate_column} as rate,
                        "startDate" as start_date,
                        "weeklyPay" as weekly_pay,
                        "hourlyPay" as hourly_pay,
                        "billRate" as bill_rate
                    FROM vmsrawscrape_prod
                    WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                        AND LOWER(city) = LOWER($2)
                        AND LOWER(state) = LOWER($3)
                        AND {rate_column} BETWEEN $4 AND $5
                        AND {rate_column} IS NOT NULL
                        AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "clientName" IS NOT NULL
                    ORDER BY "startDate" ASC
                    LIMIT 20
                """
                results = await self.execute_query(query, specialty, city, state, min_rate, max_rate)
            elif state or location:
                # State-level search
                state_code = state or location
                query = f"""
                    SELECT
                        specialty,
                        "clientName" as client_name,
                        city,
                        state,
                        {rate_column} as rate,
                        "startDate" as start_date,
                        "weeklyPay" as weekly_pay,
                        "hourlyPay" as hourly_pay,
                        "billRate" as bill_rate
                    FROM vmsrawscrape_prod
                    WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                        AND LOWER(state) = LOWER($2)
                        AND {rate_column} BETWEEN $3 AND $4
                        AND {rate_column} IS NOT NULL
                        AND "startDate" >= CURRENT_DATE
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "clientName" IS NOT NULL
                    ORDER BY "startDate" ASC
                    LIMIT 20
                """
                results = await self.execute_query(query, specialty, state_code, min_rate, max_rate)
            else:
                return None

            if results:
                jobs = []
                for row in results:
                    start_date = row.get('start_date')
                    jobs.append({
                        "specialty": row.get('specialty'),
                        "client_name": row.get('client_name'),
                        "city": row.get('city'),
                        "state": row.get('state'),
                        "rate": float(row.get('rate', 0)),
                        "start_date": start_date.isoformat() if start_date else None,
                        "weekly_pay": float(row.get('weekly_pay', 0)) if row.get('weekly_pay') else None,
                        "hourly_pay": float(row.get('hourly_pay', 0)) if row.get('hourly_pay') else None,
                        "bill_rate": float(row.get('bill_rate', 0)) if row.get('bill_rate') else None
                    })

                return {
                    "jobs": jobs,
                    "total_jobs": len(jobs),
                    "specialty": specialty,
                    "city": city,
                    "state": state or location,
                    "rate_range": {"min": min_rate, "max": max_rate},
                    "rate_type_label": rate_label
                }

            return None

        except Exception as e:
            print(f"Error getting comparable jobs: {e}")
            return None

    async def get_highest_rates_in_market(self, parameters) -> Optional[Dict[str, Any]]:
        """
        Get the highest rates in the market for competitive comparison
        Used when positions aren't filling - compare against top market rates
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized")
                return None

            specialty = getattr(parameters, 'specialty', None)
            city = getattr(parameters, 'city', None)
            state = getattr(parameters, 'state', None)
            location = getattr(parameters, 'location', None)
            rate_type = getattr(parameters, 'rate_type', None)

            # Map rate_type to column
            if rate_type == 'hourly_pay':
                rate_column = '"hourlyPay"'
                rate_label = 'hourly pay'
            elif rate_type == 'weekly_pay':
                rate_column = '"weeklyPay"'
                rate_label = 'weekly pay'
            else:
                rate_column = '"billRate"'
                rate_label = 'bill rate'

            print(f"🔍 Getting highest rates: specialty='{specialty}', city='{city}', state='{state}', rate_type='{rate_column}'")

            # Get top 10% of rates (90th percentile and above)
            if city and state:
                query = f"""
                    SELECT
                        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {rate_column}) as percentile_75,
                        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY {rate_column}) as percentile_90,
                        MAX({rate_column}) as max_rate,
                        AVG({rate_column}) as market_average,
                        AVG("weeklyPay") as avg_weekly_pay,
                        AVG("hourlyPay") as avg_hourly_pay,
                        AVG("billRate") as avg_bill_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                        AND LOWER(city) = LOWER($2)
                        AND LOWER(state) = LOWER($3)
                        AND {rate_column} IS NOT NULL
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    HAVING COUNT(*) >= 5
                """
                result = await self.execute_one(query, specialty, city, state)
            elif state or location:
                state_code = state or location
                query = f"""
                    SELECT
                        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {rate_column}) as percentile_75,
                        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY {rate_column}) as percentile_90,
                        MAX({rate_column}) as max_rate,
                        AVG({rate_column}) as market_average,
                        AVG("weeklyPay") as avg_weekly_pay,
                        AVG("hourlyPay") as avg_hourly_pay,
                        AVG("billRate") as avg_bill_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                        AND LOWER(state) = LOWER($2)
                        AND {rate_column} IS NOT NULL
                        AND "startDate" >= NOW() - INTERVAL '3 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                    GROUP BY specialty
                """
                result = await self.execute_one(query, specialty, state_code)
            else:
                return None

            if result:
                return {
                    "specialty": specialty,
                    "city": city,
                    "state": state or location,
                    "percentile_75": float(result.get('percentile_75', 0)),
                    "percentile_90": float(result.get('percentile_90', 0)),
                    "max_rate": float(result.get('max_rate', 0)),
                    "market_average": float(result.get('market_average', 0)),
                    "avg_weekly_pay": float(result.get('avg_weekly_pay', 0)) if result.get('avg_weekly_pay') else None,
                    "avg_hourly_pay": float(result.get('avg_hourly_pay', 0)) if result.get('avg_hourly_pay') else None,
                    "avg_bill_rate": float(result.get('avg_bill_rate', 0)) if result.get('avg_bill_rate') else None,
                    "rate_type_label": rate_label,
                    "sample_size": int(result.get('sample_size', 0))
                }

            return None

        except Exception as e:
            print(f"Error getting highest rates: {e}")
            return None

    async def get_vendors_at_location(self, client_name: str, city: str = None, state: str = None, specialty: str = None) -> Optional[Dict[str, Any]]:
        """
        Get vendors/agencies working at a specific hospital or location

        Args:
            client_name: Hospital/facility name (can be partial match)
            city: Optional city filter
            state: Optional state filter
            specialty: Optional specialty filter
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized")
                return None

            print(f"🔍 Looking for vendors at: client='{client_name}', city='{city}', state='{state}', specialty='{specialty}'")

            # Build query with optional filters
            where_clauses = []
            params = []
            param_num = 1

            # Client name - use ILIKE for partial matching
            where_clauses.append(f'"clientName" ILIKE ${param_num}')
            params.append(f'%{client_name}%')
            param_num += 1

            if city:
                where_clauses.append(f'LOWER(city) = LOWER(${param_num})')
                params.append(city)
                param_num += 1

            if state:
                where_clauses.append(f'LOWER(state) = LOWER(${param_num})')
                params.append(state)
                param_num += 1

            if specialty:
                where_clauses.append(f'specialty ~ (\'(^|\\s|-)\' || ${param_num} || \'($|\\s)\')')
                params.append(specialty)
                param_num += 1

            where_clause = ' AND '.join(where_clauses)

            query = f"""
                SELECT
                    "vendorName" as vendor_name,
                    "clientName" as client_name,
                    city,
                    state,
                    specialty,
                    COUNT(*) as assignment_count,
                    AVG("billRate") as avg_bill_rate,
                    AVG("hourlyPay") as avg_hourly_pay,
                    AVG("weeklyPay") as avg_weekly_pay,
                    MAX("startDate") as most_recent
                FROM vmsrawscrape_prod
                WHERE {where_clause}
                    AND "vendorName" IS NOT NULL
                    AND "startDate" >= NOW() - INTERVAL '6 months'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                GROUP BY "vendorName", "clientName", city, state, specialty
                ORDER BY assignment_count DESC, most_recent DESC
                LIMIT 20
            """

            results = await self.execute_query(query, *params)

            if results:
                vendors = []
                for row in results:
                    most_recent = row.get('most_recent')
                    vendors.append({
                        "vendor_name": row.get('vendor_name'),
                        "client_name": row.get('client_name'),
                        "city": row.get('city'),
                        "state": row.get('state'),
                        "specialty": row.get('specialty'),
                        "assignment_count": int(row.get('assignment_count', 0)),
                        "avg_bill_rate": float(row.get('avg_bill_rate', 0)) if row.get('avg_bill_rate') else None,
                        "avg_hourly_pay": float(row.get('avg_hourly_pay', 0)) if row.get('avg_hourly_pay') else None,
                        "avg_weekly_pay": float(row.get('avg_weekly_pay', 0)) if row.get('avg_weekly_pay') else None,
                        "most_recent": most_recent.isoformat() if most_recent else None
                    })

                return {
                    "vendors": vendors,
                    "total_vendors": len(vendors),
                    "client_name": client_name,
                    "city": city,
                    "state": state,
                    "specialty": specialty
                }

            return None

        except Exception as e:
            print(f"Error getting vendors at location: {e}")
            return None

    async def get_vendor_info(self, vendor_name: str, specialty: str = None) -> Optional[Dict[str, Any]]:
        """
        Get vendor information

        This is a stub implementation. Replace with your actual database schema.
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized - cannot query vendor info")
                return None

            query = """
                SELECT
                    "vendorName" as vendor_name,
                    specialty,
                    state as location,
                    AVG("billRate") as average_rate,
                    COUNT(*) as total_assignments
                FROM vmsrawscrape_prod
                WHERE "vendorName" = $1
                    AND ($2 IS NULL OR specialty = $2)
                    AND "startDate" > NOW() - INTERVAL '180 days'
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                GROUP BY "vendorName", specialty, state
                LIMIT 1
            """

            result = await self.execute_one(query, vendor_name, specialty)

            if result:
                return {
                    "vendor_name": result.get('vendor_name', vendor_name),
                    "specialty": result.get('specialty', specialty or 'All'),
                    "location": result.get('location', 'National'),
                    "average_rate": float(result.get('average_rate', 0)),
                    "total_assignments": int(result.get('total_assignments', 0))
                }

            return None

        except Exception as e:
            print(f"Error getting vendor info: {e}")
            return None

    async def get_rate_trends_by_state(self, parameters, trend_direction: str = 'rising', limit: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get states where rates are rising or falling for a specialty

        Compares recent 30 days vs previous 60 days to identify trends

        Args:
            parameters: Query parameters with specialty and rate_type
            trend_direction: 'rising' or 'falling'
            limit: Number of states to return (default 5)
        """
        try:
            if not self.pool:
                print("❌ Database pool not initialized")
                return None

            specialty = getattr(parameters, 'specialty', None)
            rate_type = getattr(parameters, 'rate_type', None)
            profession = getattr(parameters, 'profession', None)

            if not specialty:
                return None

            # Map rate_type to column
            if rate_type == 'hourly_pay':
                rate_column = '"hourlyPay"'
                rate_label = 'hourly pay'
            elif rate_type == 'weekly_pay':
                rate_column = '"weeklyPay"'
                rate_label = 'weekly pay'
            else:
                rate_column = '"billRate"'
                rate_label = 'bill rate'

            # Normalize specialty
            normalized_specialty = self._normalize_specialty_for_query(specialty) if specialty else None
            profession_filter = self._get_profession_filter(profession)

            print(f"🔍 Analyzing rate trends: specialty='{specialty}', rate_type='{rate_label}', direction='{trend_direction}'")

            # Query to compare recent vs older rates by state
            order = "DESC" if trend_direction == 'rising' else "ASC"
            # Filter direction: rising = positive changes, falling = negative changes
            direction_filter = "> 0" if trend_direction == 'rising' else "< 0"

            query = f"""
                WITH recent_rates AS (
                    SELECT
                        state,
                        AVG({rate_column}) as avg_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE "newSpecialty" ~ $1
                        AND {rate_column} IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '30 days'
                        {profession_filter}
                    GROUP BY state
                    HAVING COUNT(*) >= 2
                ),
                older_rates AS (
                    SELECT
                        state,
                        AVG({rate_column}) as avg_rate,
                        COUNT(*) as sample_size
                    FROM vmsrawscrape_prod
                    WHERE "newSpecialty" ~ $1
                        AND {rate_column} IS NOT NULL
                        AND "billRate" BETWEEN 30 AND 800
                        AND "weeklyPay" BETWEEN 1200 AND 15000
                        AND "hourlyPay" BETWEEN 10 AND 250
                        AND "startDate" >= NOW() - INTERVAL '90 days'
                        AND "startDate" < NOW() - INTERVAL '30 days'
                        {profession_filter}
                    GROUP BY state
                    HAVING COUNT(*) >= 2
                )
                SELECT
                    r.state,
                    r.avg_rate as recent_rate,
                    o.avg_rate as older_rate,
                    ((r.avg_rate - o.avg_rate) / o.avg_rate * 100) as percent_change,
                    r.sample_size as recent_sample_size,
                    o.sample_size as older_sample_size
                FROM recent_rates r
                JOIN older_rates o ON r.state = o.state
                WHERE ((r.avg_rate - o.avg_rate) / o.avg_rate * 100) {direction_filter}
                    AND ABS((r.avg_rate - o.avg_rate) / o.avg_rate * 100) >= 1.0
                ORDER BY percent_change {order}
                LIMIT $2
            """

            results = await self.execute_query(query, normalized_specialty, limit)

            if results:
                trends = []
                for row in results:
                    trends.append({
                        "state": row.get('state'),
                        "recent_rate": float(row.get('recent_rate', 0)),
                        "older_rate": float(row.get('older_rate', 0)),
                        "percent_change": float(row.get('percent_change', 0)),
                        "recent_sample_size": int(row.get('recent_sample_size', 0)),
                        "older_sample_size": int(row.get('older_sample_size', 0))
                    })

                return {
                    "trends": trends,
                    "specialty": specialty,
                    "rate_type_label": rate_label,
                    "trend_direction": trend_direction,
                    "total_states": len(trends)
                }

            return None

        except Exception as e:
            print(f"Error getting rate trends: {e}")
            return None

    async def get_vendor_for_client(self, client_name: str, city: str = None, state: str = None) -> Optional[Dict[str, Any]]:
        """
        Get the top 3 most common VMS vendors for a given client (for active/future jobs)

        Args:
            client_name: The client/hospital/facility name to search for
            city: Optional city filter
            state: Optional state filter

        Returns:
            Dict with vendor info including:
            - vendors: List of top 3 vendors with their counts
            - total_jobs: Total jobs matching the criteria
            - client_name: Matched client name from database
            - city: City if filtered
            - state: State if filtered
        """
        try:
            print(f"🔍 Looking up vendor/MSP for client: {client_name}")
            if city:
                print(f"   City filter: {city}")
            if state:
                print(f"   State filter: {state}")

            # Build WHERE clause with optional city/state filters
            where_conditions = ['"clientName" ILIKE $1']
            params = [f"%{client_name}%"]
            param_count = 1

            if city:
                param_count += 1
                where_conditions.append(f'city ILIKE ${param_count}')
                params.append(f"%{city}%")

            if state:
                param_count += 1
                where_conditions.append(f'state ILIKE ${param_count}')
                params.append(f"%{state}%")

            where_clause = " AND ".join(where_conditions)

            # Query to find top 3 VMS vendors for active/future jobs
            # Use parentOrg column which is standardized (instead of raw vms column)
            # Filter for startDate >= CURRENT_DATE (active/future jobs only)
            query = f"""
                WITH vendor_counts AS (
                    SELECT
                        "parentOrg" as vendor_name,
                        COUNT(*) as vms_count
                    FROM vmsrawscrape_prod
                    WHERE {where_clause}
                        AND "parentOrg" IS NOT NULL
                        AND TRIM("parentOrg") != ''
                        AND "startDate" >= CURRENT_DATE
                    GROUP BY "parentOrg"
                    ORDER BY vms_count DESC
                    LIMIT 3
                ),
                total_jobs AS (
                    SELECT
                        COUNT(*) as total_count,
                        "clientName",
                        city,
                        state
                    FROM vmsrawscrape_prod
                    WHERE {where_clause}
                        AND "startDate" >= CURRENT_DATE
                    GROUP BY "clientName", city, state
                    LIMIT 1
                )
                SELECT
                    json_agg(
                        json_build_object(
                            'vendor_name', vc.vendor_name,
                            'vms_count', vc.vms_count,
                            'percentage', ROUND((vc.vms_count::numeric / tj.total_count::numeric) * 100, 1)
                        )
                        ORDER BY vc.vms_count DESC
                    ) as vendors,
                    tj.total_count as total_jobs,
                    tj."clientName" as client_name,
                    tj.city,
                    tj.state
                FROM vendor_counts vc
                CROSS JOIN total_jobs tj
                GROUP BY tj.total_count, tj."clientName", tj.city, tj.state
            """

            result = await self.execute_one(query, *params)

            if result and result.get('vendors'):
                # Parse vendors JSON if it's a string
                import json
                vendors = result['vendors']
                if isinstance(vendors, str):
                    vendors = json.loads(vendors)

                print(f"  ✅ Found {len(vendors)} vendors:")
                for v in vendors:
                    print(f"     - {v['vendor_name']}: {v['vms_count']} jobs ({v['percentage']}%)")
                print(f"  📊 Total active jobs: {result['total_jobs']}")

                # Update result with parsed vendors
                result['vendors'] = vendors
                return result
            else:
                print(f"  ⚠️ No vendor data found for client matching '{client_name}'")
                return None

        except Exception as e:
            print(f"❌ Error getting vendor for client: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def find_nearby_jobs(
        self,
        center_lat: float,
        center_lon: float,
        radius_miles: float = 50,
        specialty: str = None,
        rate_type: str = "billRate",
        min_rate: float = None,
        profession: str = None,
        limit: int = 20
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Find jobs within a certain radius of a given location

        Args:
            center_lat: Center point latitude
            center_lon: Center point longitude
            radius_miles: Search radius in miles (default: 50)
            specialty: Optional specialty filter
            rate_type: billRate, weeklyPay, or hourlyPay (default: billRate)
            min_rate: Optional minimum rate filter
            profession: Optional profession filter
            limit: Maximum number of results (default: 20)

        Returns:
            List of jobs with distance information, sorted by distance
        """
        try:
            print(f"🔍 Finding jobs within {radius_miles} miles of ({center_lat}, {center_lon})")

            # Build WHERE conditions
            where_conditions = [
                'latitude IS NOT NULL',
                'longitude IS NOT NULL',
                '"startDate" >= NOW() - INTERVAL \'3 months\''  # Recent jobs (last 3 months)
            ]

            params = []
            param_count = 0

            if specialty:
                normalized_specialty = self._normalize_specialty_for_query(specialty)
                param_count += 1
                where_conditions.append(f'"newSpecialty" ~ ${param_count}')
                params.append(normalized_specialty)

            if profession:
                param_count += 1
                where_conditions.append(f'"newProfession" = ${param_count}')
                params.append(profession)

            # Map rate_type to column name
            rate_column_map = {
                "billRate": "billRate",
                "bill_rate": "billRate",
                "weeklyPay": "weeklyPay",
                "weekly_pay": "weeklyPay",
                "hourlyPay": "hourlyPay",
                "hourly_pay": "hourlyPay"
            }
            rate_column = rate_column_map.get(rate_type, "billRate")
            where_conditions.append(f'"{rate_column}" IS NOT NULL')

            if min_rate:
                param_count += 1
                where_conditions.append(f'"{rate_column}" >= ${param_count}')
                params.append(min_rate)

            where_clause = " AND ".join(where_conditions)

            # PostgreSQL query using the Haversine formula directly in SQL for efficiency
            # This calculates distance in the database rather than in Python
            query = f"""
                SELECT
                    "clientName",
                    city,
                    state,
                    "newSpecialty",
                    "newProfession",
                    "{rate_column}" as rate,
                    "startDate",
                    "shiftType",
                    vms,
                    latitude,
                    longitude,
                    (
                        3959 * acos(
                            cos(radians({center_lat})) * cos(radians(latitude)) *
                            cos(radians(longitude) - radians({center_lon})) +
                            sin(radians({center_lat})) * sin(radians(latitude))
                        )
                    ) AS distance_miles
                FROM vmsrawscrape_prod
                WHERE {where_clause}
                    AND (
                        3959 * acos(
                            cos(radians({center_lat})) * cos(radians(latitude)) *
                            cos(radians(longitude) - radians({center_lon})) +
                            sin(radians({center_lat})) * sin(radians(latitude))
                        )
                    ) <= {radius_miles}
                ORDER BY distance_miles ASC
                LIMIT {limit}
            """

            results = await self.execute_query(query, *params)

            if results:
                print(f"  ✅ Found {len(results)} jobs within {radius_miles} miles")
                for i, job in enumerate(results[:3], 1):
                    print(f"     {i}. {job['clientName']} - {job['newSpecialty']} - {job['distance_miles']:.1f} mi - ${job['rate']:.0f}")
            else:
                print(f"  ⚠️ No jobs found within {radius_miles} miles")

            return results

        except Exception as e:
            print(f"❌ Error finding nearby jobs: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            result = await self.execute_one("SELECT 1 as test")
            return result is not None
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
