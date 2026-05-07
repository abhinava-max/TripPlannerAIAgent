import asyncio
from typing import Any, Awaitable, Callable

from .api_clients import (
    get_flight_data,
    get_geoapify_places_by_city,
    get_weather,
    search_hotels,
)
from .config import settings
from .schemas import TripGenerateRequest


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()

        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        return loop.run_until_complete(coro)

    except RuntimeError:
        return asyncio.run(coro)


def compact_place(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties", {})

    return {
        "name": props.get("name") or props.get("formatted"),
        "address": props.get("address_line2") or props.get("formatted"),
        "categories": props.get("categories", [])[:3],
        "distance_m": props.get("distance"),
    }


def compact_weather(data: dict[str, Any], days: int) -> list[dict[str, Any]]:
    forecast = []

    for item in data.get("list", [])[: min(days * 2, 10)]:
        forecast.append({
            "date_time": item.get("dt_txt"),
            "temp_c": item.get("main", {}).get("temp"),
            "condition": item.get("weather", [{}])[0].get("description"),
            "rain_3h_mm": item.get("rain", {}).get("3h", 0),
        })

    return forecast


def compact_flights(data: dict[str, Any]) -> dict[str, Any]:
    departures = []
    arrivals = []

    for flight in data.get("departures", [])[:3]:
        departures.append({
            "airline": flight.get("airline", {}).get("name"),
            "flight_number": flight.get("number"),
            "status": flight.get("status"),
            "departure_time": flight.get("departure", {}).get("scheduledTime", {}).get("local"),
            "arrival_airport": flight.get("arrival", {}).get("airport", {}).get("name"),
        })

    for flight in data.get("arrivals", [])[:3]:
        arrivals.append({
            "airline": flight.get("airline", {}).get("name"),
            "flight_number": flight.get("number"),
            "status": flight.get("status"),
            "arrival_time": flight.get("arrival", {}).get("scheduledTime", {}).get("local"),
            "departure_airport": flight.get("departure", {}).get("airport", {}).get("name"),
        })

    return {
        "departures": departures,
        "arrivals": arrivals,
    }


async def call_with_retry(
    name: str,
    call: Callable[[], Awaitable[Any]],
    warnings: list[str],
):
    attempts = max(settings.AGENT_TOOL_RETRIES + 1, 1)

    for attempt in range(attempts):
        try:
            if settings.AGENT_TOOL_DELAY_SECONDS > 0:
                await asyncio.sleep(settings.AGENT_TOOL_DELAY_SECONDS)

            return await call()

        except Exception as exc:
            if attempt == attempts - 1:
                warnings.append(f"{name} tool failed: {str(exc)}")
            else:
                await asyncio.sleep(settings.AGENT_TOOL_DELAY_SECONDS)

    return None


async def build_agent_context_async(request: TripGenerateRequest, days: int) -> dict[str, Any]:
    warnings: list[str] = []
    context_used: list[str] = []
    context: dict[str, Any] = {
        "destination": request.destination,
        "source": request.source,
        "interests": request.interests,
        "currency": request.currency,
    }

    weather = await call_with_retry(
        "weather",
        lambda: get_weather(request.destination, min(days, 5)),
        warnings,
    )
    if weather:
        context["weather"] = compact_weather(weather, days)
        context_used.append("weather")

    attractions = await call_with_retry(
        "attractions",
        lambda: get_geoapify_places_by_city(
            request.destination,
            "tourism.sights,tourism.attraction,entertainment.museum",
            radius=10000,
            limit=8,
        ),
        warnings,
    )
    if attractions:
        context["attractions"] = [
            compact_place(feature)
            for feature in attractions.get("features", [])[:8]
        ]
        context_used.append("attractions")

    restaurants = await call_with_retry(
        "restaurants",
        lambda: get_geoapify_places_by_city(
            request.destination,
            "catering.restaurant,catering.cafe,catering.fast_food",
            radius=10000,
            limit=6,
        ),
        warnings,
    )
    if restaurants:
        context["restaurants"] = [
            compact_place(feature)
            for feature in restaurants.get("features", [])[:6]
        ]
        context_used.append("restaurants")

    hotels = await call_with_retry(
        "hotels",
        lambda: search_hotels(request.destination),
        warnings,
    )
    if hotels:
        context["hotels"] = [
            compact_place(feature)
            for feature in hotels.get("features", [])[:6]
        ]
        context["hotel_price_note"] = "Geoapify provides hotel/place data, not guaranteed live booking prices."
        context_used.append("hotels")

    if request.travel_mode in {"flight", "any"} and request.destination_airport_code:
        flights = await call_with_retry(
            "flights",
            lambda: get_flight_data(request.destination_airport_code.upper()),
            warnings,
        )
        if flights:
            context["destination_airport_flights"] = compact_flights(flights)
            context_used.append("flights")

    return {
        "context": context,
        "context_used": context_used,
        "warnings": warnings,
    }


def build_agent_context(request: TripGenerateRequest, days: int) -> dict[str, Any]:
    return run_async(build_agent_context_async(request, days))
