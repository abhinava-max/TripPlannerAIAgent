import json
import re
from time import sleep
from datetime import date, datetime, timedelta

from pydantic import ValidationError

from .config import settings
from .groq_client import get_llm
from .schemas import TripGenerateRequest


MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


SYSTEM_PROMPT = """
You are a Trip Planner AI Agent.

Use tools whenever useful:
- weather_tool for weather
- places_tool for attractions
- hotel_tool for stay suggestions
- budget_calculator_tool for budget
- policy_tool for visa, baggage, safety, and travel rules
- flight_tool only if airport code is available

Important:
- Do not invent live prices.
- If price is estimated, clearly mention it.
- Return ONLY valid JSON.
- Do not use markdown.
- Do not wrap JSON in ```.

Required JSON format:
{
  "summary": "string",
  "day_wise_plan": [
    {
      "day": 1,
      "title": "string",
      "morning": "string",
      "afternoon": "string",
      "evening": "string",
      "food_suggestion": "string",
      "travel_notes": "string",
      "estimated_cost": 0
    }
  ],
  "estimated_budget": {
    "currency": "INR",
    "travel": 0,
    "stay": 0,
    "food": 0,
    "local_transport": 0,
    "activities": 0,
    "buffer": 0,
    "total": 0,
    "fits_budget": true
  },
  "travel_options": [
    {
      "mode": "string",
      "details": "string",
      "estimated_cost": 0
    }
  ],
  "stay_options": [
    {
      "name": "string",
      "type": "string",
      "location": "string",
      "estimated_price_per_night": 0,
      "note": "string"
    }
  ],
  "tips": ["string"]
}

Budget rules:
- estimated_budget.total must equal travel + stay + food + local_transport + activities + buffer.
- day_wise_plan estimated_cost should be the estimated cost for that day.
- Day plans must include practical travel notes such as nearby area grouping, commute suggestion, or pacing warning.
"""


def extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("AI response did not contain valid JSON")

    return json.loads(match.group())


def run_trip_agent_json(user_prompt: str, delay_seconds: float = 0):
    if delay_seconds > 0:
        sleep(delay_seconds)

    response = get_llm().invoke(f"{SYSTEM_PROMPT}\n\n{user_prompt}")

    return extract_json(response.content)


def run_trip_agent_json_with_day_count(
    user_prompt: str,
    expected_days: int,
    delay_seconds: float = 0,
):
    result = run_trip_agent_json(user_prompt, delay_seconds=delay_seconds)

    if len(result.get("day_wise_plan", [])) == expected_days:
        return result

    correction_prompt = f"""
The previous response did not contain the required number of day-wise items.

Required day_wise_plan length: {expected_days}
Actual day_wise_plan length: {len(result.get("day_wise_plan", []))}

Rewrite the complete response as valid JSON in the required format.
Keep the same trip, budget, travel options, stay options, and tips where possible.
The day_wise_plan array MUST contain exactly {expected_days} items, numbered 1 to {expected_days}.

Original generation prompt:
{user_prompt[:5000]}

Previous invalid JSON:
{json.dumps(result, ensure_ascii=True)[:5000]}
"""

    return run_trip_agent_json(
        correction_prompt,
        delay_seconds=settings.AGENT_TOOL_DELAY_SECONDS,
    )


