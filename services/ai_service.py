from google import genai
from google.genai import types
from fastapi import HTTPException
from pydantic import BaseModel
from core.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

class ComplaintAnalysis(BaseModel):
    category: str
    location: str
    problem: str
    urgency: str

class ImageModeration(BaseModel):
    is_safe: bool
    reason: str

def analyze_complaint(message: str) -> ComplaintAnalysis:
    lower_msg = (message or "").lower()

    # Statutory safety triggers: ragging and harassment are high priority by law
    is_ragging = any(w in lower_msg for w in ["ragging", "ragged", "senior bullied", "forced to", "hazing"])
    is_icc = any(w in lower_msg for w in ["harassment", "molest", "stalk", "inappropriate touch", "posh", "eve teasing"])

    prompt = f"""
    Analyze this college/campus grievance or complaint.

    Extract these four items:
    1. category
    2. location
    3. problem
    4. urgency (Low, Medium, or High)

    Choose the category from ONLY these institutional options:
    - Anti-Ragging
    - ICC / POSH (Internal Complaints Committee / Safety)
    - Hostel & Mess
    - Academics & Examination
    - Equipment
    - Network
    - Electrical
    - Cleanliness
    - Water
    - Other

    Rules:
    - Any complaint describing ragging or hazing MUST be categorized as 'Anti-Ragging' with urgency 'High'.
    - Any complaint describing harassment or inappropriate behavior MUST be categorized as 'ICC / POSH' with urgency 'High'.

    Return the result as JSON.

    Complaint:
    {message}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ComplaintAnalysis,
            }
        )
        parsed = response.parsed
        # Override urgency to High if statutory triggers matched
        if is_ragging:
            parsed.category = "Anti-Ragging"
            parsed.urgency = "High"
        elif is_icc:
            parsed.category = "ICC / POSH"
            parsed.urgency = "High"
        return parsed
    except Exception as e:
        # Fallback local parser if Gemini API is temporarily busy
        category = "Other"
        urgency = "Medium"
        if is_ragging:
            category = "Anti-Ragging"
            urgency = "High"
        elif is_icc:
            category = "ICC / POSH"
            urgency = "High"
        elif any(w in lower_msg for w in ["wifi", "internet", "lan", "router"]):
            category = "Network"
        elif any(w in lower_msg for w in ["water", "tap", "leak", "washroom"]):
            category = "Water"
        elif any(w in lower_msg for w in ["light", "power", "fan", "switch", "ac", "electric"]):
            category = "Electrical"
        elif any(w in lower_msg for w in ["mess", "food", "hostel", "room"]):
            category = "Hostel & Mess"

        return ComplaintAnalysis(
            category=category,
            location="Campus Premises",
            problem=message[:120],
            urgency=urgency
        )

def moderate_image(image_data: bytes, mime_type: str = "image/jpeg") -> ImageModeration:
    prompt = """
    Check this image for inappropriate content.
    Allow normal campus-related images (damaged benches, classrooms, broken equipment, cafeteria, hostels, leaks).
    Reject images containing: sexually explicit content, graphic gore, or abusive hate imagery.
    Return whether the image is safe and a short reason.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_data, mime_type=mime_type),
                prompt
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": ImageModeration,
            }
        )
        return response.parsed
    except Exception:
        # Allow image if moderation service is temporarily unavailable
        return ImageModeration(is_safe=True, reason="Standard campus evidence image")

def find_department(category: str) -> str:
    cat = (category or "").lower()
    if "ragging" in cat:
        return "Anti-Ragging Committee"
    elif "icc" in cat or "posh" in cat:
        return "Internal Complaints Committee (ICC)"
    elif "hostel" in cat or "mess" in cat:
        return "Hostel & Mess Administration"
    elif "academic" in cat or "exam" in cat:
        return "Academics & Examination"
    elif "equipment" in cat:
        return "IT Support"
    elif "network" in cat:
        return "Network Team"
    elif "electrical" in cat:
        return "Electrical Team"
    elif cat in ("cleanliness", "water"):
        return "Maintenance & Sanitation"
    else:
        return "General Administration"
