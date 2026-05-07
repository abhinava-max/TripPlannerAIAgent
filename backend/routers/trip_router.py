from datetime import datetime
import json
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException

from ..agent_context import build_agent_context
from ..budget_planner import (
    calculate_trip_budget,
    calculate_trip_budget_from_assumptions,
    get_currency_symbol,
)
from ..config import settings
from ..schemas import (
    BookingLinksResponse,
    TripGenerateRequest,
    TripGenerateResponse,
    TripPromptRequest,
)
from ..trip_agent import (
    estimate_agent_budget_assumptions,
    normalize_trip_response,
    parse_trip_prompt,
    run_trip_agent_json_with_day_count,
)


router = APIRouter(
    prefix="/trip",
    tags=["Trip Generation"]
)


def calculate_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    return max((end - start).days + 1, 1)


def normalize_estimate_mode(mode: str | None) -> str:
    return "agent" if (mode or "").strip().lower() == "agent" else "quick"


def apply_prompt_options(trip_request: TripGenerateRequest, prompt_request: TripPromptRequest):
    trip_request.estimate_mode = normalize_estimate_mode(prompt_request.estimate_mode)

    return trip_request


def parse_prompt_request(prompt_request: TripPromptRequest) -> TripGenerateRequest:
    mode = normalize_estimate_mode(prompt_request.estimate_mode)

    return parse_trip_prompt(prompt_request.prompt, estimate_mode=mode)


def build_trip_generation_prompt(request: TripGenerateRequest) -> str:
    days = calculate_days(request.start_date, request.end_date)
    budget_estimate = calculate_trip_budget(
        budget=request.budget,
        people=request.people,
        days=days,
        travel_mode=request.travel_mode,
        stay_type=request.stay_type,
        currency=request.currency,
    )
    currency_symbol = get_currency_symbol(request.currency)

    interests_text = ", ".join(request.interests or [])

    return f"""
Create a realistic day-wise trip plan.

Trip Details:
Source: {request.source}
Destination: {request.destination}
Start Date: {request.start_date}
End Date: {request.end_date}
Total Days: {days}
Budget: {currency_symbol}{request.budget} {budget_estimate["currency"]}
People: {request.people}
Currency: {budget_estimate["currency"]}
Travel Mode: {request.travel_mode}
Stay Type: {request.stay_type}
Interests: {interests_text if interests_text else "general sightseeing"}

Use reasonable travel-planning assumptions.
Do not claim live prices, live hotel availability, or live flight data.
Mention that costs are estimates when needed.
Use only {budget_estimate["currency"]} for every monetary amount in the response.
Do not use another currency symbol in day plans, notes, travel options, stay options, or tips.

Phase 7 Budget Planner:
- Use this exact budget estimate. Do not change these numbers:
  travel: {budget_estimate["travel"]}
  stay: {budget_estimate["stay"]}
  food: {budget_estimate["food"]}
  local_transport: {budget_estimate["local_transport"]}
  activities: {budget_estimate["activities"]}
  buffer: {budget_estimate["buffer"]}
  total: {budget_estimate["total"]}
  fits_budget: {str(budget_estimate["fits_budget"]).lower()}

Phase 8 Day-wise Itinerary:
- Create exactly {days} day-wise plan items.
- Each day must include morning, afternoon, evening, food_suggestion, travel_notes, and estimated_cost.
- Keep activities geographically practical for the day.

Return only valid JSON in the required format.
"""


def build_agent_trip_generation_prompt(
    request: TripGenerateRequest,
    days: int,
    budget_estimate: dict,
    agent_context: dict,
    assumption_notes: list[str],
):
    currency_symbol = get_currency_symbol(budget_estimate["currency"])
    interests_text = ", ".join(request.interests or [])
    context_text = json.dumps(agent_context, ensure_ascii=True, indent=2)[:7000]
    notes_text = "; ".join(str(note) for note in assumption_notes[:4])

    return f"""
Create a realistic day-wise trip plan using compact live/context data where available.

Trip Details:
Source: {request.source}
Destination: {request.destination}
Start Date: {request.start_date}
End Date: {request.end_date}
Total Days: {days}
Budget: {currency_symbol}{request.budget} {budget_estimate["currency"]}
People: {request.people}
Currency: {budget_estimate["currency"]}
Travel Mode: {request.travel_mode}
Stay Type: {request.stay_type}
Interests: {interests_text if interests_text else "general sightseeing"}
Estimate Mode: agent

Compact tool context:
{context_text}

Budget assumptions note:
{notes_text or "Context-aware estimates were used where exact live prices were unavailable."}

Use this exact Python-calculated budget. Do not change these numbers:
  travel: {budget_estimate["travel"]}
  stay: {budget_estimate["stay"]}
  food: {budget_estimate["food"]}
  local_transport: {budget_estimate["local_transport"]}
  activities: {budget_estimate["activities"]}
  buffer: {budget_estimate["buffer"]}
  total: {budget_estimate["total"]}
  fits_budget: {str(budget_estimate["fits_budget"]).lower()}

Rules:
- Create exactly {days} day-wise plan items.
- Prefer specific places, areas, restaurants, weather notes, and hotel areas from compact tool context.
- Do not claim guaranteed live prices or availability.
- Clearly mention when costs are estimates.
- Use only {budget_estimate["currency"]} for monetary amounts.
- Keep activities geographically practical for the day.

Return only valid JSON in the required format.
"""


