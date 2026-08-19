import os
from google import genai

# ==========================================================
# CONFIG
# ==========================================================

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    API_KEY = input("Enter your Gemini API key: ").strip()

# Create client
client = genai.Client(api_key=API_KEY)

# ==========================================================
# LIST ALL MODELS
# ==========================================================

print("\n" + "=" * 80)
print("ALL MODELS AVAILABLE TO YOUR API KEY")
print("=" * 80)

try:
    models = list(client.models.list())

    if not models:
        print("No models were returned.")
    else:
        for model in models:
            print(f"\nModel: {model.name}")
            print(f"Display Name: {getattr(model, 'display_name', 'N/A')}")
            print(f"Supported Actions: {getattr(model, 'supported_actions', [])}")

except Exception as e:
    print("\nERROR:")
    print(e)

# ==========================================================
# MODELS THAT SUPPORT generateContent
# ==========================================================

print("\n" + "=" * 80)
print("MODELS YOU CAN USE FOR TEXT GENERATION")
print("=" * 80)

try:
    for model in models:
        actions = getattr(model, "supported_actions", [])

        if "generateContent" in actions:
            print(model.name)

except Exception as e:
    print("\nERROR:")
    print(e)

# ==========================================================
# MODELS THAT SUPPORT EMBEDDINGS
# ==========================================================

print("\n" + "=" * 80)
print("MODELS YOU CAN USE FOR EMBEDDINGS")
print("=" * 80)

try:
    for model in models:
        actions = getattr(model, "supported_actions", [])

        if "embedContent" in actions:
            print(model.name)

except Exception as e:
    print("\nERROR:")
    print(e)