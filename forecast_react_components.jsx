// Add these new components to your HealthcareIntelligenceChatbot.jsx

import { TrendingUp, TrendingDown, Minus, Calendar, Target, AlertTriangle, CheckCircle } from 'lucide-react';

const ForecastInsightCard = ({ forecastAnalysis }) => {
  const { forecast_insights, business_recommendations, location, specialty, time_horizon } = forecastAnalysis;
  
  const getTrendIcon = (direction) => {
    switch (direction) {
      case 'increasing': return <TrendingUp className="w-5 h-5 text-green-600" />;
      case 'decreasing': return <TrendingDown className="w-5 h-5 text-red-600" />;
      default: return <Minus className="w-5 h-5 text-gray-600" />;
    }
  };

  const getTrendColor = (direction) => {
    switch (direction) {
      case 'increasing': return 'text-green-600 bg-green-50 border-green-200';
      case 'decreasing': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getConfidenceIcon = (level) => {
    switch (level) {
      case 'high': return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'medium': return <AlertTriangle className="w-4 h-4 text-yellow-600" />;
      case 'low': return <AlertTriangle className="w-4 h-4 text-red-600" />;
      default: return <AlertTriangle className="w-4 h-4 text-gray-600" />;
    }
  };

  const getConfidenceColor = (level) => {
    switch (level) {
      case 'high': return 'text-green-700 bg-green-50';
      case 'medium': return 'text-yellow-700 bg-yellow-50';
      case 'low': return 'text-red-700 bg-red-50';
      default: return 'text-gray-700 bg-gray-50';
    }
  };

  const formatTimeHorizon = (horizon) => {
    return horizon?.replace('_', ' ').replace('weeks', 'week') || 'forecast';
  };

  return (
    <div className="bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200 rounded-lg p-4 mt-3">
      <div className="flex items-center gap-2 mb-4">
        <Calendar className="w-5 h-5 text-purple-600" />
        <h3 className="font-semibold text-purple-800">Market Forecast Analysis</h3>
      </div>
      
      {/* Header Info */}
      <div className="bg-white rounded-lg p-3 border border-purple-100 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="text-center">
            <div className="text-sm text-gray-600">Specialty</div>
            <div className="font-bold text-lg">{specialty}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600">Location</div>
            <div className="font-bold text-lg capitalize">{location}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600">Time Horizon</div>
            <div className="font-bold text-lg capitalize">{formatTimeHorizon(time_horizon)}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600">Model</div>
            <div className="font-bold text-lg capitalize">{forecast_insights.model_used}</div>
          </div>
        </div>
      </div>

      {/* Current vs Future */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div className="bg-white rounded-lg p-3 border border-purple-100">
          <div className="text-sm text-gray-600 mb-1">Current Rate</div>
          <div className="text-2xl font-bold text-blue-600">
            {formatCurrency(forecast_insights.current_value)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {forecast_insights.target_metric.replace('_', ' ')}
          </div>
        </div>
        
        <div className="bg-white rounded-lg p-3 border border-purple-100">
          <div className="text-sm text-gray-600 mb-1">
            {formatTimeHorizon(time_horizon).replace('week', 'Week')} Forecast
          </div>
          <div className="text-2xl font-bold text-purple-600">
            {formatCurrency(forecast_insights.forecasts[time_horizon] || 0)}
          </div>
          <div className="flex items-center gap-1 mt-1">
            {getTrendIcon(forecast_insights.trend_direction)}
            <span className={`text-sm font-medium ${
              forecast_insights.growth_rates[time_horizon] > 0 ? 'text-green-600' : 
              forecast_insights.growth_rates[time_horizon] < 0 ? 'text-red-600' : 'text-gray-600'
            }`}>
              {forecast_insights.growth_rates[time_horizon] > 0 ? '+' : ''}
              {forecast_insights.growth_rates[time_horizon]?.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Trend Analysis */}
      <div className={`rounded-lg p-3 border mb-4 ${getTrendColor(forecast_insights.trend_direction)}`}>
        <div className="flex items-center gap-2 mb-2">
          {getTrendIcon(forecast_insights.trend_direction)}
          <h4 className="font-semibold">Market Trend: {forecast_insights.trend_direction.toUpperCase()}</h4>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="font-medium">4 Weeks</div>
            <div>{forecast_insights.growth_rates['4_weeks'] > 0 ? '+' : ''}{forecast_insights.growth_rates['4_weeks']?.toFixed(1)}%</div>
          </div>
          <div>
            <div className="font-medium">12 Weeks</div>
            <div>{forecast_insights.growth_rates['12_weeks'] > 0 ? '+' : ''}{forecast_insights.growth_rates['12_weeks']?.toFixed(1)}%</div>
          </div>
          <div>
            <div className="font-medium">26 Weeks</div>
            <div>{forecast_insights.growth_rates['26_weeks'] > 0 ? '+' : ''}{forecast_insights.growth_rates['26_weeks']?.toFixed(1)}%</div>
          </div>
          <div>
            <div className="font-medium">52 Weeks</div>
            <div>{forecast_insights.growth_rates['52_weeks'] > 0 ? '+' : ''}{forecast_insights.growth_rates['52_weeks']?.toFixed(1)}%</div>
          </div>
        </div>
      </div>

      {/* Confidence & Accuracy */}
      <div className={`rounded-lg p-3 border mb-4 ${getConfidenceColor(forecast_insights.confidence_level)}`}>
        <div className="flex items-center gap-2 mb-2">
          {getConfidenceIcon(forecast_insights.confidence_level)}
          <h4 className="font-semibold">
            Forecast Confidence: {forecast_insights.confidence_level.toUpperCase()}
          </h4>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="font-medium">Model Accuracy</div>
            <div>{(100 - forecast_insights.accuracy_mape).toFixed(1)}% accurate</div>
          </div>
          <div>
            <div className="font-medium">Error Rate</div>
            <div>{forecast_insights.accuracy_mape?.toFixed(1)}% MAPE</div>
          </div>
        </div>
      </div>

      {/* Role-based Recommendations */}
      {business_recommendations && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-800 flex items-center gap-2">
            <Target className="w-4 h-4" />
            Strategic Recommendations
          </h4>
          
          {Object.entries(business_recommendations).map(([role, recommendations]) => (
            recommendations.length > 0 && (
              <div key={role} className={`rounded-lg p-3 border ${getRoleColor(role)}`}>
                <div className="flex items-center gap-2 mb-2">
                  {getRoleIcon(role)}
                  <h5 className="font-semibold capitalize">{role} Perspective</h5>
                </div>
                <ul className="text-sm space-y-1">
                  {recommendations.map((rec, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <span className="text-xs mt-1 flex-shrink-0">•</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          ))}
        </div>
      )}

      {/* Extended Forecast Timeline */}
      <div className="bg-white rounded-lg p-3 border border-purple-100 mt-4">
        <h4 className="font-medium text-gray-800 mb-3">Extended Forecast Timeline</h4>
        <div className="space-y-2">
          {Object.entries(forecast_insights.forecasts).map(([period, value]) => (
            <div key={period} className="flex justify-between items-center text-sm">
              <span className="capitalize text-gray-600">
                {period.replace('_', ' ').replace('weeks', 'week')}
              </span>
              <div className="flex items-center gap-2">
                <span className="font-medium">{formatCurrency(value)}</span>
                <span className={`text-xs px-2 py-1 rounded ${
                  forecast_insights.growth_rates[period] > 0 ? 'bg-green-100 text-green-700' :
                  forecast_insights.growth_rates[period] < 0 ? 'bg-red-100 text-red-700' : 
                  'bg-gray-100 text-gray-700'
                }`}>
                  {forecast_insights.growth_rates[period] > 0 ? '+' : ''}
                  {forecast_insights.growth_rates[period]?.toFixed(1)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Processing Info */}
      <div className="text-xs text-gray-500 mt-3 text-center">
        Processed in {forecast_insights.processing_time || 0}s • 
        Data source: {forecastAnalysis.data_source} • 
        Target metric: {forecast_insights.target_metric}
      </div>
    </div>
  );
};

// Add this to your MessageBubble component's content section:

const MessageBubble = ({ message }) => (
  <div className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'} mb-4`}>
    <div className={`flex max-w-[85%] ${message.type === 'user' ? 'flex-row-reverse' : 'flex-row'} gap-3`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        message.type === 'user' 
          ? 'bg-blue-600 text-white' 
          : message.isError 
            ? 'bg-red-100 text-red-600'
            : 'bg-gray-100 text-gray-600'
      }`}>
        {message.type === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>
      
      <div className={`rounded-lg px-4 py-3 ${
        message.type === 'user' 
          ? 'bg-blue-600 text-white' 
          : message.isError 
            ? 'bg-red-50 border border-red-200 text-red-800'
            : 'bg-white border border-gray-200 text-gray-800'
      }`}>
        <div className="whitespace-pre-wrap">{message.content}</div>
        
        {/* Forecast Analysis Display */}
        {message.forecastAnalysis && (
          <ForecastInsightCard forecastAnalysis={message.forecastAnalysis} />
        )}
        
        {/* Existing displays */}
        {message.leadAnalysis && (
          <LeadAnalysisCard leadAnalysis={message.leadAnalysis} />
        )}
        
        {message.rateRecommendation && (
          <MultiPerspectiveCard recommendation={message.rateRecommendation} />
        )}
        
        <div className="text-xs opacity-60 mt-2">
          {message.timestamp.toLocaleTimeString()}
          {message.detectedRole && (
            <span className="ml-2 capitalize">• {message.detectedRole} focus</span>
          )}
          {message.extractedParameters?.is_temporal_query && (
            <span className="ml-2">• Forecast query</span>
          )}
        </div>
      </div>
    </div>
  </div>
);

// Update the main component to handle forecast responses:

const HealthcareIntelligenceChatbot = () => {
  // ... existing state and functions ...

  // Update the sendMessage function to handle forecast analysis:
  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    
    const newHistory = [...conversationHistory, 
      { role: 'user', content: userMessage.content }
    ].slice(-8);
    
    setConversationHistory(newHistory);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.content,
          user_role: selectedRole !== 'general' ? selectedRole : null,
          conversation_history: newHistory
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: data.response,
        timestamp: new Date(),
        rateRecommendation: data.rate_recommendation,
        vendorInfo: data.vendor_info,
        leadAnalysis: data.lead_analysis,
        forecastAnalysis: data.forecast_analysis, // New forecast data
        extractedParameters: data.extracted_parameters,
        detectedRole: data.user_role_detected
      };

      setMessages(prev => [...prev, botMessage]);
      
      setConversationHistory(prev => [...prev, 
        { role: 'assistant', content: data.response }
      ].slice(-8));

    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: 'Sorry, I encountered an error processing your request. Please try again or check your connection.',
        timestamp: new Date(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Update the placeholder text to include forecast examples:
  return (
    <div className="flex flex-col h-[700px] bg-gray-50 rounded-lg border border-gray-200">
      {/* ... existing header and messages sections ... */}

      {/* Updated Input */}
      <div className="p-4 bg-white border-t border-gray-200 rounded-b-lg">
        <div className="flex gap-3">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about current rates, future forecasts, leads, or opportunities... (e.g., 'What will ICU rates be next quarter?' or 'Show me best opportunities in Texas')"
            className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows="1"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!inputValue.trim() || isLoading}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default HealthcareIntelligenceChatbot;

// Example forecast queries to test:
/*
"What will ICU rates be in California next quarter?"
"Should I lock in OR rates now or wait 6 months?"
"Rate outlook for ED positions in 2025"
"Forecast trends for Med-Surg in Texas"
"Will bill rates increase next year?"
"Market prediction for nursing rates"
*/