def estimate_agent_budget_assumptions(
    request: TripGenerateRequest,
    days: int,
    quick_estimate: dict,
    agent_context: dict,
) -> dict:
    context_text = json.dumps(agent_context, ensure_ascii=True, indent=2)[:6000]

    prompt = f"""
You are helping estimate a trip budget from compact travel context.

Return ONLY valid JSON with this exact schema:
{{
  "currency": "{quick_estimate["currency"]}",
  "travel_per_person": 0,
  "stay_per_night": 0,
  "food_per_person_per_day": 0,
  "local_transport_per_day": 0,
  "activities_per_person_per_day": 0,
  "buffer_percent": 10,
  "confidence": "low",
  "notes": ["string"]
}}

Rules:
- Use the same currency as the user: {quick_estimate["currency"]}.
- Use compact context when it helps, but do not claim live hotel or flight prices unless they are present in context.
- If exact prices are not available, create realistic context-aware estimates.
- Keep all numeric fields as plain integers except buffer_percent.
- Use the quick estimate as a fallback anchor, not as a mandatory final value.
- Do not calculate totals. Python will calculate totals.

Trip:
Source: {request.source}
Destination: {request.destination}
Days: {days}
People: {request.people}
Budget: {request.budget} {quick_estimate["currency"]}
Travel Mode: {request.travel_mode}
Stay Type: {request.stay_type}
Interests: {", ".join(request.interests or []) or "general sightseeing"}

Quick estimate anchor:
{json.dumps(quick_estimate, ensure_ascii=True, indent=2)}

Compact tool context:
{context_text}
"""

    if settings.AGENT_TOOL_DELAY_SECONDS > 0:
        sleep(settings.AGENT_TOOL_DELAY_SECONDS)

    response = get_llm().invoke(prompt)
    data = extract_json(response.content)

    return {
        "currency": data.get("currency") or quick_estimate["currency"],
        "travel_per_person": int(data.get("travel_per_person") or 0),
        "stay_per_night": int(data.get("stay_per_night") or 0),
        "food_per_person_per_day": int(data.get("food_per_person_per_day") or 0),
        "local_transport_per_day": int(data.get("local_transport_per_day") or 0),
        "activities_per_person_per_day": int(data.get("activities_per_person_per_day") or 0),
        "buffer_percent": float(data.get("buffer_percent") or 10),
        "confidence": data.get("confidence") or "low",
        "notes": data.get("notes") or [],
    }


def normalize_trip_response(
    data: dict,
    budget: int | None = None,
    budget_estimate: dict | None = None,
    expected_days: int | None = None,
):
    estimated_budget = data.setdefault("estimated_budget", {})

    if budget_estimate:
        estimated_budget.update(budget_estimate)

    estimated_budget["currency"] = estimated_budget.get("currency") or "INR"

    for key in ["travel", "stay", "food", "local_transport", "activities", "buffer"]:
        estimated_budget[key] = int(estimated_budget.get(key) or 0)

    estimated_budget["total"] = (
        estimated_budget["travel"]
        + estimated_budget["stay"]
        + estimated_budget["food"]
        + estimated_budget["local_transport"]
        + estimated_budget["activities"]
        + estimated_budget["buffer"]
    )

    if budget is not None:
        estimated_budget["fits_budget"] = estimated_budget["total"] <= budget
    else:
        estimated_budget["fits_budget"] = bool(estimated_budget.get("fits_budget", True))

    day_wise_plan = data.setdefault("day_wise_plan", [])

    if expected_days is not None:
        if len(day_wise_plan) > expected_days:
            data["day_wise_plan"] = day_wise_plan[:expected_days]
            day_wise_plan = data["day_wise_plan"]

        while len(day_wise_plan) < expected_days:
            next_day = len(day_wise_plan) + 1
            day_wise_plan.append({
                "day": next_day,
                "title": f"Day {next_day}",
                "morning": "Flexible sightseeing based on pace, weather, and local opening hours.",
                "afternoon": "Continue nearby experiences to avoid unnecessary commute time.",
                "evening": "Relax, explore food options nearby, and prepare for the next day.",
                "food_suggestion": "Choose a well-reviewed local restaurant close to your stay.",
                "travel_notes": "This fallback day was added because the AI returned fewer days than requested.",
                "estimated_cost": 0,
            })

    for index, day_plan in enumerate(day_wise_plan, start=1):
        day_plan["day"] = index
        day_plan.setdefault("day", index)
        day_plan.setdefault("title", f"Day {index}")
        day_plan.setdefault("morning", "")
        day_plan.setdefault("afternoon", "")
        day_plan.setdefault("evening", "")
        day_plan.setdefault("food_suggestion", "")
        day_plan.setdefault("travel_notes", "")
        day_plan["estimated_cost"] = int(day_plan.get("estimated_cost") or 0)

    return data


