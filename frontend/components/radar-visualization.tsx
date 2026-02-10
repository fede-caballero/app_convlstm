'use client'

import { useState, useEffect, useMemo, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Play, Pause, RotateCcw, Calendar, Clock, Trash2, MapPin, X, AlertTriangle, Pencil } from "lucide-react"
import { ImageWithBounds, WeatherReport, deleteReport } from "@/lib/api"
import Map, { Source, Layer, NavigationControl, ScaleControl, FullscreenControl, GeolocateControl, MapRef, Popup } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useAuth } from "@/lib/auth-context"
import { ReportDialog } from "./report-dialog"

interface RadarVisualizationProps {
  inputFiles: ImageWithBounds[]
  predictionFiles: ImageWithBounds[]
  isProcessing: boolean
  reports?: WeatherReport[]
  userLocation?: { lat: number, lon: number } | null
  onReportUpdate?: () => void
}

const INITIAL_VIEW_STATE = {
  longitude: -68.016,
  latitude: -34.647,
  zoom: 8
};

// Dark Matter style for a premium look
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function haversineDistance(coords1: { lat: number, lon: number }, coords2: { lat: number, lon: number }) {
  const toRad = (x: number) => x * Math.PI / 180;
  const R = 6371; // km
  const dLat = toRad(coords2.lat - coords1.lat);
  const dLon = toRad(coords2.lon - coords1.lon);
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(coords1.lat)) * Math.cos(toRad(coords2.lat)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export function RadarVisualization({
  inputFiles,
  predictionFiles,
  isProcessing = false,
  reports,
  userLocation,
  onReportUpdate
}: RadarVisualizationProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [boundariesData, setBoundariesData] = useState<any>(null)
  const [selectedReport, setSelectedReport] = useState<{
    longitude: number,
    latitude: number,
    properties: any
  } | null>(null)
  const [editingReport, setEditingReport] = useState<WeatherReport | null>(null)
  const [isReportOpen, setIsReportOpen] = useState(false)
  const mapRef = useRef<MapRef>(null)
  const { user, token } = useAuth()
  const [showLocationHint, setShowLocationHint] = useState(true)

  useEffect(() => {
    if (userLocation) {
      setShowLocationHint(false);
    }
  }, [userLocation]);

  // Merge frames: Inputs + Predictions
  const frames = useMemo(() => {
    return [...inputFiles, ...predictionFiles];
  }, [inputFiles, predictionFiles]);

  const totalFrames = frames.length;

  // Load boundaries
  useEffect(() => {
    fetch('/boundaries.json')
      .then(res => res.json())
      .then(data => setBoundariesData(data))
      .catch(err => console.error("Failed to load boundaries", err));
  }, []);

  // Animation logic
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isPlaying && totalFrames > 0) {
      interval = setInterval(() => {
        setCurrentFrameIndex((prev) => {
          if (prev >= totalFrames - 1) return 0; // Loop back to start
          return prev + 1;
        })
      }, 2000) // 2000ms per frame (slower for better loading on high latency)
    }
    return () => clearInterval(interval)
  }, [isPlaying, totalFrames])

  // Reset when data changes significantly
  useEffect(() => {
    if (totalFrames > 0 && currentFrameIndex >= totalFrames) {
      setCurrentFrameIndex(0);
    }
  }, [totalFrames]);

  const togglePlay = () => setIsPlaying(!isPlaying)
  const resetAnimation = () => { setIsPlaying(false); setCurrentFrameIndex(0); }

  const currentImage = frames[currentFrameIndex];
  const isPrediction = currentFrameIndex >= inputFiles.length;

  const getImageCoordinates = (image: ImageWithBounds | undefined) => {
    if (!image?.bounds) return undefined;
    const b = image.bounds as any;
    const p1 = b[0];
    const p2 = b[1];

    const minLat = Math.min(p1[0], p2[0]);
    const maxLat = Math.max(p1[0], p2[0]);
    const minLon = Math.min(p1[1], p2[1]);
    const maxLon = Math.max(p1[1], p2[1]);

    return [
      [minLon, maxLat], // TL
      [maxLon, maxLat], // TR
      [maxLon, minLat], // BR
      [minLon, minLat]  // BL
    ] as [[number, number], [number, number], [number, number], [number, number]];
  }

  const imageCoordinates = useMemo(() => getImageCoordinates(currentImage), [currentImage]);

  // Calculate center of current image for distance
  const stormCenter = useMemo(() => {
    if (!currentImage?.bounds) return null;
    const b = currentImage.bounds as any;
    // Assuming bounds are [[lat1, lon1], [lat2, lon2]] or similar based on usage
    // Code above uses p1[0] as lat, p1[1] as lon
    const p1 = b[0];
    const p2 = b[1];
    return {
      lat: (p1[0] + p2[0]) / 2,
      lon: (p1[1] + p2[1]) / 2
    };
  }, [currentImage]);

  const distanceToStorm = useMemo(() => {
    if (!userLocation || !stormCenter) return null;
    return haversineDistance(
      { lat: userLocation.lat, lon: userLocation.lon },
      stormCenter
    );
  }, [userLocation, stormCenter]);



  const boundaryLayerStyle = {
    id: 'boundaries-layer',
    type: 'line',
    paint: {
      'line-color': '#facc15',
      'line-width': 2,
      'line-opacity': 0.6
    }
  } as const;

  // Calculate time label (approximate based on index)
  // Assuming inputs are every 15 min and predictions every 3 min (based on previous context)
  // But for simplicity in UI, we'll just show "Past" vs "Forecast +X min"
  const getTimeLabel = () => {
    if (!currentImage) return "Esperando datos del radar...";

    if (currentImage.target_time) {
      if (isPrediction) {
        return `Pronóstico ${currentImage.target_time}`;
      } else {
        return `Observación ${currentImage.target_time}`;
      }
    }
    return ""; // Fallback empty
  };

  // --- Reports Layer Logic ---
  const reportsGeoJSON = useMemo(() => {
    if (!reports || reports.length === 0) return null;
    return {
      type: "FeatureCollection",
      features: reports.map(r => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [r.longitude, r.latitude] },
        properties: {
          type: r.report_type,
          id: r.id,
          description: r.description,
          username: r.username,
          image_url: r.image_url,
          time: new Date(r.timestamp!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      }))
    };
  }, [reports]);

  const reportLayerStyle = {
    id: 'reports-layer',
    type: 'circle',
    paint: {
      'circle-radius': 8,
      'circle-color': [
        'match',
        ['get', 'type'],
        'lluvia_debil', '#60a5fa', // Blue
        'lluvia_fuerte', '#4f46e5', // Indigo
        'granizo_pequeno', '#f97316', // Orange
        'granizo_grande', '#dc2626', // Red
        'cielo_despejado', '#eab308', // Yellow
        '#ffffff' // Default white
      ],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.9
    }
  } as const;

  // Optional: Text labels for reports
  const reportLabelStyle = {
    id: 'reports-labels',
    type: 'symbol',
    layout: {
      'text-field': ['get', 'type'], // Or use icon if we load sprite
      'text-size': 10,
      'text-offset': [0, 1.5],
      'text-variable-anchor': ['top', 'bottom', 'left', 'right'],
    },
    paint: {
      'text-color': '#ffffff',
      'text-halo-color': '#000000',
      'text-halo-width': 2
    }
  } as const;



  return (
    <div className="relative w-full h-full bg-black">
      <Map
        ref={mapRef}
        initialViewState={INITIAL_VIEW_STATE}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLE}
        attributionControl={false}
        onClick={(event) => {
          const feature = event.features?.[0];
          if (feature && feature.layer.id === 'reports-layer') {
            // Prevent map click from closing immediately if we just clicked a feature
            setSelectedReport({
              longitude: event.lngLat.lng,
              latitude: event.lngLat.lat,
              properties: feature.properties
            });
          } else {
            setSelectedReport(null);
          }
        }}
        interactiveLayerIds={['reports-layer']}
      >
        <NavigationControl position="top-right" style={{ marginTop: '100px', marginRight: '10px' }} />
        <GeolocateControl
          position="top-right"
          style={{ marginRight: '10px' }}
          trackUserLocation={true}
          showUserLocation={true}
        />
        <ScaleControl />
        <FullscreenControl position="top-right" />

        {/* Location Hint Overlay */}
        {showLocationHint && !userLocation && (
          <div
            className="absolute top-[210px] right-[50px] z-50 animate-bounce cursor-pointer flex items-center gap-2"
            onClick={() => setShowLocationHint(false)}
          >
            <div className="bg-primary text-primary-foreground text-xs font-bold px-3 py-1.5 rounded-full shadow-[0_0_15px_rgba(255,255,255,0.3)] flex items-center gap-2 border border-white/20">
              <span>¿Activar tu ubicación?</span>
              <MapPin className="h-3 w-3 animate-pulse" />
            </div>
            {/* Arrow pointing right towards the geolocation button */}
            <div className="w-0 h-0 border-t-[6px] border-t-transparent border-l-[8px] border-l-primary border-b-[6px] border-b-transparent drop-shadow-sm"></div>
          </div>
        )}



        {
          boundariesData && (
            <Source id="boundaries-source" type="geojson" data={boundariesData}>
              <Layer {...boundaryLayerStyle} />
            </Source>
          )
        }

        {/* Reports Layer (Crowdsourcing) */}
        {
          reportsGeoJSON && (
            <Source id="reports-source" type="geojson" data={reportsGeoJSON as any}>
              <Layer {...reportLayerStyle as any} />
              {/* Labels disabled for cleaner look, hover tooltip could be better */}
            </Source>
          )
        }

        {/* Report Popup */}
        {
          selectedReport && (
            <Popup
              longitude={selectedReport.longitude}
              latitude={selectedReport.latitude}
              anchor="bottom"
              onClose={() => setSelectedReport(null)}
              closeOnClick={false}
              className="z-50 dark-popup"
            >
              <div className="p-2 min-w-[200px] max-w-[250px] text-zinc-100">
                {selectedReport.properties.image_url && (
                  <div className="mb-2 rounded-md overflow-hidden h-32 w-full bg-zinc-800 relative">
                    <img
                      src={`${process.env.NEXT_PUBLIC_API_URL || ''}${selectedReport.properties.image_url}`}
                      alt="Reporte"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // Fallback if image fails
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}
                <div className="flex justify-between items-start pr-6">
                  <h3 className="font-bold text-sm uppercase mb-1 text-zinc-100">{selectedReport.properties.type.replace('_', ' ')}</h3>
                  <div className="flex gap-1">
                    {user?.username === selectedReport.properties.username && (
                      <button
                        onClick={() => {
                          const reportToEdit: WeatherReport = {
                            id: selectedReport.properties.id,
                            report_type: selectedReport.properties.type,
                            description: selectedReport.properties.description,
                            image_url: selectedReport.properties.image_url,
                            latitude: selectedReport.latitude,
                            longitude: selectedReport.longitude,
                            username: selectedReport.properties.username
                          };
                          setEditingReport(reportToEdit);
                          setIsReportOpen(true);
                          setSelectedReport(null); // Close popup
                        }}
                        className="text-zinc-400 hover:text-white p-1"
                        title="Editar Reporte"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                    )}
                    {user?.role === 'admin' && (
                      <button
                        onClick={async () => {
                          if (confirm("¿Eliminar este reporte permanentemente?")) {
                            try {
                              await deleteReport(selectedReport.properties.id, token!);
                              if (onReportUpdate) onReportUpdate();
                              setSelectedReport(null);
                            } catch (e) {
                              alert("Error al eliminar");
                            }
                          }
                        }}
                        className="text-red-500 hover:text-red-400 p-1"
                        title="Eliminar Reporte (Admin)"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
                <p className="text-xs text-zinc-400 mb-2">{selectedReport.properties.time} - {selectedReport.properties.username}</p>
                {selectedReport.properties.description && (
                  <p className="text-sm border-t border-zinc-800 pt-2 mt-1 text-zinc-300">{selectedReport.properties.description}</p>
                )}
              </div>
            </Popup>
          )
        }

        {
          currentImage && imageCoordinates && (
            <Source
              id="radar-source"
              type="image"
              url={currentImage.url}
              coordinates={imageCoordinates}
            >
              <Layer
                id="radar-layer"
                type="raster"
                paint={{
                  "raster-opacity": 0.8,
                  "raster-fade-duration": 0
                }}
              />
            </Source>
          )
        }

        {/* Unified Timeline Control Bar */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/90 via-black/60 to-transparent pb-8 pt-12">
          <div className="max-w-4xl mx-auto w-full flex flex-col gap-2">

            {/* Time Label & Status */}
            <div className="flex justify-between items-end px-2 mb-1">
              <div className="flex flex-col">
                <span className={`text-xs font-bold uppercase tracking-wider ${isPrediction ? 'text-primary' : 'text-muted-foreground'}`}>
                  {isPrediction ? 'Modelo Predictivo' : 'Datos Observados'}
                </span>
                <span className="text-2xl font-bold text-white drop-shadow-md flex items-center gap-2 tracking-wide">
                  {isPrediction ? <Clock className="w-6 h-6 text-white" /> : <Calendar className="w-6 h-6 text-white/80" />}
                  {getTimeLabel()}
                </span>
              </div>

              <div className="flex gap-2">
                <Button
                  size="icon"
                  variant="secondary"
                  className="h-10 w-10 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(133,153,51,0.5)]"
                  onClick={togglePlay}
                >
                  {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-1" />}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-10 w-10 rounded-full text-muted-foreground hover:text-foreground hover:bg-white/10"
                  onClick={resetAnimation}
                >
                  <RotateCcw className="h-5 w-5" />
                </Button>
              </div>
            </div>

            {/* Slider Track */}
            <div className="relative h-6 flex items-center group">
              {/* Background Track with "Past" vs "Future" distinction */}
              <div className="absolute inset-x-0 h-1.5 bg-white/10 rounded-full overflow-hidden flex">
                <div
                  className="h-full bg-white/20"
                  style={{ width: `${(inputFiles.length / Math.max(1, totalFrames)) * 100}%` }}
                />
                <div
                  className="h-full bg-primary/20"
                  style={{ width: `${(predictionFiles.length / Math.max(1, totalFrames)) * 100}%` }}
                />
              </div>

              <Slider
                value={[currentFrameIndex]}
                onValueChange={(value) => { setIsPlaying(false); setCurrentFrameIndex(value[0]); }}
                max={Math.max(0, totalFrames - 1)}
                step={1}
                className="cursor-pointer z-10"
              />
            </div>

            {/* Ticks/Labels under slider */}
            <div className="flex justify-between text-[10px] text-muted-foreground px-1 font-mono uppercase tracking-widest">
              <span>Pasado</span>
              <span>Ahora</span>
              <span>Futuro</span>
            </div>

          </div>
        </div>
      </Map >

      {/* Report Dialog */}
      <ReportDialog
        open={isReportOpen}
        onOpenChange={(open) => {
          setIsReportOpen(open);
          if (!open) setEditingReport(null);
        }}
        userLocation={userLocation ?? null}
        existingReport={editingReport}
      />
    </div >
  )
}
