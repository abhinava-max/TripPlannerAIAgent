DAILY_COSTS = {
    "INR": {
        "symbol": "₹",
        "stay": {
            "budget": 1500,
            "standard": 3500,
            "luxury": 8000,
        },
        "travel": {
            "flight": 7000,
            "train": 1800,
            "bus": 1200,
            "car": 3000,
            "any": 3000,
        },
        "food_per_person_per_day": 700,
        "local_transport_per_day": 1200,
        "activities_per_person_per_day": 800,
    },
    "USD": {
        "symbol": "$",
        "stay": {
            "budget": 45,
            "standard": 110,
            "luxury": 250,
        },
        "travel": {
            "flight": 220,
            "train": 70,
            "bus": 45,
            "car": 90,
            "any": 100,
        },
        "food_per_person_per_day": 35,
        "local_transport_per_day": 35,
        "activities_per_person_per_day": 30,
    },
    "EUR": {
        "symbol": "€",
        "stay": {
            "budget": 40,
            "standard": 100,
            "luxury": 230,
        },
        "travel": {
            "flight": 200,
            "train": 65,
            "bus": 40,
            "car": 85,
            "any": 95,
        },
        "food_per_person_per_day": 32,
        "local_transport_per_day": 32,
        "activities_per_person_per_day": 28,
    },
    "GBP": {
        "symbol": "£",
        "stay": {
            "budget": 35,
            "standard": 85,
            "luxury": 200,
        },
        "travel": {
            "flight": 180,
            "train": 55,
            "bus": 35,
            "car": 75,
            "any": 85,
        },
        "food_per_person_per_day": 28,
        "local_transport_per_day": 28,
        "activities_per_person_per_day": 25,
    },
    "AED": {
        "symbol": "د.إ",
        "stay": {
            "budget": 160,
            "standard": 400,
            "luxury": 900,
        },
        "travel": {
            "flight": 800,
            "train": 250,
            "bus": 160,
            "car": 330,
            "any": 360,
        },
        "food_per_person_per_day": 120,
        "local_transport_per_day": 120,
        "activities_per_person_per_day": 110,
    },
    "SGD": {
        "symbol": "S$",
        "stay": {
            "budget": 60,
            "standard": 145,
            "luxury": 330,
        },
        "travel": {
            "flight": 300,
            "train": 95,
            "bus": 60,
            "car": 125,
            "any": 135,
        },
        "food_per_person_per_day": 45,
        "local_transport_per_day": 45,
        "activities_per_person_per_day": 40,
    },
}


def normalize_currency(currency: str | None) -> str:
    normalized = (currency or "INR").strip().upper()

    return normalized if normalized in DAILY_COSTS else "INR"


def get_currency_symbol(currency: str | None) -> str:
    normalized = normalize_currency(currency)

    return DAILY_COSTS[normalized]["symbol"]


def calculate_trip_budget(
    budget: int,
    people: int,
    days: int,
    travel_mode: str = "any",
    stay_type: str = "budget",
    currency: str = "INR",
):
    normalized_currency = normalize_currency(currency)
    cost_rules = DAILY_COSTS[normalized_currency]

    nights = max(days - 1, 1)
    normalized_travel_mode = travel_mode if travel_mode in cost_rules["travel"] else "any"
    normalized_stay_type = stay_type if stay_type in cost_rules["stay"] else "budget"

    travel = cost_rules["travel"][normalized_travel_mode] * people
    stay = cost_rules["stay"][normalized_stay_type] * nights
    food = cost_rules["food_per_person_per_day"] * people * days
    local_transport = cost_rules["local_transport_per_day"] * days
    activities = cost_rules["activities_per_person_per_day"] * people * days
    buffer = int((travel + stay + food + local_transport + activities) * 0.10)
    total = travel + stay + food + local_transport + activities + buffer

    return {
        "currency": normalized_currency,
        "travel": travel,
        "stay": stay,
        "food": food,
        "local_transport": local_transport,
        "activities": activities,
        "buffer": buffer,
        "total": total,
        "fits_budget": total <= budget,
    }
