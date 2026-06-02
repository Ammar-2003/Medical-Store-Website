import json
import os
import re
from typing import List, Dict, Any, Set

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "dataset.json")


COMMON_WORDS = {
    "i", "have", "has", "am", "is", "are", "was", "were",
    "a", "an", "the", "and", "or", "but", "with", "without",
    "my", "me", "mine", "in", "on", "of", "to", "for",
    "from", "since", "very", "much", "feel", "feeling",
    "suffering", "having", "patient", "problem", "issue",
    "symptom", "symptoms",

    # Noisy medical words that can cause wrong matches
    "discomfort",
    "uncomfortable",
    "mild",
    "moderate"
}


SYMPTOM_SYNONYMS = {
    # Headache
    "pain in head": "headache",
    "pain my head": "headache",
    "head pain": "headache",
    "my head hurts": "headache",
    "head hurts": "headache",
    "aching head": "headache",
    "pressure in head": "headache",
    "forehead pain": "headache",

    # Fever
    "high temperature": "fever",
    "temperature": "fever",
    "body hot": "fever",
    "hot body": "fever",
    "feeling hot": "fever",
    "i feel hot": "fever",

    # Chest / heart / breathing
    "chest discomfort": "chest pain",
    "chest heaviness": "chest pain",
    "chest pressure": "chest pain",
    "tight chest": "chest pain",
    "pain in chest": "chest pain",
    "breathing problem": "shortness of breath",
    "difficulty breathing": "shortness of breath",
    "short breath": "shortness of breath",
    "can't breathe": "shortness of breath",
    "cant breathe": "shortness of breath",

    # Cough / cold
    "throat pain": "sore throat",
    "pain in throat": "sore throat",
    "runny nose": "runny nose",
    "blocked nose": "nasal congestion",
    "stuffy nose": "nasal congestion",
    "chest blocked": "chest congestion",
    "chest congestion": "chest congestion",

    # Stomach / digestion
    "stomach pain": "abdominal pain",
    "pain in stomach": "abdominal pain",
    "belly pain": "abdominal pain",
    "tummy pain": "abdominal pain",
    "gas problem": "gas",
    "acid problem": "acidity",
    "heart burn": "heartburn",
    "heartburn": "heartburn",

    # Diarrhea
    "loose motion": "diarrhea",
    "loose motions": "diarrhea",
    "loose stool": "diarrhea",
    "loose stools": "diarrhea",
    "watery stool": "diarrhea",
    "watery stools": "diarrhea",

    # Vomiting / nausea
    "throwing up": "vomiting",
    "throw up": "vomiting",
    "feel vomiting": "nausea",
    "feeling vomiting": "nausea",
    "feeling sick": "nausea",

    # Body pain
    "body pain": "body aches",
    "body ache": "body aches",
    "whole body pain": "body aches",
    "muscle pain": "muscle pain",

    # Legs
    "leg discomfort": "leg pain",
    "legs discomfort": "leg pain",
    "leg pain": "leg pain"
}


