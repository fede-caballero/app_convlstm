"use client"

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Slider } from "@/components/ui/slider"
import { MapPin, Clock, Play, Pause, RotateCcw, ZoomIn, ZoomOut } from "lucide-react"

interface RadarVisualizationProps {
  inputFiles: string[]
  predictionFiles: string[]
  isProcessing: boolean
}

export function RadarVisualization({ inputFiles, predictionFiles, isProcessing }: RadarVisualizationProps) {
  const [animationPlaying, setAnimationPlaying] = useState(false)
  const [currentFrame, setCurrentFrame] = useState(0)
  const [zoomLevel, setZoomLevel] = useState(1)

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

  const handleZoomIn = () => setZoomLevel((prev) => Math.min(prev * 1.2, 5))
  const handleZoomOut = () => setZoomLevel((prev) => Math.max(prev / 1.2, 0.5))

  const currentImage = inputFiles[currentFrame]
  const getTimestampFromUrl = (url: string) => {
    const match = url.match(/INPUT_(\d{8}_\d{6}).png/)
    if (!match) return "N/A"
    const [_, datetime] = match
    const [date, time] = [datetime.slice(0, 8), datetime.slice(9)]
    return `${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)} ${time.slice(0,2)}:${time.slice(2,4)}:${time.slice(4,6)}`
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Visualización de Radar</CardTitle>
        <CardDescription>Datos de entrada del radar y predicciones del modelo.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="original" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="original">Datos de Entrada</TabsTrigger>
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
                  <div className="flex items-center space-x-2">
                    <Button size="sm" variant="outline" onClick={handleZoomOut}><ZoomOut className="h-4 w-4" /></Button>
                    <span className="text-sm font-medium min-w-16 text-center">{Math.round(zoomLevel * 100)}%</span>
                    <Button size="sm" variant="outline" onClick={handleZoomIn}><ZoomIn className="h-4 w-4" /></Button>
                  </div>
                  <Badge variant="outline">Frame {currentFrame + 1}/{inputFiles.length}</Badge>
                </div>

                <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: "500px" }}>
                  <div className="absolute inset-0 flex items-center justify-center" style={{ transform: `scale(${zoomLevel})` }}>
                    {currentImage && <img src={currentImage} alt={`Radar scan ${currentFrame + 1}`} className="max-w-full max-h-full object-contain" />}
                  </div>
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
              <PredictionsView predictions={predictionFiles} zoomLevel={zoomLevel} />
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

function PredictionsView({ predictions, zoomLevel }: { predictions: string[], zoomLevel: number }) {
  const [selectedPrediction, setSelectedPrediction] = useState(0)

  useEffect(() => {
    if (selectedPrediction >= predictions.length) {
      setSelectedPrediction(0)
    }
  }, [predictions, selectedPrediction])

  const currentPredictionImage = predictions[selectedPrediction]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Mostrando predicción T+{selectedPrediction + 1}</p>
      </div>
      <div className="relative bg-black rounded-lg overflow-hidden" style={{ height: "500px" }}>
        <div className="absolute inset-0 flex items-center justify-center" style={{ transform: `scale(${zoomLevel})` }}>
          {currentPredictionImage && <img src={currentPredictionImage} alt={`Prediction T+${selectedPrediction + 1}`} className="max-w-full max-h-full object-contain" />}
        </div>
        <div className="absolute top-4 left-4 bg-black bg-opacity-70 text-white p-2 rounded">
          <p className="text-sm font-medium">Predicción T+{selectedPrediction + 1}</p>
          <p className="text-xs opacity-80">+{(selectedPrediction + 1) * 3} minutos</p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {predictions.map((pred, index) => (
          <div
            key={pred}
            className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
              selectedPrediction === index ? "border-blue-500" : "border-transparent"
            }`}
            onClick={() => setSelectedPrediction(index)}
          >
            <img src={pred} alt={`T+${index + 1}`} className="w-full h-24 object-cover" />
            <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs p-1 text-center">
              T+{index + 1}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
