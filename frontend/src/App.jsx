import { useEffect, useMemo, useRef, useState, memo, useCallback } from 'react'
import { Bot, Loader2, Send, User } from 'lucide-react'
import './App.css'

const API_URL = import.meta.env.VITE_CHATBOT_API_URL || 'http://localhost:8000/chat'

const roleOptions = [
  { value: 'general', label: 'General' },
  { value: 'sales', label: 'Sales' },
  { value: 'recruiter', label: 'Recruiter' },
  { value: 'operations', label: 'Operations' },
  { value: 'finance', label: 'Finance' },
]

const professionOptions = [
  { value: 'all', label: 'All Professions' },
  { value: 'Nursing', label: 'Nursing' },
  { value: 'Allied', label: 'Allied' },
  { value: 'Locum/Tenens', label: 'Locum/Tenens' },
  { value: 'Therapy', label: 'Therapy' },
]

const formatCurrency = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

const ForecastInsightCard = memo(({ analysis }) => {
  if (!analysis?.forecast_insights) return null

  const {
    forecast_insights: insights,
    national_forecast_insights: nationalInsights,
    business_recommendations: recommendations = {},
    location,
    specialty,
    dual_forecast: hasDualForecast = false
  } = analysis

  // Memoize expensive computations to avoid recalculating on every render
  const orderedForecastEntries = useMemo(() => {
    const forecastEntries = Object.entries(insights.forecasts || {})
    const periodOrder = { '4_weeks': 1, '12_weeks': 2, '26_weeks': 3, '52_weeks': 4 }
    return [...forecastEntries].sort(
      ([a], [b]) => (periodOrder[a] || 99) - (periodOrder[b] || 99),
    )
  }, [insights.forecasts])

  const growthEntries = useMemo(() =>
    Object.entries(insights.growth_rates || {}),
    [insights.growth_rates]
  )

  return (
    <div className="forecast-card">
      <header>
        <div>
          <h4>Forecast Analysis {hasDualForecast && '(State + National)'}</h4>
          <p>
            {specialty || 'Market'} &bull; {location || 'National'} &bull; Model:{' '}
            {insights.model_used || 'Unknown'}
            {hasDualForecast && ' &bull; Limited state data - showing national for comparison'}
          </p>
        </div>
        <span className={`trend ${insights.trend_direction ?? 'stable'}`}>
          {insights.trend_direction ? insights.trend_direction.toUpperCase() : 'STABLE'}
        </span>
      </header>

      <section className="forecast-stats">
        <div>
          <span>Current</span>
          <strong>{formatCurrency(insights.current_value)}</strong>
          <small>{(insights.target_metric || '').replaceAll('_', ' ')}</small>
        </div>
        {orderedForecastEntries.map(([period, value]) => {
          const growthValue = growthEntries.find(([p]) => p === period)?.[1]
          const formattedGrowth =
            typeof growthValue === 'number'
              ? `${growthValue > 0 ? '+' : ''}${growthValue.toFixed(1)}%`
              : '—'
          return (
            <div key={period}>
              <span>{period.replaceAll('_', ' ')}</span>
              <strong>{formatCurrency(value)}</strong>
              <small>{formattedGrowth}</small>
            </div>
          )
        })}
      </section>

      <section className="forecast-insights">
        <div>
          <span>Confidence</span>
          <strong>{(insights.confidence_level || 'unknown').toUpperCase()}</strong>
        </div>
        <div>
          <span>Accuracy (1-MAPE)</span>
          <strong>{insights.accuracy_mape ? `${(100 - insights.accuracy_mape).toFixed(1)}%` : '—'}</strong>
        </div>
        <div>
          <span>Processing Time</span>
          <strong>{insights.processing_time ? `${insights.processing_time}s` : '—'}</strong>
        </div>
      </section>

      {hasDualForecast && nationalInsights && (
        <>
          <section className="forecast-divider">
            <h5>National Forecast (For Comparison)</h5>
          </section>

          <section className="forecast-stats">
            <div>
              <span>Current (National)</span>
              <strong>{formatCurrency(nationalInsights.current_value)}</strong>
              <small>{(nationalInsights.target_metric || '').replaceAll('_', ' ')}</small>
            </div>
            {Object.entries(nationalInsights.forecasts || {})
              .sort(([a], [b]) => {
                const order = { '4_weeks': 1, '12_weeks': 2, '26_weeks': 3, '52_weeks': 4 }
                return (order[a] || 99) - (order[b] || 99)
              })
              .map(([period, value]) => {
                const growthValue = nationalInsights.growth_rates?.[period]
                const formattedGrowth =
                  typeof growthValue === 'number'
                    ? `${growthValue > 0 ? '+' : ''}${growthValue.toFixed(1)}%`
                    : '—'
                return (
                  <div key={`national-${period}`}>
                    <span>{period.replaceAll('_', ' ')}</span>
                    <strong>{formatCurrency(value)}</strong>
                    <small>{formattedGrowth}</small>
                  </div>
                )
              })}
          </section>
        </>
      )}

      {Object.keys(recommendations).length > 0 && (
        <section className="forecast-recommendations">
          <h5>Strategic Recommendations</h5>
          <div className="recommendation-columns">
            {Object.entries(recommendations).map(([role, items]) =>
              items?.length ? (
                <div key={role}>
                  <h6>{role.charAt(0).toUpperCase() + role.slice(1)}</h6>
                  <ul>
                    {items.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null,
            )}
          </div>
        </section>
      )}
    </div>
  )
})

const MessageBubble = memo(({ message }) => {
  const Icon = message.type === 'user' ? User : Bot

  return (
    <div className={`message-row ${message.type}`}>
      <div className="avatar">
        <Icon size={18} />
      </div>
      <div className={`message-bubble ${message.type}`}>
        <div className="message-text">{message.content}</div>
        {message.forecastAnalysis && <ForecastInsightCard analysis={message.forecastAnalysis} />}
        {message.error && <div className="message-error">{message.error}</div>}
        <div className="message-meta">
          <span>{message.timestamp.toLocaleTimeString()}</span>
          {message.detectedRole && <span>• {message.detectedRole} focus</span>}
          {message.extractedParameters?.is_temporal_query && <span>• Forecast query</span>}
        </div>
      </div>
    </div>
  )
})

function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      content:
        'Hi! I\'m **AVA** (AI Virtual Assistant), your healthcare staffing intelligence expert.\n\n' +
        'I can help you with:\n\n' +
        '• **Rate Insights** - "What\'s the bill rate for ICU nurses in Texas?"\n' +
        '• **Market Forecasts** - "Will CRNA rates increase in California next quarter?"\n' +
        '• **High-Paying Jobs** - "Show me the highest paying RN positions in Ohio"\n' +
        '• **Client Analysis** - "Which facilities pay the best for ED nurses nationwide?"\n' +
        '• **Rate Comparisons** - "Compare ICU rates in New York vs Florida"\n\n' +
        'What would you like to know?',
      timestamp: new Date(),
    },
  ])
  const [inputValue, setInputValue] = useState('')
  const [selectedRole, setSelectedRole] = useState('general')
  const [selectedProfession, setSelectedProfession] = useState('all')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationHistory, setConversationHistory] = useState([])
  const [errorBanner, setErrorBanner] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const placeholder = useMemo(
    () =>
      'Ask anything like "What will ICU rates be next quarter?" or "Show me the best opportunities in Texas."',
    [],
  )

  const sendMessage = useCallback(async () => {
    if (!inputValue.trim() || isLoading) return

    const trimmed = inputValue.trim()
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: trimmed,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)
    setErrorBanner('')

    const updatedHistory = [...conversationHistory, { role: 'user', content: trimmed }].slice(-8)
    setConversationHistory(updatedHistory)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmed,
          user_role: selectedRole !== 'general' ? selectedRole : null,
          profession: selectedProfession !== 'all' ? selectedProfession : null,
          conversation_history: updatedHistory,
        }),
      })

      if (!response.ok) {
        throw new Error(`API responded with status ${response.status}`)
      }

      const data = await response.json()

      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: data.response || 'I do not have an answer for that yet.',
        timestamp: new Date(),
        forecastAnalysis: data.forecast_analysis,
        extractedParameters: data.extracted_parameters,
        detectedRole: data.user_role_detected,
      }

      setMessages((prev) => [...prev, botMessage])
      setConversationHistory((prev) =>
        [...prev, { role: 'assistant', content: botMessage.content }].slice(-8),
      )
    } catch (error) {
      console.error(error)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          type: 'bot',
          content: 'Sorry, I could not process that request.',
          error: error.message,
          timestamp: new Date(),
        },
      ])
      setErrorBanner('Unable to reach the chatbot API. Confirm the backend is running on port 8000.')
    } finally {
      setIsLoading(false)
    }
  }, [inputValue, isLoading, selectedRole, selectedProfession, conversationHistory])

  const handleKeyDown = useCallback((event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }, [sendMessage])

  return (
    <div className="app">
      <header className="hero">
        <h1>AVA - AI Virtual Assistant</h1>
        <p>
          Your healthcare staffing intelligence expert. Real-time market insights, future rate forecasts, and strategic recommendations tailored to your role.
        </p>
        <div className="controls">
          <label htmlFor="role-select">Perspective</label>
          <select
            id="role-select"
            value={selectedRole}
            onChange={(event) => setSelectedRole(event.target.value)}
          >
            {roleOptions.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>

          <label htmlFor="profession-select">Profession</label>
          <select
            id="profession-select"
            value={selectedProfession}
            onChange={(event) => setSelectedProfession(event.target.value)}
          >
            {professionOptions.map((profession) => (
              <option key={profession.value} value={profession.value}>
                {profession.label}
              </option>
            ))}
          </select>
        </div>
        {errorBanner && <div className="error-banner">{errorBanner}</div>}
      </header>

      <main className="chat-shell">
        <div className="chat-window">
          <div className="message-list">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="message-row bot">
                <div className="avatar">
                  <Bot size={18} />
                </div>
                <div className="message-bubble bot loading">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="composer">
            <textarea
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={isLoading}
              rows={2}
            />
            <button onClick={sendMessage} disabled={isLoading || !inputValue.trim()}>
              {isLoading ? (
                <>
                  <Loader2 className="spin" size={18} /> Sending…
                </>
              ) : (
                <>
                  <Send size={16} /> Send
                </>
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
