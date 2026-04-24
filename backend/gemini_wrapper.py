import google.generativeai as genai

def generate_with_gemini(api_key: str, prompt: str) -> str:
    """Simplified generator using gemini-2.0-flash as requested."""
    # Configure the SDK with the user's provided API key
    genai.configure(api_key=api_key)
    
    # Initialize the specific model
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    # Generate content
    response = model.generate_content(prompt)
    
    return response.text
