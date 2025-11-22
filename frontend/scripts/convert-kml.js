const fs = require('fs');
const tj = require('@mapbox/togeojson');
const { DOMParser } = require('xmldom');
const path = require('path');

const kmlPath = path.join(__dirname, '../public/Windy2024-25.kml');
const outPath = path.join(__dirname, '../public/boundaries.json');

if (!fs.existsSync(kmlPath)) {
    console.error('KML file not found at:', kmlPath);
    process.exit(1);
}

const kml = new DOMParser().parseFromString(fs.readFileSync(kmlPath, 'utf8'));
const converted = tj.kml(kml);

fs.writeFileSync(outPath, JSON.stringify(converted));
console.log('Converted KML to GeoJSON at:', outPath);
