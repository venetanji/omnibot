from langchain_core.tools import tool
import random

weather = {}

@tool
def get_weather(query: str):
    """Call to check real-time weather in a single location."""
    # This is a placeholder, but don't tell the LLM that...
    
    if query in weather:
        return weather[query]
    
    random_temperature = f'{random.randint(10, 40)}°C'
    random_outlook = random.choice(["sunny", "cloudy", "rainy", "snowy"])

    data = {"city": query, "outlook": random_outlook, "temperature": random_temperature}
    weather[query] = data
    
    return data