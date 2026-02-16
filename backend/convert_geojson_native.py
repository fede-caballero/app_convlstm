import json
import math
import os

INPUT_FILE = '/home/f-caballero/UM/TIF3/convLSTM-project/app_convlstm/frontend/public/mendoza_departamentos.geojson'
OUTPUT_FILE = INPUT_FILE # Overwrite

def web_mercator_to_wgs84(x, y):
    lon = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return [lon, lat]

def transform_coords(coords):
    # Depending on geometry type, coords can be nested differently
    # [x, y]
    if len(coords) == 2 and isinstance(coords[0], (int, float)):
        return web_mercator_to_wgs84(coords[0], coords[1])
    # Array of coords
    return [transform_coords(c) for c in coords]

def main():
    print(f"Reading {INPUT_FILE}...")
    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    # Verify CRS
    crs = data.get('crs', {})
    props = crs.get('properties', {})
    name = props.get('name', '')
    
    print(f"Current CRS detected: {name}")
    # Force conversion regardless of name if coordinates look big
    
    # Process features
    for feature in data['features']:
        geom = feature['geometry']
        if geom['coordinates']:
            geom['coordinates'] = transform_coords(geom['coordinates'])
    
    # Update CRS metadata to 4326
    data['crs'] = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    }

    print(f"Writing Converted GeoJSON to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f)
    
    print("Done!")

if __name__ == '__main__':
    main()
