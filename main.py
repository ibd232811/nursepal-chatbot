"""
Healthcare Staffing Intelligence Chatbot with Forecasting
Main FastAPI Application
"""

import os
import sys
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import asyncio
import json
import time

# Load environment variables (override=True ensures .env takes precedence)
load_dotenv(override=True)

# Import local modules
from database_service import DatabaseService
from openai_processor import OpenAIProcessor, QueryParameters
from forecasting_integration import ForecastingService, ChatbotForecastIntegration
from cache_service import CacheService

# Initialize FastAPI app
app = FastAPI(
    title="Healthcare Staffing Intelligence Chatbot",
    description="AI-powered chatbot for healthcare staffing with forecasting capabilities",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class ChatQuery(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    user_role: Optional[str] = None  # "sales", "recruiter", "operations", "finance"
    profession: Optional[str] = None  # "Nursing", "Allied", "Locum/Tenens", "Therapy"

class RateRecommendation(BaseModel):
    specialty: str
    location: str
    recommended_min: float
    recommended_max: float
    competitive_floor: float
    market_average: float
    sample_size: int
    avg_weekly_pay: Optional[float] = None
    avg_hourly_pay: Optional[float] = None
    avg_bill_rate: Optional[float] = None
    rate_type: Optional[str] = None

class VendorInfo(BaseModel):
    vendor_name: str
    specialty: str
    location: str
    average_rate: float
    total_assignments: int

class LeadAnalysis(BaseModel):
    opportunities: List[Dict[str, Any]]
    total_opportunities: int
    estimated_value: float

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
    forecast_insights: Union[ForecastInsight, List[Dict[str, Any]]]  # Single state or multi-state
    business_recommendations: Dict[str, List[str]]  # Recommendations by role
    data_source: str
    location: str
    specialty: str
    time_horizon: str
    is_multi_state_fallback: Optional[bool] = None  # True if showing multiple states
    fallback_reason: Optional[str] = None  # Explanation for fallback
    requested_location: Optional[str] = None  # Original requested location
    multi_state_forecasts: Optional[List[Dict[str, Any]]] = None  # Full state data

class ChatResponse(BaseModel):
    response: str
    rate_recommendation: Optional[RateRecommendation] = None
    vendor_info: Optional[VendorInfo] = None
    lead_analysis: Optional[LeadAnalysis] = None
    forecast_analysis: Optional[ForecastAnalysis] = None
    extracted_parameters: Optional[Dict[str, Any]] = None
    requires_data: bool = False
    user_role_detected: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str  # "processing", "complete", "error"
    message: str
    progress: Optional[int] = None  # 0-100 percentage
    data: Optional[Dict[str, Any]] = None

# Global service instances
db_service: Optional[DatabaseService] = None
openai_processor: Optional[OpenAIProcessor] = None
forecasting_service: Optional[ForecastingService] = None
cache_service: Optional[CacheService] = None

# Nurse License Compact States
COMPACT_STATES = [
    "AL", "AZ", "AR", "CO", "CT", "DE", "FL", "GA", "GU", "ID", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MS", "MO", "MT", "NE", "NH", "NJ", "NM", "NC", "ND", "OH",
    "OK", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "VI", "WA", "WV", "WI", "WY"
]

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global db_service, openai_processor, forecasting_service, cache_service

    print("🚀 Starting AVA - AI Virtual Assistant...")
    print("   Your Healthcare Staffing Intelligence Partner")

    # Initialize cache service (300 seconds = 5 minutes TTL)
    cache_service = CacheService(default_ttl=300)
    print("✅ Cache service initialized (5 min TTL)")

    # Initialize database service
    try:
        db_service = DatabaseService(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", "5432"))
        )
        await db_service.connect()
        print("✅ Database connection established")
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print("   Continuing in limited mode (forecasting only)")

    # Initialize OpenAI processor
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_processor = OpenAIProcessor(api_key=openai_api_key)
        print("✅ OpenAI processor initialized")
    else:
        print("⚠️  OPENAI_API_KEY not found - AI features disabled")

    # Initialize forecasting service
    forecasting_url = os.getenv("FORECASTING_URL", "http://localhost:8001")
    forecasting_service = ForecastingService(forecasting_base_url=forecasting_url)
    print(f"✅ Forecasting service configured: {forecasting_url}")

    print("\n🎯 Server ready! Available endpoints:")
    print("   POST /chat - Main chat endpoint")
    print("   GET /health - Health check")
    print("   GET /docs - API documentation\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global db_service, forecasting_service

    if db_service:
        await db_service.close()

    if forecasting_service:
        await forecasting_service.close_session()

    print("👋 Shutdown complete")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Healthcare Staffing Intelligence Chatbot",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "Current market analysis",
            "Rate recommendations",
            "Lead generation",
            "Future forecasting",
            "Role-based insights"
        ],
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if db_service else "disconnected",
        "openai": "enabled" if openai_processor else "disabled",
        "forecasting": "configured" if forecasting_service else "not configured"
    }

@app.post("/chat/stream")
async def chat_stream_endpoint(query: ChatQuery):
    """
    Streaming chat endpoint that provides real-time status updates

    Returns Server-Sent Events (SSE) stream with status updates and final response
    """
    async def generate_status_stream() -> AsyncGenerator[str, None]:
        try:
            # Send initial status
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Analyzing your query...', 'progress': 10})}\n\n"
            await asyncio.sleep(0.1)

            if not openai_processor:
                yield f"data: {json.dumps({'status': 'error', 'message': 'OpenAI processor not initialized. Check OPENAI_API_KEY.'})}\n\n"
                return

            # Extract parameters
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Understanding your request...', 'progress': 20})}\n\n"
            await asyncio.sleep(0.1)

            parameters = await openai_processor.extract_parameters(
                query.message,
                query.conversation_history,
                query.user_role
            )

            # Context merging logic (same as original endpoint)
            if query.conversation_history and len(query.conversation_history) >= 2:
                current_msg_words = query.message.lower().strip().split()
                if len(current_msg_words) <= 5:
                    last_assistant_msg = None
                    last_user_params = None
                    for i in range(len(query.conversation_history) - 1, -1, -1):
                        msg = query.conversation_history[i]
                        if msg.get('role') == 'assistant' and not last_assistant_msg:
                            last_assistant_msg = msg.get('content', '')
                        elif msg.get('role') == 'user' and i < len(query.conversation_history) - 1:
                            try:
                                last_user_params = await openai_processor.extract_parameters(
                                    msg.get('content', ''), None, query.user_role
                                )
                            except Exception:
                                pass
                            break

                    if last_assistant_msg and last_user_params:
                        asking_for_specialty = 'specialty' in last_assistant_msg.lower() and 'interested' in last_assistant_msg.lower()
                        asking_for_rate_type = 'rate type' in last_assistant_msg.lower() and 'compare' in last_assistant_msg.lower()
                        asking_for_state = 'which state' in last_assistant_msg.lower()
                        asking_for_time_frame = 'time frame' in last_assistant_msg.lower() and 'forecast' in last_assistant_msg.lower()
                        asking_for_forecast_location = 'which state would you like to forecast' in last_assistant_msg.lower()

                        if asking_for_specialty and not parameters.specialty and parameters.query_type in ['general', 'rate_recommendation', 'forecast_analysis']:
                            if not parameters.location_list and last_user_params.location_list:
                                parameters.location_list = last_user_params.location_list
                            if not parameters.rate_type and last_user_params.rate_type:
                                parameters.rate_type = last_user_params.rate_type
                            if not parameters.location and last_user_params.location:
                                parameters.location = last_user_params.location
                            if not parameters.city and last_user_params.city:
                                parameters.city = last_user_params.city
                            if not parameters.state and last_user_params.state:
                                parameters.state = last_user_params.state
                            if not parameters.time_horizon and last_user_params.time_horizon:
                                parameters.time_horizon = last_user_params.time_horizon
                            if not parameters.query_type or parameters.query_type == 'general':
                                parameters.query_type = last_user_params.query_type
                        elif asking_for_rate_type and not parameters.rate_type:
                            if not parameters.specialty and last_user_params.specialty:
                                parameters.specialty = last_user_params.specialty
                            if not parameters.location_list and last_user_params.location_list:
                                parameters.location_list = last_user_params.location_list
                            if not parameters.query_type or parameters.query_type == 'general':
                                parameters.query_type = last_user_params.query_type
                        elif asking_for_time_frame and parameters.time_horizon:
                            if not parameters.specialty and last_user_params.specialty:
                                parameters.specialty = last_user_params.specialty
                            if not parameters.location and last_user_params.location:
                                parameters.location = last_user_params.location
                            if not parameters.city and last_user_params.city:
                                parameters.city = last_user_params.city
                            if not parameters.state and last_user_params.state:
                                parameters.state = last_user_params.state
                            if not parameters.rate_type and last_user_params.rate_type:
                                parameters.rate_type = last_user_params.rate_type
                            if not parameters.query_type or parameters.query_type == 'general':
                                parameters.query_type = last_user_params.query_type
                        elif asking_for_forecast_location and (parameters.state or parameters.location):
                            if not parameters.specialty and last_user_params.specialty:
                                parameters.specialty = last_user_params.specialty
                            if not parameters.time_horizon and last_user_params.time_horizon:
                                parameters.time_horizon = last_user_params.time_horizon
                            if not parameters.rate_type and last_user_params.rate_type:
                                parameters.rate_type = last_user_params.rate_type
                            if not parameters.query_type or parameters.query_type == 'general':
                                parameters.query_type = last_user_params.query_type
                        elif asking_for_state:
                            if not parameters.specialty and last_user_params.specialty:
                                parameters.specialty = last_user_params.specialty
                            if not parameters.rate_type and last_user_params.rate_type:
                                parameters.rate_type = last_user_params.rate_type
                            if not parameters.time_horizon and last_user_params.time_horizon:
                                parameters.time_horizon = last_user_params.time_horizon
                            if not parameters.query_type or parameters.query_type == 'general':
                                parameters.query_type = last_user_params.query_type
                            if last_user_params.location_list and 'and' in query.message.lower():
                                pass
                            elif last_user_params.location_list:
                                if not parameters.location_list:
                                    parameters.location_list = last_user_params.location_list

            query_type = parameters.query_type

            # Route to appropriate handler based on query type
            if query_type == "forecast_analysis":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Generating forecast analysis...', 'progress': 40})}\n\n"
            elif query_type == "rate_recommendation" or query_type == "competitive_analysis":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Fetching current market data...', 'progress': 40})}\n\n"
            elif query_type == "market_comparison":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Comparing markets...', 'progress': 40})}\n\n"
            elif query_type == "client_search":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Searching for clients...', 'progress': 40})}\n\n"
            elif query_type == "forecast_comparison":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Comparing current vs future rates...', 'progress': 40})}\n\n"
            elif query_type == "rate_comparison":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Analyzing your proposed rate...', 'progress': 40})}\n\n"
            elif query_type == "vendor_location":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Finding vendors at this location...', 'progress': 40})}\n\n"
            elif query_type == "vendor_contract":
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Looking up vendor/MSP contract...', 'progress': 40})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Processing your request...', 'progress': 40})}\n\n"

            await asyncio.sleep(0.1)

            # Call the main chat endpoint to get the response
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Finalizing response...', 'progress': 70})}\n\n"
            response = await chat_endpoint(query)

            # Final response
            yield f"data: {json.dumps({'status': 'complete', 'message': 'Done!', 'progress': 100, 'data': response.dict()})}\n\n"

        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"

    return StreamingResponse(generate_status_stream(), media_type="text/event-stream")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(query: ChatQuery):
    """
    Main chat endpoint with forecasting capabilities

    Handles:
    - Rate recommendations and competitive analysis
    - Lead generation and opportunity scoring
    - Future forecasting and trend analysis
    - Role-specific business intelligence
    """
    try:
        if not openai_processor:
            raise HTTPException(
                status_code=503,
                detail="OpenAI processor not initialized. Check OPENAI_API_KEY."
            )

        # Generate cache key from query
        import hashlib
        import json
        cache_key = hashlib.md5(
            json.dumps({
                "message": query.message,
                "role": query.user_role
            }, sort_keys=True).encode()
        ).hexdigest()

        # Check cache first
        if cache_service:
            cached_response = cache_service.get(cache_key)
            if cached_response:
                print(f"✨ Cache hit for query: {query.message[:50]}...")
                return ChatResponse(**cached_response)

        # Extract parameters from the user query
        parameters = await openai_processor.extract_parameters(
            query.message,
            query.conversation_history,
            query.user_role
        )

        # Set profession filter if provided by frontend
        if query.profession:
            parameters.profession = query.profession
            print(f"🎯 Profession filter: {query.profession}")

        # Check if this is a follow-up answer to a clarification question
        # If the current message is very short and the previous response asked a question,
        # try to merge context from previous user message
        if query.conversation_history and len(query.conversation_history) >= 2:
            current_msg_words = query.message.lower().strip().split()

            # If current message is 1-5 words and doesn't have complete info
            if len(current_msg_words) <= 5:
                # Get the last assistant message
                last_assistant_msg = None
                last_user_params = None

                for i in range(len(query.conversation_history) - 1, -1, -1):
                    msg = query.conversation_history[i]
                    if msg.get('role') == 'assistant' and not last_assistant_msg:
                        last_assistant_msg = msg.get('content', '')
                    elif msg.get('role') == 'user' and i < len(query.conversation_history) - 1:
                        # This is the previous user message, extract its parameters
                        try:
                            last_user_params = await openai_processor.extract_parameters(
                                msg.get('content', ''),
                                None,
                                query.user_role
                            )
                        except:
                            pass
                        break

                # Check if last assistant message was asking for clarification
                if last_assistant_msg and last_user_params:
                    asking_for_specialty = 'specialty' in last_assistant_msg.lower() and 'interested' in last_assistant_msg.lower()
                    asking_for_rate_type = 'rate type' in last_assistant_msg.lower() and 'compare' in last_assistant_msg.lower()
                    asking_for_state = 'which state' in last_assistant_msg.lower()
                    asking_for_time_frame = 'time frame' in last_assistant_msg.lower() and 'forecast' in last_assistant_msg.lower()
                    asking_for_forecast_location = 'which state would you like to forecast' in last_assistant_msg.lower()

                    # Merge context based on what was being asked
                    if asking_for_specialty and not parameters.specialty and parameters.query_type in ['general', 'rate_recommendation', 'forecast_analysis']:
                        # User just answered with a specialty, carry forward other params
                        if not parameters.location_list and last_user_params.location_list:
                            parameters.location_list = last_user_params.location_list
                        if not parameters.rate_type and last_user_params.rate_type:
                            parameters.rate_type = last_user_params.rate_type
                        if not parameters.location and last_user_params.location:
                            parameters.location = last_user_params.location
                        if not parameters.city and last_user_params.city:
                            parameters.city = last_user_params.city
                        if not parameters.state and last_user_params.state:
                            parameters.state = last_user_params.state
                        if not parameters.time_horizon and last_user_params.time_horizon:
                            parameters.time_horizon = last_user_params.time_horizon
                        if not parameters.query_type or parameters.query_type == 'general':
                            parameters.query_type = last_user_params.query_type

                    elif asking_for_rate_type and not parameters.rate_type:
                        # User just answered with rate type, carry forward other params
                        if not parameters.specialty and last_user_params.specialty:
                            parameters.specialty = last_user_params.specialty
                        if not parameters.location_list and last_user_params.location_list:
                            parameters.location_list = last_user_params.location_list
                        if not parameters.query_type or parameters.query_type == 'general':
                            parameters.query_type = last_user_params.query_type

                    elif asking_for_time_frame and parameters.time_horizon:
                        # User just answered with time frame, carry forward other params
                        if not parameters.specialty and last_user_params.specialty:
                            parameters.specialty = last_user_params.specialty
                        if not parameters.location and last_user_params.location:
                            parameters.location = last_user_params.location
                        if not parameters.city and last_user_params.city:
                            parameters.city = last_user_params.city
                        if not parameters.state and last_user_params.state:
                            parameters.state = last_user_params.state
                        if not parameters.rate_type and last_user_params.rate_type:
                            parameters.rate_type = last_user_params.rate_type
                        if not parameters.query_type or parameters.query_type == 'general':
                            parameters.query_type = last_user_params.query_type

                    elif asking_for_forecast_location and (parameters.state or parameters.location):
                        # User just answered with location for forecast, carry forward other params
                        if not parameters.specialty and last_user_params.specialty:
                            parameters.specialty = last_user_params.specialty
                        if not parameters.time_horizon and last_user_params.time_horizon:
                            parameters.time_horizon = last_user_params.time_horizon
                        if not parameters.rate_type and last_user_params.rate_type:
                            parameters.rate_type = last_user_params.rate_type
                        if not parameters.query_type or parameters.query_type == 'general':
                            parameters.query_type = last_user_params.query_type

                    elif asking_for_state:
                        # User is providing state info, merge with previous location context
                        if not parameters.specialty and last_user_params.specialty:
                            parameters.specialty = last_user_params.specialty
                        if not parameters.rate_type and last_user_params.rate_type:
                            parameters.rate_type = last_user_params.rate_type
                        if not parameters.time_horizon and last_user_params.time_horizon:
                            parameters.time_horizon = last_user_params.time_horizon
                        if not parameters.query_type or parameters.query_type == 'general':
                            parameters.query_type = last_user_params.query_type

                        # Parse the current message for location info and merge with previous
                        if last_user_params.location_list and 'and' in query.message.lower():
                            # User provided both locations with states
                            # Just use the new parameters.location_list as is
                            pass
                        elif last_user_params.location_list:
                            # Carry forward location_list if new extraction missed it
                            if not parameters.location_list:
                                parameters.location_list = last_user_params.location_list

        # Debug logging
        print(f"📊 Query: {query.message}")
        print(f"🎯 Detected type: {parameters.query_type}")
        print(f"🏥 Specialty: {parameters.specialty}")
        print(f"📍 Location: {parameters.location}")
        if parameters.location_list:
            print(f"📍 Location List: {parameters.location_list}")
        if parameters.rate_type:
            print(f"💰 Rate Type: {parameters.rate_type}")

        # Route based on query type
        if parameters.query_type == "forecast_analysis":
            # Handle forecast queries
            if not forecasting_service:
                raise HTTPException(
                    status_code=503,
                    detail="Forecasting service not configured"
                )

            # Check if we have a specialty
            if not parameters.specialty:
                return ChatResponse(
                    response="To generate a forecast, which specialty are you interested in?\n\n" +
                            "• **ICU** (Intensive Care Unit)\n" +
                            "• **ED** (Emergency Department)\n" +
                            "• **OR** (Operating Room)\n" +
                            "• **Med/Surg** (Medical Surgical)\n" +
                            "• **Telemetry**\n\n" +
                            "For example: 'What will ICU rates be next year?' or 'Forecast ED rates in 6 months'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if we have a time frame
            if not parameters.time_horizon:
                specialty_context = f" for {parameters.specialty}" if parameters.specialty else ""
                location_context = ""
                if parameters.location:
                    location_context = f" in {parameters.location}"
                elif parameters.state:
                    location_context = f" in {parameters.state}"
                elif parameters.city and parameters.state:
                    location_context = f" in {parameters.city}, {parameters.state}"

                return ChatResponse(
                    response=f"What time frame would you like to forecast{specialty_context}{location_context}?\n\n" +
                            "• **2 weeks** (4 weeks)\n" +
                            "• **3 months** (12 weeks)\n" +
                            "• **6 months** (26 weeks)\n" +
                            "• **1 year** (52 weeks)\n\n" +
                            "For example: 'Forecast {parameters.specialty or 'ICU'} rates in 6 months' or 'What will rates be next year?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if user explicitly asked for national/all-states data
            message_lower = query.message.lower()
            is_national_query = any(keyword in message_lower for keyword in ['nationally', 'national', 'nationwide', 'all states', 'across the us', 'entire us', 'in the us', 'the us', ' us ', ' us?', ' us.'])

            # DEFAULT BEHAVIOR: If no state is specified, use national (all states)
            # Only ask for clarification if the query seems ambiguous
            if not parameters.state and not parameters.location and not is_national_query:
                # Default to national forecast (aggregate all states)
                parameters.location = None
                parameters.state = None
                parameters.city = None
                print("💡 No state specified - defaulting to NATIONAL forecast (all states aggregate)")

            # If it's an explicit national query, ensure location is null
            if is_national_query:
                parameters.location = None
                parameters.state = None
                parameters.city = None
                print("💡 National forecast query detected - using nationwide data (all states)")

            # Auto-detect if this is a nurse-focused query and default to weekly_pay
            # BUT: If user explicitly asks for "bill rate" or "hourly", respect that!
            message_lower = query.message.lower()

            # Check if user explicitly mentioned a rate type
            explicitly_asked_bill_rate = 'bill rate' in message_lower or 'billing rate' in message_lower
            explicitly_asked_hourly = 'hourly' in message_lower or 'per hour' in message_lower or '/hr' in message_lower

            # Only auto-detect if user DIDN'T explicitly ask for a rate type
            if not explicitly_asked_bill_rate and not explicitly_asked_hourly:
                nurse_keywords = ['nurse', 'rn', 'job', 'jobs', 'work', 'pay', 'make', 'earn', 'salary', 'compensation', 'i want', 'should i']
                is_nurse_query = any(keyword in message_lower for keyword in nurse_keywords)

                if is_nurse_query and not parameters.rate_type:
                    # Default to weekly_pay for nurse forecast queries
                    parameters.rate_type = "weekly_pay"
                    print("💡 Auto-detected nurse forecast query, defaulting to weekly_pay")
                elif not parameters.rate_type:
                    # Default to bill_rate for business queries
                    parameters.rate_type = "bill_rate"
            else:
                # User explicitly asked for bill_rate or hourly_pay - use it!
                if explicitly_asked_bill_rate and not parameters.rate_type:
                    parameters.rate_type = "bill_rate"
                    print("💡 User explicitly asked for bill rate")
                elif explicitly_asked_hourly and not parameters.rate_type:
                    parameters.rate_type = "hourly_pay"
                    print("💡 User explicitly asked for hourly pay")
                elif not parameters.rate_type:
                    parameters.rate_type = "bill_rate"

            forecast_integration = ChatbotForecastIntegration(forecasting_service)
            forecast_data = await forecast_integration.generate_forecast_analysis(parameters)

            if "error" in forecast_data:
                error_response = f"I couldn't generate a forecast: {forecast_data['error']}"
                return ChatResponse(
                    response=error_response,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                    requires_data=False
                )

            # Create forecast analysis object
            forecast_analysis = ForecastAnalysis(**forecast_data)

            # Generate AI response
            ai_response = await openai_processor.generate_forecast_response(
                forecast_data, query.message, parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                forecast_analysis=forecast_analysis,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'forecast_comparison':
            # Handle forecast comparison queries (e.g., "Compare current ICU rates to next quarter in NY")
            if not forecasting_service or not db_service:
                return ChatResponse(
                    response="⚠️ I need both database and forecasting services to compare current vs future rates.",
                    requires_data=False
                )

            # Check if we have a specialty
            if not parameters.specialty:
                return ChatResponse(
                    response="To compare current and future rates, which specialty are you interested in?\n\n" +
                            "• **ICU** (Intensive Care Unit)\n" +
                            "• **ED** (Emergency Department)\n" +
                            "• **OR** (Operating Room)\n" +
                            "• **Med/Surg** (Medical Surgical)\n" +
                            "• **Telemetry**\n\n" +
                            "For example: 'Compare current ICU rates to next quarter in NY'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if we have a time frame
            if not parameters.time_horizon:
                specialty_context = f" for {parameters.specialty}" if parameters.specialty else ""
                location_context = ""
                if parameters.location:
                    location_context = f" in {parameters.location}"
                elif parameters.state:
                    location_context = f" in {parameters.state}"
                elif parameters.city and parameters.state:
                    location_context = f" in {parameters.city}, {parameters.state}"

                return ChatResponse(
                    response=f"What future time frame would you like to compare against{specialty_context}{location_context}?\n\n" +
                            "• **3 months** (12 weeks)\n" +
                            "• **6 months** (26 weeks)\n" +
                            "• **1 year** (52 weeks)\n\n" +
                            "For example: 'Compare current {parameters.specialty or 'ICU'} rates to 6 months from now'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if we have a location (state is required)
            if not parameters.state and not parameters.location:
                specialty_context = f" for {parameters.specialty}" if parameters.specialty else ""
                time_map = {
                    "4_weeks": "in 4 weeks",
                    "12_weeks": "in 3 months",
                    "26_weeks": "in 6 months",
                    "52_weeks": "next year"
                }
                time_context = f" {time_map.get(parameters.time_horizon, '')}" if parameters.time_horizon else ""

                return ChatResponse(
                    response=f"Which state would you like to compare{specialty_context}{time_context}?\n\n" +
                            "For example:\n" +
                            "• 'NY' or 'New York'\n" +
                            "• 'CA' or 'California'\n" +
                            "• 'TX' or 'Texas'\n\n" +
                            f"Try: 'Compare current {parameters.specialty or 'ICU'} rates{time_context} in NY'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get current rates from database
            current_rates = await db_service.get_rate_recommendation(parameters)

            if not current_rates:
                location_msg = f" in {parameters.location or parameters.state or 'this location'}"
                return ChatResponse(
                    response=f"I don't have enough current market data for {parameters.specialty}{location_msg}.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get forecast rates
            forecast_integration = ChatbotForecastIntegration(forecasting_service)
            forecast_data = await forecast_integration.generate_forecast_analysis(parameters)

            if "error" in forecast_data:
                return ChatResponse(
                    response=f"I couldn't generate future forecast: {forecast_data['error']}",
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                    requires_data=False
                )

            # Generate comparison response
            ai_response = await openai_processor.generate_forecast_comparison_response(
                current_rates, forecast_data, query.message, parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                rate_recommendation=current_rates,
                forecast_analysis=ForecastAnalysis(**forecast_data),
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'rate_comparison':
            # Handle rate comparison queries (e.g., "Is $120 too high for ICU in NY?")
            if not db_service:
                return ChatResponse(
                    response="⚠️ Database connection failed. I can't access current rate data right now.",
                    requires_data=False
                )

            if not parameters.proposed_rate:
                return ChatResponse(
                    response="I'd be happy to help evaluate a rate! Please provide a specific dollar amount, like 'Is $120 too high for ICU in NY?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if we have enough context to proceed
            missing_info = []
            if not parameters.specialty:
                missing_info.append("specialty (e.g., ICU, ED, OR, Med/Surg)")
            if not parameters.location and not parameters.city and not parameters.state:
                missing_info.append("location (city and/or state)")

            if missing_info:
                return ChatResponse(
                    response=f"To evaluate the ${parameters.proposed_rate:.0f}/hr rate, I need a bit more information:\n\n" +
                             "\n".join([f"• **{info}**" for info in missing_info]) +
                             f"\n\nFor example, try: 'Is ${parameters.proposed_rate:.0f}/hr too high for ICU in Ohio?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get market data for comparison
            recommendation = await db_service.get_rate_recommendation(parameters)

            if not recommendation:
                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.location}" if parameters.location else ""
                return ChatResponse(
                    response=f"I don't have enough recent market data{specialty_msg}{location_msg} to compare your rate against. Try a different specialty or location.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Calculate percentage difference from market average
            market_avg = recommendation.get('market_average', 0)
            proposed_rate = parameters.proposed_rate
            recommended_min = recommendation.get('recommended_min', 0)
            recommended_max = recommendation.get('recommended_max', 0)

            if market_avg == 0:
                return ChatResponse(
                    response="I couldn't calculate a market average for comparison. Please try again.",
                    requires_data=False
                )

            percentage_diff = ((proposed_rate - market_avg) / market_avg) * 100

            # Build comparison response
            specialty_str = parameters.specialty or "this specialty"
            location_str = parameters.location or "this market"

            # Check if rate is within recommended range
            within_range = recommended_min <= proposed_rate <= recommended_max

            if within_range:
                # Rate is perfectly aligned with market - give positive feedback
                response_text = f"""✅ **Great job pricing this!** Your proposed rate of **${proposed_rate:.0f}/hr** for {specialty_str} in {location_str} is perfectly aligned with the market.

**Market Context**:
- Your Rate: ${proposed_rate:.0f}/hr ({abs(percentage_diff):.1f}% {'above' if percentage_diff > 0 else 'below' if percentage_diff < 0 else 'at'} market average of ${market_avg:.2f}/hr)
- Recommended Range: ${recommended_min:.2f} - ${recommended_max:.2f}/hr ✓
- Competitive Floor (25th percentile): ${recommendation.get('competitive_floor', 0):.2f}/hr
- Sample Size: {recommendation.get('sample_size', 0)} recent assignments

💡 **Strategic Insight**: This rate is competitively positioned to attract quality candidates while maintaining reasonable client costs - a balanced approach that should help you fill this position efficiently."""
            else:
                # Rate is outside recommended range
                if percentage_diff > 0:
                    comparison = f"**{abs(percentage_diff):.1f}% above** market average"
                    strategic_advice = "\n\n💡 **Strategic Insight**: Higher bill rates typically fill positions faster as they're more attractive to candidates, but they may not always be financially advantageous from the client's perspective. Consider your urgency and budget constraints."
                elif percentage_diff < 0:
                    comparison = f"**{abs(percentage_diff):.1f}% below** market average"
                    strategic_advice = "\n\n💡 **Strategic Insight**: This rate is below market average, which may be more cost-effective for the client but could take longer to fill or attract less experienced candidates."
                else:
                    comparison = "**right at** market average"
                    strategic_advice = "\n\n💡 **Strategic Insight**: This rate is competitively positioned at the market average - a balanced approach for both attracting candidates and maintaining reasonable client costs."

                response_text = f"""Your proposed rate of **${proposed_rate:.0f}/hr** for {specialty_str} in {location_str} is {comparison} (${market_avg:.2f}/hr).

**Market Context**:
- Recommended Range: ${recommended_min:.2f} - ${recommended_max:.2f}/hr
- Competitive Floor (25th percentile): ${recommendation.get('competitive_floor', 0):.2f}/hr
- Sample Size: {recommendation.get('sample_size', 0)} recent assignments{strategic_advice}"""

            chat_response = ChatResponse(
                response=response_text,
                rate_recommendation=recommendation,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'rate_impact':
            # Handle rate impact analysis queries (e.g., "If I drop the bill rate by $10, can we still fill?")
            if not db_service:
                return ChatResponse(
                    response="⚠️ Database connection failed. I can't access current rate data right now.",
                    requires_data=False
                )

            if not parameters.proposed_rate:
                return ChatResponse(
                    response="To analyze the impact of changing rates, please specify the new rate you're considering. For example: 'If I drop the bill rate to $85, can we still fill the position?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if we have enough context
            missing_info = []
            if not parameters.specialty:
                missing_info.append("specialty (e.g., ICU, ED, OR)")
            if not parameters.location and not parameters.city and not parameters.state:
                missing_info.append("location (city and/or state)")

            if missing_info:
                return ChatResponse(
                    response=f"To analyze the impact of a ${parameters.proposed_rate:.0f}/hr rate, I need:\n\n" +
                             "\n".join([f"• **{info}**" for info in missing_info]) +
                             f"\n\nFor example: 'If I drop the ICU bill rate in Buffalo to ${parameters.proposed_rate:.0f}, can we still fill?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get market data for comparison
            recommendation = await db_service.get_rate_recommendation(parameters)

            if not recommendation:
                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.location or parameters.city or parameters.state}" if (parameters.location or parameters.city or parameters.state) else ""
                return ChatResponse(
                    response=f"I don't have enough market data{specialty_msg}{location_msg} to analyze the impact of this rate change.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Calculate percentile of proposed rate
            market_avg = recommendation.get('market_average', 0)
            competitive_floor = recommendation.get('competitive_floor', 0)
            proposed_rate = parameters.proposed_rate

            if market_avg == 0:
                return ChatResponse(
                    response="I couldn't calculate market statistics for comparison.",
                    requires_data=False
                )

            # Calculate where the proposed rate falls
            percentage_of_avg = (proposed_rate / market_avg) * 100

            # Estimate percentile (rough approximation)
            # If competitive_floor is 25th percentile, we can estimate
            if competitive_floor > 0:
                if proposed_rate < competitive_floor:
                    estimated_percentile = (proposed_rate / competitive_floor) * 25  # Below 25th percentile
                else:
                    # Rough linear interpolation between 25th and 50th (assuming avg ~= 50th)
                    estimated_percentile = 25 + ((proposed_rate - competitive_floor) / (market_avg - competitive_floor)) * 25
            else:
                estimated_percentile = percentage_of_avg / 2  # Rough estimate

            # Build impact assessment
            specialty_str = parameters.specialty or "this specialty"
            location_str = parameters.location or parameters.city or parameters.state or "this market"

            # Determine fillability assessment
            if estimated_percentile < 40:
                fillability = "⚠️ **High Risk** - You will likely struggle to fill and retain talent at this rate."
                recommendation_text = f"This rate is significantly below market (estimated ~{estimated_percentile:.0f}th percentile). Consider these alternatives:\n\n1. **Increase to at least ${competitive_floor:.2f}/hr** (25th percentile) to improve competitiveness\n2. **Target ${market_avg * 0.975:.2f}-${market_avg * 1.025:.2f}/hr** (recommended range) for optimal fill rates\n3. **Offer additional incentives** (bonuses, housing, flexible schedules) if rate must stay low"
            elif estimated_percentile < 50:
                fillability = "⚠️ **Moderate Risk** - This rate may take longer to fill and could attract less experienced candidates."
                recommendation_text = f"While this rate is within the bottom half of the market (~{estimated_percentile:.0f}th percentile), you may experience:\n- Longer time-to-fill\n- Candidates with less experience\n- Higher turnover risk\n\nConsider moving closer to the market average (${market_avg:.2f}/hr) for better results."
            else:
                fillability = "✅ **Good** - This rate should be competitive enough to fill the position."
                recommendation_text = f"This rate is at or above the market median (~{estimated_percentile:.0f}th percentile), which should help you:\n- Attract qualified candidates\n- Fill positions in reasonable time\n- Retain talent effectively"

            response_text = f"""**Impact Analysis: ${proposed_rate:.0f}/hr for {specialty_str} in {location_str}**

{fillability}

**Market Position:**
- Your Rate: ${proposed_rate:.0f}/hr ({percentage_of_avg:.1f}% of market average)
- Market Average: ${market_avg:.2f}/hr
- Competitive Floor (25th percentile): ${competitive_floor:.2f}/hr
- Recommended Range: ${recommendation.get('recommended_min', 0):.2f}-${recommendation.get('recommended_max', 0):.2f}/hr

**📊 Rule of Thumb:** Rates below the 40th percentile typically struggle with filling positions and retaining talent. Your proposed rate is estimated at the **{estimated_percentile:.0f}th percentile**.

**💡 Recommendation:**
{recommendation_text}

*Based on {recommendation.get('sample_size', 0)} recent assignments in this market.*"""

            chat_response = ChatResponse(
                response=response_text,
                rate_recommendation=recommendation,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'unfilled_position':
            # Handle unfilled position analysis (e.g., "Why can't I fill this ICU position?")
            if not db_service:
                return ChatResponse(
                    response="⚠️ Database connection failed. I can't access market data right now.",
                    requires_data=False
                )

            # Check if we have enough context
            missing_info = []
            if not parameters.specialty:
                missing_info.append("specialty (e.g., ICU, ED, OR)")
            if not parameters.location and not parameters.city and not parameters.state:
                missing_info.append("location (city and/or state)")

            if not parameters.proposed_rate:
                missing_info.append("current pay rate you're offering")

            if missing_info:
                return ChatResponse(
                    response=f"To help you understand why your position isn't filling, I need:\n\n" +
                             "\n".join([f"• **{info}**" for info in missing_info]) +
                             "\n\nFor example: 'I'm offering $85/hr for ICU in Buffalo but can't get anyone interested. Why?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get highest rates in the market for comparison
            market_data = await db_service.get_highest_rates_in_market(parameters)

            if not market_data:
                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.location or parameters.city or parameters.state}" if (parameters.location or parameters.city or parameters.state) else ""
                return ChatResponse(
                    response=f"I don't have enough market data{specialty_msg}{location_msg} to analyze this unfilled position.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Compare current rate against market
            current_rate = parameters.proposed_rate
            market_avg = market_data.get('market_average', 0)
            percentile_75 = market_data.get('percentile_75', 0)
            percentile_90 = market_data.get('percentile_90', 0)
            max_rate = market_data.get('max_rate', 0)

            if market_avg == 0:
                return ChatResponse(
                    response="I couldn't calculate market statistics for comparison.",
                    requires_data=False
                )

            # Calculate gap from various benchmarks
            gap_from_avg = ((current_rate - market_avg) / market_avg) * 100
            gap_from_75th = ((current_rate - percentile_75) / percentile_75) * 100 if percentile_75 > 0 else 0
            gap_from_90th = ((current_rate - percentile_90) / percentile_90) * 100 if percentile_90 > 0 else 0

            specialty_str = parameters.specialty or "this specialty"
            location_str = parameters.location or parameters.city or parameters.state or "this market"

            # Determine root cause and recommendations
            if current_rate < percentile_75:
                diagnosis = f"🔴 **Your rate is below competitive levels** - You're offering ${current_rate:.0f}/hr, which is {abs(gap_from_75th):.1f}% below the 75th percentile (${percentile_75:.2f}/hr). Nurses can easily find better-paying positions elsewhere."
                recommendations = f"""**Recommended Actions:**

1. **Increase to at least ${percentile_75:.2f}/hr** (75th percentile) to become competitive
2. **Target ${percentile_90:.2f}/hr** (90th percentile) if you need to fill quickly
3. **Consider going up to ${max_rate:.2f}/hr** (highest in market) for hard-to-fill positions

**Alternative strategies if you can't increase pay:**
- Offer sign-on bonuses or completion bonuses
- Provide housing stipends or free housing
- Highlight desirable schedule flexibility
- Emphasize location benefits or facility reputation"""
            elif current_rate < percentile_90:
                diagnosis = f"🟡 **Your rate is competitive but not top-tier** - At ${current_rate:.0f}/hr, you're {gap_from_avg:.1f}% {'above' if gap_from_avg > 0 else 'below'} average but {abs(gap_from_90th):.1f}% below top-paying positions (${percentile_90:.2f}/hr). Nurses may be holding out for better offers."
                recommendations = f"""**Recommended Actions:**

1. **Increase to ${percentile_90:.2f}/hr** (90th percentile) to match top-paying facilities
2. **Offer incentives** to make total package more attractive (bonuses, housing, benefits)
3. **Speed up hiring process** - top candidates get snapped up quickly
4. **Market the non-financial benefits** - location, team culture, growth opportunities

Current gap: ${percentile_90 - current_rate:.2f}/hr from top market rates"""
            else:
                diagnosis = f"✅ **Your rate is in the top tier** - At ${current_rate:.0f}/hr, you're already paying above the 90th percentile. The issue likely isn't compensation."
                recommendations = """**Other factors to investigate:**

1. **Hiring process** - Are you taking too long to make offers?
2. **Job posting visibility** - Are nurses seeing your positions?
3. **Reputation** - Check facility reviews and ratings
4. **Schedule/shifts** - Are you offering desirable shifts?
5. **Requirements** - Are your qualifications too strict?
6. **Location challenges** - Is the area less desirable?

Consider conducting candidate surveys to understand why offers are being declined."""

            response_text = f"""**Why Your {specialty_str} Position in {location_str} Isn't Filling**

{diagnosis}

**Market Comparison:**
- Your Current Rate: ${current_rate:.0f}/hr
- Market Average: ${market_avg:.2f}/hr ({gap_from_avg:+.1f}%)
- Top 25% of Market (75th percentile): ${percentile_75:.2f}/hr
- Top 10% of Market (90th percentile): ${percentile_90:.2f}/hr
- Highest Rate in Market: ${max_rate:.2f}/hr

{recommendations}

**💡 Key Insight:** Nurses are demanding higher wages in today's market. To compete effectively, you typically need to be in the top 25-30% of pay rates to attract quality candidates quickly.

*Based on {market_data.get('sample_size', 0)} recent assignments in this market.*"""

            chat_response = ChatResponse(
                response=response_text,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'market_comparison':
            # Handle market comparison queries (e.g., "Compare ICU rates in Ohio and NY")
            if not db_service:
                return ChatResponse(
                    response="⚠️ Database connection failed. I can't access market data right now.",
                    requires_data=False
                )

            # Check if we have a specialty
            if not parameters.specialty:
                return ChatResponse(
                    response="To compare markets, I need to know which specialty you're interested in. For example: 'Compare ICU rates in Ohio and NY' or 'How much higher is Buffalo than Ithaca for ED nurses?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Check if rate_type is specified - default to weekly_pay for nurse queries
            if not parameters.rate_type:
                # Auto-detect if this is a nurse-focused query based on context
                message_lower = query.message.lower()
                nurse_keywords = ['nurse', 'rn', 'travel nurse', 'she', 'he', 'make money', 'pay', 'salary', 'compensation', 'where should']
                is_nurse_query = any(keyword in message_lower for keyword in nurse_keywords)

                if is_nurse_query:
                    # Default to weekly_pay for nurse queries
                    parameters.rate_type = "weekly_pay"
                    print(f"💡 Auto-detected nurse query, defaulting to weekly_pay")
                else:
                    # Ask for clarification for business queries
                    return ChatResponse(
                        response=f"To compare {parameters.specialty} rates, which rate type would you like to compare?\n\n" +
                                "• **Bill Rate** (what you charge clients)\n" +
                                "• **Weekly Pay** (weekly compensation)\n" +
                                "• **Hourly Pay** (hourly compensation)\n\n" +
                                f"For example: 'Compare {parameters.specialty} bill rates in {parameters.location_list[0] if parameters.location_list and len(parameters.location_list) > 0 else 'those markets'}' or " +
                                f"'Show me weekly pay comparison for {parameters.specialty}'",
                        requires_data=False,
                        extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                    )

            # Get locations to compare
            locations = parameters.location_list if parameters.location_list else []
            if not locations or len(locations) < 2:
                # Try to use city/state/location as fallback
                if parameters.city and parameters.state:
                    locations = [parameters.city, parameters.state]
                elif parameters.location:
                    return ChatResponse(
                        response=f"To compare markets, I need at least two locations. For example: 'Compare {parameters.specialty} rates in Buffalo, NY and Rochester, NY' or 'How much higher is Ohio than NY?'",
                        requires_data=False,
                        extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                    )

            # Parse locations and validate they have state info
            # Full state names to abbreviations
            state_name_to_abbr = {
                "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
                "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
                "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
                "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
                "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
                "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
                "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
                "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
                "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
                "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
                "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
                "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
                "wisconsin": "WI", "wyoming": "WY"
            }

            # Common major cities that don't need clarification
            obvious_cities = {
                "new york city": "NY", "nyc": "NY", "manhattan": "NY",
                "los angeles": "CA", "la": "CA", "san francisco": "CA",
                "chicago": "IL", "houston": "TX", "phoenix": "AZ",
                "philadelphia": "PA", "san antonio": "TX", "san diego": "CA",
                "dallas": "TX", "san jose": "CA", "austin": "TX",
                "jacksonville": "FL", "miami": "FL", "orlando": "FL",
                "seattle": "WA", "denver": "CO", "boston": "MA",
                "atlanta": "GA", "detroit": "MI", "minneapolis": "MN",
                "las vegas": "NV", "portland": "OR", "baltimore": "MD"
            }

            parsed_locations = []
            needs_clarification = []

            for loc in locations:
                loc_clean = loc.strip()

                # Check if it's already "City, State" format
                if ',' in loc_clean:
                    parts = [p.strip() for p in loc_clean.split(',')]
                    if len(parts) == 2:
                        city, state = parts
                        parsed_locations.append({'city': city, 'state': state, 'display': loc_clean})
                        continue

                # Check if it's a 2-letter state code
                if len(loc_clean) == 2 and loc_clean.isalpha():
                    parsed_locations.append({'city': None, 'state': loc_clean.upper(), 'display': loc_clean.upper()})
                    continue

                # Check if it's a full state name
                if loc_clean.lower() in state_name_to_abbr:
                    state_abbr = state_name_to_abbr[loc_clean.lower()]
                    parsed_locations.append({'city': None, 'state': state_abbr, 'display': loc_clean.title()})
                    continue

                # Check if it's an obvious major city
                if loc_clean.lower() in obvious_cities:
                    state = obvious_cities[loc_clean.lower()]
                    parsed_locations.append({'city': loc_clean, 'state': state, 'display': f"{loc_clean}, {state}"})
                    continue

                # Otherwise, it's ambiguous - need clarification
                needs_clarification.append(loc_clean)

            # If any locations need clarification, ask the user
            if needs_clarification:
                return ChatResponse(
                    response=f"I need to know which state for: **{', '.join(needs_clarification)}**\n\n" +
                            f"There are multiple cities with these names. Please specify like:\n" +
                            f"• 'Compare {parameters.specialty} rates in {needs_clarification[0]}, [STATE] and {locations[-1]}'\n" +
                            f"• For example: 'Buffalo, NY' or 'Springfield, IL'\n\n" +
                            f"Or you can compare at the state level: 'Compare {parameters.specialty} rates in Ohio vs New York'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get rate data for each location
            location1_params = QueryParameters(
                query_type="rate_recommendation",
                specialty=parameters.specialty,
                city=parsed_locations[0]['city'],
                state=parsed_locations[0]['state'],
                location=parsed_locations[0]['state'],  # Fallback to state
                rate_type=parameters.rate_type
            )
            location2_params = QueryParameters(
                query_type="rate_recommendation",
                specialty=parameters.specialty,
                city=parsed_locations[1]['city'],
                state=parsed_locations[1]['state'],
                location=parsed_locations[1]['state'],  # Fallback to state
                rate_type=parameters.rate_type
            )

            loc1_data = await db_service.get_rate_recommendation(location1_params)
            loc2_data = await db_service.get_rate_recommendation(location2_params)

            # Use display names for comparison
            loc1_display = parsed_locations[0]['display']
            loc2_display = parsed_locations[1]['display']

            if not loc1_data or not loc2_data:
                missing = []
                if not loc1_data:
                    missing.append(f"{loc1_display}")
                if not loc2_data:
                    missing.append(f"{loc2_display}")

                return ChatResponse(
                    response=f"I don't have enough market data for {parameters.specialty} in {' or '.join(missing)} to make a comparison. Try different locations or specialties.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Calculate difference and percentage
            loc1_avg = loc1_data.get('market_average', 0)
            loc2_avg = loc2_data.get('market_average', 0)
            difference = loc1_avg - loc2_avg
            percentage_diff = (abs(difference) / loc2_avg) * 100 if loc2_avg > 0 else 0

            higher_location = loc1_display if loc1_avg > loc2_avg else loc2_display
            lower_location = loc2_display if loc1_avg > loc2_avg else loc1_display
            abs_diff = abs(difference)

            rate_label = loc1_data.get('rate_type', 'rate')

            response_text = f"""**Market Comparison: {parameters.specialty} {rate_label.title()} Rates**

**{loc1_display}** vs **{loc2_display}**

{higher_location} is **{percentage_diff:.1f}% higher** than {lower_location} (${abs_diff:.2f}/hr difference)

**Detailed Breakdown:**

**{loc1_display}:**
- Market Average: ${loc1_avg:.2f}/hr
- Recommended Range: ${loc1_data.get('recommended_min', 0):.2f} - ${loc1_data.get('recommended_max', 0):.2f}/hr
- Competitive Floor: ${loc1_data.get('competitive_floor', 0):.2f}/hr
- Sample Size: {loc1_data.get('sample_size', 0)} assignments

**{loc2_display}:**
- Market Average: ${loc2_avg:.2f}/hr
- Recommended Range: ${loc2_data.get('recommended_min', 0):.2f} - ${loc2_data.get('recommended_max', 0):.2f}/hr
- Competitive Floor: ${loc2_data.get('competitive_floor', 0):.2f}/hr
- Sample Size: {loc2_data.get('sample_size', 0)} assignments

💡 **Strategic Insight:** {higher_location}'s higher rates may reflect cost of living differences, demand/supply dynamics, or facility budgets. Consider these factors when pricing positions or recruiting across these markets."""

            chat_response = ChatResponse(
                response=response_text,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type in ['rate_recommendation', 'competitive_analysis']:
            # Handle rate analysis queries
            if not db_service:
                return ChatResponse(
                    response="⚠️ Database connection failed. I can't access current rate data right now. Try asking about future forecasts instead, or check that the database server at 192.168.1.221 is running and accessible.",
                    requires_data=False
                )

            # Check if user explicitly asked for national/all-states data
            message_lower = query.message.lower()
            is_national_query = any(keyword in message_lower for keyword in ['nationally', 'national', 'nationwide', 'all states', 'across the us', 'entire us', 'in the us', 'the us', ' us ', ' us?', ' us.'])

            # Check if we have enough context to proceed
            missing_info = []
            if not parameters.specialty:
                missing_info.append("specialty (e.g., ICU, ED, OR, Med/Surg, Telemetry)")
            # Only require location if NOT a national query
            if not is_national_query and not parameters.location and not parameters.city and not parameters.state:
                missing_info.append("location (city and/or state)")

            if missing_info:
                examples = "\n\nFor example: 'What's the bill rate for ICU in Texas?' or 'Suggest a rate for ED nurses in Buffalo, NY'"
                if is_national_query:
                    examples = "\n\nFor example: 'What's the bill rate for ICU nationally?' or 'National average for CRNA rates'"

                return ChatResponse(
                    response=f"I'd be happy to help with rate information! I need a bit more details:\n\n" +
                             "\n".join([f"• **{info}**" for info in missing_info]) +
                             examples,
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            recommendation = await db_service.get_rate_recommendation(parameters)

            # If no data found in database, return helpful message
            if not recommendation:
                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.location}" if parameters.location else ""
                return ChatResponse(
                    response=f"I don't have enough recent market data{specialty_msg}{location_msg}. Try a different specialty or location, or ask about forecast trends instead.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            ai_response = await openai_processor.generate_response(
                {'recommendation': recommendation},
                query.message,
                parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                rate_recommendation=recommendation,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'client_search':
            # Handle client search queries
            if not db_service:
                return ChatResponse(
                    response="Database service is not available. I can't search for clients right now.",
                    requires_data=False
                )

            # Check if we have enough context to proceed
            # Check if user explicitly asked for national/all-states data
            message_lower = query.message.lower()
            is_national_query = any(keyword in message_lower for keyword in ['nationally', 'national', 'nationwide', 'all states', 'across the us', 'entire us', 'in the us', 'the us', ' us ', ' us?', ' us.'])

            missing_info = []
            if not parameters.specialty:
                missing_info.append("specialty (e.g., ICU, ED, OR, Med/Surg)")
            # Only require location if NOT a national query
            if not is_national_query and not parameters.location and not parameters.city and not parameters.state:
                missing_info.append("location (city and/or state)")

            if missing_info:
                examples = "\n\nFor example: 'What clients in Texas have the highest ICU rates?' or 'Show me facilities with low ED rates in California'"
                if is_national_query:
                    examples = "\n\nFor example: 'What clients nationally have the highest ICU rates?' or 'Show me facilities with the best CRNA rates nationwide'"

                return ChatResponse(
                    response=f"To search for clients, I need:\n\n" +
                             "\n".join([f"• **{info}**" for info in missing_info]) +
                             examples,
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Auto-detect if this is a nurse-focused query and default to weekly_pay
            if not parameters.rate_type or parameters.rate_type == "highest":
                message_lower = query.message.lower()
                nurse_keywords = ['nurse', 'rn', 'travel nurse', 'she', 'he', 'job', 'jobs', 'pay', 'paying', 'make', 'earn', 'salary', 'compensation', 'where should', 'highest paying']
                is_nurse_query = any(keyword in message_lower for keyword in nurse_keywords)

                if is_nurse_query:
                    # Default to weekly_pay for nurse job queries
                    parameters.rate_type = "weekly_pay"
                    print(f"💡 Auto-detected nurse job query, defaulting to weekly_pay")

            # Detect if user is asking about compact states
            message_lower = query.message.lower()
            wants_compact_states = 'compact' in message_lower and ('license' in message_lower or 'state' in message_lower)

            # If no specific location but wants compact states, set location to "compact"
            if wants_compact_states and not parameters.location:
                parameters.location = "COMPACT_STATES"
                print("💡 User requested compact states - will filter to compact states only")

            # Extract target rate from conversation if this is a follow-up
            target_rate = None
            # You could extract this from conversation_history if they just asked about rates

            client_results = await db_service.get_clients_by_rate(parameters, target_rate=target_rate)

            # Filter results to compact states if requested
            if wants_compact_states and client_results and 'clients' in client_results:
                original_count = len(client_results['clients'])
                client_results['clients'] = [
                    client for client in client_results['clients']
                    if client.get('state') in COMPACT_STATES
                ]
                filtered_count = len(client_results['clients'])
                print(f"💡 Filtered to compact states: {filtered_count}/{original_count} clients")

                if filtered_count == 0:
                    return ChatResponse(
                        response=f"I couldn't find any {parameters.specialty} jobs in compact states matching your criteria. Try broadening your search or checking specific compact states like FL, TX, CA, or AZ.",
                        requires_data=False,
                        extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                    )

            if not client_results:
                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.location}" if parameters.location else ""
                return ChatResponse(
                    response=f"I couldn't find any clients{specialty_msg}{location_msg} matching those criteria.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            ai_response = await openai_processor.generate_response(
                {'client_results': client_results},
                query.message,
                parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'comparable_jobs':
            # Handle comparable jobs queries
            if not db_service:
                return ChatResponse(
                    response="Database service is not available. I can't search for jobs right now.",
                    requires_data=False
                )

            # Extract rate context from conversation history if available
            # Look for previous rate recommendation to get target rate
            target_rate = None
            rate_range = None

            if query.conversation_history:
                # Look through recent messages for rate context
                for msg in reversed(query.conversation_history[-3:]):
                    content = msg.get('content', '')
                    # Check if this was a rate recommendation response
                    if 'Market Average' in content or 'Recommended' in content:
                        # Try to extract the market average from the message
                        import re
                        # Match patterns like "$2,384.67/week" or "$98.00/hr"
                        rate_match = re.search(r'\$([0-9,]+\.?\d*)', content)
                        if rate_match:
                            rate_str = rate_match.group(1).replace(',', '')
                            target_rate = float(rate_str)
                            print(f"📊 Extracted target rate from history: ${target_rate}")
                            break

            # If we still don't have a target rate, get current market average
            if not target_rate:
                recommendation = await db_service.get_rate_recommendation(parameters)
                if recommendation:
                    target_rate = recommendation.get('market_average')
                    print(f"📊 Using market average as target: ${target_rate}")

            if not target_rate:
                return ChatResponse(
                    response="I need more context to find comparable jobs. Please first ask about rates for a specific specialty and location, then I can show you comparable positions.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get comparable jobs with ±10% rate range
            jobs_results = await db_service.get_comparable_jobs(parameters, target_rate=target_rate)

            if not jobs_results or jobs_results.get('total_jobs', 0) == 0:
                specialty_msg = f" {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.city or parameters.state or parameters.location}" if (parameters.city or parameters.state or parameters.location) else ""
                return ChatResponse(
                    response=f"I couldn't find any comparable{specialty_msg} positions{location_msg} with similar pay packages. Try broadening your search or asking about a different location.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Generate AI response with job listings
            ai_response = await openai_processor.generate_response(
                {'comparable_jobs': jobs_results},
                query.message,
                parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'vendor_location':
            # Handle vendor location queries (e.g., "What vendors are at Memorial Hospital?")
            if not db_service:
                return ChatResponse(
                    response="Database service is not available. I can't search for vendor information right now.",
                    requires_data=False
                )

            if not parameters.client_name:
                return ChatResponse(
                    response="To find which vendors are at a specific location, please provide the hospital or facility name. For example: 'What vendors are at Memorial Hospital?' or 'Which agencies work at Cleveland Clinic?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get vendors at the specified location
            vendor_results = await db_service.get_vendors_at_location(
                client_name=parameters.client_name,
                city=parameters.city,
                state=parameters.state,
                specialty=parameters.specialty
            )

            if not vendor_results or vendor_results.get('total_vendors', 0) == 0:
                location_info = []
                if parameters.city:
                    location_info.append(f"in {parameters.city}")
                if parameters.state:
                    location_info.append(f"in {parameters.state}")
                location_str = " ".join(location_info) if location_info else ""

                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""

                return ChatResponse(
                    response=f"I couldn't find any vendor information for '{parameters.client_name}'{location_str}{specialty_msg}. This could mean:\n\n" +
                            "• The facility name might be spelled differently in our system\n" +
                            "• No recent assignments (past 6 months) from vendors at this location\n" +
                            "• Try a partial name (e.g., 'Memorial' instead of 'Memorial Hospital')",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Generate AI response with vendor listings
            ai_response = await openai_processor.generate_response(
                {'vendor_location': vendor_results},
                query.message,
                parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'vendor_contract':
            # Handle vendor contract queries (e.g., "Who has the contract with Strong Memorial?")
            if not db_service:
                return ChatResponse(
                    response="Database service is not available. I can't search for vendor contract information right now.",
                    requires_data=False
                )

            if not parameters.client_name:
                return ChatResponse(
                    response="To find which vendor/MSP has a contract with a facility, please provide the hospital or facility name. For example: 'Who has the contract with Strong Memorial Hospital?' or 'What vendor works with Cleveland Clinic?'",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Get the most common vendor/MSP for this client
            vendor_info = await db_service.get_vendor_for_client(parameters.client_name)

            if not vendor_info:
                return ChatResponse(
                    response=f"I couldn't find any vendor or MSP information for '{parameters.client_name}'. This could mean:\n\n" +
                            "• The facility name might be spelled differently in our system\n" +
                            "• No recent job postings (with VMS/parentOrg data) for this client\n" +
                            "• Try a partial name (e.g., 'Strong Memorial' instead of 'Strong Memorial Hospital')",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            # Generate natural language response
            response_text = f"**{vendor_info['client_name']}** primarily works with **{vendor_info['vendor_name']}**.\n\n"
            response_text += f"Based on {vendor_info['total_jobs']} job postings in our system, "
            response_text += f"{vendor_info['vendor_name']} appears on {vendor_info['occurrence_count']} of them "
            response_text += f"({vendor_info['percentage']}% of jobs)."

            if vendor_info['percentage'] < 100:
                response_text += f"\n\nNote: The remaining {100 - vendor_info['percentage']}% of jobs may be with other vendors or have no MSP/VMS listed."

            chat_response = ChatResponse(
                response=response_text,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'lead_generation':
            # Handle lead generation queries
            if not db_service:
                return ChatResponse(
                    response="Database service is not available. I can only provide forecasting analysis at the moment.",
                    requires_data=False
                )

            lead_analysis = await db_service.get_lead_opportunities(parameters)

            # If no leads found, return helpful message
            if not lead_analysis:
                specialty_msg = f" for {parameters.specialty}" if parameters.specialty else ""
                location_msg = f" in {parameters.location}" if parameters.location else ""
                return ChatResponse(
                    response=f"I don't have any current lead opportunities{specialty_msg}{location_msg}. Try broadening your search criteria.",
                    requires_data=False,
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {}
                )

            ai_response = await openai_processor.generate_response(
                {'lead_analysis': lead_analysis},
                query.message,
                parameters
            )

            chat_response = ChatResponse(
                response=ai_response,
                lead_analysis=lead_analysis,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

            # Cache the response
            if cache_service:
                cache_service.set(cache_key, chat_response.dict())

            return chat_response

        elif parameters.query_type == 'rate_trends':
            # Handle rate trends analysis - which states have rising/falling rates
            print(f"📈 Rate Trends Query - Specialty: {parameters.specialty}, Direction: {parameters.trend_direction}")

            if not parameters.specialty:
                return ChatResponse(
                    response="I'd be happy to show you rate trends! Which specialty would you like to analyze? For example: ICU, ED, OR, CRNA, etc.",
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                    requires_data=False
                )

            # Determine trend direction (default to rising if not specified)
            trend_direction = parameters.trend_direction if hasattr(parameters, 'trend_direction') and parameters.trend_direction else 'rising'

            # Get rate trends from database
            trends_data = await db_service.get_rate_trends_by_state(
                parameters,
                trend_direction=trend_direction,
                limit=5
            )

            if not trends_data:
                return ChatResponse(
                    response=f"I don't have enough recent data to analyze rate trends for {parameters.specialty}. Rate trend analysis requires at least 3 samples in multiple states over the past 90 days.",
                    extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                    requires_data=False
                )

            # Format the response with AI
            rate_type_label = {
                'bill_rate': 'bill rates',
                'hourly_pay': 'hourly pay',
                'weekly_pay': 'weekly pay'
            }.get(parameters.rate_type or 'bill_rate', 'bill rates')

            direction_word = "rising" if trend_direction == "rising" else "falling"

            # Build a detailed context for the AI
            trends_list = trends_data.get('trends', [])
            trends_summary = f"Top 5 states where {parameters.specialty} {rate_type_label} are {direction_word}:\n\n"
            for i, trend in enumerate(trends_list[:5], 1):
                state = trend.get('state', 'Unknown')
                recent_rate = trend.get('recent_rate', 0)
                older_rate = trend.get('older_rate', 0)
                percent_change = trend.get('percent_change', 0)
                recent_samples = trend.get('recent_sample_size', 0)

                change_symbol = "📈" if percent_change > 0 else "📉"
                trends_summary += f"{i}. **{state}** {change_symbol}\n"
                trends_summary += f"   - Recent (30 days): ${recent_rate:,.2f}\n"
                trends_summary += f"   - Previous (60 days): ${older_rate:,.2f}\n"
                trends_summary += f"   - Change: {percent_change:+.1f}%\n"
                trends_summary += f"   - Sample size: {recent_samples} positions\n\n"

            # Generate AI response
            ai_prompt = f"User asked: {query.message}\n\nHere are the rate trends:\n{trends_summary}\n\nProvide a helpful analysis of these trends and what they mean for the user."

            ai_response = await openai_processor.generate_response(
                {'rate_trends': trends_data},
                ai_prompt,
                parameters
            )

            return ChatResponse(
                response=ai_response,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=True,
                user_role_detected=parameters.user_perspective if hasattr(parameters, 'user_perspective') else None
            )

        elif parameters.query_type == 'conversational':
            # Handle conversational responses (thank you, hello, etc.)
            conversational_responses = {
                'thank': "You're very welcome! I'm glad I could help. Feel free to ask me anything else about rates, forecasts, or market opportunities. I'm here to help! 😊",
                'great': "I'm so glad this was helpful! Let me know if you need anything else - whether it's more market data, client searches, or forecast insights. Happy to assist!",
                'awesome': "Thanks! I'm here whenever you need market intelligence or staffing insights. Just ask away!",
                'perfect': "Excellent! Don't hesitate to reach out if you need more information. I'm here to help you make data-driven decisions!",
                'appreciate': "My pleasure! That's what I'm here for. Anytime you need staffing market insights, just ask!",
                'hello': "Hello! I'm your healthcare staffing intelligence assistant. I can help you with current rates, future forecasts, client searches, and market opportunities. What would you like to know?",
                'hi': "Hi there! Ready to help with any healthcare staffing questions - rates, forecasts, leads, you name it. What can I look up for you?"
            }

            # Find matching response
            message_lower = query.message.lower()
            response = "I'm happy to help! Feel free to ask me about rates, forecasts, or market opportunities anytime."

            for keyword, resp in conversational_responses.items():
                if keyword in message_lower:
                    response = resp
                    break

            return ChatResponse(
                response=response,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=False
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

**Example queries**:
- "What should I bill for ICU in California?"
- "What will OR rates be next quarter?"
- "Show me best sales opportunities in Texas"
- "Should I lock in ED rates now or wait?"

What type of analysis would you like?"""

            return ChatResponse(
                response=general_response,
                extracted_parameters=parameters.__dict__ if hasattr(parameters, '__dict__') else {},
                requires_data=False
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")

    print(f"""
╔════════════════════════════════════════════════════════════╗
║   Healthcare Staffing Intelligence Chatbot                ║
║   Version 2.0.0 - With Forecasting Capabilities           ║
╚════════════════════════════════════════════════════════════╝

Starting server on http://{host}:{port}
API Documentation: http://{host}:{port}/docs

Press CTRL+C to stop
""")

    reload_enabled = os.getenv("UVICORN_RELOAD", "true").lower() == "true"

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level="info"
    )
