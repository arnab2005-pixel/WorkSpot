#!/usr/bin/env python3
"""
Mock Data Seeding Script for PM-AJAY Voice Assistant.

Generates and inserts realistic mock data into MongoDB:
- Training centers/kiosks across multiple Indian districts
- Diverse NSQF courses with proper sector mapping
- Sample beneficiaries for testing

Run: python scripts/seed_mock_data.py
"""

import asyncio
import hashlib
import random
import secrets
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, TEXT

# District data: LGD code -> (State, District Name, Blocks)
DISTRICTS = {
    # Uttar Pradesh
    "UP_VARANASI": (
        "Uttar Pradesh",
        "Varanasi",
        ["Chiraigaon", "Kashi Vidyapeeth", "Pindra", "Harhua", "Araziline"],
    ),
    "UP_PRAYAGRAJ": (
        "Uttar Pradesh",
        "Prayagraj",
        ["Kaurihar", "Phulpur", "Soraon", "Handia", "Meja"],
    ),
    "UP_LUCKNOW": (
        "Uttar Pradesh",
        "Lucknow",
        ["Bakshi Ka Talab", "Chinhat", "Gosainganj", "Kakori", "Malihabad"],
    ),
    "UP_CHANDAULI": (
        "Uttar Pradesh",
        "Chandauli",
        ["Chandauli", "Chakia", "Naugarh", "Sakaldiha", "Dhanapur"],
    ),
    "UP_AGRA": (
        "Uttar Pradesh",
        "Agra",
        ["Agra", "Bah", "Etmadpur", "Fatehabad", "Kheragarh"],
    ),
    "UP_KANPUR": (
        "Uttar Pradesh",
        "Kanpur Nagar",
        ["Kanpur", "Bhognipur", "Ghatampur", "Narwal", "Sarsaul"],
    ),
    "UP_ALIGARH": (
        "Uttar Pradesh",
        "Aligarh",
        ["Aligarh", "Atrauli", "Bijauli", "Gangiri", "Iglas"],
    ),
    "UP_MEERUT": (
        "Uttar Pradesh",
        "Meerut",
        ["Meerut", "Daurala", "Hastinapur", "Janikhurd", "Kharkhoda"],
    ),
    "UP_GORAKHPUR": (
        "Uttar Pradesh",
        "Gorakhpur",
        ["Gorakhpur", "Bansgaon", "Barhalganj", "Campierganj", "Chauri Chaura"],
    ),
    "UP_BAREILLY": (
        "Uttar Pradesh",
        "Bareilly",
        ["Bareilly", "Aonla", "Baheri", "Faridpur", "Meerganj"],
    ),
    # Bihar
    "BR_PATNA": (
        "Bihar",
        "Patna",
        ["Patna Sadar", "Danapur", "Phulwari", "Maner", "Bihta"],
    ),
    "BR_GAYA": (
        "Bihar",
        "Gaya",
        ["Gaya Sadar", "Bodh Gaya", "Wazirganj", "Tekari", "Sherghati"],
    ),
    "BR_MUZAFFARPUR": (
        "Bihar",
        "Muzaffarpur",
        ["Muzaffarpur", "Kanti", "Marwan", "Mushari", "Sakri"],
    ),
    "BR_BHAGALPUR": (
        "Bihar",
        "Bhagalpur",
        ["Bhagalpur", "Nathnagar", "Sultanganj", "Kahalgaon", "Pirpainti"],
    ),
    "BR_DARBHANGA": (
        "Bihar",
        "Darbhanga",
        ["Darbhanga", "Bahadurpur", "Beniapur", "Ghanshyampur", "Hanumannagar"],
    ),
    # Madhya Pradesh
    "MP_BHOPAL": ("Madhya Pradesh", "Bhopal", ["Bhopal", "Berasia", "Huzur", "Kolar"]),
    "MP_INDORE": ("Madhya Pradesh", "Indore", ["Indore", "Depalpur", "Mhow", "Sanwer"]),
    "MP_JABALPUR": (
        "Madhya Pradesh",
        "Jabalpur",
        ["Jabalpur", "Kundam", "Majholi", "Patan", "Sihora"],
    ),
    "MP_GWALIOR": (
        "Madhya Pradesh",
        "Gwalior",
        ["Gwalior", "Bhitarwar", "Dabra", "Ghatigaon", "Morar"],
    ),
    "MP_UJJAIN": (
        "Madhya Pradesh",
        "Ujjain",
        ["Ujjain", "Badnagar", "Khachrod", "Mahidpur", "Tarana"],
    ),
    # Rajasthan
    "RJ_JAIPUR": (
        "Rajasthan",
        "Jaipur",
        ["Jaipur", "Amber", "Bassi", "Chaksu", "Dudu", "Kotputli"],
    ),
    "RJ_JODHPUR": (
        "Rajasthan",
        "Jodhpur",
        ["Jodhpur", "Balesar", "Bap", "Bilara", "Luni", "Osian"],
    ),
    "RJ_KOTA": (
        "Rajasthan",
        "Kota",
        ["Kota", "Digod", "Kanwas", "Ladpura", "Ramganj Mandi"],
    ),
    "RJ_BIKANER": (
        "Rajasthan",
        "Bikaner",
        ["Bikaner", "Chhatargarh", "Kolayat", "Lunkaransar", "Nokha"],
    ),
    "RJ_AJMER": (
        "Rajasthan",
        "Ajmer",
        ["Ajmer", "Beawar", "Kekri", "Kishangarh", "Masuda", "Nasirabad"],
    ),
    # Maharashtra
    "MH_MUMBAI": ("Maharashtra", "Mumbai", ["Mumbai City", "Mumbai Suburban"]),
    "MH_PUNE": (
        "Maharashtra",
        "Pune",
        ["Pune City", "Haveli", "Khed", "Maval", "Mulshi", "Purandar"],
    ),
    "MH_NAGPUR": (
        "Maharashtra",
        "Nagpur",
        ["Nagpur", "Hingna", "Kamptee", "Mauda", "Narkhed", "Parseoni"],
    ),
    "MH_AURANGABAD": (
        "Maharashtra",
        "Aurangabad",
        ["Aurangabad", "Gangapur", "Kannad", "Khuldabad", "Paithan"],
    ),
    "MH_NASHIK": (
        "Maharashtra",
        "Nashik",
        ["Nashik", "Dindori", "Igatpuri", "Kalwan", "Malegaon", "Nandgaon"],
    ),
    # West Bengal
    "WB_KOLKATA": ("West Bengal", "Kolkata", ["Kolkata"]),
    "WB_HOWRAH": (
        "West Bengal",
        "Howrah",
        ["Howrah Sadar", "Bally Jagacha", "Domjur", "Panchla", "Sankrail", "Uluberia"],
    ),
    "WB_NORTH_24_PARGANAS": (
        "West Bengal",
        "North 24 Parganas",
        ["Barasat", "Barrackpore", "Basirhat", "Bongaon", "Habra"],
    ),
    "WB_SOUTH_24_PARGANAS": (
        "West Bengal",
        "South 24 Parganas",
        ["Alipore", "Baruipur", "Canning", "Diamond Harbour", "Kakdwip"],
    ),
    "WB_PASCHIM_MEDINIPUR": (
        "West Bengal",
        "Paschim Medinipur",
        ["Medinipur Sadar", "Ghatal", "Jhargram", "Kharagpur"],
    ),
}