def quick_assumptions_from_budget(budget_estimate: dict, people: int, days: int):
    nights = max(days - 1, 1)

    return {
        "currency": budget_estimate["currency"],
        "travel_per_person": int(budget_estimate["travel"] / max(people, 1)),
        "stay_per_night": int(budget_estimate["stay"] / nights),
        "food_per_person_per_day": int(budget_estimate["food"] / max(people * days, 1)),
        "local_transport_per_day": int(budget_estimate["local_transport"] / max(days, 1)),
        "activities_per_person_per_day": int(budget_estimate["activities"] / max(people * days, 1)),
        "buffer_percent": 10,
        "confidence": "low",
        "notes": ["Fallback quick estimate assumptions were used because agent assumptions failed."],
    }


def generate_quick_trip_plan(request: TripGenerateRequest):
    days = calculate_days(request.start_date, request.end_date)
    budget_estimate = calculate_trip_budget(
        budget=request.budget,
        people=request.people,
        days=days,
        travel_mode=request.travel_mode,
        stay_type=request.stay_type,
        currency=request.currency,
    )
    user_prompt = build_trip_generation_prompt(request)
    result = run_trip_agent_json_with_day_count(user_prompt, days)
    result = normalize_trip_response(result, request.budget, budget_estimate, expected_days=days)
    result["estimate_mode"] = "quick"
    result.setdefault("context_used", [])
    result.setdefault("warnings", [])

    return result


def generate_agent_trip_plan(request: TripGenerateRequest):
    days = calculate_days(request.start_date, request.end_date)
    quick_estimate = calculate_trip_budget(
        budget=request.budget,
        people=request.people,
        days=days,
        travel_mode=request.travel_mode,
        stay_type=request.stay_type,
        currency=request.currency,
    )
    agent_context_bundle = build_agent_context(request, days)
    agent_context = agent_context_bundle["context"]
    warnings = agent_context_bundle["warnings"]

    try:
        assumptions = estimate_agent_budget_assumptions(
            request=request,
            days=days,
            quick_estimate=quick_estimate,
            agent_context=agent_context,
        )
    except Exception as exc:
        warnings.append(f"Agent budget assumption step failed: {str(exc)}")
        assumptions = quick_assumptions_from_budget(quick_estimate, request.people, days)

    budget_estimate = calculate_trip_budget_from_assumptions(
        budget=request.budget,
        people=request.people,
        days=days,
        currency=request.currency,
        assumptions=assumptions,
    )
    user_prompt = build_agent_trip_generation_prompt(
        request=request,
        days=days,
        budget_estimate=budget_estimate,
        agent_context=agent_context,
        assumption_notes=assumptions.get("notes", []),
    )
    result = run_trip_agent_json_with_day_count(
        user_prompt,
        expected_days=days,
        delay_seconds=settings.AGENT_TOOL_DELAY_SECONDS,
    )
    result = normalize_trip_response(result, request.budget, budget_estimate, expected_days=days)
    result["estimate_mode"] = "agent"
    result["context_used"] = agent_context_bundle["context_used"]
    result["warnings"] = warnings

    if assumptions.get("confidence"):
        result.setdefault("tips", []).append(
            f"Agent estimate confidence: {assumptions['confidence']}."
        )

    if warnings:
        result.setdefault("tips", []).append(
            "Some live context tools failed, so parts of this plan may use fallback estimates."
        )

    return result


