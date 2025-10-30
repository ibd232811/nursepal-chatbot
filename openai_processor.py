"""
OpenAI Processor for Healthcare Staffing Intelligence
Handles NLP parameter extraction and response generation
"""

from openai import AsyncOpenAI
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import json


@dataclass
class QueryParameters:
    """Extracted parameters from user query"""
    query_type: str  # "rate_recommendation", "lead_generation", "forecast_analysis", etc.
    specialty: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    client_name: Optional[str] = None  # Facility/hospital name for vendor_location queries
    location_list: Optional[list] = None  # List of locations for market_comparison queries
    user_perspective: Optional[str] = None  # "sales", "recruiter", "operations", "finance"
    time_horizon: Optional[str] = None  # For forecasting: "4_weeks", "12_weeks", etc.
    is_temporal_query: bool = False
    rate_type: Optional[str] = None  # "bill_rate", "hourly_pay", or "weekly_pay"
    rate_filter: Optional[str] = None  # "highest", "lowest", or "similar"
    proposed_rate: Optional[float] = None  # User's proposed/suggested rate for comparison
    profession: Optional[str] = None  # "Nursing", "Allied", "Locum/Tenens", "Therapy"
    trend_direction: Optional[str] = None  # "rising" or "falling" for rate_trends queries
    radius_miles: Optional[float] = None  # Search radius in miles for nearby_jobs queries


class OpenAIProcessor:
    """Handles OpenAI API interactions for NLP tasks"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: int = 30):
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.timeout = timeout

    async def extract_parameters(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        user_role: Optional[str] = None
    ) -> QueryParameters:
        """
        Extract structured parameters from user message using GPT

        Detects:
        - Query type (rate recommendation, lead generation, forecasting)
        - Specialty (ICU, ED, OR, etc.)
        - Location (state or city)
        - User perspective (sales, recruiter, operations, finance)
        - Time horizon for forecasting queries
        """

        # Build context from conversation history
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-4:]
            history_context = "\nRecent conversation:\n"
            for msg in recent_messages:
                history_context += f"{msg.get('role', 'user')}: {msg.get('content', '')}\n"

        role_context = f"\nUser role: {user_role}" if user_role else ""

        system_prompt = """You are a parameter extraction system for healthcare staffing queries.

Analyze the user's message and extract:
1. query_type: One of:
   - "rate_recommendation" - asking about CURRENT rates, pricing, "what should I charge", "what's the rate", "how much", "bill rate", "pay rate"
   - "rate_comparison" - asking if a specific rate is too high/low, "is $120 too high", "should I charge $95", "is this rate competitive", "am I overpriced", "are my competitors billing more"
   - "market_comparison" - comparing rates between two locations, "how much higher is Buffalo than Ithaca", "compare ICU rates in Ohio and NY", "what's the difference between"
   - "rate_impact" - asking about impact of changing rates, "if I drop the rate", "can we still fill at $X", "what if I lower/raise the rate", "will we struggle to fill"
   - "unfilled_position" - asking why position isn't filling, "why can't I fill this", "position not filling", "having trouble filling", "nurses demanding higher wages", "can't get anyone"
   - "nearby_jobs" - asking for jobs within a radius/distance of a location, "show me jobs within X miles", "jobs near Cincinnati", "within 50 miles of", "jobs around", "nearby positions", "open jobs within"
   - "comparable_jobs" - asking about similar positions/jobs, "what are comparable jobs", "show me similar positions", "what other jobs", "comparable positions"
   - "client_search" - asking about specific clients/facilities/hospitals with certain rates or jobs, "what clients", "which facilities", "who pays", "facilities with rates", "what hospital has", "what hospital pays", "highest-paying opening", "highest-paying job", "which hospital", "show me facilities", "show me hospitals", "show me clients"
   - "vendor_contract" - asking who has the contract/MSP/VMS with a specific client/hospital, "who has the contract with", "what vendor works with", "who is their MSP", "who do they work with", "what VMS", "who is the MSP for", "vendor for this hospital", "MSP at this facility"
   - "vendor_location" - asking which vendors/agencies/MSP are at a specific hospital/location, "what vendors at Memorial", "which agencies work at this hospital", "who has nurses at", "what staffing agencies"
   - "lead_generation" - looking for sales opportunities, "best opportunities", "where should I sell", "hot markets"
   - "competitive_analysis" - comparing to competitors, "how do we compare", "competitive position"
   - "forecast_analysis" - asking about FUTURE rates or trends (detect time references like "next quarter", "will be", "forecast")
   - "forecast_comparison" - comparing current rates to future forecasted rates, "compare current to future", "should I lock in now or wait", "will rates go up", "better now or in 6 months", "current vs projected"
   - "rate_trends" - asking where rates are rising, falling, increasing, decreasing, growing, OR asking which state/location has highest/lowest rates, "where are rates rising", "which states have increasing rates", "where are ICU rates going up", "states with falling rates", "where are rates dropping", "what state has the highest rates", "which state has the lowest rates", "where are rates highest", "where are rates lowest", "what location has the best rates"
   - "vendor_info" - asking about specific vendors by name
   - "conversational" - casual conversation like "thank you", "thanks", "this is great", "awesome", "perfect", "appreciate it", "hello", "hi"
   - "general" - ONLY if none of the above match

