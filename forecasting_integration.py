import aiohttp
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json

class ForecastingService:
    """Integration with your existing forecasting FastAPI service"""
    
    def __init__(self, forecasting_base_url: str = "http://localhost:8002"):
        self.base_url = forecasting_base_url
        self.session = None
    
    async def get_session(self):
        """Get or create aiohttp session with SSL verification disabled for self-signed certs"""
        if self.session is None or self.session.closed:
            import ssl
            # Create SSL context that doesn't verify certificates (for self-signed certs)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_rate_forecast(self, specialties: List[str], states: List[str] = None,
                               target: str = "weekly_pay", model: str = "prophet",
                               timeout: int = 90, profession: str = None) -> Dict:
        """
        Get rate forecasts from your forecasting service

        Args:
            specialties: List of nursing specialties (e.g., ["ICU", "ED", "CRNA"])
            states: List of states (e.g., ["CA", "TX"]) - optional for national
            target: "weekly_pay", "bill_rate", or "hourly_pay"
            model: "ensemble", "prophet", "xgboost", or "random_forest"
            timeout: Request timeout in seconds (default: 30)
            profession: Profession filter from frontend ("Nursing", "Locum/Tenens", "Allied", "Therapy")
        """

        session = await self.get_session()

        # Locum/Tenens specialties that should NOT get "RN - " prefix
        locum_specialties = ["CRNA", "CAA", "PA", "NP", "FNP", "AGACNP", "PMHNP"]

        # Format specialties - only add "RN - " prefix for Nursing specialties
        formatted_specialties = []
        for spec in specialties:
            # Don't add prefix if already has one
            if spec.startswith("RN - ") or spec.startswith("PA - ") or spec.startswith("NP - "):
                formatted_specialties.append(spec)
            # Don't add "RN -" to Locum/Tenens specialties or if profession is Locum/Tenens
            elif spec in locum_specialties or profession == "Locum/Tenens":
                formatted_specialties.append(spec)
            else:
                # Default: add "RN - " for regular nursing specialties
                formatted_specialties.append(f"RN - {spec}")

        payload = {
            "specialties": formatted_specialties,
            "states": states or [],
            "model": model,
            "target": target
        }

        try:
            url = f"{self.base_url}/forecast"
            print(f"🔍 Forecasting API Request:")
            print(f"   URL: {url}")
            print(f"   Payload: {payload}")

            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout_obj
            ) as response:
                print(f"   Response Status: {response.status}")
                if response.status == 200:
                    response_data = await response.json()
                    print(f"   Response Data Keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
                    if isinstance(response_data, dict) and response_data:
                        print(f"   First level keys preview: {str(response_data)[:300]}")
                    return response_data
                else:
                    error_text = await response.text()
                    print(f"   ❌ Forecasting API Error Response: {error_text}")
                    print(f"   Request details: specialties={formatted_specialties}, states={states}, model={model}, target={target}")

                    # Parse error for better user feedback
                    if "list index out of range" in error_text:
                        raise Exception(f"Forecasting service error: Not enough historical data for {', '.join(formatted_specialties)} in {', '.join(states or ['national'])}. The forecasting model requires sufficient historical data points.")
                    elif "Data fetch failed" in error_text:
                        raise Exception(f"Forecasting service error: Failed to fetch data for {', '.join(formatted_specialties)} in {', '.join(states or ['national'])}. This specialty/state combination may not have enough data.")
                    else:
                        raise Exception(f"Forecasting API error {response.status}: {error_text}")

        except asyncio.TimeoutError:
            raise Exception(f"Forecasting API request timed out after {timeout} seconds")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error connecting to forecasting service: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to get forecast: {str(e)}")
    
    def extract_forecast_insights(self, forecast_data: Dict, specialty: str,
                                 state: str = "national") -> Dict:
        """Extract key insights from forecast data for chatbot responses"""

        try:
            # Navigate to the specific forecast
            specialty_data = forecast_data.get(specialty, {})
            location_data = specialty_data.get(state, specialty_data.get("national", {}))

            print(f"🔍 Extracting insights for {specialty} in {state}")
            print(f"   Specialty data keys: {list(specialty_data.keys()) if isinstance(specialty_data, dict) else 'Not a dict'}")
            print(f"   Location data keys: {list(location_data.keys()) if isinstance(location_data, dict) else 'Not a dict'}")

            if "error" in location_data:
                return {"error": location_data["error"]}

            forecast_points = location_data.get("forecast", [])
            historical_points = location_data.get("historical", [])
            metadata = forecast_data.get("_metadata", {})

            print(f"   Forecast points: {len(forecast_points) if forecast_points else 0}")
            print(f"   Historical points: {len(historical_points) if historical_points else 0}")

            if not forecast_points:
                return {"error": "No forecast data available"}

            # Current vs Future Analysis
            # Try to get current value from historical data, or use first forecast point as baseline
            if historical_points:
                current_value = historical_points[-1]["y"]
            elif forecast_points:
                # Use first forecast point as current baseline if no historical data
                current_value = forecast_points[0]["yhat"]
            else:
                current_value = 0
            
            # Get forecast values for different time horizons
            forecast_4_weeks = forecast_points[3]["yhat"] if len(forecast_points) > 3 else 0
            forecast_12_weeks = forecast_points[11]["yhat"] if len(forecast_points) > 11 else 0
            forecast_26_weeks = forecast_points[25]["yhat"] if len(forecast_points) > 25 else 0
            forecast_52_weeks = forecast_points[51]["yhat"] if len(forecast_points) > 51 else 0
            
            # Calculate growth rates
            growth_4_weeks = ((forecast_4_weeks - current_value) / current_value * 100) if current_value > 0 else 0
            growth_12_weeks = ((forecast_12_weeks - current_value) / current_value * 100) if current_value > 0 else 0
            growth_26_weeks = ((forecast_26_weeks - current_value) / current_value * 100) if current_value > 0 else 0
            growth_52_weeks = ((forecast_52_weeks - current_value) / current_value * 100) if current_value > 0 else 0
            
            # Trend analysis
            trend_direction = "increasing" if growth_12_weeks > 1 else "decreasing" if growth_12_weeks < -1 else "stable"
            
            # Confidence assessment based on MAPE
            mape = location_data.get("mape", 100)
            confidence_level = "high" if mape < 10 else "medium" if mape < 20 else "low"
            
            # Projections from your service
            projections = location_data.get("projection", {})
            
            return {
                "current_value": round(current_value, 2),
                "forecasts": {
                    "4_weeks": round(forecast_4_weeks, 2),
                    "12_weeks": round(forecast_12_weeks, 2),
                    "26_weeks": round(forecast_26_weeks, 2),
                    "52_weeks": round(forecast_52_weeks, 2)
                },
                "growth_rates": {
                    "4_weeks": round(growth_4_weeks, 1),
                    "12_weeks": round(growth_12_weeks, 1),
                    "26_weeks": round(growth_26_weeks, 1),
                    "52_weeks": round(growth_52_weeks, 1)
                },
                "trend_direction": trend_direction,
                "confidence_level": confidence_level,
                "accuracy_mape": round(mape, 1),
                "model_used": location_data.get("model", "unknown"),
                "projections": projections,
                "target_metric": metadata.get("target", "weekly_pay"),
                "processing_time": metadata.get("processing_time_seconds", 0)
            }
            
        except Exception as e:
            return {"error": f"Failed to extract insights: {str(e)}"}

class ChatbotForecastIntegration:
    """Integration layer for chatbot to use forecasting service"""
    
    def __init__(self, forecasting_service: ForecastingService):
        self.forecasting_service = forecasting_service
    
    def detect_temporal_query(self, message: str) -> Dict[str, Any]:
        """Detect if query is asking about future rates"""
        
        temporal_indicators = [
            "next", "future", "forecast", "predict", "will be", "going to be",
            "trend", "projection", "outlook", "6 months", "next year", 
            "quarter", "Q1", "Q2", "Q3", "Q4", "2025", "2026",
            "next month", "next week", "coming months", "upcoming",
            "rate increase", "rate growth", "market direction"
        ]
        
        time_horizons = {
            "4 weeks": ["month", "4 weeks", "next month"],
            "12 weeks": ["quarter", "3 months", "Q1", "Q2", "Q3", "Q4", "12 weeks"],
            "26 weeks": ["6 months", "half year", "26 weeks"],
            "52 weeks": ["year", "annual", "12 months", "52 weeks", "2025", "2026"]
        }
        
        message_lower = message.lower()
        
        # Check for temporal indicators
        is_temporal = any(indicator in message_lower for indicator in temporal_indicators)
        
        # Determine time horizon
        detected_horizon = "12 weeks"  # Default
        for horizon, keywords in time_horizons.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_horizon = horizon
                break
        
        return {
            "is_temporal_query": is_temporal,
            "time_horizon": detected_horizon,
            "confidence": "high" if is_temporal else "low"
        }
    
    async def generate_forecast_analysis(self, parameters: 'QueryParameters') -> Dict[str, Any]:
        """Generate forecast analysis for chatbot response"""
        
        if not parameters.specialty:
            return {"error": "Specialty required for forecast analysis"}
        
        try:
            # Get city and state from parameters (same as market comparison)
            city = getattr(parameters, "city", None)
            state = getattr(parameters, "state", None)
            location = getattr(parameters, "location", None)

            # Determine the state to use
            normalized_state = None

            # If we have a state parameter, use it
            if state:
                normalized_state = state.upper() if len(state) == 2 else state
            # If location is a 2-letter code, treat as state
            elif location and len(location) == 2 and location.isalpha():
                normalized_state = location.upper()
            # If we have a city but no state, we need to ask for clarification
            elif city and not state:
                # Check if it's an obvious major city
                obvious_cities = {
                    "new york city": "NY", "nyc": "NY", "manhattan": "NY",
                    "los angeles": "CA", "la": "CA", "san francisco": "CA",
                    "chicago": "IL", "houston": "TX", "phoenix": "AZ",
                    "philadelphia": "PA", "boston": "MA", "atlanta": "GA",
                    "seattle": "WA", "denver": "CO", "miami": "FL",
                    "dallas": "TX", "detroit": "MI", "las vegas": "NV"
                }
                city_lower = city.lower().strip()
                if city_lower in obvious_cities:
                    normalized_state = obvious_cities[city_lower]
                else:
                    # City without state - need clarification
                    return {
                        "error": f"Please specify which state {city} is in. For example: '{city}, NY' or '{city}, CA'"
                    }
            # If location looks like a city name (more than 2 chars), ask for state
            elif location and len(location) > 2:
                return {
                    "error": f"Please specify which state for {location}. For example: '{location}, NY' or just use the state abbreviation."
                }
            
            # Determine target metric based on rate_type parameter
            rate_type = getattr(parameters, "rate_type", None) or "bill_rate"

            # Map rate_type to forecasting API target
            if rate_type == "bill_rate":
                target_metric = "bill_rate"
            elif rate_type == "hourly_pay":
                target_metric = "hourly_pay"
            elif rate_type == "weekly_pay":
                target_metric = "weekly_pay"
            else:
                # Fallback to bill_rate as default
                target_metric = "bill_rate"
            
            # Check profession to determine if we should fetch national data as backup
            profession = getattr(parameters, "profession", None)
            should_include_national = profession in ["Locum/Tenens", "Allied", "Therapy"]

            # Get forecast from your service (state-level)
            forecast_data = await self.forecasting_service.get_rate_forecast(
                specialties=[parameters.specialty],
                states=[normalized_state] if normalized_state else [],
                target=target_metric,
                model="prophet",  # Use prophet model as default
                profession=profession  # Pass profession filter
            )

            # Determine formatted specialty based on profession
            locum_specialties = ["CRNA", "CAA", "PA", "NP", "FNP", "AGACNP", "PMHNP"]
            if parameters.specialty in locum_specialties or profession == "Locum/Tenens":
                formatted_specialty = parameters.specialty
            elif not parameters.specialty.startswith("RN - "):
                formatted_specialty = f"RN - {parameters.specialty}"
            else:
                formatted_specialty = parameters.specialty
            location_key = normalized_state if normalized_state else "national"
            insights = self.forecasting_service.extract_forecast_insights(
                forecast_data,
                formatted_specialty,
                location_key
            )

            if "error" in insights:
                return insights

            # Check if we have sufficient state data, and fetch national if needed
            state_sample_size = len(insights.get("forecast", {}).get("historical", [])) if isinstance(insights.get("forecast"), dict) else 0
            national_insights = None

            # For Locum/Tenens, Allied, Therapy: fetch national data if state data is sparse (< 3 samples)
            if should_include_national and normalized_state and state_sample_size < 3:
                print(f"📊 State data sparse ({state_sample_size} samples) for {profession}, fetching national data as supplement...")

                try:
                    # Get national forecast (no state filter)
                    national_forecast_data = await self.forecasting_service.get_rate_forecast(
                        specialties=[parameters.specialty],
                        states=[],  # Empty = national
                        target=target_metric,
                        model="prophet",
                        profession=profession  # Pass profession filter
                    )

                    national_insights = self.forecasting_service.extract_forecast_insights(
                        national_forecast_data,
                        formatted_specialty,
                        "national"
                    )

                    if "error" not in national_insights:
                        print("✅ Successfully fetched national forecast data")
                    else:
                        national_insights = None

                except Exception as e:
                    print(f"⚠️ Could not fetch national data: {e}")
                    national_insights = None

            # Generate business recommendations based on forecast
            recommendations = self._generate_forecast_recommendations(insights, parameters)

            selected_horizon = getattr(parameters, "time_horizon", None) or "12_weeks"

            result = {
                "forecast_insights": insights,
                "business_recommendations": recommendations,
                "data_source": "prophet_model",
                "location": location_key,
                "specialty": parameters.specialty,
                "time_horizon": selected_horizon,
                "has_limited_state_data": state_sample_size < 3 if normalized_state else False
            }

            # Include national insights if we fetched them
            if national_insights:
                result["national_forecast_insights"] = national_insights
                result["dual_forecast"] = True
                print(f"🌍 Returning dual forecast: {location_key} + national")

            return result
            
        except Exception as e:
            return {"error": f"Forecast analysis failed: {str(e)}"}
    
    def _generate_forecast_recommendations(self, insights: Dict, parameters: 'QueryParameters') -> Dict[str, List[str]]:
        """Generate role-specific recommendations based on forecast data"""
        
        current_value = insights.get("current_value", 0)
        growth_12_weeks = insights.get("growth_rates", {}).get("12_weeks", 0)
        growth_26_weeks = insights.get("growth_rates", {}).get("26_weeks", 0)
        trend = insights.get("trend_direction", "stable")
        confidence = insights.get("confidence_level", "medium")
        
        recommendations = {
            "sales": [],
            "recruiter": [],
            "operations": [],
            "finance": []
        }
        
        # Sales recommendations
        if growth_12_weeks > 5:  # Strong growth expected
            recommendations["sales"].append("Lock in long-term contracts now before rates increase")
            recommendations["sales"].append(f"Market shows {growth_12_weeks:.1f}% growth over 3 months - negotiate premium rates")
        elif growth_12_weeks < -3:  # Declining rates
            recommendations["sales"].append("Consider aggressive pricing to win market share")
            recommendations["sales"].append("Short-term contracts preferred due to declining rates")
        else:
            recommendations["sales"].append("Rates stable - focus on relationship building and service quality")
        
        # Recruiter recommendations  
        if growth_12_weeks > 3:
            recommendations["recruiter"].append("Candidate attraction will improve as rates increase")
            recommendations["recruiter"].append("Accelerate recruitment efforts before market gets more competitive")
        elif growth_12_weeks < -2:
            recommendations["recruiter"].append("Pay competitiveness may decline - adjust expectations")
            recommendations["recruiter"].append("Focus on non-monetary benefits and work environment")
        
        # Operations recommendations
        if abs(growth_12_weeks) > 5:
            recommendations["operations"].append("Significant rate changes expected - review capacity planning")
            recommendations["operations"].append("Monitor margin impact from rate volatility")
        else:
            recommendations["operations"].append("Stable rate environment supports predictable operations")
        
        # Finance recommendations
        if trend == "increasing":
            recommendations["finance"].append(f"Budget for {growth_26_weeks:.1f}% rate increases over 6 months")
            recommendations["finance"].append("Consider hedging strategies for large contracts")
        elif trend == "decreasing":
            recommendations["finance"].append("Margin improvement opportunities from declining rates")
            recommendations["finance"].append("Accelerate contract renewals before rates fall further")
        
        # Add confidence disclaimers
        if confidence == "low":
            for role in recommendations:
                recommendations[role].append(f"⚠️ Low forecast confidence ({insights.get('accuracy_mape', 0):.1f}% error) - monitor closely")
        
        return recommendations