def infer_duration_days(prompt: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\s*(?:day|days)\b", prompt, re.IGNORECASE)

    if not match:
        return None

    days = int(match.group(1))

    return days if 1 <= days <= 30 else None


def infer_month_start(prompt: str, today: date) -> date | None:
    normalized = prompt.lower()
    month = None

    for name, number in MONTHS.items():
        if re.search(rf"\b{name}\b", normalized):
            month = number
            break

    if month is None:
        return None

    year_match = re.search(r"\b(20\d{2})\b", prompt)
    year = int(year_match.group(1)) if year_match else today.year
    start = date(year, month, 4)

    if start < today:
        start = date(year + 1, month, 4)

    return start


def next_month_fourth(today: date) -> date:
    year = today.year
    month = today.month + 1

    if month == 13:
        year += 1
        month = 1

    return date(year, month, 4)


def has_exact_date_hint(prompt: str) -> bool:
    normalized = prompt.lower()

    if re.search(r"\b20\d{2}-\d{1,2}-\d{1,2}\b", normalized):
        return True

    month_names = "|".join(re.escape(name) for name in MONTHS)

    return bool(
        re.search(rf"\b(?:{month_names})\s+\d{{1,2}}\b", normalized)
        or re.search(rf"\b\d{{1,2}}\s+(?:{month_names})\b", normalized)
        or re.search(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", normalized)
    )


def apply_date_defaults(prompt: str, trip_request: TripGenerateRequest) -> TripGenerateRequest:
    duration_days = infer_duration_days(prompt) or 4
    today = date.today()

    if has_exact_date_hint(prompt):
        return trip_request

    month_start = infer_month_start(prompt, today)
    start = month_start or next_month_fourth(today)

    trip_request.start_date = start.isoformat()
    trip_request.end_date = (start + timedelta(days=duration_days - 1)).isoformat()

    return trip_request


def parse_trip_prompt(prompt: str, estimate_mode: str = "quick") -> TripGenerateRequest:
    today = date.today()
    default_start = next_month_fourth(today)
    default_end = default_start + timedelta(days=3)
    normalized_estimate_mode = "agent" if (estimate_mode or "").strip().lower() == "agent" else "quick"

    parser_prompt = f"""
Convert the user's trip request into ONLY this JSON schema:
{{
  "source": "string",
  "destination": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "budget": 0,
  "people": 1,
  "currency": "INR",
  "travel_mode": "any",
  "stay_type": "budget",
  "interests": ["string"],
  "estimate_mode": "{normalized_estimate_mode}",
  "source_airport_code": null,
  "destination_airport_code": null
}}

Rules:
- Return only valid JSON. No markdown.
- Today's date is {today.isoformat()}.
- If source is missing, use "Not specified".
- If destination is missing, use "Not specified".
- If exact dates are missing but a month is mentioned, use the 4th day of that month as start_date.
- If exact dates and month are both missing, use {default_start.isoformat()} as start_date.
- If the user mentions a duration like "7 day" or "7 days", end_date must make the range contain exactly that many days.
- If no duration is mentioned, default to a 4 day trip.
- If budget is missing, use 0.
- If currency is missing, infer it from the prompt if possible, otherwise use "INR".
- If people count is missing, use 1.
- travel_mode must be one of: flight, train, bus, car, any.
- stay_type must be one of: budget, standard, luxury.
- estimate_mode must be exactly "{normalized_estimate_mode}". Do not infer or change it from the user prompt.
- If airport IATA codes are clearly mentioned, extract them. Otherwise use null.
- Convert interests into a short list of lowercase strings.

User request:
{prompt}
"""

    response = get_llm().invoke(parser_prompt)
    parsed = extract_json(response.content)
    parsed["estimate_mode"] = normalized_estimate_mode

    try:
        return apply_date_defaults(prompt, TripGenerateRequest(**parsed))
    except ValidationError as exc:
        raise ValueError(f"Prompt could not be converted into trip schema: {exc}") from exc
