"""
HeatGuard Public Safety Guidance Module.

Defines maintainable, non-diagnostic safety recommendations mapped to the
educational risk tiers, as well as role/vulnerability-specific guidance
(outdoor workers, older adults, children, sensitive groups).

NON-DIAGNOSTIC & NON-MEDICAL DISCLAIMER:
These guidelines provide general educational precautions. They do NOT constitute
personalized medical advice, clinical diagnoses, or emergency medical direction.
Suspected cases of heatstroke or severe heat exhaustion require immediate
local emergency medical assistance.
"""

# Risk Category Safety Guidance Structure
CATEGORY_SAFETY_GUIDANCE = {
    'NORMAL': {
        'headline': "Baseline Seasonal Precautions",
        'summary': "Conditions currently reflect minimal thermal heat stress.",
        'hydration': "Maintain routine daily fluid intake. Drink water before, during, and after physical exercise.",
        'shade_and_rest': "Normal work/rest intervals. Enjoy outdoor activities with standard sun protection.",
        'outdoor_activity': "Standard outdoor physical activity and work routines can proceed as scheduled.",
        'vulnerable_care': "Standard care. Remind infants, older adults, and pets to remain well-hydrated.",
        'warning_signs': "Be mindful of mild dehydration (thirst, slight dry mouth, fatigue).",
        'urgency_level': "low",
    },
    'CAUTION': {
        'headline': "Elevated Heat Precaution",
        'summary': "Fatigue and discomfort possible with prolonged outdoor exposure and physical exertion.",
        'hydration': "Drink water regularly even before feeling thirsty. Avoid excessive sugary or alcoholic beverages.",
        'shade_and_rest': "Take periodic breaks in shaded, well-ventilated, or cooled areas during outdoor work.",
        'outdoor_activity': "Pace physical exertion. If working outdoors, rotate tasks to minimize continuous sun exposure.",
        'vulnerable_care': "Check on elderly neighbors and family members. Ensure pets have ample fresh water and shade.",
        'warning_signs': "Watch for heavy sweating, muscle cramps, headache, dizziness, and mild nausea.",
        'urgency_level': "moderate",
    },
    'EXTREME_CAUTION': {
        'headline': "Heightened Thermal Stress Advisory",
        'summary': "Heat cramps and heat exhaustion possible with prolonged exposure or physical exertion.",
        'hydration': "Drink cool water or electrolyte-balanced fluids every 15–20 minutes during outdoor activity.",
        'shade_and_rest': "Enforce mandatory rest intervals in shaded or air-conditioned environments.",
        'outdoor_activity': "Schedule strenuous outdoor work and athletic training during cooler early morning or late evening hours.",
        'vulnerable_care': "Actively verify that older adults and individuals with pre-existing cardiovascular conditions have access to cooled spaces.",
        'warning_signs': "Watch for persistent dizziness, cool/moist skin with goosebumps, weakness, and rapid pulse.",
        'urgency_level': "high",
    },
    'DANGER': {
        'headline': "Severe Heatwave Precaution",
        'summary': "Heat cramps and heat exhaustion likely; heatstroke possible with continuous outdoor exposure.",
        'hydration': "Continuous hydration is essential. Avoid heavy meals; consume cool fluids and fruits with high water content.",
        'shade_and_rest': "Stay indoors in air-conditioned or well-ventilated spaces. Minimize all direct midday sun exposure.",
        'outdoor_activity': "Reschedule or suspend non-essential outdoor physical labor between 11:00 and 16:00.",
        'vulnerable_care': "Frequent welfare checks on infants, young children, pregnant individuals, and older adults. NEVER leave anyone in a parked vehicle.",
        'warning_signs': "Severe warning signs include vomiting, fainting, confusion, hot/red skin, or lack of sweating. Seek emergency medical care immediately.",
        'urgency_level': "very-high",
    },
    'EXTREME_DANGER': {
        'headline': "Emergency Extreme Heat Precaution",
        'summary': "Heatstroke imminent or highly likely with prolonged outdoor activity. High-risk life safety emergency.",
        'hydration': "Drink fluids continuously. Replenish electrolytes as recommended by health professionals.",
        'shade_and_rest': "Remain indoors in climate-controlled environments. If cooling is unavailable, relocate to designated community cooling centers.",
        'outdoor_activity': "Cease all strenuous outdoor labor and sports. Direct sun exposure can become hazardous within minutes.",
        'vulnerable_care': "Immediate community care: verify cooling access for vulnerable family and community members. Emergency protocols active.",
        'warning_signs': "High body temperature (> 39.5°C / 103°F), altered mental state, confusion, loss of consciousness, seizures. Call local emergency services (e.g. 108/112/911) immediately.",
        'urgency_level': "extreme",
    },
}

