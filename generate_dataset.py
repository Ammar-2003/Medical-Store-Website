import json
import random

SYMPTOMS_POOL = [
    "fever", "headache", "cough", "sore throat", "runny nose",
    "sneezing", "body aches", "fatigue", "nausea", "vomiting",
    "diarrhea", "abdominal pain", "chest congestion",
    "shortness of breath", "dizziness", "loss of appetite"
]

CONDITIONS = [
    ("Common Cold", "Low"),
    ("Flu", "Medium"),
    ("Migraine", "Medium"),
    ("Gastritis", "Medium"),
    ("Food Poisoning", "High"),
    ("Allergy", "Low"),
    ("Bronchitis", "Medium"),
    ("Sinusitis", "Medium"),
    ("Viral Fever", "Medium"),
    ("Muscle Pain", "Low")
]

MEDICINES_POOL = [
    {
        "name": "Paracetamol",
        "purpose": "Fever and pain relief",
        "dosage": "500mg every 6-8 hours",
        "note": "Do not exceed 4000mg per day"
    },
    {
        "name": "Ibuprofen",
        "purpose": "Pain and inflammation",
        "dosage": "200-400mg every 6-8 hours",
        "note": "Take with food"
    },
    {
        "name": "Cetirizine",
        "purpose": "Allergy relief",
        "dosage": "10mg once daily",
        "note": "May cause drowsiness"
    },
    {
        "name": "ORS",
        "purpose": "Rehydration",
        "dosage": "After each loose stool",
        "note": "Essential for dehydration"
    }
]


def generate_entry(i):
    condition, severity = random.choice(CONDITIONS)

    symptoms = random.sample(SYMPTOMS_POOL, random.randint(3, 6))
    medicines = random.sample(MEDICINES_POOL, random.randint(1, 2))

    return {
        "id": i,
        "condition": condition,
        "symptoms": symptoms,
        "description": f"{condition} related symptoms.",
        "severity": severity,
        "medicines": medicines,
        "medicalAdvice": [
            "Rest well",
            "Stay hydrated",
            "Monitor symptoms"
        ],
        "homeRemedies": [
            "Drink warm fluids",
            "Use steam inhalation",
            "Take adequate rest"
        ],
        "warning": "Consult a doctor if symptoms worsen or persist."
    }


def generate_dataset(n=1000):
    return [generate_entry(i) for i in range(1, n + 1)]


if __name__ == "__main__":
    data = generate_dataset(1000)

    with open("dataset.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("✅ dataset.json with 1000 entries created!")