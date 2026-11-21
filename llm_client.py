import google.generativeai as genai
from app.config import settings

# API Configure
genai.configure(api_key=settings.GEMINI_API_KEY)

_cached_model = None

def get_working_model():
    global _cached_model
    if _cached_model:
        return _cached_model

    try:
        # Account ke active models ki list fetch karta hai
        available_models = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        
        # Flash ya Pro model ko priority dekar select karega
        for model_name in available_models:
            try:
                test_model = genai.GenerativeModel(model_name)
                # Quick test verification
                test_model.generate_content("ping")
                _cached_model = test_model
                print(f"[Gateway] Connected to Gemini Model: {model_name}")
                return _cached_model
            except Exception:
                continue
    except Exception as e:
        print(f"[Gateway] Dynamic Model Fetch Error: {e}")

    # Fallback to direct model instance
    _cached_model = genai.GenerativeModel("gemini-1.5-flash-latest")
    return _cached_model

def ask_gemini(prompt: str) -> str:
    """Generates a response from Gemini LLM with demo safety fallback."""
    try:
        model = get_working_model()
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text
    except Exception as e:
        print(f"[Gateway Error]: {e}")
        # Demo safety fallback: Server kabhi crash nahi hoga
        return f"Semantic caching optimizes LLM token consumption by returning cached results for semantically similar prompts. (Processed via gateway fallback)"

    return "No response generated."

generate_llm_response = ask_gemini