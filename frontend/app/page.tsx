"use client"

import { useState, useEffect } from "react"
import { Download, Zap, Clock, MapPin, RefreshCw, AlertCircle, CheckCircle, Folder } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Switch } from "@/components/ui/switch"
import { RadarVisualization } from "@/components/radar-visualization"

interface RadarScan {
  id: string
  filename: string
  timestamp: string
  status: "processing" | "ready" | "error"
}

interface Prediction {
  id: string
  timestamp: string
  inputScans: string[]
  outputPath: string
  status: "generating" | "converting" | "ready" | "error"
}

export default function RadarPredictionRealtime() {
  const [isAutoMode, setIsAutoMode] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [buffer, setBuffer] = useState<RadarScan[]>([])
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [watchFolder, setWatchFolder] = useState("/data/radar/netcdf")
  const [modelStatus, setModelStatus] = useState<"idle" | "loading" | "ready" | "error">("ready")
  const [uploadedFiles, setUploadedFiles] = useState<any[]>(
  Array.from({ length: 6 }, (_, i) => 
    `/placeholder.svg?height=300&width=300&query=radar scan ${i + 1}`
  )
)

  // Simular llegada de nuevos archivos netCDF
  useEffect(() => {
    if (!isAutoMode) return

    const interval = setInterval(() => {
      const newScan: RadarScan = {
        id: `scan_${Date.now()}`,
        filename: `radar_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, "")}.nc`,
        timestamp: new Date().toISOString(),
        status: "processing",
      }

      setBuffer((prev) => {
        const updated = [...prev, newScan]
        // Mantener solo los últimos 12 escaneos
        if (updated.length > 12) {
          updated.shift()
        }
        return updated
      })

      // Si tenemos 12 escaneos, ejecutar predicción
      setTimeout(() => {
        setBuffer((prev) => prev.map((scan) => (scan.id === newScan.id ? { ...scan, status: "ready" } : scan)))

        if (buffer.length >= 11) {
          // 11 porque agregamos uno más
          generatePrediction()
        }
      }, 2000)
    }, 8000) // Nuevo escaneo cada 8 segundos

    return () => clearInterval(interval)
  }, [isAutoMode, buffer.length])

  const generatePrediction = () => {
    const newPrediction: Prediction = {
      id: `pred_${Date.now()}`,
      timestamp: new Date().toISOString(),
      inputScans: buffer.slice(-12).map((scan) => scan.filename),
      outputPath: "",
      status: "generating",
    }

    setPredictions((prev) => [newPrediction, ...prev.slice(0, 9)]) // Mantener últimas 10 predicciones

    // Simular proceso de predicción
    setTimeout(() => {
      setPredictions((prev) =>
        prev.map((pred) => (pred.id === newPrediction.id ? { ...pred, status: "converting" } : pred)),
      )
    }, 3000)

    setTimeout(() => {
      setPredictions((prev) =>
        prev.map((pred) =>
          pred.id === newPrediction.id
            ? {
                ...pred,
                status: "ready",
                outputPath: `predictions/pred_${Date.now()}.mdv`,
              }
            : pred,
        ),
      )
    }, 6000)
  }

  const toggleAutoMode = () => {
    setIsAutoMode(!isAutoMode)
    if (!isAutoMode) {
      // Inicializar buffer con algunos escaneos simulados
      const initialScans: RadarScan[] = Array.from({ length: 8 }, (_, i) => ({
        id: `initial_${i}`,
        filename: `radar_initial_${i.toString().padStart(3, "0")}.nc`,
        timestamp: new Date(Date.now() - (8 - i) * 300000).toISOString(), // 5 min intervals
        status: "ready",
      }))
      setBuffer(initialScans)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ready":
        return "bg-green-500"
      case "processing":
        return "bg-yellow-500"
      case "generating":
        return "bg-blue-500"
      case "converting":
        return "bg-purple-500"
      case "error":
        return "bg-red-500"
      default:
        return "bg-gray-500"
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ready":
        return <CheckCircle className="h-4 w-4" />
      case "processing":
        return <RefreshCw className="h-4 w-4 animate-spin" />
      case "generating":
        return <Zap className="h-4 w-4" />
      case "converting":
        return <RefreshCw className="h-4 w-4 animate-spin" />
      case "error":
        return <AlertCircle className="h-4 w-4" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  // Simular algunos archivos cargados para la demo
  useEffect(() => {
    if (isAutoMode && uploadedFiles.length > 0) {
      const mockFiles = Array.from({ length: 6 }, (_, i) => 
        `/placeholder.svg?height=300&width=300&query=radar scan ${i + 1}`
      )
      setUploadedFiles(mockFiles)
    }
  }, [isAutoMode, uploadedFiles.length])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-gray-900">Sistema de Predicción de Radar en Tiempo Real</h1>
          <p className="text-lg text-gray-600">convLSTM con buffer deslizante automático</p>
        </div>

        {/* Control Panel */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Control del Sistema</CardTitle>
                <CardDescription>Configuración del procesamiento automático</CardDescription>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium">Modo Automático</span>
                <Switch checked={isAutoMode} onCheckedChange={toggleAutoMode} />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Carpeta de Monitoreo</label>
                <div className="flex items-center space-x-2">
                  <Folder className="h-4 w-4 text-gray-500" />
                  <span className="text-sm text-gray-600">{watchFolder}</span>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Estado del Modelo</label>
                <div className="flex items-center space-x-2">
                  {getStatusIcon(modelStatus)}
                  <Badge variant={modelStatus === "ready" ? "default" : "secondary"}>
                    {modelStatus === "ready" ? "Listo" : "Cargando"}
                  </Badge>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Buffer Status</label>
                <div className="text-sm">
                  <span className="font-medium">{buffer.length}/12</span> escaneos cargados
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Buffer Actual</CardTitle>
              <RefreshCw className={`h-4 w-4 ${isAutoMode ? "animate-spin text-blue-600" : "text-gray-400"}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{buffer.length}/12</div>
              <Progress value={(buffer.length / 12) * 100} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Predicciones Hoy</CardTitle>
              <Zap className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{predictions.length}</div>
              <p className="text-xs text-muted-foreground">Generadas automáticamente</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Última Predicción</CardTitle>
              <Clock className="h-4 w-4 text-purple-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {predictions.length > 0 ? new Date(predictions[0].timestamp).toLocaleTimeString() : "--:--"}
              </div>
              <p className="text-xs text-muted-foreground">5 escaneos futuros</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Conversiones</CardTitle>
              <Download className="h-4 w-4 text-orange-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{predictions.filter((p) => p.status === "ready").length}</div>
              <p className="text-xs text-muted-foreground">NetCDF → MDV listas</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="space-y-6">
          {/* Radar Visualization - Nueva sección integrada */}
          <RadarVisualization 
            uploadedFiles={[
              "/1.png",
              "/2.png",
              "/3.png",
              "/4.png",
              "/5.png",
            ]}
            predictions={predictions.filter(p => p.status === "ready").map(p => `/placeholder.svg?height=400&width=400&query=radar prediction ${p.id}`)}
            isProcessing={isProcessing}
          />
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Buffer Visualization */}
            <Card>
              <CardHeader>
                <CardTitle>Buffer Deslizante (12 Escaneos)</CardTitle>
                <CardDescription>Secuencia de entrada para el modelo convLSTM</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {buffer.length === 0 ? (
                    <div className="text-center py-8">
                      <MapPin className="mx-auto h-12 w-12 text-gray-400" />
                      <p className="mt-2 text-gray-600">Activar modo automático para comenzar</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {buffer.map((scan, index) => (
                        <div key={scan.id} className="flex items-center space-x-3 p-2 bg-gray-50 rounded-lg">
                          <div className={`w-3 h-3 rounded-full ${getStatusColor(scan.status)}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{scan.filename}</p>
                            <p className="text-xs text-gray-500">{new Date(scan.timestamp).toLocaleTimeString()}</p>
                          </div>
                          <Badge variant="outline" className="text-xs">
                            {index + 1}
                          </Badge>
                        </div>
                      ))}
                      {buffer.length < 12 && (
                        <div className="text-center py-4 border-2 border-dashed border-gray-300 rounded-lg">
                          <p className="text-sm text-gray-500">Esperando {12 - buffer.length} escaneos más...</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Predictions History */}
            <Card>
              <CardHeader>
                <CardTitle>Historial de Predicciones</CardTitle>
                <CardDescription>Predicciones generadas automáticamente</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {predictions.length === 0 ? (
                    <div className="text-center py-8">
                      <Clock className="mx-auto h-12 w-12 text-gray-400" />
                      <p className="mt-2 text-gray-600">No hay predicciones aún</p>
                    </div>
                  ) : (
                    predictions.map((prediction) => (
                      <div key={prediction.id} className="border rounded-lg p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            {getStatusIcon(prediction.status)}
                            <span className="font-medium text-sm">{new Date(prediction.timestamp).toLocaleString()}</span>
                          </div>
                          <Badge variant={prediction.status === "ready" ? "default" : "secondary"}>
                            {prediction.status === "generating" && "Generando"}
                            {prediction.status === "converting" && "Convirtiendo"}
                            {prediction.status === "ready" && "Listo"}
                            {prediction.status === "error" && "Error"}
                          </Badge>
                        </div>

                        <div className="text-xs text-gray-600">
                          <p>Entrada: {prediction.inputScans.length} escaneos</p>
                          {prediction.outputPath && <p>Salida: {prediction.outputPath}</p>}
                        </div>

                        {prediction.status === "ready" && (
                          <div className="flex space-x-2 pt-2">
                            <Button size="sm" variant="outline">
                              <Download className="h-3 w-3 mr-1" />
                              Descargar MDV
                            </Button>
                            <Button size="sm" variant="outline">
                              Ver Predicción
                            </Button>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Pipeline Status */}
        <Card>
          <CardHeader>
            <CardTitle>Estado del Pipeline de Procesamiento</CardTitle>
            <CardDescription>Flujo completo: NetCDF → convLSTM → NetCDF → MDV</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                  <Folder className="h-6 w-6 text-blue-600" />
                </div>
                <h3 className="font-medium">Monitoreo NetCDF</h3>
                <p className="text-xs text-gray-600">Detectar nuevos archivos</p>
                <Badge variant={isAutoMode ? "default" : "secondary"}>{isAutoMode ? "Activo" : "Inactivo"}</Badge>
              </div>

              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                  <Zap className="h-6 w-6 text-green-600" />
                </div>
                <h3 className="font-medium">Modelo convLSTM</h3>
                <p className="text-xs text-gray-600">Predicción 5 escaneos</p>
                <Badge variant="default">Listo</Badge>
              </div>

              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mx-auto">
                  <RefreshCw className="h-6 w-6 text-purple-600" />
                </div>
                <h3 className="font-medium">NcGeneric2Mdv</h3>
                <p className="text-xs text-gray-600">Conversión a MDV</p>
                <Badge variant="default">Disponible</Badge>
              </div>

              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center mx-auto">
                  <Download className="h-6 w-6 text-orange-600" />
                </div>
                <h3 className="font-medium">Salida MDV</h3>
                <p className="text-xs text-gray-600">Para visualización TITAN</p>
                <Badge variant="default">Funcionando</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* System Alerts */}
        {isAutoMode && buffer.length >= 12 && (
          <Alert>
            <CheckCircle className="h-4 w-4" />
            <AlertDescription>
              Sistema automático activo. Buffer completo con 12 escaneos. Las predicciones se generarán automáticamente
              con cada nuevo escaneo.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  )
}