def build_booking_links(request: TripGenerateRequest):
    destination = request.destination
    source = request.source
    date_range = f"{request.start_date} to {request.end_date}"
    interests_text = " ".join(request.interests or [])

    destination_query = quote_plus(destination)
    source_query = quote_plus(source)
    attraction_query = quote_plus(f"top attractions {destination} {interests_text}".strip())
    restaurant_query = quote_plus(f"best food restaurants in {destination}")
    activities_query = quote_plus(f"things to do in {destination} {interests_text}".strip())
    booking_query = quote_plus(f"{request.stay_type} hotels {destination} {request.start_date} {request.end_date}")
    flight_query = quote_plus(f"flights from {source} to {destination} {request.start_date}")
    train_query = quote_plus(f"trains from {source} to {destination} {request.start_date}")
    bus_query = quote_plus(f"bus from {source} to {destination} {request.start_date}")

    links = [
        {
            "label": f"{destination} on Google Maps",
            "type": "location",
            "url": f"https://www.google.com/maps/search/?api=1&query={destination_query}",
            "note": "Open destination location and nearby places."
        },
        {
            "label": f"Route: {source} to {destination}",
            "type": "route",
            "url": f"https://www.google.com/maps/dir/?api=1&origin={source_query}&destination={destination_query}",
            "note": "Use for driving/local route planning."
        },
        {
            "label": "Hotel Search",
            "type": "stay",
            "url": f"https://www.google.com/travel/hotels/{destination_query}?q={booking_query}",
            "note": "Compare hotel options and availability."
        },
        {
            "label": "Booking.com Hotel Search",
            "type": "stay",
            "url": f"https://www.booking.com/searchresults.html?ss={destination_query}&checkin={request.start_date}&checkout={request.end_date}&group_adults={request.people}",
            "note": "Direct accommodation booking search."
        },
        {
            "label": "Attractions Search",
            "type": "activity",
            "url": f"https://www.google.com/search?q={attraction_query}",
            "note": "Find tourist attractions and activity ideas."
        },
        {
            "label": "Activities and Tours",
            "type": "activity",
            "url": f"https://www.google.com/search?q={activities_query}+tours+booking",
            "note": "Search guided tours, tickets, and activities."
        },
        {
            "label": "Restaurants and Food",
            "type": "food",
            "url": f"https://www.google.com/maps/search/{restaurant_query}",
            "note": "Find restaurants near the destination."
        },
    ]

    if request.travel_mode in {"flight", "any"}:
        links.append({
            "label": "Flight Search",
            "type": "travel",
            "url": f"https://www.google.com/travel/flights?q={flight_query}",
            "note": "Compare flight options. Prices are external and live."
        })

    if request.travel_mode in {"train", "any"}:
        links.append({
            "label": "Train Search",
            "type": "travel",
            "url": f"https://www.google.com/search?q={train_query}",
            "note": "Search train availability and booking options."
        })

    if request.travel_mode in {"bus", "any"}:
        links.append({
            "label": "Bus Search",
            "type": "travel",
            "url": f"https://www.google.com/search?q={bus_query}",
            "note": "Search bus availability and booking options."
        })

    return {
        "source": source,
        "destination": destination,
        "date_range": date_range,
        "links": links
    }


def raise_trip_generation_error(exc: Exception):
    detail = str(exc)

    if "Request too large" in detail or "tokens per minute" in detail or "Error code: 413" in detail:
        raise HTTPException(
            status_code=413,
            detail="Trip generation request became too large for the current Groq model limit. Try fewer days, fewer interests, or retry after reducing tool context."
        ) from exc

    raise HTTPException(status_code=500, detail=detail) from exc


@router.post("/generate", response_model=TripGenerateResponse)
def generate_trip_plan(request: TripGenerateRequest):
    try:
        request.estimate_mode = normalize_estimate_mode(request.estimate_mode)

        if request.estimate_mode == "agent":
            return generate_agent_trip_plan(request)

        return generate_quick_trip_plan(request)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/parse-prompt", response_model=TripGenerateRequest)
def parse_prompt(request: TripPromptRequest):
    try:
        return apply_prompt_options(parse_prompt_request(request), request)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/generate-from-prompt", response_model=TripGenerateResponse)
def generate_trip_plan_from_prompt(request: TripPromptRequest):
    try:
        trip_request = apply_prompt_options(parse_prompt_request(request), request)

        if trip_request.estimate_mode == "agent":
            return generate_agent_trip_plan(trip_request)

        return generate_quick_trip_plan(trip_request)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/booking-links", response_model=BookingLinksResponse)
def get_booking_links(request: TripGenerateRequest):
    try:
        request.estimate_mode = normalize_estimate_mode(request.estimate_mode)

        return build_booking_links(request)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/booking-links-from-prompt", response_model=BookingLinksResponse)
def get_booking_links_from_prompt(request: TripPromptRequest):
    try:
        trip_request = apply_prompt_options(parse_prompt_request(request), request)

        return build_booking_links(trip_request)

    except Exception as e:
        raise_trip_generation_error(e)