# Training center types
CENTER_TYPES = [
    "ITI (Industrial Training Institute)",
    "PMKVY Training Center",
    "NSFDC Skill Center",
    "PM-AJAY Kiosk",
    "Rural Self Employment Training Institute (RSETI)",
    "District Skill Center",
    "Polytechnic College",
    "Community College",
    "Private Training Partner",
    "NGO Vocational Center",
]

# Sectors with trades
SECTORS_TRADES = {
    "Apparel, Made-ups & Home Furnishing": [
        ("AMH/Q0301", "Self Employed Tailor", "स्व-रोज़गार दर्जी", 4, 1),
        ("AMH/Q1001", "Hand Embroiderer", "कसीदाकारी कारीगर", 3, 0),
        ("AMH/Q0801", "Sewing Machine Operator", "सिलाई मशीन ऑपरेटर", 3, 1),
        ("AMH/Q1201", "Fashion Designer", "फैशन डिजाइनर", 4, 2),
        ("AMH/Q1501", "Boutique Manager", "बुटीक प्रबंधक", 4, 3),
    ],
    "Construction": [
        ("CON/Q0101", "Assistant Mason", "सहायक राजमिस्त्री", 2, 0),
        ("CON/Q0601", "Bar Bender & Steel Fixer", "बार बेंडर और स्टील फिक्सर", 3, 1),
        ("CON/Q1101", "Construction Painter", "निर्माण पेंटर", 3, 1),
        ("CON/Q2101", "Scaffolder", "स्कैफोल्डर", 3, 0),
        ("CON/Q0301", "Shuttering Carpenter", "शटरिंग कारपेंटर", 3, 1),
    ],
    "Electronics & Hardware": [
        ("ELE/Q3101", "LED Light Repair Technician", "एलईडी लाइट मरम्मत तकनीशियन", 4, 2),
        (
            "ELE/Q3501",
            "Mobile Phone Hardware Repair Technician",
            "मोबाइल फोन हार्डवेयर मरम्मत",
            4,
            2,
        ),
        (
            "ELE/Q4601",
            "Solar Panel Installation Technician",
            "सौर पैनल स्थापना तकनीशियन",
            4,
            1,
        ),
        ("ELE/Q5901", "CCTV Installation Technician", "सीसीटीवी स्थापना तकनीशियन", 3, 1),
        ("ELE/Q6301", "Home Appliance Repair Technician", "घरेलू उपकरण मरम्मत", 3, 1),
    ],
    "Beauty & Wellness": [
        ("BWS/Q0101", "Assistant Beauty Therapist", "सहायक ब्यूटी थेरेपिस्ट", 3, 1),
        ("BWS/Q0201", "Hair Stylist", "हेयर स्टाइलिस्ट", 4, 2),
        ("BWS/Q0301", "Beautician", "ब्यूटीशियन", 3, 1),
        ("BWS/Q0401", "Makeup Artist", "मेकअप आर्टिस्ट", 3, 2),
        ("BWS/Q0501", "Nail Technician", "नेल तकनीशियन", 3, 1),
    ],
    "Automotive": [
        (
            "ASC/Q1401",
            "Automotive Service Technician (2/3 Wheeler)",
            "ऑटोमोटिव सर्विस तकनीशियन",
            4,
            1,
        ),
        ("ASC/Q1101", "Automotive Body Repair Technician", "ऑटोमोटिव बॉडी मरम्मत", 4, 2),
        ("ASC/Q1901", "Electric Vehicle Technician", "इलेक्ट्रिक वाहन तकनीशियन", 4, 3),
        ("ASC/Q2001", "Automotive Paint Technician", "ऑटोमोटिव पेंट तकनीशियन", 3, 1),
    ],
    "Food Processing": [
        ("FIC/Q0101", "Food Products Packaging Technician", "खाद्य उत्पाद पैकेजिंग", 3, 1),
        ("FIC/Q1001", "Bakery & Confectionery Technician", "बेकरी और कन्फेक्शनरी", 4, 1),
        ("FIC/Q2001", "Pickle Making Technician", "अचार निर्माण तकनीशियन", 3, 0),
        ("FIC/Q3001", "Spice Processing Technician", "मसाला प्रसंस्करण", 3, 1),
    ],
    "Agriculture": [
        ("AGR/Q0101", "Organic Grower", "जैविक उत्पादक", 4, 1),
        ("AGR/Q0201", "Dairy Farmer", "डेयरी किसान", 4, 0),
        ("AGR/Q0301", "Poultry Farmer", "पोल्ट्री किसान", 3, 0),
        ("AGR/Q0401", "Mushroom Cultivator", "मशरूम उत्पादक", 3, 0),
        ("AGR/Q0501", "Beekeeper", "मधुमक्खी पालक", 3, 0),
    ],
    "IT-ITeS": [
        ("SSC/Q0101", "Domestic Data Entry Operator", "डेटा एंट्री ऑपरेटर", 4, 2),
        ("SSC/Q0201", "Domestic IT Helpdesk Attendant", "आईटी हेल्पडेस्क अटेंडेंट", 4, 2),
        ("SSC/Q0301", "Junior Software Developer", "जूनियर सॉफ्टवेयर डेवलपर", 5, 3),
        ("SSC/Q0401", "CRM Domestic Voice", "सीआरएम घरेलू वॉयस", 4, 2),
    ],
    "Healthcare": [
        ("HSS/Q0101", "General Duty Assistant", "सामान्य ड्यूटी सहायक", 4, 1),
        ("HSS/Q0201", "Home Health Aide", "होम हेल्थ सहायक", 4, 1),
        ("HSS/Q0301", "Pharmacy Assistant", "फार्मेसी सहायक", 4, 2),
        (
            "HSS/Q0401",
            "Emergency Medical Technician",
            "आपातकालीन चिकित्सा तकनीशियन",
            4,
            2,
        ),
    ],
    "Tourism & Hospitality": [
        (
            "THC/Q0101",
            "Food & Beverage Service Assistant",
            "खाद्य और पेय सेवा सहायक",
            3,
            1,
        ),
        ("THC/Q0201", "Front Office Associate", "फ्रंट ऑफिस सहयोगी", 4, 2),
        ("THC/Q0301", "Housekeeping Assistant", "हाउसकीपिंग सहायक", 3, 0),
        ("THC/Q0401", "Tour Guide", "टूर गाइड", 4, 2),
    ],
}

