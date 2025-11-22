"use client"

import { useState, useEffect } from "react"
import { Download, Zap, Clock, MapPin, RefreshCw, AlertCircle, CheckCircle, Folder, Server, Activity, Database } from 'lucide-react'
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

  const getStatusIcon = (currentStatus: string) => {
    switch (currentStatus) {
      case "IDLE":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "PROCESSING":
      case "PREDICTING":
        return <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />
      case "ERROR":
        return <AlertCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  const bufferSize = status?.buffer_status?.current_size ?? 0
  const bufferMaxSize = status?.buffer_status?.max_size ?? 12
  const lastPredictionTime = status?.last_prediction?.timestamp
    ? new Date(status.last_prediction.timestamp).toLocaleTimeString()
    : "--:--"

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      <div className="max-w-[1600px] mx-auto space-y-8">

        {/* Header Section */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-6">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              RadarCast AI
            </h1>
            <p className="text-slate-400 text-sm">Sistema de Predicción Meteorológica en Tiempo Real</p>
          </div>
          <div className="flex items-center space-x-4 mt-4 md:mt-0">
            <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800">
              <div className={`w-2 h-2 rounded-full ${status ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
              <span className="text-xs font-mono text-slate-300">
                {status ? "SYSTEM ONLINE" : "DISCONNECTED"}
              </span>
            </div>
          </div>
        </header>

        {error && (
          <Alert variant="destructive" className="bg-red-900/20 border-red-900/50 text-red-200">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* Main Map Visualization Area */}
          <div className="lg:col-span-9 h-[700px]">
            <RadarVisualization
              inputFiles={images.input_images}
              predictionFiles={images.prediction_images}
              isProcessing={status?.status.includes("PROCESSING") || status?.status.includes("PREDICTING")}
            />
          </div>

          {/* Sidebar Metrics */}
          <div className="lg:col-span-3 space-y-4">

            {/* Worker Status */}
            <MetricCard
              title="Estado del Worker"
              icon={<Server className="h-4 w-4 text-slate-400" />}
              value={status?.status ?? "..."}
              subtext={status?.message}
              statusColor={status?.status === "IDLE" ? "text-green-400" : "text-blue-400"}
            />

            {/* Buffer Status */}
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader className="pb-2">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm font-medium text-slate-400">Buffer de Entrada</CardTitle>
                  <Database className="h-4 w-4 text-slate-500" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex justify-between items-end mb-2">
                  <span className="text-2xl font-bold text-slate-100">{bufferSize}</span>
                  <span className="text-xs text-slate-500 mb-1">/ {bufferMaxSize} frames</span>
                </div>
                <Progress value={(bufferSize / bufferMaxSize) * 100} className="h-1 bg-slate-800" />
              </CardContent>
            </Card>

            {/* Pipeline Steps */}
            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-slate-400">Pipeline Activo</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <PipelineStep
                  label="Ingesta MDV"
                  active={!!status?.status}
                  icon={<Folder className="h-3 w-3" />}
                />
                <PipelineStep
                  label="Conversión NetCDF"
                  active={status?.status === "PROCESSING"}
                  icon={<RefreshCw className="h-3 w-3" />}
                />
                <PipelineStep
                  label="Inferencia convLSTM"
                  active={status?.status === "PREDICTING"}
                  icon={<Zap className="h-3 w-3" />}
                />
                <PipelineStep
                  label="Post-procesamiento"
                  active={false} // Usually instant
                  icon={<Download className="h-3 w-3" />}
                />
              </CardContent>
            </Card>

            {/* Last Update */}
            <div className="text-center pt-4">
              <p className="text-xs text-slate-600 font-mono">
                Última actualización: {lastPredictionTime}
              </p>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ title, icon, value, subtext, statusColor = "text-slate-100" }: any) {
  return (
    <Card className="bg-slate-900/50 border-slate-800">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-sm font-medium text-slate-400">{title}</CardTitle>
          {icon}
        </div>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${statusColor}`}>{value}</div>
        {subtext && <p className="text-xs text-slate-500 mt-1 truncate">{subtext}</p>}
      </CardContent>
    </Card>
  )
}

function PipelineStep({ label, active, icon }: any) {
  return (
    <div className={`flex items-center justify-between p-2 rounded-lg transition-colors ${active ? 'bg-blue-900/20 border border-blue-900/50' : 'bg-transparent'}`}>
      <div className="flex items-center space-x-3">
        <div className={`p-1.5 rounded-md ${active ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-500'}`}>
          {icon}
        </div>
        <span className={`text-sm ${active ? 'text-blue-200 font-medium' : 'text-slate-500'}`}>{label}</span>
      </div>
      {active && <Activity className="h-3 w-3 text-blue-400 animate-pulse" />}
    </div>
  )
}
