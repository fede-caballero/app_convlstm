'use client'

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Slider } from "@/components/ui/slider"
import { MapPin, Clock, Play, Pause, RotateCcw } from "lucide-react"
import { MapContainer, TileLayer, ImageOverlay } from "react-leaflet"
import { LatLngBoundsExpression } from "leaflet"
import { ImageWithBounds } from "@/lib/api" // Importar la nueva interfaz

interface RadarVisualizationProps {
  inputFiles: ImageWithBounds[]
  predictionFiles: ImageWithBounds[]
  isProcessing: boolean
}

// Coordenadas de San Rafael, Mendoza, Argentina. Temporales hasta que el API las provea.
const MAP_CENTER: [number, number] = [-34.647, -68.016]

export function RadarVisualization({ inputFiles, predictionFiles, isProcessing }: RadarVisualizationProps) {
  const [animationPlaying, setAnimationPlaying] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(0)

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
  const mapBounds = currentImage?.bounds as LatLngBoundsExpression | undefined

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Visualización de Radar</CardTitle>
        <CardDescription>Datos de entrada del radar y predicciones del modelo.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="original" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="original">Datos de Entrada (Mapa Interactivo)</TabsTrigger>
            <TabsTrigger value="predictions">Predicciones</TabsTrigger>
          </TabsList>

          <TabsContent value="original" className="space-y-4">
            {inputFiles.length > 0 ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Button size="sm" variant="outline" onClick={toggleAnimation}>
                      {animationPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </Button>
                    <Button size="sm" variant="outline" onClick={resetAnimation}>
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                  </div>
                  <Badge variant="outline">Frame {currentFrame + 1}/{inputFiles.length}</Badge>
                </div>

                <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: "500px" }}>
                  <MapContainer center={MAP_CENTER} zoom={9} style={{ height: "100%", width: "100%" }}>
                    <TileLayer
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    />
                    {currentImage && mapBounds && (
                      <ImageOverlay
                        url={currentImage.url}
                        bounds={mapBounds}
                        opacity={0.7}
                        zIndex={10}
                      />
                    )}
                  </MapContainer>
                </div>

                <div className="space-y-2">
                   <Slider
                    value={[currentFrame]}
                    onValueChange={(value) => setCurrentFrame(value[0])}
                    max={inputFiles.length > 0 ? inputFiles.length - 1 : 0}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Más antiguo</span>
                    <span>Más reciente</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <MapPin className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-2 text-gray-600">Esperando datos de entrada del backend...</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="predictions" className="space-y-4">
            {predictionFiles.length > 0 ? (
              <PredictionsView predictions={predictionFiles} />
            ) : (
              <div className="text-center py-12">
                <Clock className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-2 text-gray-600">
                  {isProcessing ? "Generando predicciones..." : "No hay predicciones disponibles aún."}
                </p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

// Vista de predicciones con mapa interactivo
function PredictionsView({ predictions }: { predictions: ImageWithBounds[] }) {
  const [selectedPrediction, setSelectedPrediction] = useState(0)

  useEffect(() => {
    if (selectedPrediction >= predictions.length) {
      setSelectedPrediction(0)
    }
  }, [predictions, selectedPrediction])

  const currentPrediction = predictions[selectedPrediction]
  const mapBounds = currentPrediction?.bounds as LatLngBoundsExpression | undefined

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Mostrando predicción T+{selectedPrediction + 1} (+{(selectedPrediction + 1) * 3} min)</p>
      </div>
      <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: "500px" }}>
        <MapContainer center={MAP_CENTER} zoom={9} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          {currentPrediction && mapBounds && (
            <ImageOverlay
              url={currentPrediction.url}
              bounds={mapBounds}
              opacity={0.7}
              zIndex={10}
            />
          )}
        </MapContainer>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {predictions.map((pred, index) => (
          <div
            key={pred.url}
            className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
              selectedPrediction === index ? "border-blue-500" : "border-transparent"
            }`}
            onClick={() => setSelectedPrediction(index)}
          >
            <img src={pred.url} alt={`T+${index + 1}`} className="w-full h-24 object-cover" />
            <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 text-center">
              T+{index + 1}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
