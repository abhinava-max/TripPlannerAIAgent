import asyncio
import json
from langchain_core.tools import tool

from .api_clients import (
    get_weather,
    get_exchange_rate,
    geocode_location,
    get_geoapify_places_by_city,
    get_flight_data,
    search_hotels
)
from .policy_vector_store import get_policy_retriever


def run_async(coro):
    """
    Allows async API client functions to run inside normal LangChain tools.
    """
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


def compact_json(data, max_chars: int = 1800):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text[:max_chars]


@tool
def weather_tool(city: str, days: int = 3) -> str:
    """
    Get weather forecast for a destination city.
    Use this when the trip plan needs weather, temperature, rain, or climate-aware itinerary planning.
    """
    try:
        data = run_async(get_weather(city=city, days=days))

        cleaned = []

        for item in data.get("list", [])[: min(days * 4, 16)]:
            cleaned.append({
                "date_time": item.get("dt_txt"),
                "temp_c": item.get("main", {}).get("temp"),
                "condition": item.get("weather", [{}])[0].get("description"),
                "rain": item.get("rain", {}).get("3h", 0),
            })

        return compact_json({
            "city": city,
            "forecast": cleaned
        })

    except Exception as e:
        return f"Weather tool failed: {str(e)}"


@tool
def exchange_rate_tool(base_currency: str = "INR") -> str:
    """
    Get latest currency exchange rates.
    Use this for international trip budget conversion.
    """
    try:
        data = run_async(get_exchange_rate(base_currency=base_currency))

        rates = data.get("conversion_rates", {})

        useful_rates = {
            "USD": rates.get("USD"),
            "EUR": rates.get("EUR"),
            "GBP": rates.get("GBP"),
            "AED": rates.get("AED"),
            "THB": rates.get("THB"),
            "SGD": rates.get("SGD"),
            "INR": rates.get("INR")
        }

        return compact_json({
            "base_currency": base_currency,
            "rates": useful_rates
        })

    except Exception as e:
        return f"Exchange rate tool failed: {str(e)}"


@tool
def geocode_tool(location: str) -> str:
    """
    Get latitude and longitude for a city or destination.
    Use this before searching nearby places if coordinates are needed.
    """
    try:
        data = run_async(geocode_location(location))

        features = data.get("features", [])

        if not features:
            return f"No coordinates found for {location}"

        props = features[0].get("properties", {})

        return compact_json({
            "location": location,
            "formatted": props.get("formatted"),
            "lat": props.get("lat"),
            "lon": props.get("lon"),
            "country": props.get("country"),
            "city": props.get("city")
        })

    except Exception as e:
        return f"Geocode tool failed: {str(e)}"


@tool
def places_tool(city: str, category: str = "tourism.sights") -> str:
    """
    Search tourist places, attractions, restaurants, beaches, cafes, museums, or local places in a city.
    Categories examples:
    tourism.sights
    catering.restaurant
    catering.cafe
    entertainment
    beach
    accommodation.hotel
    """
    try:
        data = run_async(
            get_geoapify_places_by_city(
                city=city,
                category=category,
                radius=10000,
                limit=8
            )
        )

        places = []

        for feature in data.get("features", []):
            props = feature.get("properties", {})

            places.append({
                "name": props.get("name"),
                "address": props.get("address_line2"),
                "categories": props.get("categories", [])[:3],
                "distance": props.get("distance")
            })

        return compact_json({
            "city": city,
            "category": category,
            "places": places
        })

    except Exception as e:
        return f"Places tool failed: {str(e)}"


@tool
def hotel_tool(city: str, stay_preference: str = "budget") -> str:
    """
    Search hotels and guest houses in a city.
    Use this for stay suggestions.
    This returns location-based hotel data, not guaranteed live hotel prices.
    """
    try:
        data = run_async(search_hotels(city))

        hotels = []

        for feature in data.get("features", []):
            props = feature.get("properties", {})

            hotels.append({
                "name": props.get("name"),
                "address": props.get("address_line2"),
                "categories": props.get("categories", [])[:3],
                "distance": props.get("distance"),
                "website": props.get("website")
            })

        return compact_json({
            "city": city,
            "stay_preference": stay_preference,
            "note": "Hotel prices may be estimated because Geoapify does not provide live booking prices.",
            "hotels": hotels[:6]
        })

    except Exception as e:
        return f"Hotel tool failed: {str(e)}"


