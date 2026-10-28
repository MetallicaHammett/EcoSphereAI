"""
Physics-flavoured campus model used to generate realistic demo data and live readings.

It stands in for the sensing layer until real meters are connected: loads follow the academic
timetable, cooling follows outdoor temperature, solar follows irradiance and water follows
daily routines. Day-level randomness is seeded by date so history and live data agree.
"""

import math
import random
from dataclasses import dataclass

# code, name, type, area m2, occupants, lat, lng, solar kWp, indoor sensors
BUILDINGS = [
    ("ACA", "Academic Block A", "academic", 12000, 2500, 13.0517, 80.2121, 200, True),
    ("ACB", "Academic Block B", "academic", 10000, 2000, 13.0522, 80.2129, 0, True),
    ("TPL", "Tech Park Labs", "lab", 8000, 900, 13.0511, 80.2133, 0, True),
    ("LIB", "Central Library", "library", 5000, 600, 13.0526, 80.2117, 100, True),
    ("ADM", "Administration Block", "admin", 3000, 200, 13.0514, 80.2112, 0, False),
    ("BH1", "Boys Hostel 1", "hostel", 9000, 800, 13.0531, 80.2138, 150, True),
    ("BH2", "Boys Hostel 2", "hostel", 6000, 500, 13.0535, 80.2131, 0, False),
    ("GH1", "Girls Hostel 1", "hostel", 7000, 600, 13.0508, 80.2141, 0, True),
    ("FDC", "Food Court", "canteen", 1500, 1200, 13.0519, 80.2140, 0, False),
    ("SPC", "Sports Complex", "sports", 4000, 200, 13.0503, 80.2125, 0, False),
]

# W/m2: always-on base, occupied load, cooling per occupied m2 at +8 C above 24 C
LOADS = {
    "academic": (4, 22, 18), "lab": (8, 25, 18), "library": (4, 18, 20), "admin": (4, 20, 18),
    "hostel": (3, 10, 12), "canteen": (10, 60, 10), "sports": (2, 12, 4),
}
WATER_L_PER_OCCUPANT = {"academic": 45, "lab": 60, "library": 30, "admin": 45, "hostel": 135, "canteen": 25,
                        "sports": 40}
SOURCE_SHARES = {"municipal": 0.35, "borewell": 0.40, "recycled": 0.15, "rainwater": 0.10}


@dataclass
class Weather:
    temperature: float
    humidity: float
    irradiance: float
    rainfall_mm: float


def day_random(day, salt=""):
    return random.Random(f"{day.isoformat()}:{salt}")


def weather(ts):
    """Chennai-like climate: warm, humid, monsoon rain in Oct-Dec."""
    dr = day_random(ts.date(), "weather")
    doy = ts.timetuple().tm_yday
    rainy = dr.random() < (0.38 if ts.month in (10, 11, 12) else 0.18)
    cloud = dr.uniform(0.35, 0.65) if rainy else dr.uniform(0.8, 1.0)
    offset = dr.uniform(-1.2, 1.2) - (1.5 if rainy else 0)
    hour = ts.hour + ts.minute / 60
    temp = 29.5 + 2.0 * math.cos(2 * math.pi * (doy - 150) / 365) + 3.8 * math.sin(2 * math.pi * (hour - 9) / 24) + offset
    sun = max(0.0, math.sin(math.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 0.0
    rain = dr.uniform(2, 35) / 6 if rainy and 14 <= ts.hour < 20 else 0.0
    humidity = min(98.0, 72 - 10 * math.sin(2 * math.pi * (hour - 9) / 24) + (12 if rainy else 0))
    return Weather(round(temp, 2), round(humidity, 1), round(950 * sun * cloud, 1), round(rain, 2))


def occupancy(btype, hour, working):
    if btype == "hostel":
        if 22 <= hour or hour < 7:
            return 0.9
        if 18 <= hour < 22:
            return 0.85
        return 0.4 if working else 0.75
    if btype == "canteen":
        table = {7: .6, 8: .7, 9: .5, 10: .3, 11: .5, 12: 1, 13: 1, 14: .6, 15: .4, 16: .5, 17: .5, 18: .4,
                 19: .7, 20: .6, 21: .3}
        return table.get(hour, 0.02) * (1 if working else 0.45)
    if btype == "sports":
        table = {6: .6, 7: .6, 8: .3, 16: .7, 17: 1, 18: 1, 19: .8, 20: .4}
        return table.get(hour, 0.08)
    if not working:
        return 0.25 if btype == "library" and 9 <= hour < 17 else 0.04
    if 9 <= hour < 16:
        return 1.0
    if hour in (8, 16):
        return 0.6
    if hour == 17:
        return 0.35
    if btype == "library" and 18 <= hour < 21:
        return 0.55
    if btype == "lab" and 18 <= hour < 20:
        return 0.25
    return 0.04


def building_load_kw(btype, area, ts, working, temp, noise=1.0):
    base, occ_w, cool_w = LOADS[btype]
    occ = occupancy(btype, ts.hour, working)
    cooling = cool_w * occ * max(0.0, temp - 24) / 8
    return area * (base + occ_w * occ + cooling) / 1000 * noise


def solar_kw(kwp, irradiance, noise=1.0):
    return kwp * irradiance / 1000 * 0.8 * noise


def water_weights(btype, working):
    if btype == "hostel":
        hourly = {0: .02, 1: .02, 2: .02, 3: .02, 4: .03, 5: .3, 6: 1, 7: 1, 8: .8, 9: .5, 10: .25, 11: .25,
                  12: .4, 13: .4, 14: .25, 15: .25, 16: .3, 17: .45, 18: .7, 19: .7, 20: .7, 21: .6, 22: .3, 23: .1}
        return [hourly[h] for h in range(24)]
    return [occupancy(btype, h, working) + 0.02 for h in range(24)]


def water_klph(btype, occupants, hour, working, noise=1.0):
    # Normalise by the working-day profile so quiet days use less water while night flow stays the same.
    daily_kl = occupants * WATER_L_PER_OCCUPANT[btype] / 1000
    return daily_kl * water_weights(btype, working)[hour] / sum(water_weights(btype, True)) * noise


def indoor(btype, occupants, ts, working, outdoor, rnd):
    occ = occupancy(btype, ts.hour, working)
    cooled = occ > 0.3
    temperature = rnd.uniform(23.5, 25.5) if cooled else outdoor - rnd.uniform(0.5, 1.5)
    co2 = 420 + occ * rnd.uniform(520, 760)
    return round(temperature, 1), round(rnd.uniform(48, 62) if cooled else 70.0, 1), round(co2), int(occ * occupants)
