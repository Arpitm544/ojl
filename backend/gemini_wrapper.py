import google.generativeai as genai

def generate_with_gemini(api_key: str, prompt: str) -> str:
    """Simplified generator using gemini-2.5-flash with model discovery."""
    # Configure the SDK with the user's provided API key
    genai.configure(api_key=api_key)
    
    model_name = "gemini-2.5-flash"
    
    try:
        # Initialize the specific model
        model = genai.GenerativeModel(model_name)
        # Generate content
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        if "404" in str(e):
            # If 404, try to find available models to help the user
            try:
                available = [m.name.replace("models/", "") for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
                raise Exception(f"Model '{model_name}' not found. Available models on your key: {', '.join(available)}")
            except:
                pass
        raise e