# Role & Vulnerability Group Guidance
GROUP_SAFETY_GUIDANCE = [
    {
        'group_name': "Outdoor Workers & Laborers",
        'badge': "Occupational Health",
        'key_points': [
            "Implement a buddy system so workers monitor each other for early symptoms of confusion or dizziness.",
            "Establish shaded rest stations with cool potable water accessible within 50 meters of the work area.",
            "Adopt gradual acclimatization for workers returning from leave or new to hot environments (over 7–14 days).",
            "Wear light-colored, loose-fitting, breathable clothing and broad-brimmed hats.",
        ],
        'emergency_action': "If a worker exhibits confusion, slurred speech, or collapses, move them to shade immediately, loosen clothing, apply cool water, and call emergency services."
    },
    {
        'group_name': "Older Adults (Seniors)",
        'badge': "Vulnerable Population",
        'key_points': [
            "Aging bodies have a reduced physiological ability to regulate temperature and perceive thirst.",
            "Many common medications (e.g. diuretics, beta-blockers, antihistamines) impair heat tolerance.",
            "Spend at least 2–4 hours during peak afternoon hours in an air-conditioned room, library, or community center.",
            "Family and community members should call or visit older relatives at least twice daily during hot spells.",
        ],
        'emergency_action': "Do not rely on electric fans alone when ambient temperature exceeds 35°C (95°F) as fans may accelerate dehydration."
    },
    {
        'group_name': "Infants & Young Children",
        'badge': "Pediatric Care",
        'key_points': [
            "Children absorb environmental heat faster than adults and produce less sweat per unit of body mass.",
            "NEVER leave a child or pet inside a parked vehicle, even for a minute with windows cracked.",
            "Dress infants in lightweight, single-layer cotton garments and keep them out of direct sunlight.",
            "Encourage regular sips of water or diluted fluids; infants under 6 months should receive breastmilk/formula regularly.",
        ],
        'emergency_action': "Seek immediate medical attention if a child is unusually lethargic, irritable, has dry nappies for over 6 hours, or develops a high fever."
    },
    {
        'group_name': "People with Chronic Health Conditions",
        'badge': "Medical Sensitivity",
        'key_points': [
            "Cardiovascular, kidney, and respiratory diseases significantly increase vulnerability to heat stress.",
            "Consult a physician or primary healthcare provider regarding fluid intake limits and medication adjustments in summer.",
            "Store life-saving medications (including insulin and asthma inhalers) below recommended temperature limits.",
            "Monitor blood pressure and blood sugar regularly during prolonged heatwaves.",
        ],
        'emergency_action': "Follow individual management plans provided by your attending physician."
    },
]

# Reliable Official Public Health Resources
OFFICIAL_HEALTH_RESOURCES = [
    {
        'agency': "World Health Organization (WHO)",
        'title': "Heat and Health Guidance & Information Sheets",
        'url': "https://www.who.int/news-room/fact-sheets/detail/heat-and-health",
        'description': "Global public health guidance on preparing for extreme temperatures and preventing heat-related morbidity."
    },
    {
        'agency': "National Disaster Management Authority (NDMA India)",
        'title': "Guidelines on Prevention and Management of Heatwave",
        'url': "https://ndma.gov.in/Natural-Hazards/Heat-Wave",
        'description': "National action plan framework, 'Do's and Don'ts' for citizens, and community heat health strategies."
    },
    {
        'agency': "Centers for Disease Control and Prevention (CDC)",
        'title': "Warning Signs and Symptoms of Heat-Related Illness",
        'url': "https://www.cdc.gov/extreme-heat/signs-symptoms/index.html",
        'description': "Clinical descriptions distinguishing heat cramps, heat exhaustion, and medical emergency heatstroke."
    },
    {
        'agency': "India Meteorological Department (IMD)",
        'title': "National Weather Forecast and Heat Warning Bulletins",
        'url': "https://mausam.imd.gov.in/",
        'description': "Official operational weather forecasts, temperature departure charts, and color-coded alerts."
    },
]


def get_safety_guidance_for_risk(risk_category):
    """
    Returns the safety guidance dictionary for a given risk category.
    Returns a cautious fallback without falsely reassuring the user if the category is unknown or None.
    """
    if not risk_category or str(risk_category).upper() not in CATEGORY_SAFETY_GUIDANCE:
        return {
            'headline': "Thermal Assessment Unavailable",
            'summary': "Risk category could not be evaluated due to missing or incomplete telemetry.",
            'hydration': "Follow standard hydration practices. Drink water regularly when active.",
            'shade_and_rest': "Take precautions if ambient air feels hot or humid. Seek shade as appropriate.",
            'outdoor_activity': "Monitor local conditions and heed warnings issued by local public health departments.",
            'vulnerable_care': "Ensure infants, older adults, and pets have access to drinking water and ventilated spaces.",
            'warning_signs': "If you experience dizziness, headache, or nausea in hot conditions, rest in a cooled area.",
            'urgency_level': "unknown",
        }

    return CATEGORY_SAFETY_GUIDANCE[str(risk_category).upper()]
