import json
import math
import os

FILES_TO_PROCESS = [
    '/home/f-caballero/UM/TIF3/convLSTM-project/app_convlstm/frontend/public/distritos-mendoza.geojson',
    '/home/f-caballero/UM/TIF3/convLSTM-project/app_convlstm/frontend/public/localidades.geojson'
]

def web_mercator_to_wgs84(x, y):
    lon = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return [lon, lat]

def transform_coords(coords):
    # Depending on geometry type, coords can be nested differently
    # Point [x, y]
    if len(coords) == 2 and isinstance(coords[0], (int, float)):
        return web_mercator_to_wgs84(coords[0], coords[1])
    # Nested arrays (LineString, Polygon, key checking for recursion)
    return [transform_coords(c) for c in coords]

def process_file(file_path):
    print(f"Reading {file_path}...")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return

    # Verify CRS
    crs = data.get('crs', {})
    props = crs.get('properties', {})
    name = props.get('name', '')
    
    print(f"Current CRS detected for {os.path.basename(file_path)}: {name}")
    
    # Process features
    for feature in data['features']:
        geom = feature['geometry']
        if geom and 'coordinates' in geom:
            geom['coordinates'] = transform_coords(geom['coordinates'])
    
    # Update CRS metadata to 4326
    data['crs'] = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    }

    print(f"Writing Converted GeoJSON to {file_path}...")
    with open(file_path, 'w') as f:
        json.dump(data, f)
    
    print(f"Done with {os.path.basename(file_path)}!\n")

def main():
    for file_path in FILES_TO_PROCESS:
        process_file(file_path)

if __name__ == '__main__':
    main()