2. specialty: Nursing specialty (ICU, ED, OR, Med/Surg, Telemetry, PACU, CVOR, Cath Lab, etc.) or null
   CRITICAL: Do NOT confuse state abbreviations with specialties:
   - "CA" = California (state), NOT CRNA specialty
   - "OR" = Oregon (state) when used alone, or Operating Room when with "nurse" context
   - "PA" = Pennsylvania (state), NOT Physician Assistant
   - If user says just "CA", "TX", "NY", "FL" etc. alone, it's a STATE not a specialty
3. location: US state abbreviation (CA, TX, NY, FL, etc.) or city name, or null
   - CRITICAL: If user says "nationally", "national", "across the US", "all states", "nationwide", "in the US", "the US" → set location=null, state=null, city=null
   - This indicates a national/all-states query with no geographic filter
3a. city: City name if mentioned (Buffalo, NYC, Los Angeles, etc.) or null
3b. state: State abbreviation if mentioned (NY, CA, TX, FL, etc.) or null
   - CRITICAL: Single 2-letter codes like "CA", "NY", "TX" should go in state field, NOT specialty
   - If user says "nationally", "national", "across the US", "in the US", "the US" → set state=null (no state filter)
3c. client_name: Hospital or facility name if mentioned (Memorial Hospital, Cleveland Clinic, etc.) or null
3d. location_list: For market_comparison queries, extract array of locations being compared:
   - Extract full location names with city and state if provided (e.g., ["Cincinnati, OH", "Buffalo, NY"] or ["Buffalo", "Ithaca"])
   - Use city names if mentioned (e.g., "Cincinnati" and "Buffalo")
   - Use state abbreviations if only states mentioned (e.g., ["Ohio", "NY"] or ["OH", "NY"])
   - CRITICAL: If comparing to "nationally", "national", "nationwide", "across the US", "the US", use "National" as the location string
   - Examples: "compare Cincinnati Ohio and Buffalo NY" → ["Cincinnati, OH", "Buffalo, NY"]
   - Examples: "Buffalo vs Ithaca" → ["Buffalo", "Ithaca"]
   - Examples: "Ohio vs NY" → ["OH", "NY"]
   - Examples: "MI vs nationally" → ["MI", "National"]
   - Examples: "CRNA jobs in MI versus nationally" → ["MI", "National"]
   - null if not a market_comparison query
