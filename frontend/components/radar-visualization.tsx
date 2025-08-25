"use client"

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { MapPin, Clock, Download, Play, Pause, RotateCcw, ZoomIn, ZoomOut, Layers } from "lucide-react"

interface RadarVisualizationProps {
  uploadedFiles: string[]
  predictions: string[]
  isProcessing: boolean
}

interface RadarLayer {
  id: string
  name: string
  type: "reflectivity" | "velocity" | "composite"
  visible: boolean
  opacity: number
  timestamp: string
  imagePath: string
}

export function RadarVisualization({ uploadedFiles, predictions, isProcessing }: RadarVisualizationProps) {
  const [activeView, setActiveView] = useState<"map" | "composite">("composite")
  const [selectedProduct, setSelectedProduct] = useState("reflectivity")
  const [animationPlaying, setAnimationPlaying] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [radarLayers, setRadarLayers] = useState<RadarLayer[]>([])

  // Simular datos de radar layers
  useEffect(() => {
    if (uploadedFiles.length > 0) {
      const layers: RadarLayer[] = uploadedFiles.map((file, index) => ({
        id: `layer_${index}`,
        name: `Escaneo ${index + 1}`,
        type: "reflectivity",
        visible: index === currentFrame,
        opacity: 0.8,
        timestamp: new Date(Date.now() - (uploadedFiles.length - index) * 300000).toISOString(),
        imagePath: file,
      }))
      setRadarLayers(layers)
    } else {
      setRadarLayers([]); 
    }
  }, [uploadedFiles, currentFrame])

  // Animación automática
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (animationPlaying && radarLayers.length > 0) {
      interval = setInterval(() => {
        setCurrentFrame((prev) => (prev + 1) % radarLayers.length)
      }, 500)
    }
    return () => clearInterval(interval)
  }, [animationPlaying, radarLayers.length])

  const toggleAnimation = () => {
    setAnimationPlaying(!animationPlaying)
  }

  const resetAnimation = () => {
    setAnimationPlaying(false)
    setCurrentFrame(0)
  }

  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(prev * 1.2, 5))
  }

  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(prev / 1.2, 0.5))
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Visualización de Radar</CardTitle>
            <CardDescription>Datos originales vs predicciones del modelo</CardDescription>
          </div>
          <div className="flex items-center space-x-2">
            <Select value={activeView} onValueChange={(value: "map" | "composite") => setActiveView(value)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="composite">Composite</SelectItem>
                <SelectItem value="map">Mapa</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="original" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="original">Datos Originales</TabsTrigger>
            <TabsTrigger value="predictions">Predicciones</TabsTrigger>
          </TabsList>

          <TabsContent value="original" className="space-y-4">
            {uploadedFiles.length > 0 ? (
              <div className="space-y-4">
                {/* Controles de Visualización */}
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <Button size="sm" variant="outline" onClick={toggleAnimation}>
                        {animationPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                      </Button>
                      <Button size="sm" variant="outline" onClick={resetAnimation}>
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium">Producto:</span>
                      <Select value={selectedProduct} onValueChange={setSelectedProduct}>
                        <SelectTrigger className="w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="reflectivity">Reflectividad</SelectItem>
                          <SelectItem value="velocity">Velocidad</SelectItem>
                          <SelectItem value="composite">Composite</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Button size="sm" variant="outline" onClick={handleZoomOut}>
                        <ZoomOut className="h-4 w-4" />
                      </Button>
                      <span className="text-sm font-medium min-w-16 text-center">{Math.round(zoomLevel * 100)}%</span>
                      <Button size="sm" variant="outline" onClick={handleZoomIn}>
                        <ZoomIn className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Badge variant="outline">
                      Frame {currentFrame + 1}/{radarLayers.length}
                    </Badge>
                    <Badge variant="secondary">
                      {radarLayers[currentFrame]?.timestamp
                        ? new Date(radarLayers[currentFrame].timestamp).toLocaleTimeString()
                        : "--:--"}
                    </Badge>
                  </div>
                </div>

                {/* Visualización Principal */}
                {activeView === "composite" ? (
                  <CompositeView
                    layers={radarLayers}
                    currentFrame={currentFrame}
                    zoomLevel={zoomLevel}
                    selectedProduct={selectedProduct}
                  />
                ) : (
                  <MapView layers={radarLayers} currentFrame={currentFrame} selectedProduct={selectedProduct} />
                )}

                {/* Timeline de Frames */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Timeline</span>
                    <span className="text-xs text-gray-500">{radarLayers.length} escaneos cargados</span>
                  </div>
                  <Slider
                    value={[currentFrame]}
                    onValueChange={(value) => setCurrentFrame(value[0])}
                    max={radarLayers.length - 1}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Más antiguo</span>
                    <span>Más reciente</span>
                  </div>
                </div>

                {/* Información del Frame Actual */}
                {radarLayers[currentFrame] && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-blue-50 rounded-lg">
                    <div>
                      <span className="text-sm font-medium text-blue-900">Timestamp</span>
                      <p className="text-sm text-blue-700">
                        {new Date(radarLayers[currentFrame].timestamp).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-blue-900">Producto</span>
                      <p className="text-sm text-blue-700 capitalize">{selectedProduct}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-blue-900">Resolución</span>
                      <p className="text-sm text-blue-700">1km x 1km</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-blue-900">Cobertura</span>
                      <p className="text-sm text-blue-700">240km radio</p>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12">
                <MapPin className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-2 text-gray-600">Carga archivos MDV para visualizar</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="predictions" className="space-y-4">
            {predictions.length > 0 ? (
              <div>
                <Alert className="mb-4">
                  <Clock className="h-4 w-4" />
                  <AlertDescription>Predicciones para los próximos 5 escaneos de radar</AlertDescription>
                </Alert>

                <PredictionsView predictions={predictions} selectedProduct={selectedProduct} zoomLevel={zoomLevel} />
              </div>
            ) : (
              <div className="text-center py-12">
                <Clock className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-2 text-gray-600">
                  {isProcessing ? "Generando predicciones..." : "Ejecuta el modelo para ver predicciones"}
                </p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function CompositeView({
  layers,
  currentFrame,
  zoomLevel,
  selectedProduct,
}: {
  layers: RadarLayer[]
  currentFrame: number
  zoomLevel: number
  selectedProduct: string
}) {
  const currentLayer = layers[currentFrame]

  if (!currentLayer) return null

  return (
    <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: "500px" }}>
      {/* Imagen de Radar */}
      <div className="absolute inset-0 flex items-center justify-center" style={{ transform: `scale(${zoomLevel})` }}>
        <img
          src={currentLayer.imagePath || "/placeholder.svg"}
          alt={`Radar ${selectedProduct} - ${currentLayer.name}`}
          className="max-w-full max-h-full object-contain"
          style={{ opacity: currentLayer.opacity }}
        />
      </div>

      {/* Overlay de Información */}
      <div className="absolute top-4 left-4 bg-black bg-opacity-70 text-white p-2 rounded">
        <p className="text-sm font-medium">{currentLayer.name}</p>
        <p className="text-xs opacity-80">{selectedProduct.toUpperCase()}</p>
      </div>

      {/* Escala de Colores */}
      <div className="absolute bottom-4 right-4 bg-black bg-opacity-70 text-white p-2 rounded">
        <div className="flex items-center space-x-2">
          <div className="w-20 h-4 bg-gradient-to-r from-blue-500 to-red-500 rounded"></div>
          <div className="text-xs">
            <div>70 dBZ</div>
            <div>-10 dBZ</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function MapView({
  layers,
  currentFrame,
  selectedProduct,
}: {
  layers: RadarLayer[]
  currentFrame: number
  selectedProduct: string
}) {
  return (
    <div className="relative bg-gray-100 rounded-lg overflow-hidden" style={{ height: "500px" }}>
      {/* Placeholder para mapa */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <Layers className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <p className="text-gray-600 mb-2">Vista de Mapa</p>
          <p className="text-sm text-gray-500">Integración con Google Maps/Leaflet próximamente</p>
          <Button className="mt-4 bg-transparent" variant="outline">
            <MapPin className="h-4 w-4 mr-2" />
            Configurar Mapa
          </Button>
        </div>
      </div>

      {/* Controles de Capas */}
      <div className="absolute top-4 right-4 bg-white p-3 rounded-lg shadow-lg">
        <h4 className="text-sm font-medium mb-2">Capas</h4>
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <input type="checkbox" id="radar-layer" defaultChecked />
            <label htmlFor="radar-layer" className="text-sm">
              Radar
            </label>
          </div>
          <div className="flex items-center space-x-2">
            <input type="checkbox" id="cities-layer" defaultChecked />
            <label htmlFor="cities-layer" className="text-sm">
              Ciudades
            </label>
          </div>
          <div className="flex items-center space-x-2">
            <input type="checkbox" id="roads-layer" />
            <label htmlFor="roads-layer" className="text-sm">
              Carreteras
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}

function PredictionsView({
  predictions,
  selectedProduct,
  zoomLevel,
}: {
  predictions: string[]
  selectedProduct: string
  zoomLevel: number
}) {
  const [selectedPrediction, setSelectedPrediction] = useState(0)

  return (
    <div className="space-y-4">
      {/* Selector de Predicción */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium">Tiempo futuro:</span>
          <Select
            value={selectedPrediction.toString()}
            onValueChange={(value) => setSelectedPrediction(Number.parseInt(value))}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {predictions.map((_, index) => (
                <SelectItem key={index} value={index.toString()}>
                  T+{index + 1} (15min)
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" variant="outline">
          <Download className="h-4 w-4 mr-2" />
          Descargar
        </Button>
      </div>

      {/* Visualización de Predicción */}
      <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: "500px" }}>
        <div className="absolute inset-0 flex items-center justify-center" style={{ transform: `scale(${zoomLevel})` }}>
          <img
            src={predictions[selectedPrediction] || "/placeholder.svg?height=400&width=400&query=radar prediction"}
            alt={`Predicción T+${selectedPrediction + 1}`}
            className="max-w-full max-h-full object-contain"
          />
        </div>

        {/* Overlay de Información */}
        <div className="absolute top-4 left-4 bg-black bg-opacity-70 text-white p-2 rounded">
          <p className="text-sm font-medium">Predicción T+{selectedPrediction + 1}</p>
          <p className="text-xs opacity-80">+{(selectedPrediction + 1) * 15} minutos</p>
        </div>

        {/* Indicador de Confianza */}
        <div className="absolute top-4 right-4 bg-black bg-opacity-70 text-white p-2 rounded">
          <p className="text-xs">Confianza</p>
          <div className="flex items-center space-x-1 mt-1">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
            <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
            <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
          </div>
        </div>
      </div>

      {/* Grid de Todas las Predicciones */}
      <div className="grid grid-cols-5 gap-2">
        {predictions.map((pred, index) => (
          <div
            key={index}
            className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
              selectedPrediction === index ? "border-blue-500" : "border-gray-200"
            }`}
            onClick={() => setSelectedPrediction(index)}
          >
            <img src={pred || "/placeholder.svg"} alt={`T+${index + 1}`} className="w-full h-20 object-cover" />
            <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-1 text-center">
              T+{index + 1}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
