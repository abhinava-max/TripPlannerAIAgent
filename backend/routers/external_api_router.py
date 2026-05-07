import httpx
from fastapi import APIRouter, HTTPException, Query

from ..api_clients import (
    get_weather,
    get_exchange_rate,
    geocode_location,
    get_geoapify_places,
    get_geoapify_places_by_city,
    get_geoapify_place_details,
    get_flight_data,
    search_hotels
)


def raise_external_api_error(exc: Exception, service_name: str):
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code

        if status_code in {401, 403}:
            detail = f"{service_name} authentication failed. Check the API key in your .env file."
        else:
            detail = f"{service_name} returned HTTP {status_code}."

        raise HTTPException(status_code=502, detail=detail) from exc

    if isinstance(exc, httpx.RequestError):
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach {service_name}."
        ) from exc

    raise HTTPException(status_code=500, detail="External API request failed.") from exc


router = APIRouter(
    prefix="/external",
    tags=["External APIs"]
)


@router.get("/weather/{city}")
async def weather(city: str, days: int = 3):
    try:
        return await get_weather(city, days)
    except Exception as e:
        raise_external_api_error(e, "OpenWeatherMap")


@router.get("/exchange/{base_currency}")
async def exchange(base_currency: str = "INR"):
    try:
        return await get_exchange_rate(base_currency)
    except Exception as e:
        raise_external_api_error(e, "ExchangeRate API")


@router.get("/geocode")
async def geocode(location: str):
    try:
        return await geocode_location(location)
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/geoapify-places")
async def geoapify_places(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    category: str = "tourism.sights",
    radius: int = Query(5000, ge=1, le=50000),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        return await get_geoapify_places(lat, lon, category, radius, limit)
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/places")
async def places(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    category: str = "tourism.sights",
    radius: int = Query(5000, ge=1, le=50000),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        return await get_geoapify_places(lat, lon, category, radius, limit)
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/attractions")
async def attractions(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(5000, ge=1, le=50000),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        return await get_geoapify_places(
            lat,
            lon,
            "tourism.sights,tourism.attraction,entertainment.museum",
            radius,
            limit
        )
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/restaurants")
async def restaurants(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(5000, ge=1, le=50000),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        return await get_geoapify_places(
            lat,
            lon,
            "catering.restaurant,catering.cafe,catering.fast_food",
            radius,
            limit
        )
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/hotels-nearby")
async def hotels_nearby(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(10000, ge=1, le=50000),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        return await get_geoapify_places(
            lat,
            lon,
            "accommodation.hotel,accommodation.guest_house",
            radius,
            limit
        )
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/places-by-city/{city}")
async def places_by_city(
    city: str,
    category: str = "tourism.sights",
    radius: int = Query(5000, ge=1, le=50000),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        return await get_geoapify_places_by_city(city, category, radius, limit)
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/place-details")
async def place_details(
    place_id: str | None = None,
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    features: str = "details"
):
    try:
        return await get_geoapify_place_details(place_id, lat, lon, features)
    except Exception as e:
        raise_external_api_error(e, "Geoapify")


@router.get("/flights/{airport_code}")
async def flights(airport_code: str):
    try:
        return await get_flight_data(airport_code.upper())
    except Exception as e:
        raise_external_api_error(e, "AeroDataBox")


@router.get("/hotels/{city}")
async def hotels(city: str):
    try:
        return await search_hotels(city)
    except Exception as e:
        raise_external_api_error(e, "Geoapify")