4. user_perspective: Inferred role - "sales", "recruiter", "operations", "finance", or null
5. is_temporal_query: true if asking about future/predictions (contains: "will be", "next quarter", "forecast", "outlook", "predict", "trend", "2025", "2026", specific future months, etc.)
6. time_horizon: If temporal query, ALWAYS calculate and return a timeframe (NEVER return null for temporal queries):
   - Current date context: October 21, 2025
   - For SPECIFIC FUTURE DATES, calculate weeks from now and map to closest option:
     * "March 2026" = ~20 weeks from now → return "26_weeks"
     * "January 2026" = ~10 weeks from now → return "12_weeks"
     * "April 2026" = ~24 weeks from now → return "26_weeks"
     * "December 2025" = ~6 weeks from now → return "4_weeks"
     * "July 2026" = ~36 weeks from now → return "52_weeks"
     * "October 2026" = ~52 weeks from now → return "52_weeks"
   - For RELATIVE TIMES:
     * "next month", "4 weeks", "1 month" → "4_weeks"
     * "3 months", "next quarter", "Q1" → "12_weeks"
     * "6 months", "half year" → "26_weeks"
     * "1 year", "next year", "12 months" → "52_weeks"
   - CRITICAL: If is_temporal_query is true, time_horizon MUST have a value (default to "12_weeks" if unclear)
   - Only return null if NOT a temporal query
7. rate_type: Determine which rate metric to use:
   - "bill_rate" - if asking about billing, client rates, what to charge, sales perspective (default for sales/operations)
   - "hourly_pay" - if asking about pay, compensation, what nurses earn, recruiter perspective (default for recruiters)
   - "weekly_pay" - if asking about weekly pay, weekly rates, weekly compensation, "per week", "/week", "weekly"
   - null - if unclear, will default to bill_rate
8. rate_filter: For client_search queries, determine what kind of rates:
   - "highest" - if asking for "highest", "best paying", "top rates", "most expensive"
   - "lowest" - if asking for "lowest", "cheapest", "most affordable"
   - "similar" - if asking for "similar to", "around", "close to" (with specific rate)
   - null - default to "highest" for client searches
9. proposed_rate: Extract numeric rate if user asks about a specific rate:
   - Extract numbers from queries like "is $120 too high", "should I charge $95", "is 85/hr competitive", "if I drop it to $90"
   - Return as float (e.g., 120.0, 95.0, 85.0, 90.0)
   - For rate_impact queries, extract the new/changed rate being proposed (e.g., "drop by $10" → extract the resulting rate)
   - CRITICAL: DO NOT extract proposed_rate if user is just asking "what about [location]" - that's a new rate_recommendation query
   - CRITICAL: DO NOT carry forward rates from conversation history when user asks about a different location
   - Only carry forward if it's clearly the same rate being discussed (e.g., "is this competitive in another city?")
   - null if no specific rate mentioned in the current message
10. trend_direction: For rate_trends queries, determine direction:
   - "rising" - if asking about "rising", "increasing", "going up", "growing", "climbing", "higher", "highest", "best rates", "top rates"
   - "falling" - if asking about "falling", "decreasing", "going down", "dropping", "declining", "lower", "lowest", "cheapest rates"
   - null - if not a rate_trends query (default to "rising" if unclear)
   - IMPORTANT: "what state has the highest rates" → trend_direction = "rising" (showing top states)
11. radius_miles: For nearby_jobs queries, extract the distance radius:
   - Extract numeric value from phrases like "within 50 miles", "50 mile radius", "100 miles of", "near" (default 25 miles for "near")
   - Examples: "within 50 miles" → 50.0, "100 mile radius" → 100.0, "near Cincinnati" → 25.0
   - Return as float (e.g., 50.0, 100.0, 25.0)
   - null if not a nearby_jobs query