# Dialects by state
STATE_DIALECTS = {
    "Uttar Pradesh": ["bhojpuri_mixed", "awadhi_mixed", "braj_bhasha_mixed"],
    "Bihar": ["bhojpuri_mixed", "maithili_mixed", "magahi_mixed"],
    "Madhya Pradesh": ["bundeli_mixed", "malvi_mixed", "nimari_mixed"],
    "Rajasthan": ["marwari_mixed", "mewati_mixed", "dhundhari_mixed"],
    "Maharashtra": ["marathi_mixed", "varhadi_mixed", "konkani_mixed"],
    "West Bengal": ["bengali_mixed", "rajbanshi_mixed"],
}

EDUCATION_LEVELS = ["none", "class_5", "class_8", "class_10", "class_12"]
EDUCATION_TIER_MAP = {
    "none": 0,
    "class_5": 1,
    "class_8": 2,
    "class_10": 3,
    "class_12": 4,
}

AGE_BRACKETS = ["18-25", "25-35", "35-45", "45-60", "60+"]
EMPLOYMENT_INTENTS = ["WAGE", "SELF_EMPLOYMENT", "HYBRID"]

TRADITIONAL_TRADES = [
    "सिलाई / Tailoring",
    "कढ़ाई / Embroidery",
    "बढ़ई / Carpentry",
    "लोहार / Blacksmith",
    "कुम्हार / Pottery",
    "चमड़ा कार्य / Leather Work",
    "बांस शिल्प / Bamboo Craft",
    "जूट शिल्प / Jute Craft",
    "हथकरघा बुनाई / Handloom Weaving",
    "खेती / Farming",
    "पशुपालन / Animal Husbandry",
    "मछली पालन / Fishery",
    "ब्यूटी पार्लर / Beauty Parlor",
    "मेहंदी डिजाइन / Mehndi Design",
    "मोबाइल मरम्मत / Mobile Repair",
    "इलेक्ट्रीशियन / Electrician",
    "प्लंबर / Plumber",
    "वेल्डिंग / Welding",
    "पेंटिंग / Painting",
    "ड्राइविंग / Driving",
    "कंप्यूटर / Computer",
    "अकाउंटिंग / Accounting",
]

