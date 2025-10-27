# Forecasting API Requirements for CRNA Support

## Overview
The chatbot is ready to support CRNA forecasting by aggregating data using the `newSubprofession` field, but the forecasting API needs to be updated to handle this.

## Current Issue
When the chatbot sends CRNA forecast requests, it gets a 500 error: `"Data fetch failed: list index out of range"`

This happens because:
1. CRNA data is spread across multiple specialty name variations
2. The API isn't aggregating them properly
3. Insufficient data points for reliable forecasting

## CRNA Specialty Variations in Database

```
newSpecialty                              | newSubprofession
------------------------------------------|---------------------------------
APRN - CRNA                               | Advanced Practice Registered Nurse
Certified Nurse Anesthetist (CRNA)       | CRNA
CRNA - Certified Registered Nurse Anesthetist | CRNA
```

## Solution: Query by `newSubprofession`

Instead of querying by `newSpecialty`, query by `newSubprofession='CRNA'` to aggregate ALL CRNA records together.

---

## Required API Changes

### 1. Update Input Schema

Add `use_subprofession` parameter to your API's input schema:

```python
# In your InputSchema or request model
class ForecastRequest(BaseModel):
    specialties: List[str]
    states: List[str] = []
    model: str = "prophet"
    target: str = "bill_rate"
    use_subprofession: bool = False  # NEW PARAMETER
```

### 2. Update Database Query Logic

Modify your data fetching function:

```python
def fetch_data(specialty: str, states: List[str], use_subprofession: bool = False):
    """
    Fetch historical data for forecasting

    Args:
        specialty: Specialty name (e.g., "CRNA", "ICU")
        states: List of states (empty = all states)
        use_subprofession: If True, query by newSubprofession field instead of newSpecialty
    """

    if use_subprofession and specialty.upper() == "CRNA":
        # For CRNA, aggregate by subprofession to get all variations
        query = """
            SELECT * FROM assignments
            WHERE newSubprofession = 'CRNA'
        """

        if states and len(states) > 0:
            query += f" AND state IN ({','.join(['?'] * len(states))})"
            params = states
        else:
            # Empty states = national (all states)
            params = []

    else:
        # Regular specialty query
        query = """
            SELECT * FROM assignments
            WHERE newSpecialty LIKE ?
        """
        params = [f"%{specialty}%"]

        if states and len(states) > 0:
            query += f" AND state IN ({','.join(['?'] * len(states))})"
            params.extend(states)

    # Execute query and return results
    return execute_query(query, params)
```

### 3. Handle Empty States Array

Make sure `states=[]` means "all states" not "no data":

```python
def should_filter_by_state(states: List[str]) -> bool:
    """
    Determine if we should filter by specific states

    Returns:
        True if specific states requested
        False if national (all states)
    """
    return states is not None and len(states) > 0

# Usage:
if should_filter_by_state(request.states):
    # Add state filter to query
    query += " WHERE state IN (?)"
else:
    # National query - no state filter (aggregate all states)
    pass
```

---

## Testing

After implementing these changes, test with:

```bash
curl -X POST http://192.168.1.210:8001/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "specialties": ["CRNA"],
    "states": ["CA"],
    "model": "prophet",
    "target": "hourly_pay",
    "use_subprofession": true
  }'
```

Should return forecast data aggregating all CRNA subprofession records in California.

---

## Benefits

1. **More Data Points**: Aggregating by subprofession gives 3x more records
2. **Better Forecasts**: More data = more reliable predictions
3. **National Queries Work**: Enough data for national-level forecasting
4. **Consistent**: All CRNA variations treated the same way

---

## Rollout Plan

1. **Phase 1** (Current): Chatbot sends regular CRNA queries (no `use_subprofession`)
2. **Phase 2**: Update forecasting API to support `use_subprofession` parameter
3. **Phase 3**: Uncomment line 157 in `forecasting_integration.py` to enable the feature
4. **Phase 4**: Test and verify improved forecast quality

---

## Contact

If you need help implementing these changes, the chatbot team can assist!