def normalize_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def apply_symptom_synonyms(text: str) -> str:
    """
    Converts natural user phrases into dataset-friendly symptom terms.
    Example:
    'I have chest discomfort' -> 'i have chest pain'
    """

    cleaned = normalize_text(text)

    for phrase, replacement in sorted(
        SYMPTOM_SYNONYMS.items(),
        key=lambda item: len(item[0]),
        reverse=True
    ):
        pattern = r"\b" + re.escape(phrase) + r"\b"
        cleaned = re.sub(pattern, replacement, cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def tokenize_text(text: str) -> Set[str]:
    cleaned = normalize_text(text)
    words = cleaned.split()

    return {
        word for word in words
        if len(word) >= 3 and word not in COMMON_WORDS
    }


class LocalMedicalEngine:
    def __init__(self):
        self.dataset = self.load_dataset()

        if not self.dataset:
            raise ValueError("dataset.json is empty or invalid.")

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english"
        )

        self.condition_texts = [
            self.build_condition_text(item) for item in self.dataset
        ]

        self.condition_vectors = self.vectorizer.fit_transform(self.condition_texts)

    def load_dataset(self) -> List[Dict]:
        try:
            with open(DATASET_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("dataset.json must contain a list of conditions.")

            return data

        except FileNotFoundError:
            raise FileNotFoundError(f"dataset.json not found at: {DATASET_PATH}")

        except json.JSONDecodeError:
            raise ValueError("dataset.json contains invalid JSON.")

    def build_condition_text(self, item: Dict) -> str:
        condition = item.get("condition", "")
        symptoms = " ".join(item.get("symptoms", []))
        description = item.get("description", "")

        raw_text = f"{condition} {symptoms} {description}"
        return apply_symptom_synonyms(raw_text)

    def get_condition_key(self, item: Dict) -> str:
        return normalize_text(item.get("condition", "unknown condition"))

    def get_condition_tokens(self, item: Dict) -> Set[str]:
        condition = item.get("condition", "")
        return tokenize_text(apply_symptom_synonyms(condition))

    def get_symptom_tokens(self, item: Dict) -> Set[str]:
        symptoms = " ".join(item.get("symptoms", []))
        return tokenize_text(apply_symptom_synonyms(symptoms))

    def get_all_item_tokens(self, item: Dict) -> Set[str]:
        condition = item.get("condition", "")
        symptoms = " ".join(item.get("symptoms", []))
        description = item.get("description", "")

        return tokenize_text(
            apply_symptom_synonyms(f"{condition} {symptoms} {description}")
        )

    def get_match_details(self, user_tokens: Set[str], item: Dict) -> Dict:
        symptom_tokens = self.get_symptom_tokens(item)
        condition_tokens = self.get_condition_tokens(item)
        all_tokens = self.get_all_item_tokens(item)

        symptom_overlap = user_tokens.intersection(symptom_tokens)
        condition_overlap = user_tokens.intersection(condition_tokens)
        all_overlap = user_tokens.intersection(all_tokens)

        return {
            "symptom_overlap": symptom_overlap,
            "condition_overlap": condition_overlap,
            "all_overlap": all_overlap,
            "symptom_count": len(symptom_overlap),
            "condition_count": len(condition_overlap),
            "all_count": len(all_overlap)
        }

    def calculate_final_score(
        self,
        user_tokens: Set[str],
        item: Dict,
        tfidf_score: float
    ) -> float:
        details = self.get_match_details(user_tokens, item)

        score = tfidf_score

        # Direct symptom matches matter most.
        score += details["symptom_count"] * 0.35

        # Condition name matches matter strongly.
        score += details["condition_count"] * 0.25

        # General text overlap matters slightly.
        score += details["all_count"] * 0.03

        return score

    def normalize_medicine(self, med: Any) -> Dict:
        if isinstance(med, str):
            return {
                "name": med,
                "purpose": "Symptom relief",
                "dosage": "As directed by doctor or pharmacist",
                "note": "Do not self-medicate. Check allergies and consult a healthcare professional."
            }

        if isinstance(med, dict):
            return {
                "name": med.get("name", "Medicine"),
                "purpose": med.get("purpose", "Symptom relief"),
                "dosage": med.get("dosage", "As directed by doctor or pharmacist"),
                "note": med.get("note", "Consult a healthcare professional before use.")
            }

        return {
            "name": "Consult Healthcare Provider",
            "purpose": "Professional medical guidance",
            "dosage": "As prescribed",
            "note": "Medicine information was not available in a valid format."
        }

    def medicine_key(self, med: Dict) -> str:
        return normalize_text(med.get("name", ""))

    def no_match_response(self) -> Dict:
        return {
            "suggestedMedicines": [],
            "medicalAdvice": [
                "Please provide more detailed symptoms.",
                "Mention duration, severity, age, fever, pain location, cough, vomiting, diarrhea, rash, or other symptoms.",
                "Consult a qualified healthcare professional for proper evaluation."
            ],
            "homeRemedies": [
                "Rest",
                "Drink fluids",
                "Monitor symptoms"
            ],
            "warning": "No reliable local medicine suggestion found. Do not self-medicate without professional advice."
        }

    def predict(self, user_symptoms: str) -> Dict:
        cleaned_input = apply_symptom_synonyms(user_symptoms)

        if not cleaned_input:
            return self.no_match_response()

        user_tokens = tokenize_text(cleaned_input)

        if not user_tokens:
            return self.no_match_response()

        input_vector = self.vectorizer.transform([cleaned_input])
        tfidf_scores = cosine_similarity(input_vector, self.condition_vectors)[0]

        # Conditions are used internally only to find the best medicines.
        # Condition names are NOT returned to the frontend.
        MAX_MATCHED_ITEMS = 2
        MAX_MEDICINES = 2
        MIN_FINAL_SCORE = 0.30

        scored_items = []

        for idx, item in enumerate(self.dataset):
            base_score = float(tfidf_scores[idx])
            details = self.get_match_details(user_tokens, item)

            # Must match actual symptom or condition internally.
            if details["symptom_count"] == 0 and details["condition_count"] == 0:
                continue

            final_score = self.calculate_final_score(
                user_tokens=user_tokens,
                item=item,
                tfidf_score=base_score
            )

            if final_score < MIN_FINAL_SCORE:
                continue

            scored_items.append({
                "idx": idx,
                "score": final_score,
                "base_score": base_score,
                "condition_key": self.get_condition_key(item),
                "matched_symptom_count": details["symptom_count"],
                "matched_condition_count": details["condition_count"]
            })

        scored_items.sort(
            key=lambda x: (
                x["matched_condition_count"],
                x["matched_symptom_count"],
                x["score"]
            ),
            reverse=True
        )

        selected_items = []
        seen_conditions = set()

        for scored in scored_items:
            condition_key = scored["condition_key"]

            if condition_key in seen_conditions:
                continue

            selected_items.append(scored)
            seen_conditions.add(condition_key)

            if len(selected_items) >= MAX_MATCHED_ITEMS:
                break

        if not selected_items:
            return self.no_match_response()

        suggested_medicines = []
        medicine_names_seen = set()

        medical_advice = []
        home_remedies = []
        warnings = []

        for scored in selected_items:
            idx = scored["idx"]
            item = self.dataset[idx]

            for med in item.get("medicines", []):
                normalized_med = self.normalize_medicine(med)
                key = self.medicine_key(normalized_med)

                if key and key not in medicine_names_seen:
                    suggested_medicines.append(normalized_med)
                    medicine_names_seen.add(key)

                if len(suggested_medicines) >= MAX_MEDICINES:
                    break

            for advice in item.get("medicalAdvice", []):
                if advice not in medical_advice:
                    medical_advice.append(advice)

            for remedy in item.get("homeRemedies", []):
                if remedy not in home_remedies:
                    home_remedies.append(remedy)

            if item.get("warning") and item["warning"] not in warnings:
                warnings.append(item["warning"])

        return {
            "suggestedMedicines": suggested_medicines[:MAX_MEDICINES],
            "medicalAdvice": medical_advice[:6],
            "homeRemedies": home_remedies[:6],
            "warning": " | ".join(warnings[:2]) if warnings else "Always consult a qualified doctor before taking any medicine."
        }


engine = LocalMedicalEngine()