CURRENT_ACTIVITIES = [
    "गृहिणी / Homemaker",
    "किसान / Farmer",
    "मजदूर / Laborer",
    "छोटा दुकानदार / Small Shopkeeper",
    "बेरोजगार / Unemployed",
    "छात्र / Student",
    "पारिवारिक व्यवसाय में सहायता / Helping in Family Business",
    "मनरेगा श्रमिक / MGNREGA Worker",
    "आंगनवाड़ी कार्यकर्ता / Anganwadi Worker",
    "आशा कार्यकर्ता / ASHA Worker",
    "स्वयं सहायता समूह सदस्य / SHG Member",
]


def generate_embedding(seed: float) -> list[float]:
    """Generate a normalized 768-dim embedding vector (deterministic for reproducibility)."""
    import math

    vec = []
    sum_sq = 0.0
    for i in range(768):
        val = math.sin(seed + i)
        vec.append(val)
        sum_sq += val * val
    norm = math.sqrt(sum_sq)
    return [v / norm for v in vec]


def create_phone_hash(phone_number: str, salt: str | None = None) -> tuple:
    """Create salted SHA-256 hash of phone number."""
    if salt is None:
        salt = secrets.token_hex(32)
    normalized = phone_number.strip().replace(" ", "").replace("-", "")
    if not normalized.startswith("+91"):
        if normalized.startswith("91"):
            normalized = "+" + normalized
        elif normalized.startswith("0"):
            normalized = "+91" + normalized[1:]
        else:
            normalized = "+91" + normalized
    hash_obj = hashlib.sha256()
    hash_obj.update(salt.encode())
    hash_obj.update(normalized.encode())
    return hash_obj.hexdigest(), salt