@tool
def flight_tool(airport_code: str) -> str:
    """
    Get airport flight data using airport IATA code.
    Use this when user provides source or destination airport code.
    Example airport codes: AMD, BOM, DEL, GOI, DXB, BKK.
    """
    try:
        data = run_async(get_flight_data(airport_code.upper()))

        departures = data.get("departures", [])[:4]
        arrivals = data.get("arrivals", [])[:4]

        cleaned_departures = []
        cleaned_arrivals = []

        for flight in departures:
            cleaned_departures.append({
                "airline": flight.get("airline", {}).get("name"),
                "flight_number": flight.get("number"),
                "status": flight.get("status"),
                "departure_time": flight.get("departure", {}).get("scheduledTime", {}).get("local"),
                "arrival_airport": flight.get("arrival", {}).get("airport", {}).get("name")
            })

        for flight in arrivals:
            cleaned_arrivals.append({
                "airline": flight.get("airline", {}).get("name"),
                "flight_number": flight.get("number"),
                "status": flight.get("status"),
                "arrival_time": flight.get("arrival", {}).get("scheduledTime", {}).get("local"),
                "departure_airport": flight.get("departure", {}).get("airport", {}).get("name")
            })

        return compact_json({
            "airport_code": airport_code.upper(),
            "departures": cleaned_departures,
            "arrivals": cleaned_arrivals
        })

    except Exception as e:
        return f"Flight tool failed: {str(e)}"


@tool
def policy_tool(question: str) -> str:
    """
    Search ChromaDB policy documents for visa rules, travel restrictions, baggage rules,
    cancellation policies, country travel rules, and safety guidelines.
    """
    try:
        retriever = get_policy_retriever(k=2)
        docs = retriever.invoke(question)

        if not docs:
            return "No relevant policy documents found."

        results = []

        for doc in docs:
            results.append({
                "source": doc.metadata.get("source"),
                "page": doc.metadata.get("page"),
                "content": doc.page_content[:500]
            })

        return compact_json({
            "question": question,
            "retrieved_policy_context": results
        })

    except Exception as e:
        return f"Policy tool failed: {str(e)}"


@tool
def budget_calculator_tool(
    people: int,
    days: int,
    budget: int,
    stay_preference: str = "budget",
    travel_preference: str = "any"
) -> str:
    """
    Estimate trip budget using simple local rules.
    Use this for budget breakdown and checking whether the trip fits user's budget.
    """

    if stay_preference == "budget":
        stay_per_night = 1500
    elif stay_preference == "standard":
        stay_per_night = 3500
    else:
        stay_per_night = 8000

    if travel_preference == "flight":
        travel_per_person = 7000
    elif travel_preference == "train":
        travel_per_person = 1800
    elif travel_preference == "bus":
        travel_per_person = 1200
    else:
        travel_per_person = 3000

    food_per_person_per_day = 700
    local_transport_per_day = 1200
    activity_per_person_per_day = 800
    buffer = int(budget * 0.10)

    nights = max(days - 1, 1)

    travel_total = travel_per_person * people
    stay_total = stay_per_night * nights
    food_total = food_per_person_per_day * people * days
    local_transport_total = local_transport_per_day * days
    activity_total = activity_per_person_per_day * people * days

    total = (
        travel_total
        + stay_total
        + food_total
        + local_transport_total
        + activity_total
        + buffer
    )

    return compact_json({
        "people": people,
        "days": days,
        "nights": nights,
        "budget": budget,
        "breakdown": {
            "travel": travel_total,
            "stay": stay_total,
            "food": food_total,
            "local_transport": local_transport_total,
            "activities": activity_total,
            "buffer": buffer,
            "estimated_total": total
        },
        "fits_budget": total <= budget,
        "difference": budget - total
    })


tools = [
    weather_tool,
    exchange_rate_tool,
    geocode_tool,
    places_tool,
    hotel_tool,
    flight_tool,
    policy_tool,
    budget_calculator_tool
]
