from typing import List, Optional

from pydantic import BaseModel, Field


class TripAgentRequest(BaseModel):
    source: str
    destination: str
    start_date: str
    end_date: str
    budget: int
    people: int
    travel_preference: str = "any"
    stay_preference: str = "budget"
    food_preference: str = "any"
    interests: Optional[List[str]] = []
    source_airport_code: Optional[str] = None
    destination_airport_code: Optional[str] = None
    base_currency: str = "INR"


class TripGenerateRequest(BaseModel):
    source: str
    destination: str
    start_date: str
    end_date: str
    budget: int
    people: int
    currency: str = "INR"
    travel_mode: str = "any"
    stay_type: str = "budget"
    interests: List[str] = Field(default_factory=list)


class TripPromptRequest(BaseModel):
    prompt: str


class BookingLink(BaseModel):
    label: str
    type: str
    url: str
    note: str = ""


class BookingLinksResponse(BaseModel):
    source: str
    destination: str
    date_range: str
    links: List[BookingLink]


class DayWisePlanItem(BaseModel):
    day: int
    title: str
    morning: str
    afternoon: str
    evening: str
    food_suggestion: str
    travel_notes: str = ""
    estimated_cost: int


class BudgetEstimate(BaseModel):
    currency: str = "INR"
    travel: int
    stay: int
    food: int
    local_transport: int
    activities: int
    buffer: int
    total: int
    fits_budget: bool


class TravelOption(BaseModel):
    mode: str
    details: str
    estimated_cost: int


class StayOption(BaseModel):
    name: str
    type: str
    location: str
    estimated_price_per_night: int
    note: str


class TripGenerateResponse(BaseModel):
    summary: str
    day_wise_plan: List[DayWisePlanItem]
    estimated_budget: BudgetEstimate
    travel_options: List[TravelOption]
    stay_options: List[StayOption]
    tips: List[str]
