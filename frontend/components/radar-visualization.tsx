'use client'

import { useState, useEffect, useMemo, useRef } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Slider } from "@/components/ui/slider"
import { MapPin, Clock, Play, Pause, RotateCcw, Maximize2, Minimize2 } from "lucide-react"
import { ImageWithBounds } from "@/lib/api"
import Map, { Source, Layer, NavigationControl, ScaleControl, FullscreenControl, MapRef } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

interface RadarVisualizationProps {
  inputFiles: ImageWithBounds[]
  predictionFiles: ImageWithBounds[]
  isProcessing: boolean
}

const INITIAL_VIEW_STATE = {
  longitude: -68.016,
  latitude: -34.647,
  zoom: 8
};

// Dark Matter style for a premium look
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export function RadarVisualization({ inputFiles, predictionFiles, isProcessing }: RadarVisualizationProps) {
  const [animationPlaying, setAnimationPlaying] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [opacity, setOpacity] = useState(0.8)
  const [boundariesData, setBoundariesData] = useState<any>(null)
  const mapRef = useRef<MapRef>(null)

  // Load boundaries
  useEffect(() => {
    fetch('/boundaries.json')
      .then(res => res.json())
      .then(data => setBoundariesData(data))
      .catch(err => console.error("Failed to load boundaries", err));
  }, []);

  // Reset frame when input files change
  useEffect(() => {
    setCurrentFrame(0)
  }, [inputFiles])

  // Animation logic
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (animationPlaying && inputFiles.length > 0) {
      interval = setInterval(() => {
        setCurrentFrame((prev) => (prev + 1) % inputFiles.length)
      }, 500)
    }
    return () => clearInterval(interval)
  }, [animationPlaying, inputFiles.length])

  const toggleAnimation = () => setAnimationPlaying(!animationPlaying)
  const resetAnimation = () => {
    setAnimationPlaying(false)
    setCurrentFrame(0)
  }

  const currentImage = inputFiles[currentFrame]

  const imageCoordinates = useMemo(() => {
    if (!currentImage?.bounds) return undefined;
    const b = currentImage.bounds as any;
    const p1 = b[0]; // [lat, lon]
    const p2 = b[1]; // [lat, lon]

    const minLat = Math.min(p1[0], p2[0]);
    const maxLat = Math.max(p1[0], p2[0]);
    const minLon = Math.min(p1[1], p2[1]);
    const maxLon = Math.max(p1[1], p2[1]);

    // MapLibre expects: Top Left, Top Right, Bottom Right, Bottom Left
    // [lon, lat]
    return [
      [minLon, maxLat], // TL
      [maxLon, maxLat], // TR
      [maxLon, minLat], // BR
      [minLon, minLat]  // BL
    ] as [[number, number], [number, number], [number, number], [number, number]];
  }, [currentImage]);

  const boundaryLayerStyle = {
    id: 'boundaries-layer',
    type: 'line',
    paint: {
      'line-color': '#facc15', // Yellow-400
      'line-width': 2,
      'line-opacity': 0.6
    }
  } as const;

  return (
    <Card className="h-full border-none shadow-none bg-transparent">
      <CardContent className="p-0">
        <Tabs defaultValue="original" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="original">Datos de Entrada (Radar)</TabsTrigger>
            <TabsTrigger value="predictions">Predicciones (Modelo)</TabsTrigger>
          </TabsList>

          <TabsContent value="original" className="space-y-4">
            <div className="relative h-[600px] w-full rounded-xl overflow-hidden border border-gray-800 shadow-2xl">
              <Map
                ref={mapRef}
                initialViewState={INITIAL_VIEW_STATE}
                style={{ width: '100%', height: '100%' }}
                mapStyle={MAP_STYLE}
                attributionControl={false}
              >
                <NavigationControl position="top-right" />
                <ScaleControl />
                <FullscreenControl position="top-right" />

                {boundariesData && (
                  <Source id="boundaries-source" type="geojson" data={boundariesData}>
                    <Layer {...boundaryLayerStyle} />
                  </Source>
                )}

                {currentImage && imageCoordinates && (
                  <Source
                    id="radar-source"
                    type="image"
                    url={currentImage.url}
                    coordinates={imageCoordinates}
                  >
                    <Layer
                      id="radar-layer"
                      type="raster"
                      paint={{ "raster-opacity": opacity, "raster-fade-duration": 0 }}
                    />
                  </Source>
                )}

                {/* Floating Controls */}
                <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 w-[90%] max-w-md">
                  <div className="bg-black/60 backdrop-blur-md border border-white/10 p-4 rounded-2xl text-white shadow-xl">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center space-x-2">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 hover:bg-white/20 text-white"
                          onClick={toggleAnimation}
                        >
                          {animationPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 hover:bg-white/20 text-white"
                          onClick={resetAnimation}
                        >
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="text-sm font-mono text-blue-300">
                        Frame {currentFrame + 1}/{inputFiles.length || 0}
                      </div>
                    </div>

                    <Slider
                      value={[currentFrame]}
                      onValueChange={(value) => {
                        setAnimationPlaying(false);
                        setCurrentFrame(value[0]);
                      }}
                      max={Math.max(0, inputFiles.length - 1)}
                      step={1}
                      className="cursor-pointer"
                    />
                    <div className="flex justify-between mt-2 text-[10px] text-gray-400 uppercase tracking-wider">
                      <span>Pasado</span>
                      <span>Presente</span>
                    </div>
                  </div>
                </div>
              </Map>
            </div>
          </TabsContent>

          <TabsContent value="predictions">
            {predictionFiles.length > 0 ? (
              <div className="space-y-6">
                <PredictionStrip predictions={predictionFiles} />
              </div>
            ) : (
              <EmptyState isProcessing={isProcessing} />
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function PredictionStrip({ predictions }: { predictions: ImageWithBounds[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {predictions.map((pred, idx) => (
        <div key={idx} className="group relative aspect-square bg-gray-900 rounded-xl overflow-hidden border border-gray-800 hover:border-blue-500 transition-all">
          <img src={pred.url} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 to-transparent p-3">
            <p className="text-xs font-bold text-blue-400">T+{idx + 1}</p>
            <p className="text-[10px] text-gray-400">+{(idx + 1) * 15} min</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function EmptyState({ isProcessing }: { isProcessing: boolean }) {
  return (
    <div className="h-[400px] flex flex-col items-center justify-center bg-gray-50/50 rounded-xl border-2 border-dashed border-gray-200">
      <div className={`p-4 rounded-full bg-white shadow-sm mb-4 ${isProcessing ? 'animate-pulse' : ''}`}>
        {isProcessing ? <Clock className="h-8 w-8 text-blue-500 animate-spin" /> : <MapPin className="h-8 w-8 text-gray-300" />}
      </div>
      <h3 className="text-lg font-medium text-gray-900">
        {isProcessing ? "Generando predicciones..." : "Esperando datos"}
      </h3>
      <p className="text-sm text-gray-500 mt-1">
        {isProcessing ? "El modelo está procesando las secuencias" : "Inicia el pipeline para ver resultados"}
      </p>
    </div>
  )
}
