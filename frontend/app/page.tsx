"use client"

import { useState, useEffect } from "react"
import { Download, Zap, Clock, MapPin, RefreshCw, AlertCircle, CheckCircle, Folder, Server } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { RadarVisualization } from "@/components/radar-visualization"
import { fetchImages, fetchStatus, ApiStatus, ApiImages } from "@/lib/api"

export default function RadarPredictionRealtime() {
  const [status, setStatus] = useState<ApiStatus | null>(null)
  const [images, setImages] = useState<ApiImages>({ input_images: [], prediction_images: [] })
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      const statusData = await fetchStatus()
      const imagesData = await fetchImages()
      setStatus(statusData)
      setImages(imagesData)
      setError(null)
    } catch (e) {
      setError("Failed to connect to the backend API. Is it running?")
      console.error(e)
    }
  }

  useEffect(() => {
    fetchData() // Fetch data on initial load
    const interval = setInterval(fetchData, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval) // Cleanup on component unmount
  }, [])

  const getStatusColor = (currentStatus: string) => {
    switch (currentStatus) {
      case "IDLE":
        return "bg-green-500"
      case "PROCESSING":
        return "bg-yellow-500"
      case "PREDICTING":
        return "bg-blue-500"
      case "ERROR":
        return "bg-red-500"
      default:
        return "bg-gray-500"
    }
  }

  const getStatusIcon = (currentStatus: string) => {
    switch (currentStatus) {
      case "IDLE":
        return <CheckCircle className="h-4 w-4" />
      case "PROCESSING":
      case "PREDICTING":
        return <RefreshCw className="h-4 w-4 animate-spin" />
      case "ERROR":
        return <AlertCircle className="h-4 w-4" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  const bufferSize = status?.buffer_status?.current_size ?? 0
  const bufferMaxSize = status?.buffer_status?.max_size ?? 12
  const lastPredictionTime = status?.last_prediction?.timestamp
    ? new Date(status.last_prediction.timestamp).toLocaleTimeString()
    : "--:--"

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-100 p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-gray-900">Sistema de Predicción de Radar en Tiempo Real</h1>
          <p className="text-lg text-gray-600">Visualización del pipeline de inferencia convLSTM</p>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Estado del Worker</CardTitle>
              {status ? getStatusIcon(status.status) : <Server className="h-4 w-4 text-gray-400" />}
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{status?.status ?? "Connecting..."}</div>
              <p className="text-xs text-muted-foreground">{status?.message ?? "Attempting to reach backend..."}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Buffer de Entrada</CardTitle>
              <RefreshCw className={`h-4 w-4 ${status?.status.includes("PROCESSING") ? "animate-spin text-blue-600" : "text-gray-400"}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{bufferSize}/{bufferMaxSize}</div>
              <Progress value={(bufferSize / bufferMaxSize) * 100} className="mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Imágenes de Predicción</CardTitle>
              <Zap className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{images.prediction_images.length}</div>
              <p className="text-xs text-muted-foreground">Generadas por el modelo</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Última Predicción</CardTitle>
              <Clock className="h-4 w-4 text-purple-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{lastPredictionTime}</div>
              <p className="text-xs text-muted-foreground">Hora de la última ejecución</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <RadarVisualization
          inputFiles={images.input_images}
          predictionFiles={images.prediction_images}
          isProcessing={status?.status.includes("PROCESSING") || status?.status.includes("PREDICTING")}
        />

        {/* Pipeline Status */}
        <Card>
          <CardHeader>
            <CardTitle>Estado del Pipeline de Procesamiento</CardTitle>
            <CardDescription>Flujo completo: MDV → NetCDF → convLSTM → PNG</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                  <Folder className="h-6 w-6 text-blue-600" />
                </div>
                <h3 className="font-medium">Entrada MDV</h3>
                <p className="text-xs text-gray-600">Monitoreando nuevos archivos</p>
                <Badge variant={status?.status ? "default" : "secondary"}>
                  {status?.status ? "Activo" : "Inactivo"}
                </Badge>
              </div>

              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto">
                  <RefreshCw className="h-6 w-6 text-yellow-600" />
                </div>
                <h3 className="font-medium">Conversión a NetCDF</h3>
                <p className="text-xs text-gray-600">Llenando el buffer de entrada</p>
                <Badge variant={status?.status === "PROCESSING" ? "default" : "secondary"}>
                  {status?.status === "PROCESSING" ? "Procesando" : "En espera"}
                </Badge>
              </div>

              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                  <Zap className="h-6 w-6 text-green-600" />
                </div>
                <h3 className="font-medium">Modelo convLSTM</h3>
                <p className="text-xs text-gray-600">Generando 5 predicciones</p>
                 <Badge variant={status?.status === "PREDICTING" ? "default" : "secondary"}>
                  {status?.status === "PREDICTING" ? "Prediciendo" : "En espera"}
                </Badge>
              </div>

              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mx-auto">
                  <Download className="h-6 w-6 text-purple-600" />
                </div>
                <h3 className="font-medium">Salida de Imágenes</h3>
                <p className="text-xs text-gray-600">Creando archivos PNG</p>
                <Badge variant="default">Listo</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