async def seed_training_centers(db) -> list[dict]:
    """Create training centers/kiosks across all districts."""
    centers = []
    center_id = 1

    for district_code, (state, district_name, blocks) in DISTRICTS.items():
        # Create 3-5 centers per district
        num_centers = random.randint(3, 5)

        for i in range(num_centers):
            block = random.choice(blocks)
            center_type = random.choice(CENTER_TYPES)

            # Generate center name
            if "Kiosk" in center_type:
                name = f"PM-AJAY Kiosk {district_name} - {block}"
            elif "ITI" in center_type:
                name = f"Government ITI {district_name} - {block}"
            elif "NSFDC" in center_type:
                name = f"NSFDC Skill Center {district_name} - {block}"
            elif "RSETI" in center_type:
                name = f"RSETI {district_name}"
            else:
                name = f"{center_type} {district_name} - {block}"

            # Sectors this center offers (2-4 sectors)
            num_sectors = random.randint(2, 4)
            center_sectors = random.sample(list(SECTORS_TRADES.keys()), num_sectors)

            center = {
                "center_id": f"TC_{center_id:05d}",
                "name": name,
                "center_type": center_type,
                "state": state,
                "district_code": district_code,
                "district_name": district_name,
                "block_name": block,
                "address": f"Near Block Office, {block}, {district_name}, {state}",
                "pincode": f"{random.randint(100000, 999999)}",
                "contact_phone": f"+91{random.randint(7000000000, 9999999999)}",
                "contact_email": f"{name.lower().replace(' ', '').replace('-', '')}@pm-ajay.gov.in",
                "sectors_offered": center_sectors,
                "facilities": random.sample(
                    [
                        "Computer Lab",
                        "Workshop",
                        "Classroom",
                        "Hostel",
                        "Canteen",
                        "Library",
                        "Placement Cell",
                        "Counseling Room",
                        "Practical Lab",
                        "Digital Literacy Lab",
                        "Women's Rest Room",
                        "Accessible Ramp",
                    ],
                    k=random.randint(3, 7),
                ),
                "capacity_per_batch": random.randint(20, 60),
                "num_trainers": random.randint(3, 12),
                "accreditation": random.choice(
                    ["NCVT", "SCVT", "NSQF Aligned", "PMKVY Affiliated"]
                ),
                "operating_hours": "9:00 AM - 5:00 PM",
                "working_days": "Monday - Saturday",
                "has_hostel": random.choice([True, False]),
                "hostel_capacity": random.randint(0, 50)
                if random.choice([True, False])
                else 0,
                "transport_available": random.choice([True, False]),
                "latitude": round(random.uniform(20.0, 30.0), 6)
                if state in ["Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan"]
                else round(random.uniform(15.0, 25.0), 6),
                "longitude": round(random.uniform(75.0, 90.0), 6)
                if state in ["Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan"]
                else round(random.uniform(72.0, 88.0), 6),
                "status": "ACTIVE",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            centers.append(center)
            center_id += 1

    # Insert into database
    if centers:
        await db.training_centers.delete_many({})
        await db.training_centers.insert_many(centers)
        # Create indexes
        await db.training_centers.create_index([("district_code", ASCENDING)])
        await db.training_centers.create_index([("state", ASCENDING)])
        await db.training_centers.create_index([("center_type", ASCENDING)])
        await db.training_centers.create_index([("sectors_offered", ASCENDING)])
        await db.training_centers.create_index([("status", ASCENDING)])
        await db.training_centers.create_index([("name", TEXT)])

    print(
        f"✅ Created {len(centers)} training centers across {len(DISTRICTS)} districts"
    )
    return centers


async def seed_courses(db, training_centers: list[dict]) -> list[dict]:
    """Create diverse NSQF courses mapped to training centers."""
    courses = []
    course_seed = 1.0

    # Map each center to courses in its sectors
    for center in training_centers:
        center_courses = []
        for sector in center["sectors_offered"]:
            trades = SECTORS_TRADES.get(sector, [])
            if not trades:
                continue
            # Pick 1-2 trades per sector per center
            num_trades = min(len(trades), random.randint(1, 2))
            selected_trades = random.sample(trades, num_trades)

            for (
                qp_code,
                course_name,
                course_name_indic,
                nsqf_level,
                min_edu_tier,
            ) in selected_trades:
                # Generate course embedding
                course_embedding = generate_embedding(course_seed)
                course_seed += 1.0

                # Stipend varies by NSQF level
                base_stipend = {
                    1: 1000,
                    2: 1200,
                    3: 1500,
                    4: 1800,
                    5: 2200,
                    6: 2500,
                    7: 2800,
                    8: 3000,
                }
                stipend = base_stipend.get(nsqf_level, 1500)

                # Duration varies
                duration = random.randint(200, 500)

                # Pathway type
                pathway = random.choice(
                    [
                        "VOCATIONAL_TRAINING",
                        "VOCATIONAL_TRAINING",
                        "VOCATIONAL_TRAINING",
                        "RPL_CERTIFICATION",
                        "EDP_ENTREPRENEURSHIP",
                    ]
                )

                # Target occupations for better matching
                target_occupations = []
                if "Tailor" in course_name or "Sewing" in course_name:
                    target_occupations = [
                        "सिलाई",
                        "टेलर",
                        "दर्जी",
                        "tailoring",
                        "stitching",
                    ]
                elif "Embroiderer" in course_name or "Embroidery" in course_name:
                    target_occupations = [
                        "कढ़ाई",
                        "कसीदाकारी",
                        "embroidery",
                        "needlework",
                    ]
                elif "Mason" in course_name:
                    target_occupations = ["राजमिस्त्री", "मेसन", "masonry", "construction"]
                elif "Electrician" in course_name or "Electrical" in course_name:
                    target_occupations = ["इलेक्ट्रीशियन", "विद्युत", "electrical", "wiring"]
                elif "Beauty" in course_name or "Beautician" in course_name:
                    target_occupations = [
                        "ब्यूटीशियन",
                        "ब्यूटी पार्लर",
                        "beauty",
                        "parlor",
                        "makeup",
                    ]
                elif "Mobile" in course_name:
                    target_occupations = [
                        "मोबाइल मरम्मत",
                        "mobile repair",
                        "phone repair",
                    ]
                elif "Solar" in course_name:
                    target_occupations = [
                        "सौर ऊर्जा",
                        "solar",
                        "solar panel",
                        "renewable energy",
                    ]
                elif "Data Entry" in course_name or "IT" in sector:
                    target_occupations = [
                        "कंप्यूटर",
                        "डेटा एंट्री",
                        "computer",
                        "data entry",
                        "typing",
                    ]
                elif "Dairy" in course_name or "Poultry" in course_name:
                    target_occupations = [
                        "डेयरी",
                        "पशुपालन",
                        "poultry",
                        "dairy",
                        "animal husbandry",
                    ]
                else:
                    target_occupations = [course_name.lower()]

                course = {
                    "qp_code": qp_code,
                    "course_name": course_name,
                    "course_name_indic": course_name_indic,
                    "sector": sector,
                    "nsqf_level": nsqf_level,
                    "min_education_tier": min_edu_tier,
                    "is_residential": random.choice(
                        [False, False, False, True]
                    ),  # 75% non-residential
                    "district_availability": [center["district_code"]],
                    "duration_hours": duration,
                    "stipend_per_month": stipend,
                    "course_fee": 0,
                    "training_center": center["name"],
                    "training_center_id": center["center_id"],
                    "training_partners": [center["name"]],
                    "pathway_type": pathway,
                    "target_occupations": target_occupations,
                    "tags": [
                        sector.lower().replace(" ", "_"),
                        center["state"].lower(),
                        center["district_name"].lower(),
                    ],
                    "status": "ACTIVE",
                    "course_embedding": course_embedding,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "gender_preference": "ANY",
                    "age_min": 18,
                    "age_max": 45,
                    "disability_friendly": random.choice([True, False]),
                    "sc_st_reserved_seats": random.randint(5, 15),
                }
                center_courses.append(course)
                courses.append(course)

    # Insert into database
    if courses:
        await db.nsqf_courses.delete_many({})
        await db.nsqf_courses.insert_many(courses)
        # Create indexes
        await db.nsqf_courses.create_index(
            [("qp_code", ASCENDING), ("training_center_id", ASCENDING)], unique=True
        )
        await db.nsqf_courses.create_index([("qp_code", ASCENDING)])
        await db.nsqf_courses.create_index([("district_availability", ASCENDING)])
        await db.nsqf_courses.create_index([("sector", ASCENDING)])
        await db.nsqf_courses.create_index([("status", ASCENDING)])
        await db.nsqf_courses.create_index([("min_education_tier", ASCENDING)])
        await db.nsqf_courses.create_index([("nsqf_level", ASCENDING)])
        await db.nsqf_courses.create_index([("training_center_id", ASCENDING)])
        await db.nsqf_courses.create_index([("target_occupations", ASCENDING)])
        await db.nsqf_courses.create_index(
            [("course_name", TEXT), ("course_name_indic", TEXT)]
        )

    print(f"✅ Created {len(courses)} courses across all training centers")
    return courses


async def seed_beneficiaries(db) -> list[dict]:
    """Create sample beneficiaries for testing."""
    beneficiaries = []

    # Generate 50 sample beneficiaries across districts
    for i in range(50):
        district_code = random.choice(list(DISTRICTS.keys()))
        state, _district_name, blocks = DISTRICTS[district_code]
        block = random.choice(blocks)
        dialect = random.choice(STATE_DIALECTS.get(state, ["hindi_mixed"]))
        education_level = random.choice(EDUCATION_LEVELS)
        education_tier = EDUCATION_TIER_MAP[education_level]

        # Phone number
        phone = f"+91{random.randint(6000000000, 9999999999)}"
        phone_hash, salt = create_phone_hash(phone)

        # Profiling
        trade = random.choice(TRADITIONAL_TRADES)
        activity = random.choice(CURRENT_ACTIVITIES)
        mobility = random.randint(5, 30)
        intent = random.choice(EMPLOYMENT_INTENTS)
        prior_exp = random.choice([True, False])

        beneficiary = {
            "phone_hash": phone_hash,
            "salt": salt,
            "preferred_language": "hi",
            "detected_dialect": dialect,
            "demographics": {
                "district_code": district_code,
                "block_name": block,
                "age_bracket": random.choice(AGE_BRACKETS),
                "education_level": education_level,
                "education_tier": education_tier,
                "caste_category": "SCHEDULED_CASTE",
            },
            "profiling_slots": {
                "traditional_trade": trade,
                "current_activity": activity,
                "mobility_radius_km": mobility,
                "employment_intent": intent,
                "prior_experience": prior_exp,
            },
            "consent_audit": {
                "voice_verified": True,
                "consent_timestamp": datetime.now(timezone.utc),
                "audio_vault_ref": f"s3://pm-ajay-consent/benef_{i:04d}_consent.wav",
                "consent_version": "1.0",
                "language": "hi",
                "purpose": "PM-AJAY Vocational Discovery & Livelihood Scheme Matching",
                "consent_withdrawn": False,
                "withdrawal_timestamp": None,
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "last_call_at": None,
            "total_calls": 0,
            "enrolled_course_qp_codes": [],
            "active_enrollment_id": None,
            "enterprise_details": None,
            "eligible_for_gia_asset_grant": False,
            "credit_desk_routing": None,
            "dpiu_prefill_status": None,
        }
        beneficiaries.append(beneficiary)

    # Insert into database
    if beneficiaries:
        await db.beneficiaries.delete_many({})
        await db.beneficiaries.insert_many(beneficiaries)
        # Create indexes
        await db.beneficiaries.create_index([("phone_hash", ASCENDING)], unique=True)
        await db.beneficiaries.create_index([("demographics.district_code", ASCENDING)])
        await db.beneficiaries.create_index([("detected_dialect", ASCENDING)])
        await db.beneficiaries.create_index([("created_at", ASCENDING)])

    print(f"✅ Created {len(beneficiaries)} sample beneficiaries")
    return beneficiaries


async def seed_kiosks(db) -> list[dict]:
    """Create PM-AJAY kiosks (lightweight access points) at panchayat level."""
    kiosks = []
    kiosk_id = 1

    # Create kiosks in a subset of blocks (not every block)
    for district_code, (state, district_name, blocks) in DISTRICTS.items():
        # Select ~40% of blocks for kiosks
        selected_blocks = random.sample(blocks, k=max(1, int(len(blocks) * 0.4)))

        for block in selected_blocks:
            # 1-2 kiosks per block
            num_kiosks = random.randint(1, 2)
            for j in range(num_kiosks):
                kiosk = {
                    "kiosk_id": f"KIOSK_{kiosk_id:05d}",
                    "name": f"PM-AJAY Kiosk {block} - {j + 1}",
                    "district_code": district_code,
                    "district_name": district_name,
                    "block_name": block,
                    "state": state,
                    "panchayat_name": f"{block} Panchayat",
                    "location_type": random.choice(
                        [
                            "CSC (Common Service Center)",
                            "Panchayat Bhawan",
                            "Library",
                            "Community Hall",
                            "Self Help Group Office",
                        ]
                    ),
                    "address": f"{block} Panchayat Bhawan, {block}, {district_name}, {state}",
                    "pincode": f"{random.randint(100000, 999999)}",
                    "vle_name": f"VLE {random.randint(1000, 9999)}",  # Village Level Entrepreneur
                    "vle_phone": f"+91{random.randint(7000000000, 9999999999)}",
                    "vle_email": f"vle_{kiosk_id}@csc.gov.in",
                    "services": [
                        "PM-AJAY Registration",
                        "Beneficiary Profiling",
                        "Course Information",
                        "Application Assistance",
                        "Document Upload",
                        "Status Tracking",
                        "Voice Assistant Access",
                    ],
                    "equipment": [
                        "Computer",
                        "Webcam",
                        "Microphone",
                        "Speaker",
                        "Printer",
                        "Scanner",
                        "Biometric Device",
                    ],
                    "internet_type": random.choice(["Broadband", "4G Dongle", "VSAT"]),
                    "operating_hours": "9:00 AM - 6:00 PM",
                    "working_days": "Monday - Saturday",
                    "latitude": round(random.uniform(20.0, 30.0), 6)
                    if state
                    in ["Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan"]
                    else round(random.uniform(15.0, 25.0), 6),
                    "longitude": round(random.uniform(75.0, 90.0), 6)
                    if state
                    in ["Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan"]
                    else round(random.uniform(72.0, 88.0), 6),
                    "status": "ACTIVE",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                kiosks.append(kiosk)
                kiosk_id += 1

    if kiosks:
        await db.kiosks.delete_many({})
        await db.kiosks.insert_many(kiosks)
        await db.kiosks.create_index([("district_code", ASCENDING)])
        await db.kiosks.create_index([("block_name", ASCENDING)])
        await db.kiosks.create_index([("status", ASCENDING)])

    print(f"✅ Created {len(kiosks)} PM-AJAY kiosks across districts")
    return kiosks


async def main():
    """Main seeding function."""
    # MongoDB connection
    MONGODB_URL = "mongodb://localhost:27017"
    DATABASE = "pm_ajay"

    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE]

    print("🌱 Starting PM-AJAY mock data seeding...")
    print(
        f"📍 Target: {len(DISTRICTS)} districts across {len({d[0] for d in DISTRICTS.values()})} states"
    )

    # Seed data
    training_centers = await seed_training_centers(db)
    courses = await seed_courses(db, training_centers)
    beneficiaries = await seed_beneficiaries(db)
    kiosks = await seed_kiosks(db)

    # Summary
    print("\n📊 Seeding Summary:")
    print(f"   Training Centers: {len(training_centers)}")
    print(f"   NSQF Courses: {len(courses)}")
    print(f"   Beneficiaries: {len(beneficiaries)}")
    print(f"   Kiosks: {len(kiosks)}")
    print(f"   Districts Covered: {len(DISTRICTS)}")

    # Sector distribution
    sector_counts = {}
    for course in courses:
        sector = course["sector"]
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    print("\n📚 Courses by Sector:")
    for sector, count in sorted(sector_counts.items()):
        print(f"   {sector}: {count}")

    # State distribution
    state_counts = {}
    for center in training_centers:
        state = center["state"]
        state_counts[state] = state_counts.get(state, 0) + 1
    print("\n🏛️  Centers by State:")
    for state, count in sorted(state_counts.items()):
        print(f"   {state}: {count}")

    print("\n✅ Mock data seeding completed successfully!")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