CRITICAL RULES:
- If user asks "what's the rate for X" or "how much for X" → query_type = "rate_recommendation"
- If user asks "what clients", "which facilities", "what hospital", "show me clients", "who has rates like" → query_type = "client_search"
- If user asks "what will the rate be" or "future rates" → query_type = "forecast_analysis"
- If user asks "compare [location1] to/and/vs [location2]", "how much higher/lower is X than Y", "difference between X and Y", "versus nationally", "vs national" → query_type = "market_comparison"
- CRITICAL for market_comparison: If comparing to "nationally", "national", "nationwide" → use "National" in location_list (e.g., ["MI", "National"])
- If user asks "show me jobs within X miles", "jobs near [city]", "within 50 miles of", "open positions around", "jobs in a X mile radius" → query_type = "nearby_jobs" (MUST extract city, state, and radius_miles)
- If user asks "comparable jobs", "similar positions", "what other jobs", "show me positions" → query_type = "comparable_jobs"
- If user asks "if I drop/lower/raise the rate", "can we fill at $X", "will we struggle", "impact of changing" → query_type = "rate_impact"
- If user asks "why can't I fill", "position not filling", "having trouble", "nurses demanding more" → query_type = "unfilled_position"
- If user asks "what vendors at", "which agencies at Memorial", "who has nurses at this hospital" → query_type = "vendor_location"
- If user asks "where are rates rising", "which states have increasing rates", "where are rates going up", "states with falling rates", "where are rates dropping", "show me rising/falling rates", "where are X rates climbing", "what state has the highest rates", "which state has lowest rates" → query_type = "rate_trends"
- Always extract specialty if mentioned (ICU, ED, OR, etc.)
- CRITICAL STATE ABBREVIATIONS: When user types ONLY a 2-letter code (CA, NY, TX, FL, PA, etc.), treat as state, NOT specialty:
  * "CA" alone → state="CA", specialty=null (NOT specialty="CRNA")
  * "PA" alone → state="PA", specialty=null (NOT specialty="PA" or "Physician Assistant")
  * "OR" alone → state="OR", specialty=null (NOT specialty="OR" or "Operating Room")
  * Only extract specialty if there's additional context like "ICU", "ED", "nurse", etc.
- For vendor_location queries, extract the hospital/facility name into client_name parameter
- For follow-up questions like "what about [city/state]", "what about for [location]" → query_type = "rate_recommendation" (NOT rate_comparison)
- For "comparable jobs" queries, use conversation history to extract the location and rate range from previous rate recommendation
- For "rate_impact" queries, use conversation history to get specialty/location context and extract the proposed new rate
- NEVER carry forward proposed_rate when user asks about a different location - treat as new rate_recommendation
- Default to "rate_recommendation" if asking about pricing/rates without future context
- Only use "general" if NO specialty or actionable query is detected
- For rate_type: "bill rate", "charge", "billing" → "bill_rate"; "pay", "compensation", "salary", "earn" → "hourly_pay"; "weekly", "/week", "per week" → "weekly_pay"
- CONTEXT CARRYOVER: If the previous message asked for missing information (like "which specialty?", "which rate type?"), and the current message is just a single word/short phrase answering that question, carry forward ALL other parameters from the previous query (query_type, location_list, city, state, rate_type, etc.) and ONLY update the missing parameter that was requested
- NURSING PERSPECTIVE CARRYOVER: If user says "what about for nursing", "what about nurses", "for nursing", "nurse perspective" after ANY query (especially forecasts), this means:
  * KEEP the same specialty from conversation history (e.g., ICU, ED, OR, etc.) - DO NOT change specialty to "Nursing"
  * CHANGE rate_type to "weekly_pay" (nurses care about weekly pay, not bill rates)
  * KEEP the same location, time_horizon, and query_type from conversation history
  * Examples: After "What will ICU rates be in NY in March 2026?" (bill_rate), if user asks "What about for nursing?", return: specialty="ICU", rate_type="weekly_pay", location="NY", time_horizon="26_weeks"

