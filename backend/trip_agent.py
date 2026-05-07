import json
import re
from datetime import date, timedelta

from pydantic import ValidationError

from .groq_client import get_llm
from .schemas import TripGenerateRequest


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


def run_trip_agent_json(user_prompt: str):
    response = get_llm().invoke(f"{SYSTEM_PROMPT}\n\n{user_prompt}")

    return extract_json(response.content)


def normalize_trip_response(data: dict, budget: int | None = None, budget_estimate: dict | None = None):
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

    for index, day_plan in enumerate(data.get("day_wise_plan", []), start=1):
        day_plan.setdefault("day", index)
        day_plan.setdefault("title", f"Day {index}")
        day_plan.setdefault("morning", "")
        day_plan.setdefault("afternoon", "")
        day_plan.setdefault("evening", "")
        day_plan.setdefault("food_suggestion", "")
        day_plan.setdefault("travel_notes", "")
        day_plan["estimated_cost"] = int(day_plan.get("estimated_cost") or 0)

    return data


def parse_trip_prompt(prompt: str) -> TripGenerateRequest:
    today = date.today()
    default_start = today + timedelta(days=30)
    default_end = default_start + timedelta(days=3)

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
  "interests": ["string"]
}}

Rules:
- Return only valid JSON. No markdown.
- Today's date is {today.isoformat()}.
- If source is missing, use "Not specified".
- If destination is missing, use "Not specified".
- If dates are missing, use {default_start.isoformat()} to {default_end.isoformat()}.
- If budget is missing, use 0.
- If currency is missing, infer it from the prompt if possible, otherwise use "INR".
- If people count is missing, use 1.
- travel_mode must be one of: flight, train, bus, car, any.
- stay_type must be one of: budget, standard, luxury.
- Convert interests into a short list of lowercase strings.

User request:
{prompt}
"""

    response = get_llm().invoke(parser_prompt)
    parsed = extract_json(response.content)

    try:
        return TripGenerateRequest(**parsed)
    except ValidationError as exc:
        raise ValueError(f"Prompt could not be converted into trip schema: {exc}") from exc
