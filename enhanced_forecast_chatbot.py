# Add these new Pydantic models to your main chatbot

class ForecastInsight(BaseModel):
    current_value: float
    forecasts: Dict[str, float]  # {"4_weeks": 85.5, "12_weeks": 88.2, etc.}
    growth_rates: Dict[str, float]  # {"4_weeks": 2.1, "12_weeks": 5.3, etc.}
    trend_direction: str  # "increasing", "decreasing", "stable"
    confidence_level: str  # "high", "medium", "low"
    accuracy_mape: float
    model_used: str
    target_metric: str

class ForecastAnalysis(BaseModel):
    forecast_insights: ForecastInsight
    business_recommendations: Dict[str, List[str]]  # Recommendations by role
    data_source: str
    location: str
    specialty: str
    time_horizon: str

class ChatResponse(BaseModel):
    response: str
    rate_recommendation: Optional[RateRecommendation] = None
    vendor_info: Optional[VendorInfo] = None
    lead_analysis: Optional[LeadAnalysis] = None
    forecast_analysis: Optional[ForecastAnalysis] = None  # New forecast data
    extracted_parameters: Optional[Dict[str, Any]] = None
    requires_data: bool = False
    user_role_detected: Optional[str] = None

# Enhanced OpenAI processor methods

class EnhancedOpenAIProcessor(OpenAIProcessor):
    """Extended OpenAI processor with forecast capabilities"""
    
    async def extract_parameters_with_forecast(self, user_message: str, conversation_history: List = None, user_role: str = None) -> EnhancedQueryParameters:
        """Enhanced parameter extraction that detects forecast queries"""
        
        # Build context from conversation history
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-4:]
            history_context = "\nRecent conversation:\n"
            for msg in recent_messages:
                history_context += f"{msg.get('role', 'user')}: {msg.get('content', '')}\n"
        
        role_context = f"\nUser role: {user_role}" if user_role else ""
        
        system_prompt = """You are a parameter extraction system for healthcare staffing queries that can handle both current market analysis AND future forecasting requests.

        Extract these parameters when mentioned:
        - specialty: ICU, ED/ER, OR, Med-Surg, Tele, NICU, PICU, Step-down, Float, Cath Lab, PACU, L&D, Psych
        - state: Full names or abbreviations (California/CA, Texas/TX, etc.)
        - city: Any city name mentioned
        - hospital_name: Specific hospital or health system names
        - hospital_type: trauma_1, trauma_2, academic, community, specialty, pediatric
        - urgency_level: urgent/asap (≤3 days), quick (≤7 days), standard (>7 days)
        - start_date: Any mentioned dates or timeframes
        - current_rate: Any existing rate mentioned (e.g., "they're currently at $80/hr")
        - query_type: 'rate_recommendation', 'vendor_info', 'competitive_analysis', 'lead_generation', 'forecast_analysis'
        - is_temporal_query: true if asking about future rates, trends, forecasts, predictions
        - forecast_horizon: '4_weeks', '12_weeks', '26_weeks', '52_weeks' based on timeframe mentioned
        - user_perspective: Detect from context clues:
          * 'sales' - mentions competing, undercutting, lowest rate, winning deals, client pressure, leads, opportunities, prospects
          * 'recruiter' - mentions fulfillment, candidate pool, time to fill, competitive pay
          * 'operations' - mentions efficiency, margins, capacity, workflow
          * 'finance' - mentions profitability, cost analysis, budget, ROI

        TEMPORAL QUERY DETECTION:
        Look for these patterns to identify forecast requests:
        - Future time references: "next quarter", "6 months", "next year", "2025", "Q1", "upcoming"
        - Prediction words: "will be", "forecast", "predict", "trend", "projection", "outlook", "going to"
        - Rate change questions: "rate increase", "market direction", "where are rates heading"
        - Planning context: "should I wait", "lock in rates", "budget for", "expect rates to"

        TIME HORIZON MAPPING:
        - "month", "4 weeks", "next month" → "4_weeks"
        - "quarter", "3 months", "Q1/Q2/Q3/Q4", "12 weeks" → "12_weeks"  
        - "6 months", "half year", "26 weeks" → "26_weeks"
        - "year", "annual", "12 months", "2025", "52 weeks" → "52_weeks"

        Return JSON only with extracted parameters. Use null for missing values.
        
        Examples:
        "What will ICU rates be in California next quarter?"
        → {"specialty": "ICU", "state": "CA", "query_type": "forecast_analysis", "is_temporal_query": true, "forecast_horizon": "12_weeks", "user_perspective": "general"}
        
        "Should I lock in OR rates now or wait 6 months?"
        → {"specialty": "OR", "query_type": "forecast_analysis", "is_temporal_query": true, "forecast_horizon": "26_weeks", "user_perspective": "sales"}
        
        "Rate outlook for ED positions in 2025"
        → {"specialty": "ED", "query_type": "forecast_analysis", "is_temporal_query": true, "forecast_horizon": "52_weeks", "user_perspective": "finance"}
        
        "Current ICU rates in Texas" (NOT temporal)
        → {"specialty": "ICU", "state": "TX", "query_type": "rate_recommendation", "is_temporal_query": false, "user_perspective": "general"}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract parameters from: '{user_message}'{history_context}{role_context}"}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            extracted = json.loads(response.choices[0].message.content)
            return EnhancedQueryParameters(**{k: v for k, v in extracted.items() if v is not None})
            
        except Exception as e:
            print(f"OpenAI extraction error: {e}")
            # Fallback extraction
            return EnhancedQueryParameters(
                query_type='rate_recommendation',
                user_perspective=user_role if user_role else 'general'
            )

    async def generate_forecast_response(self, forecast_data: Dict[str, Any], user_message: str, 
                                       parameters: EnhancedQueryParameters) -> str:
        """Generate natural language response for forecast analysis"""
        
        # Detect primary perspective if not explicitly set
        primary_perspective = parameters.user_perspective or 'general'
        
        perspective_prompts = {
            'sales': """You are a healthcare staffing sales consultant focused on forecast intelligence. Emphasize:
            - Contract timing strategies (lock in rates vs wait)
            - Competitive positioning over time
            - Revenue optimization based on rate trends
            - Risk/reward of different timing strategies
            - Market timing for proposals and negotiations""",
            
            'recruiter': """You are a healthcare recruiter focused on workforce planning. Emphasize:
            - How rate trends affect candidate attraction and retention
            - Timing of recruitment campaigns based on market direction
            - Competitive positioning for talent acquisition
            - Budget planning for compensation increases
            - Market timing for hiring initiatives""",
            
            'operations': """You are an operations manager focused on capacity planning. Emphasize:
            - Operational impact of rate trends on margins and capacity
            - Resource allocation based on forecast insights
            - Contract portfolio optimization
            - Risk management for rate volatility
            - Strategic planning for market changes""",
            
            'finance': """You are a financial analyst focused on budget planning. Emphasize:
            - Budget impact and financial forecasting
            - ROI optimization based on rate trends
            - Cost structure planning and margin analysis
            - Cash flow implications of rate changes
            - Financial risk assessment and hedging strategies""",
            
            'general': """You are a healthcare staffing market analyst providing comprehensive forecast insights. Focus on:
            - Clear explanation of rate trends and predictions
            - Market dynamics driving the forecast
            - Strategic implications for different timeframes
            - Confidence levels and risk factors
            - Actionable insights for decision making"""
        }
        
        base_prompt = perspective_prompts.get(primary_perspective, perspective_prompts['general'])
        
        system_prompt = f"""{base_prompt}
        
        Generate natural, professional responses that:
        - Clearly explain forecast insights and trends
        - Provide specific timeframe predictions with confidence levels
        - Give actionable recommendations based on forecast data
        - Address the user's specific role and concerns
        - Use concrete numbers and percentages from the forecast
        - Highlight key opportunities and risks
        - Maintain appropriate confidence based on model accuracy
        """
        
        # Prepare comprehensive forecast context
        data_context = f"Query: {user_message}\n"
        data_context += f"User perspective: {primary_perspective}\n"
        data_context += f"Extracted parameters: {parameters.__dict__}\n"
        data_context += f"Forecast analysis: {json.dumps(forecast_data, indent=2, default=str)}"
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": data_context}
                ],
                temperature=0.7,
                max_tokens=1200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"OpenAI forecast response generation error: {e}")
            return self._fallback_forecast_response(forecast_data, parameters)

    def _fallback_forecast_response(self, forecast_data: Dict[str, Any], parameters: EnhancedQueryParameters) -> str:
        """Fallback response if OpenAI fails for forecasts"""
        
        if 'error' in forecast_data:
            return f"I couldn't generate a forecast: {forecast_data['error']}"
        
        insights = forecast_data.get('forecast_insights', {})
        specialty = parameters.specialty or 'position'
        location = forecast_data.get('location', 'market')
        
        current_value = insights.get('current_value', 0)
        forecasts = insights.get('forecasts', {})
        growth_rates = insights.get('growth_rates', {})
        trend = insights.get('trend_direction', 'stable')
        
        horizon_key = parameters.forecast_horizon or '12_weeks'
        future_value = forecasts.get(horizon_key, 0)
        growth_rate = growth_rates.get(horizon_key, 0)
        
        horizon_display = horizon_key.replace('_', ' ').replace('weeks', 'week')
        
        response = f"**{specialty} Rate Forecast - {location.title()}**\n\n"
        response += f"Current rate: ${current_value:.2f}\n"
        response += f"{horizon_display.title()} forecast: ${future_value:.2f}\n"
        response += f"Expected change: {growth_rate:+.1f}%\n"
        response += f"Trend direction: {trend.title()}\n"
        
        return response

# Enhanced query parameters class
from dataclasses import dataclass

@dataclass
class EnhancedQueryParameters(QueryParameters):
    is_temporal_query: bool = False
    forecast_horizon: Optional[str] = None  # "4_weeks", "12_weeks", "26_weeks", "52_weeks"

# Usage example for the enhanced chat endpoint

@app.post("/chat", response_model=ChatResponse)
async def enhanced_chat_endpoint(query: ChatQuery):
    """Enhanced chat endpoint with forecasting capabilities"""
    try:
        # Initialize services
        forecasting_service = ForecastingService(os.getenv("FORECASTING_URL", "http://localhost:8002"))
        forecast_integration = ChatbotForecastIntegration(forecasting_service)
        enhanced_openai_processor = EnhancedOpenAIProcessor(openai_client)
        
        # Extract parameters with forecast detection
        parameters = await enhanced_openai_processor.extract_parameters_with_forecast(
            query.message, 
            query.conversation_history,
            query.user_role
        )
        
        # Route based on query type
        if parameters.query_type == "forecast_analysis":
            # Handle forecast queries
            forecast_analysis_data = await forecast_integration.generate_forecast_analysis(parameters)
            
            if "error" in forecast_analysis_data:
                error_response = f"I couldn't generate a forecast: {forecast_analysis_data['error']}"
                return ChatResponse(
                    response=error_response,
                    extracted_parameters=parameters.__dict__,
                    requires_data=False
                )
            
            # Create forecast analysis object
            forecast_analysis = ForecastAnalysis(**forecast_analysis_data)
            
            # Generate AI response focused on forecast insights
            ai_response = await enhanced_openai_processor.generate_forecast_response(
                forecast_analysis_data, query.message, parameters
            )
            
            return ChatResponse(
                response=ai_response,
                forecast_analysis=forecast_analysis,
                extracted_parameters=parameters.__dict__,
                requires_data=True,
                user_role_detected=parameters.user_perspective
            )
        
        elif parameters.query_type in ['rate_recommendation', 'competitive_analysis']:
            # Your existing rate analysis logic
            recommendation = await database_service.get_comprehensive_rate_analysis(parameters)
            
            ai_response = await enhanced_openai_processor.generate_role_based_response(
                {'recommendation': recommendation}, query.message, parameters
            )
            
            return ChatResponse(
                response=ai_response,
                rate_recommendation=recommendation,
                extracted_parameters=parameters.__dict__,
                requires_data=True,
                user_role_detected=parameters.user_perspective
            )
            
        elif parameters.query_type == 'lead_generation':
            # Your existing lead generation logic
            lead_analysis = await database_service.get_lead_opportunities(parameters)
            
            ai_response = await enhanced_openai_processor.generate_role_based_response(
                {'lead_analysis': lead_analysis}, query.message, parameters
            )
            
            return ChatResponse(
                response=ai_response,
                lead_analysis=lead_analysis,
                extracted_parameters=parameters.__dict__,
                requires_data=True,
                user_role_detected=parameters.user_perspective
            )
        
        else:
            # General conversation
            general_response = """I provide comprehensive healthcare staffing intelligence:

**Current Market Analysis**:
- Rate recommendations and competitive positioning
- Lead generation and opportunity scoring  
- Vendor intelligence and market insights

**Future Market Intelligence** 🔮:
- Rate forecasts and trend predictions
- Market timing for contracts and hiring
- Strategic planning based on rate outlook

**Example forecast queries**:
- "What will ICU rates be in California next quarter?"
- "Should I lock in OR rates now or wait 6 months?"
- "Rate outlook for ED positions in 2025"

What type of analysis would you like?"""
            
            return ChatResponse(
                response=general_response,
                extracted_parameters=parameters.__dict__,
                requires_data=False
            )
        
        # Clean up
        await forecasting_service.close_session()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