Return ONLY valid JSON with these exact keys."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User message: {user_message}{history_context}{role_context}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Override query_type if temporal query detected
            if result.get('is_temporal_query', False):
                result['query_type'] = 'forecast_analysis'

            return QueryParameters(
                query_type=result.get('query_type', 'general'),
                specialty=result.get('specialty'),
                location=result.get('location'),
                city=result.get('city'),
                state=result.get('state'),
                client_name=result.get('client_name'),
                location_list=result.get('location_list'),
                user_perspective=result.get('user_perspective') or user_role,
                time_horizon=result.get('time_horizon'),
                is_temporal_query=result.get('is_temporal_query', False),
                rate_type=result.get('rate_type'),
                rate_filter=result.get('rate_filter'),
                proposed_rate=result.get('proposed_rate'),
                profession=result.get('profession'),
                trend_direction=result.get('trend_direction'),
                radius_miles=result.get('radius_miles')
            )

        except Exception as e:
            print(f"Error extracting parameters: {e}")
            # Return default parameters
            return QueryParameters(query_type='general')

    async def generate_response(
        self,
        data: Dict[str, Any],
        user_message: str,
        parameters: QueryParameters
    ) -> str:
        """
        Generate natural language response based on data and user query

        Args:
            data: Dictionary containing recommendation, lead_analysis, or other data
            user_message: Original user question
            parameters: Extracted parameters
        """

        # Build context based on user role
        role_guidance = self._get_role_guidance(parameters.user_perspective)

        system_prompt = f"""You are an AI assistant for healthcare staffing intelligence with access to REAL-TIME market data.

Your role: Provide clear, actionable insights based ONLY on the actual data provided.

{role_guidance}

CRITICAL RESPONSE RULES:
- ONLY use the specific data provided in the data context below
- DO NOT make up rates, numbers, or general industry knowledge
- DO NOT calculate weekly pay or any other values - use ONLY the actual averages from the database
- Lead with the ACTUAL market rate from the data
- If data includes sample_size, mention it for credibility
- Use specific numbers from the data (recommended_min, recommended_max, competitive_floor, market_average, avg_weekly_pay, avg_hourly_pay, avg_bill_rate)
- Recommended range is ±2.5% of market average (min to max)
- Competitive floor is the 25th percentile of actual market rates
- Show all three rate types when available (bill rate, hourly pay, weekly pay)
- ALWAYS include dates when available (most_recent, start dates, etc.) - format as readable dates
- If user asks about dates/timing, prioritize showing the most_recent date for each item
- Remember: Nursing positions are typically 36 hours per week, NOT 40 hours
- Keep responses concise but include all relevant data points
- Format rates clearly with $ signs
- CRITICAL: Bill rates for nursing are always $20-300/hr, weekly pay is typically $1,500-$5,000/week
- If you see a value over $300, it's weekly pay (not hourly) - clarify this in your response
- Always specify the rate type clearly: "Bill Rate: $X/hr" or "Weekly Pay: $X/week"

Example good response for client search:
"Here are the top clients in New York with highest ICU bill rates:

1. **Memorial Hospital** (NYC) - $125/hr avg, 8 assignments, Most Recent: Jan 15, 2025
2. **St. Vincent Medical** (Buffalo) - $118/hr avg, 6 assignments, Most Recent: Jan 10, 2025

These represent the most recent market data available."

Example good response for comparable jobs:
"Here are comparable ICU positions in Buffalo, NY with similar pay ($2,325-$2,446/week):

1. **Strong Memorial Hospital** - Buffalo, NY
   - Start: Feb 1, 2025 | Weekly: $2,400 | Hourly: $66.67 | Bill Rate: $98

2. **Buffalo General Medical Center** - Buffalo, NY
   - Start: Feb 5, 2025 | Weekly: $2,340 | Hourly: $65.00 | Bill Rate: $95

Found 12 total positions. These are upcoming assignments with pay packages similar to the market average."

Example good response for nearby jobs:
"Here are ICU positions within 50 miles of Cincinnati, OH:

1. **UC Health** - Cincinnati, OH (2.3 mi)
   - Start: Feb 1, 2025 | Bill Rate: $98/hr | Weekly: $2,400

2. **TriHealth Good Samaritan** - Cincinnati, OH (4.1 mi)
   - Start: Feb 10, 2025 | Bill Rate: $95/hr | Weekly: $2,340

3. **St. Elizabeth Healthcare** - Edgewood, KY (8.7 mi)
   - Start: Feb 15, 2025 | Bill Rate: $92/hr | Weekly: $2,250

Found 12 total positions within the search radius."

Example BAD response:
"Memorial Hospital pays $125/hr..." (MISSING dates and distances even though available in data!)
"""

        # Format the data for the prompt
        data_context = f"\nData to reference:\n{json.dumps(data, indent=2)}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"User question: {user_message}\n{data_context}\n\nProvide a helpful response."
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating response: {e}")
            return "I encountered an error generating a response. Please try again."

    async def generate_forecast_response(
        self,
        forecast_data: Dict[str, Any],
        user_message: str,
        parameters: QueryParameters
    ) -> str:
        """
        Generate response specifically for forecast analysis

        Args:
            forecast_data: Forecast analysis data
            user_message: Original user question
            parameters: Extracted parameters
        """

        role_guidance = self._get_role_guidance(parameters.user_perspective)

        # Check if we have dual forecast (state + national)
        has_dual_forecast = forecast_data.get("dual_forecast", False)
        dual_forecast_note = ""

        if has_dual_forecast:
            dual_forecast_note = """
DUAL FORECAST DATA AVAILABLE:
- You have BOTH state-specific AND national forecast data
- The state data has limited sample size (< 3 records), so national data is provided as context
- Present BOTH forecasts to the user:
  * State forecast: from 'forecast_insights'
  * National forecast: from 'national_forecast_insights'
- Explain: "Due to limited {state} data for this specialty, I'm showing both {state} and national trends for comparison"
- Highlight any differences between state and national trends
- Recommend using the national data for broader context while noting state-specific nuances
"""

        system_prompt = f"""You are an AI assistant specializing in healthcare staffing market forecasts.

Your role: Translate forecast data into strategic business intelligence.

{role_guidance}

Forecast response guidelines:
- Start with current state, then future outlook
- Highlight the trend direction (increasing/decreasing/stable)
- Provide specific percentages and timeframes
- Include confidence level context
- Give role-specific strategic recommendations
- Use clear, decisive language for business decisions

{dual_forecast_note}

CRITICAL RULES FOR FORECAST DATA:
- ONLY use the forecast values provided in the data (4_weeks, 12_weeks, 26_weeks, 52_weeks)
- NEVER extrapolate or estimate values beyond the 52-week forecast
- If user asks about a specific date (e.g., "March 2026"), present the CLOSEST available forecast timeframe clearly
- Example: "For March 2026 (approximately 6 months out), the forecast shows..." then use the 26_weeks data
- DO NOT say "forecasts are not available" or "specific forecasts for 2026 are not available" - we HAVE forecasts, just use the closest timeframe
- DO NOT make up or estimate values like "could potentially reach 108.0" when the actual 52-week forecast is 102.66
- If discussing trends beyond 52 weeks, say "based on the current 52-week trend of X%, rates are expected to continue this trajectory" but DO NOT give specific numbers
- Always present the forecast data confidently - we ARE providing forecasts, just for the available timeframes (4, 12, 26, or 52 weeks)
"""

        data_context = f"\nForecast data:\n{json.dumps(forecast_data, indent=2)}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"User question: {user_message}\n{data_context}\n\nProvide strategic forecast insights."
                    }
                ],
                temperature=0.7,
                max_tokens=600
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating forecast response: {e}")
            return "I encountered an error generating the forecast analysis. Please try again."

    async def generate_forecast_comparison_response(
        self,
        current_rates: Dict[str, Any],
        forecast_data: Dict[str, Any],
        user_message: str,
        parameters: QueryParameters
    ) -> str:
        """
        Generate response comparing current rates to forecasted future rates

        Args:
            current_rates: Current market rate data from database
            forecast_data: Forecast analysis data
            user_message: Original user question
            parameters: Extracted parameters
        """

        role_guidance = self._get_role_guidance(parameters.user_perspective)

        system_prompt = f"""You are an AI assistant specializing in healthcare staffing market analysis and strategic timing decisions.

Your role: Compare current market rates with forecasted future rates to provide strategic recommendations.

{role_guidance}

Comparison response guidelines:
- Present CURRENT RATES first (market average, recommended range)
- Present FORECASTED RATES second (projected values, growth percentages)
- Calculate the DIFFERENCE and PERCENTAGE CHANGE
- Provide clear STRATEGIC RECOMMENDATION: "lock in now" or "wait for future rates"
- Explain WHY - market dynamics, trends, timing advantages
- Include risk considerations and alternative strategies
- Use decisive, actionable language

Format:
1. **Current Market** - rates, range, sample size
2. **Forecasted Future** - projected rates, growth/decline percentage
3. **Analysis** - difference, trend direction, confidence
4. **Strategic Recommendation** - what to do and why
"""

        # Extract key metrics for comparison
        current_avg = current_rates.get('market_average', 0)
        current_range = f"${current_rates.get('recommended_min', 0):.2f} - ${current_rates.get('recommended_max', 0):.2f}"
        sample_size = current_rates.get('sample_size', 0)
        rate_label = current_rates.get('rate_type', 'rate')

        forecast_insights = forecast_data.get('forecast_insights', {})
        time_horizon = parameters.time_horizon or "12_weeks"
        forecasts = forecast_insights.get('forecasts', {})
        growth_rates = forecast_insights.get('growth_rates', {})

        forecast_value = forecasts.get(time_horizon, 0)
        growth_rate = growth_rates.get(time_horizon, 0)
        trend = forecast_insights.get('trend_direction', 'stable')

        time_label_map = {
            "4_weeks": "4 weeks",
            "12_weeks": "3 months (quarter)",
            "26_weeks": "6 months",
            "52_weeks": "1 year"
        }
        time_label = time_label_map.get(time_horizon, time_horizon)

        data_context = f"""
Current Market Data:
- Market Average: ${current_avg:.2f}/{rate_label}
- Recommended Range: {current_range}
- Sample Size: {sample_size} recent assignments
- Location: {parameters.state or parameters.location}
- Specialty: {parameters.specialty}

Forecasted Market Data ({time_label} from now):
- Projected {rate_label.title()}: ${forecast_value:.2f}
- Growth Rate: {growth_rate:+.1f}%
- Trend Direction: {trend}
- Confidence: {forecast_insights.get('confidence_level', 'medium')}

Calculation:
- Current: ${current_avg:.2f}
- Forecast: ${forecast_value:.2f}
- Difference: ${forecast_value - current_avg:.2f}
- Change: {((forecast_value - current_avg) / current_avg * 100) if current_avg > 0 else 0:+.1f}%
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"User question: {user_message}\n{data_context}\n\nProvide strategic comparison and recommendation."
                    }
                ],
                temperature=0.7,
                max_tokens=700
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating forecast comparison response: {e}")
            return "I encountered an error generating the comparison analysis. Please try again."

    def _get_role_guidance(self, role: Optional[str]) -> str:
        """Get role-specific guidance for response generation"""

        role_guides = {
            "sales": """
User is in SALES - focus on:
- Deal timing and pricing strategy
- Competitive positioning and win probability
- Contract value and margin opportunities
- Market dynamics affecting negotiations
""",
            "recruiter": """
User is a RECRUITER - focus on:
- Candidate attraction and retention
- Competitive compensation positioning
- Talent market dynamics
- Hiring urgency and timing
""",
            "operations": """
User is in OPERATIONS - focus on:
- Capacity planning and utilization
- Cost management and efficiency
- Risk mitigation strategies
- Staffing optimization
""",
            "finance": """
User is in FINANCE - focus on:
- Budget implications and forecasting
- ROI and margin analysis
- Cost trends and financial planning
- Strategic financial recommendations
"""
        }

        return role_guides.get(role, "Provide balanced insights across all business perspectives.")

    async def test_connection(self) -> bool:
        """Test OpenAI API connectivity"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            print(f"OpenAI connection test failed: {e}")
            return False
