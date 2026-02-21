import requests
import json

url = "https://opensky-network.org/api/states/all"
params = {
    "icao24": ["e020d2", "e020d4"]
}

try:
    print(f"Buscando aviones E020D2 y E020D4 en OpenSky...")
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        states = data.get("states")
        if states:
            print("¡Encontrados!")
            print(json.dumps(states, indent=2))
        else:
            print("No se encontraron actualmente volando (o con el transponder apagado).")
    else:
        print(f"Error en la API: {response.status_code}")
except Exception as e:
    print(f"Excepción: {e}")
