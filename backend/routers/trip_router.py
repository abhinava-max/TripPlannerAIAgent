from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException

from ..budget_planner import calculate_trip_budget, get_currency_symbol
from ..schemas import (
    BookingLinksResponse,
    TripGenerateRequest,
    TripGenerateResponse,
    TripPromptRequest,
)
from ..trip_agent import normalize_trip_response, parse_trip_prompt, run_trip_agent_json


router = APIRouter(
    prefix="/trip",
    tags=["Trip Generation"]
)


def calculate_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    return max((end - start).days + 1, 1)


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
        result = run_trip_agent_json(user_prompt)

        return normalize_trip_response(result, request.budget, budget_estimate)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/parse-prompt", response_model=TripGenerateRequest)
def parse_prompt(request: TripPromptRequest):
    try:
        return parse_trip_prompt(request.prompt)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/generate-from-prompt", response_model=TripGenerateResponse)
def generate_trip_plan_from_prompt(request: TripPromptRequest):
    try:
        trip_request = parse_trip_prompt(request.prompt)
        days = calculate_days(trip_request.start_date, trip_request.end_date)
        budget_estimate = calculate_trip_budget(
            budget=trip_request.budget,
            people=trip_request.people,
            days=days,
            travel_mode=trip_request.travel_mode,
            stay_type=trip_request.stay_type,
            currency=trip_request.currency,
        )
        user_prompt = build_trip_generation_prompt(trip_request)
        result = run_trip_agent_json(user_prompt)

        return normalize_trip_response(result, trip_request.budget, budget_estimate)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/booking-links", response_model=BookingLinksResponse)
def get_booking_links(request: TripGenerateRequest):
    try:
        return build_booking_links(request)

    except Exception as e:
        raise_trip_generation_error(e)


@router.post("/booking-links-from-prompt", response_model=BookingLinksResponse)
def get_booking_links_from_prompt(request: TripPromptRequest):
    try:
        trip_request = parse_trip_prompt(request.prompt)

        return build_booking_links(trip_request)

    except Exception as e:
        raise_trip_generation_error(e)
