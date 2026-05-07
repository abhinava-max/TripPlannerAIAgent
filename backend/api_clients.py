import httpx

from .config import settings


async def get_weather(city: str, days: int = 3):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    forecast_steps = max(1, min(days, 5)) * 8

    params = {
        "q": city,
        "appid": settings.WEATHER_API_KEY,
        "units": "metric",
        "cnt": forecast_steps
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def get_exchange_rate(base_currency: str = "INR"):
    url = f"https://v6.exchangerate-api.com/v6/{settings.EXCHANGE_RATE_API_KEY}/latest/{base_currency}"

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def geocode_location(location: str):
    url = "https://api.geoapify.com/v1/geocode/search"

    params = {
        "text": location,
        "apiKey": settings.GEOAPIFY_API_KEY
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def get_geoapify_places(
    lat: float,
    lon: float,
    category: str = "tourism.sights",
    radius: int = 5000,
    limit: int = 10
):
    url = "https://api.geoapify.com/v2/places"

    params = {
        "categories": category,
        "filter": f"circle:{lon},{lat},{radius}",
        "bias": f"proximity:{lon},{lat}",
        "limit": limit,
        "apiKey": settings.GEOAPIFY_API_KEY
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def get_geoapify_places_by_city(
    city: str,
    category: str,
    radius: int = 5000,
    limit: int = 10
):
    geocode_data = await geocode_location(city)
    features = geocode_data.get("features", [])

    if not features:
        raise ValueError(f"Could not geocode city: {city}")

    properties = features[0]["properties"]
    return await get_geoapify_places(
        lat=properties["lat"],
        lon=properties["lon"],
        category=category,
        radius=radius,
        limit=limit
    )


async def get_geoapify_place_details(
    place_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    features: str = "details"
):
    url = "https://api.geoapify.com/v2/place-details"

    params = {
        "features": features,
        "apiKey": settings.GEOAPIFY_API_KEY
    }

    if place_id:
        params["id"] = place_id
    elif lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    else:
        raise ValueError("Provide either place_id or lat/lon")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def get_flight_data(airport_code: str):
    url = f"https://{settings.AERODATABOX_HOST}/flights/airports/iata/{airport_code}"

    headers = {
        "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
        "X-RapidAPI-Host": settings.AERODATABOX_HOST
    }

    params = {
        "offsetMinutes": "-120",
        "durationMinutes": "720",
        "withLeg": "true",
        "direction": "Both",
        "withCancelled": "false",
        "withCodeshared": "true",
        "withCargo": "false",
        "withPrivate": "false"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


async def search_hotels(city: str):
    return await get_geoapify_places_by_city(
        city=city,
        category="accommodation.hotel,accommodation.guest_house",
        radius=10000,
        limit=20
    )
