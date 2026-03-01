'use client'

import { useState, useEffect, useMemo, useRef, memo } from "react"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { useToast } from "@/components/ui/use-toast"
import { Play, Pause, RotateCcw, Calendar, Clock, Trash2, MapPin, X, AlertTriangle, Pencil, Plane, Cloud, Layers, Share2, Zap, CloudRain } from "lucide-react"
import { ImageWithBounds, deleteReport, fetchAircraft, fetchHailSwathToday, WeatherReport, Aircraft, StormCell } from "@/lib/api"
import { Source, Layer, NavigationControl, ScaleControl, FullscreenControl, GeolocateControl, MapRef, Popup, Marker } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useAuth } from "@/lib/auth-context"
import { ReportDialog } from "./report-dialog"
import { useLanguage } from "@/lib/language-context"
import dynamic from "next/dynamic"

// Lazy load the Map component. It's huge.
const Map = dynamic(() => import('react-map-gl/maplibre'), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-slate-900 flex items-center justify-center"><div className="w-8 h-8 rounded-full border-4 border-blue-500 border-t-transparent animate-spin"></div></div>
})

interface RadarVisualizationProps {
  inputFiles: ImageWithBounds[]
  predictionFiles: ImageWithBounds[]
  isProcessing: boolean
  reports?: WeatherReport[]
  userLocation?: { lat: number, lon: number } | null
  nearestStorm?: { distance: number, cell: any } | null
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

export const RadarVisualization = memo(function RadarVisualization({
  inputFiles,
  predictionFiles,
  isProcessing = false,
  reports,
  userLocation,
  nearestStorm,
  onReportUpdate
}: RadarVisualizationProps) {
  const { t } = useLanguage()
  const { toast } = useToast()
  const [isPlaying, setIsPlaying] = useState(true)
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [sliderDragValue, setSliderDragValue] = useState<number | null>(null) // visual position while dragging
  const [boundariesData, setBoundariesData] = useState<any>(null)

  // Hail Swath Data
  const [hailSwathData, setHailSwathData] = useState<any>(null)

  // Aircraft State
  const [aircraftData, setAircraftData] = useState<Aircraft[]>([])
  const [selectedAircraft, setSelectedAircraft] = useState<string | null>(null) // callsign tapped on mobile
  // Trail: Map of callsign -> array of [lon, lat] positions (last 30)
  // NOTE: Must use globalThis.Map, because 'Map' is imported from react-map-gl and shadows the native constructor
  const aircraftTrailRef = useRef<globalThis.Map<string, [number, number][]>>(new globalThis.Map())
  const [trailGeoJSON, setTrailGeoJSON] = useState<any>({ type: 'FeatureCollection', features: [] })
  const MAX_TRAIL_POINTS = 70

  const [districtsData, setDistrictsData] = useState<any>(null)
  // Satellite layer state: 'off' | 'hail' | 'visible' | 'ir'
  const [satelliteMode, setSatelliteMode] = useState<'off' | 'hail' | 'visible' | 'ir'>('off')
  const [satelliteEstimTime, setSatelliteEstimTime] = useState<string>("")
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

  // Nearest Storm Locator State
  const [showNearestStormMarker, setShowNearestStormMarker] = useState(false)

  // Zoom scale tracking for dynamic markers
  const [zoomLevel, setZoomLevel] = useState(INITIAL_VIEW_STATE.zoom)

  // Storm Cell Identification State
  const [selectedCell, setSelectedCell] = useState<StormCell | null>(null)

  useEffect(() => {
    if (userLocation) {
      setShowLocationHint(false);
    }
  }, [userLocation]);

  useEffect(() => {
    if (satelliteMode === 'off' || satelliteMode === 'hail') {
      setSatelliteEstimTime("");
      return;
    }
    const updateTime = () => {
      const d = new Date();
      d.setMinutes(d.getMinutes() - 30);
      d.setMinutes(Math.floor(d.getMinutes() / 10) * 10, 0, 0);
      setSatelliteEstimTime("~" + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Argentina/Mendoza' }));
    };
    updateTime();
    const interval = setInterval(updateTime, 60 * 1000);
    return () => clearInterval(interval);
  }, [satelliteMode]);

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

    // Load Mendoza districts
    fetch('/mendoza_departamentos.geojson')
      .then(res => res.json())
      .then(data => setDistrictsData(data))
      .catch(err => console.error("Failed to load districts", err));

    // Load Hail Swath (Today)
    fetchHailSwathToday()
      .then(data => setHailSwathData(data))
      .catch(err => console.error("Failed to load hail swath", err));

    // Poll Aircraft Data
    const pollAircraft = () => {
      fetchAircraft().then((data) => {
        setAircraftData(data);

        // Build GeoJSON from backend trail directly
        const features = data.map((ac: Aircraft) => {
          if (!ac.trail || ac.trail.length < 2) return null;
          return {
            type: 'Feature' as const,
            properties: { callsign: ac.reg || ac.callsign },
            geometry: { type: 'LineString' as const, coordinates: ac.trail }
          };
        }).filter(Boolean);

        setTrailGeoJSON({ type: 'FeatureCollection', features });
      });
    };
    pollAircraft(); // Initial fetch
    const acInterval = setInterval(pollAircraft, 3000); // 3s — smoother trail
    return () => clearInterval(acInterval);
  }, []);

  // Directly update MapLibre source data imperatively (more reliable than prop updates)
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const source = map.getSource('aircraft-trail-source') as any;
    if (source && typeof source.setData === 'function') {
      source.setData(trailGeoJSON);
    }
  }, [trailGeoJSON]);


  // Animation logic
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isPlaying && totalFrames > 0) {
      interval = setInterval(() => {
        setCurrentFrameIndex((prev) => {
          if (prev >= totalFrames - 1) return 0; // Loop back to start
          return prev + 1;
        })
      }, 1500) // 1500ms per frame to allow smooth crossfade
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

  // Calculate center of LAST OBSERVED image for proximity distance
  // Always use the last input image, NOT the current frame (which may be a prediction)
  const lastObservedImage = inputFiles[inputFiles.length - 1];
  const stormCenter = useMemo(() => {
    if (!lastObservedImage?.bounds) return null;
    const b = lastObservedImage.bounds as any;
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
    if (isOffline) {
      const lastInput = inputFiles && inputFiles.length > 0 ? inputFiles[inputFiles.length - 1] : null;
      if (lastInput && lastInput.target_time) {
        return `${t("Radar apagado", "Radar offline")} (Última: ${lastInput.target_time})`;
      }
      return t("Radar apagado", "Radar offline");
    }
    if (!currentImage) return t("Esperando datos del radar...", "Waiting for radar data...");

    if (currentImage.target_time) {
      if (isPrediction) {
        return `${t("Pronóstico", "Forecast")} ${currentImage.target_time}`;
      } else {
        return `${t("Observación", "Observation")} ${currentImage.target_time}`;
      }
    }
    return ""; // Fallback empty
  };

  // --- Offline Check Logic ---
  const isOffline = useMemo(() => {
    // Find the latest INPUT image (observed data)
    if (!inputFiles || inputFiles.length === 0) return false;

    // Sort by timestamp if available to be sure we get the latest
    // Input files are usually sorted chronologically in the prop, but let's be safe or just take the last one
    const latestInput = inputFiles[inputFiles.length - 1];

    if (!latestInput.timestamp_iso) return false; // Can't determine

    try {
      const lastTime = new Date(latestInput.timestamp_iso).getTime();
      const now = new Date().getTime();
      const diffMinutes = (now - lastTime) / (1000 * 60);

      return diffMinutes > 15;
    } catch (e) {
      console.error("Error checking offline status", e);
      return false;
    }
  }, [inputFiles]);

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
      'circle-radius': [
        'interpolate',
        ['linear'],
        ['zoom'],
        7, 3,   // Small at low zoom (away)
        12, 8   // Normal at high zoom (close)
      ],
      'circle-color': [
        'match',
        ['get', 'type'],
        'lluvia_debil', '#60a5fa', // Blue
        'lluvia_fuerte', '#4f46e5', // Indigo
        'granizo_pequeno', '#f97316', // Orange
        'granizo_grande', '#dc2626', // Red
        'viento_fuerte', '#94a3b8', // Slate/Grey
        'cielo_despejado', '#eab308', // Yellow
        '#ffffff' // Default white
      ],
      'circle-stroke-width': [
        'interpolate',
        ['linear'],
        ['zoom'],
        7, 1,
        12, 2
      ],
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

  const districtLineStyle = {
    id: 'districts-line',
    type: 'line' as const,
    paint: {
      'line-color': '#d4d4d8', // Light Gray for districts to contrast with 30dBZ
      'line-width': 1,
      'line-opacity': 0.5,
      'line-dasharray': [2, 2]
    }
  };

  const districtLabelStyle = {
    id: 'districts-label',
    type: 'symbol' as const,
    layout: {
      'text-field': ['get', 'departamen'] as any,
      'text-size': 10,
      'text-transform': 'uppercase' as const,
      'text-offset': [0, 0] as [number, number],
      'symbol-placement': 'point' as const,
      'text-max-width': 8
    },
    paint: {
      'text-color': '#d4d4d8',
      'text-halo-color': '#000000',
      'text-halo-width': 1.5,
      'text-opacity': 0.8
    }
  };

  const handleShare = async () => {
    const timeLabel = getTimeLabel();
    const textStr = t(`🌩️ Mirá la tormenta (${timeLabel}) en vivo desde el radar de HailCast:`, `🌩️ Watch the storm (${timeLabel}) live on HailCast radar:`);
    const urlStr = "https://hail-cast.vercel.app/";

    // Intentar capturar la imagen del mapa
    let fileToShare: File | null = null;
    try {
      const map = mapRef.current?.getMap();
      if (map) {
        // Force a render to ensure WebGL buffer is ready and populated
        const blob = await new Promise<Blob | null>((resolve) => {
          map.once('render', () => {
            map.getCanvas().toBlob(resolve, "image/jpeg", 0.8);
          });
          map.triggerRepaint();
        });
        if (blob) {
          fileToShare = new File([blob], "hailcast-radar.jpg", { type: "image/jpeg" });
        }
      }
    } catch (err) {
      console.warn("Failed to capture map screenshot:", err);
    }

    if (navigator.share) {
      try {
        const shareData: ShareData = {
          title: t('Alerta de Tormenta - HailCast', 'Storm Alert - HailCast'),
          text: textStr,
          url: urlStr,
        };

        // Incluir la imagen si es soportado por el navegador
        if (fileToShare && navigator.canShare && navigator.canShare({ files: [fileToShare] })) {
          shareData.files = [fileToShare];
        }

        await navigator.share(shareData);
        return;
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.warn('Error sharing via Web Share API:', err);
        } else {
          return; // Usuario canceló la acción
        }
      }
    }

    // Fallback to WhatsApp Web/App
    const whatsappUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(textStr + " " + urlStr)}`;
    window.open(whatsappUrl, '_blank');
  };

  return (
    <div className="relative w-full h-full bg-black">
      {/* LCP Optimization: Preload current image */}
      {currentImage && currentImage.url && (
        <link rel="preload" as="image" href={currentImage.url} />
      )}

      {/* Dynamic CSS for MapLibre Geolocate Dot and Storm Cell Markers */}
      <style dangerouslySetInnerHTML={{
        __html: `
        /* Scale the inner visible circles, not the container, to preserve MapLibre's translate(X,Y) positioning */
        .maplibregl-user-location-dot::after,
        .maplibregl-user-location-dot::before {
          transform: scale(${Math.max(0.5, Math.min(2.0, (zoomLevel - 5) / 5))}) !important;
          transition: transform 0.1s ease-out;
        }

        /* Scale storm cell markers based on zoom to avoid cluttering */
        .storm-cell-marker {
          transform: scale(${Math.max(0.4, Math.min(1.5, (zoomLevel - 5) / 4))});
          transition: transform 0.15s ease-out;
        }
        .storm-cell-marker:hover {
          transform: scale(${Math.max(0.4, Math.min(1.5, (zoomLevel - 5) / 4)) * 1.5}) !important;
          z-index: 50;
        }
      `}} />

      <Map
        ref={mapRef}
        initialViewState={INITIAL_VIEW_STATE}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLE}
        // @ts-expect-error react-map-gl doesn't include preserveDrawingBuffer in type definition
        preserveDrawingBuffer={true}
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
            setSelectedCell(null);
          } else {
            setSelectedReport(null);
            setSelectedCell(null);
          }
        }}
        onZoom={() => {
          if (mapRef.current) setZoomLevel(mapRef.current.getZoom());
        }}
        onLoad={() => {
          if (mapRef.current) setZoomLevel(mapRef.current.getZoom());
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
              <span>{t("¿Activar tu ubicación?", "Enable your location?")}</span>
              <MapPin className="h-3 w-3 animate-pulse" />
            </div>
            {/* Arrow pointing right towards the geolocation button */}
            <div className="w-0 h-0 border-t-[6px] border-t-transparent border-l-[8px] border-l-primary border-b-[6px] border-b-transparent drop-shadow-sm"></div>
          </div>
        )}



        {/* Satellite / Layers toggle — icon button below zoom controls (top-right) */}
        <div className="absolute top-[285px] right-2 z-50">
          <button
            onClick={() => setSatelliteMode(m => m === 'off' ? 'hail' : m === 'hail' ? 'visible' : m === 'visible' ? 'ir' : 'off')}
            title={satelliteMode === 'off' ? t('Manga de Granizo', 'Hail Swath') : satelliteMode === 'hail' ? t('Satélite visible', 'Visible satellite') : satelliteMode === 'visible' ? t('Satélite IR', 'IR satellite') : t('Limpiar capas', 'Clear layers')}
            className={`relative flex items-center justify-center w-8 h-8 rounded shadow-lg border transition-all
              ${satelliteMode === 'off'
                ? 'bg-white text-gray-700 border-gray-300 hover:bg-gray-100'
                : satelliteMode === 'hail'
                  ? 'bg-red-800 border-red-600 text-white shadow-red-500/40' // Dark Red for hail
                  : satelliteMode === 'visible'
                    ? 'bg-sky-500 border-sky-300 text-white shadow-sky-500/40'
                    : 'bg-indigo-600 border-indigo-400 text-white shadow-indigo-500/40'
              }`}
          >
            <Layers className="h-4 w-4" />
            {satelliteMode !== 'off' && (
              <span className="absolute -bottom-1 -right-1 text-[8px] font-bold leading-none px-[3px] py-[1px] rounded bg-black/70 text-white">
                {satelliteMode === 'visible' ? 'VIS' : satelliteMode === 'ir' ? 'IR' : 'GRZ'}
              </span>
            )}
          </button>

          {/* Satellite Estimated Timestamp Badge */}
          {(satelliteMode === 'visible' || satelliteMode === 'ir') && satelliteEstimTime && (
            <div className="absolute top-[36px] right-0 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded border border-white/20 whitespace-nowrap shadow-md">
              {satelliteEstimTime}
            </div>
          )}
        </div>

        {/* WhatsApp Share Button */}
        <div className="absolute top-[345px] right-2 z-50">
          <button
            onClick={(e) => { e.stopPropagation(); handleShare(); }}
            title={t("Compartir radar por WhatsApp", "Share radar via WhatsApp")}
            className="flex items-center justify-center w-8 h-8 rounded shadow-lg border transition-all bg-[#25D366] border-[#128C7E] text-white hover:bg-[#128C7E] shadow-[#25D366]/40"
          >
            <Share2 className="h-4 w-4" />
          </button>
        </div>

        {/* Nearest Storm Locator Button */}
        {nearestStorm && (
          <div className="absolute top-[405px] right-2 z-50">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowNearestStormMarker(true);
                mapRef.current?.flyTo({
                  center: [nearestStorm.cell.lon, nearestStorm.cell.lat],
                  zoom: 9,
                  duration: 1500
                });
                toast({
                  title: t("Celda más cercana", "Nearest Cell"),
                  description: t(`Centro convectivo (${nearestStorm.cell.max_dbz.toFixed(0)}dBZ) a ${nearestStorm.distance.toFixed(1)} km`, `Convective core (${nearestStorm.cell.max_dbz.toFixed(0)}dBZ) at ${nearestStorm.distance.toFixed(1)} km`),
                  duration: 5000,
                  className: "bg-white/10 backdrop-blur-md border-white/20 text-white"
                });
              }}
              title={t("Localizar tormenta más cercana (>50dBZ)", "Locate nearest storm (>50dBZ)")}
              className="flex items-center justify-center w-8 h-8 rounded shadow-lg border transition-all bg-red-600 border-red-400 text-white hover:bg-red-500 shadow-red-500/40 relative"
            >
              <Zap className="h-4 w-4 fill-white animate-pulse" />
              {/* Optional distance mini-badge over the button 
              <span className="absolute -bottom-2 -left-2 text-[8px] font-bold px-1 rounded bg-black/80 text-white border border-white/20">
                {nearestStorm.distance.toFixed(0)}k
              </span> */}
            </button>
          </div>
        )}

        {
          boundariesData && (
            <Source id="boundaries-source" type="geojson" data={boundariesData}>
              <Layer {...boundaryLayerStyle} />
            </Source>
          )
        }

        {/* GOES-East Satellite Layer — single WMS image cropped to Mendoza province */}
        {(satelliteMode === 'visible' || satelliteMode === 'ir') && (() => {
          const layerName = satelliteMode === 'visible'
            ? 'GOES-East_ABI_GeoColor'
            : 'GOES-East_ABI_Band13_Clean_Infrared';

          // Mendoza province bbox (EPSG:4326): lon_min, lat_min, lon_max, lat_max
          // Fetching a SINGLE image instead of dozens of tiles → much faster load
          const MZA_BBOX = '-70.6,-37.6,-66.3,-31.9';       // WGS84 corners
          const wmsUrl = [
            'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?',
            'SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap',
            '&FORMAT=image%2Fpng&TRANSPARENT=true',
            `&LAYERS=${layerName}`,
            '&SRS=EPSG%3A4326&STYLES=',
            `&BBOX=${MZA_BBOX}`,
            '&WIDTH=800&HEIGHT=600',
            '&EXCEPTIONS=INIMAGE',
          ].join('');

          // Four corners of Mendoza bbox as [lon, lat] for MapLibre Source type="image"
          const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [
            [-70.6, -31.9], // top-left
            [-66.3, -31.9], // top-right
            [-66.3, -37.6], // bottom-right
            [-70.6, -37.6], // bottom-left
          ];

          return (
            <Source
              key={`satellite-${satelliteMode}`}
              id="satellite-source"
              type="image"
              url={wmsUrl}
              coordinates={coordinates}
            >
              <Layer
                id="satellite-layer"
                type="raster"
                paint={{
                  'raster-opacity': 0.7,
                  'raster-resampling': 'linear',
                }}
                beforeId="aircraft-trail-layer"
              />
            </Source>
          );
        })()}

        {/* Daily Hail Swath (> 55dBZ history) */}
        {satelliteMode === 'hail' && hailSwathData && (
          <Source id="hail-swath-source" type="geojson" data={hailSwathData}>
            <Layer
              id="hail-swath-layer"
              type="circle"
              paint={{
                'circle-color': '#8B0000', // Solid Dark Red
                'circle-radius': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  7, 2,
                  12, 6
                ],
                'circle-opacity': 0.85 // High opacity, no blur for solid look
              }}
            />
          </Source>
        )}

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

        {/* Reports Layer (Crowdsourcing) */}
        {
          reportsGeoJSON && (
            <Source id="reports-source" type="geojson" data={reportsGeoJSON as any}>
              <Layer {...reportLayerStyle as any} />
              {/* Labels disabled for cleaner look, hover tooltip could be better */}
            </Source>
          )
        }

        {/* Nearest Storm Marker (White Dot) */}
        {showNearestStormMarker && nearestStorm && (
          <Marker
            longitude={nearestStorm.cell.lon}
            latitude={nearestStorm.cell.lat}
            anchor="center"
          >
            <div className="relative flex items-center justify-center pointer-events-none">
              <div className="absolute w-6 h-6 bg-white/30 rounded-full animate-ping z-0" />
              <div className="w-3 h-3 bg-white rounded-full border-2 border-black shadow-[0_0_10px_rgba(255,255,255,0.8)] z-10" />
            </div>
          </Marker>
        )}

        {/* Storm Cells Identification Markers */}
        {currentImage?.cells?.map((cell, idx) => {
          const dbz = cell.max_dbz;
          let color = '#3b82f6'; // Blue (Weak)
          if (dbz >= 60) color = '#9333ea'; // Purple (Severe)
          else if (dbz >= 50) color = '#ef4444'; // Red (Hail)
          else if (dbz >= 40) color = '#f97316'; // Orange (Strong)
          else if (dbz >= 30) color = '#eab308'; // Yellow (Moderate)

          return (
            <Marker
              key={`cell-${currentImage.target_time}-${idx}`}
              longitude={cell.lon}
              latitude={cell.lat}
              anchor="center"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                setSelectedCell(cell);
                setSelectedReport(null);
              }}
            >
              <div
                className="storm-cell-marker cursor-pointer w-4 h-4 rounded-full border-2 border-white/80 flex items-center justify-center shadow-lg"
                style={{ backgroundColor: color }}
              >
                {/* Inner dot */}
                <div className="w-1.5 h-1.5 bg-white/50 rounded-full" />
              </div>
            </Marker>
          );
        })}

        {/* Storm Cell Popup */}
        {selectedCell && (
          <Popup
            longitude={selectedCell.lon}
            latitude={selectedCell.lat}
            anchor="bottom"
            onClose={() => setSelectedCell(null)}
            closeOnClick={false}
            className="z-50 dark-popup"
            offset={10}
          >
            <div className="p-3 text-zinc-100 min-w-[150px] flex flex-col gap-1 rounded-md">
              <div className="flex items-center gap-2 border-b border-zinc-700/50 pb-2 mb-1">
                <CloudRain className="w-4 h-4 text-blue-400" />
                <span className="font-bold text-sm uppercase tracking-wide">
                  {t('Núcleo Detectado', 'Detected Core')}
                </span>
              </div>

              <div className="flex items-end gap-1 mt-1">
                <span className="text-2xl font-black text-white leading-none">+{selectedCell.max_dbz.toFixed(0)}</span>
                <span className="text-xs text-zinc-400 font-bold mb-0.5">dBZ</span>
              </div>

              <div className="mt-1 text-sm font-medium">
                {selectedCell.max_dbz >= 60 && (
                  <span className="text-purple-400 drop-shadow-[0_0_5px_rgba(168,85,247,0.5)]">
                    {t('Tormenta Severa', 'Severe Storm')} ⚠️
                  </span>
                )}
                {selectedCell.max_dbz >= 50 && selectedCell.max_dbz < 60 && (
                  <span className="text-red-400 drop-shadow-[0_0_5px_rgba(248,113,113,0.5)]">
                    {t('Probable Granizo', 'Probable Hail')} 🧊
                  </span>
                )}
                {selectedCell.max_dbz >= 40 && selectedCell.max_dbz < 50 && (
                  <span className="text-orange-400">
                    {t('Lluvia Fuerte', 'Heavy Rain')} 🌧️
                  </span>
                )}
                {selectedCell.max_dbz >= 30 && selectedCell.max_dbz < 40 && (
                  <span className="text-yellow-400">
                    {t('Lluvia Moderada', 'Moderate Rain')} 🌦️
                  </span>
                )}
                {selectedCell.max_dbz < 30 && (
                  <span className="text-blue-400">
                    {t('Lluvia Débil', 'Light Rain')} 💧
                  </span>
                )}
              </div>
            </div>
          </Popup>
        )}

        {/* Aircraft Trail Layer — per-callsign color via data-driven MapLibre match */}
        <Source id="aircraft-trail-source" type="geojson" data={trailGeoJSON}>
          <Layer
            id="aircraft-trail-layer"
            type="line"
            paint={{
              'line-color': [
                'match', ['get', 'callsign'],
                'VBCR', '#ffa500',  // Lucha 2 — naranja
                'VBCT', '#00ffff',  // Lucha 3 — cyan
                'VBCU', '#00ff00',  // Lucha 4 — verde
                '#ffffff'           // resto (OpenSky, etc.)
              ] as any,
              'line-width': 1.5,
              'line-opacity': 0.75,
            }}
          />
        </Source>

        {/* Aircraft Layer (TITAN Telemetry + OpenSky) */}
        {(() => {
          const AC_COLORS: Record<string, string> = {
            'VBCR': '#ffa500',
            'VBCT': '#00ffff',
            'VBCU': '#00ff00',
          };
          const getColor = (cs: string) => AC_COLORS[cs] ?? '#ffffff';

          return aircraftData.map((ac) => {
            const color = getColor(ac.callsign);
            const isSelected = selectedAircraft === ac.callsign;
            return (
              <Marker
                key={ac.callsign}
                longitude={ac.lon}
                latitude={ac.lat}
                anchor="center"
              >
                <div
                  className="relative group cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedAircraft(isSelected ? null : ac.callsign);
                  }}
                  style={{ transition: 'transform 0.4s ease' }}
                >
                  {/* Airplane SVG — tip points UP = north = 0°. Rotates with heading. */}
                  <div style={{
                    transform: `rotate(${ac.heading ?? 0}deg)`,
                    color,
                    filter: `drop-shadow(0 0 4px ${color}cc)`,
                    transition: 'transform 0.4s ease',
                  }}>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      width="16" height="16"
                      fill={color}
                      stroke="rgba(0,0,0,0.6)"
                      strokeWidth="1.5"
                    >
                      <circle cx="12" cy="12" r="6" />
                    </svg>
                  </div>

                  {/* Tooltip: visible on hover (desktop) OR when tapped/selected (mobile) */}
                  <div
                    className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 flex flex-col items-center z-50 pointer-events-none"
                    style={{ display: isSelected ? 'flex' : undefined }}
                  >
                    <div
                      className={`bg-black/80 text-xs rounded px-2 py-1 whitespace-nowrap font-mono
                        ${isSelected ? 'flex flex-col' : 'hidden group-hover:flex flex-col'}`}
                      style={{ border: `1px solid ${color}80`, color: '#e5e7eb' }}
                    >
                      <div className="font-bold" style={{ color }}>{ac.reg}</div>
                      <div>Alt: {ac.altitude ? `${Math.round(ac.altitude)}m` : '--'}</div>
                      <div>Vel: {ac.velocity ? `${Math.round(ac.velocity * 1.94)}kt` : '--'}</div>
                      {ac.source === 'titan' && <div className="text-yellow-400 text-[10px]">● TITAN</div>}
                    </div>
                    <div
                      className={`w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent
                        ${isSelected ? 'block' : 'hidden group-hover:block'}`}
                      style={{ borderTopColor: `${color}80` }}
                    />
                  </div>
                </div>
              </Marker>
            );
          });
        })()}

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
                        title={t("Editar Reporte", "Edit Report")}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                    )}
                    {user?.role === 'admin' && (
                      <button
                        onClick={async () => {
                          if (confirm(t("¿Eliminar este reporte permanentemente?", "Permanently delete this report?"))) {
                            try {
                              await deleteReport(selectedReport.properties.id, token!);
                              if (onReportUpdate) onReportUpdate();
                              setSelectedReport(null);
                            } catch (e) {
                              alert(t("Error al eliminar", "Error deleting"));
                            }
                          }
                        }}
                        className="text-red-500 hover:text-red-400 p-1"
                        title={t("Eliminar Reporte (Admin)", "Delete Report (Admin)")}
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

        {districtsData && (
          <Source id="districts" type="geojson" data={districtsData}>
            <Layer {...districtLineStyle} />
            <Layer {...districtLabelStyle} />
          </Source>
        )}

        {/* Unified Timeline Control Bar */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/90 via-black/60 to-transparent pb-8 pt-12">
          <div className="max-w-4xl mx-auto w-full flex flex-col gap-2">

            {/* Time Label & Status */}
            <div className="flex justify-between items-end px-2 mb-1">
              <div className="flex flex-col">
                <span className={`text-xs font-bold uppercase tracking-wider ${isPrediction ? 'text-primary' : 'text-muted-foreground'}`}>
                  {isPrediction ? t('Modelo Predictivo', 'Predictive Model') : t('Datos Observados', 'Observed Data')}
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
                  className="h-10 w-10 rounded-full bg-green-400 text-black hover:bg-green-500 shadow-[0_0_15px_rgba(74,222,128,0.5)]"
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

            {/* Slider Track Container */}
            <div className="relative h-10 flex flex-col justify-center group">

              {/* Custom Track Background (Yellow / Blue Split) */}
              <div className="absolute top-1/2 left-0 right-0 h-1.5 -translate-y-1/2 rounded-full overflow-hidden flex pointer-events-none">
                <div
                  className="h-full bg-yellow-500/20"
                  style={{ width: '22%' }}
                />
                <div
                  className="h-full bg-blue-500/20"
                  style={{ width: '78%' }}
                />
              </div>

              {/* Visual Tick for "Now" */}
              <div
                className="absolute top-1/2 h-3 w-0.5 bg-white/50 -translate-y-1/2 z-0"
                style={{ left: '22%' }}
              />

              {/* The Slider Component */}
              <Slider
                value={[sliderDragValue ?? currentFrameIndex]}
                min={0}
                max={Math.max(0, totalFrames - 1)}
                step={0.01}
                onValueChange={(value) => {
                  // Move thumb smoothly; only switch frame when crossing an integer
                  setIsPlaying(false);
                  setSliderDragValue(value[0]);
                  const rounded = Math.round(value[0]);
                  if (rounded !== currentFrameIndex) setCurrentFrameIndex(rounded);
                }}
                onValueCommit={(value) => {
                  // Commit exact frame on pointer/touch release
                  const rounded = Math.round(value[0]);
                  setCurrentFrameIndex(rounded);
                  setSliderDragValue(null);
                }}
                className={`cursor-pointer z-10 ${isPrediction ? '[&_.bg-primary]:bg-blue-500 [&_.border-primary]:border-blue-500' : '[&_.bg-primary]:bg-yellow-500 [&_.border-primary]:border-yellow-500'}`}
              />

              {/* Labels */}
              <div className="absolute top-full left-0 right-0 mt-1 h-5 text-[10px] sm:text-xs md:text-sm font-sans uppercase tracking-wider text-muted-foreground">
                {/* Past Label */}
                <span className="absolute left-0 text-yellow-500 font-semibold">{t("Pasado", "Past")}</span>

                {/* Now Label (Centered at split) */}
                <span
                  className="absolute -translate-x-1/2 text-white font-bold"
                  style={{ left: '22%' }}
                >
                  {t("ACTUAL", "NOW")}
                </span>

                {/* Future Label */}
                <span className="absolute right-0 text-blue-500 font-semibold">{t("Futuro", "Future")}</span>
              </div>
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
})
