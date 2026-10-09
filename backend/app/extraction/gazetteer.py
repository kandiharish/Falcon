"""Local knowledge the general language model lacks: Telangana place names and Indian law codes.

The small English model learned from American news. It reads "JNTU" as a person and "BNS"
(the criminal code) as a company. These lists are checked BEFORE the model guesses:
  • a known place is a LOCATION (confidence 0.7: a list match, still worth a glance);
  • a law or code is not an entity at all, so it is never filed as an organisation.
Add an area here when a case moves to a new city.
"""

PLACES = [
    # Hyderabad, Cyberabad and Rachakonda areas
    "Ameerpet",
    "Banjara Hills",
    "Begumpet",
    "Chandanagar",
    "Charminar",
    "Cyberabad",
    "Dilsukhnagar",
    "Gachibowli",
    "HITEC City",
    "Hitech City",
    "Hyderabad",
    "Jubilee Hills",
    "JNTU",
    "JNTU junction",
    "KPHB",
    "KPHB Colony",
    "Kondapur",
    "Kukatpally",
    "LB Nagar",
    "Madhapur",
    "Mehdipatnam",
    "Miyapur",
    "Moosapet",
    "Nizampet",
    "Rachakonda",
    "Secunderabad",
    "Uppal",
    # Other Telangana districts
    "Karimnagar",
    "Khammam",
    "Nizamabad",
    "Telangana",
    "Warangal",
]

LAWS = [
    "BNS",
    "BNSS",
    "BSA",
    "IPC",
    "CrPC",
    "IT Act",
    "Bharatiya Nyaya Sanhita",
    "Bharatiya Nagarik Suraksha Sanhita",
    "Bharatiya Sakshya Adhiniyam",
    "Indian Penal Code",
    "Indian Evidence Act",
]

PLACE_LABEL = "FALCON_PLACE"


def ruler_patterns() -> list[dict]:
    return [{"label": PLACE_LABEL, "pattern": p} for p in PLACES] + [
        {"label": "LAW", "pattern": p} for p in LAWS
    ]
