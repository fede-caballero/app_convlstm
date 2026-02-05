"use client"

import { useState, useEffect } from "react"
import { Download, Zap, Clock, MapPin, RefreshCw, AlertCircle, CheckCircle, Folder, Server, Activity, Database, Menu, X } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { RadarVisualization } from "@/components/radar-visualization"
import { AdminCommentBar } from "@/components/admin-comment-bar"
import { fetchImages, fetchStatus, ApiStatus, ApiImages } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import Link from "next/link"

export default function RadarPredictionRealtime() {
  const [status, setStatus] = useState<ApiStatus | null>(null)
  const [images, setImages] = useState<ApiImages>({ input_images: [], prediction_images: [] })
  const [error, setError] = useState<string | null>(null)
  const { user, logout } = useAuth()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

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

  // Adjusted for flat backend status structure
  const bufferSize = status?.files_in_buffer ?? 0
  const bufferMaxSize = status?.files_needed_for_run ?? 8
  const lastPredictionTime = status?.last_update
    ? new Date(status.last_update).toLocaleTimeString()
    : "--:--"

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-black font-sans">

      {/* Full Screen Map */}
      <div className="absolute inset-0 z-0">
        <RadarVisualization
          inputFiles={images.input_images}
          predictionFiles={images.prediction_images}
          isProcessing={!!(status?.status?.includes("PROCESSING") || status?.status?.includes("PREDICTING"))}
        />
      </div>

      {/* Floating Navbar & Alerts - Z-Index Higher than Map */}
      <div className="absolute top-0 left-0 right-0 z-50 p-4 pointer-events-none flex flex-col items-center">

        {/* Admin Alerts Bar */}
        <div className="pointer-events-auto w-full max-w-4xl mb-2">
          <AdminCommentBar />
        </div>

        <div className="max-w-[1600px] w-full mx-auto flex justify-between items-start pointer-events-auto">

          {/* Logo & Title */}


          {/* Right Actions */}
          <div className="flex items-center gap-3">
            {/* System Status Indicator (Admin Only) */}
            {user?.role === 'admin' && (
              <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-black/40 backdrop-blur-md border border-white/10">
                <div className={`w-2 h-2 rounded-full ${status ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
                <span className="text-xs font-mono text-gray-300">
                  {status ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
            )}

            {/* Auth Buttons */}
            {user ? (
              <div className="flex items-center gap-2 bg-black/40 backdrop-blur-md border border-white/10 p-1.5 rounded-xl">
                <span className="text-xs text-gray-300 px-2 hidden sm:inline-block">Hola, {user.username}</span>
                <Button variant="ghost" size="sm" onClick={logout} className="h-8 text-xs hover:bg-white/10 text-white">
                  Salir
                </Button>
              </div>
            ) : (
              <Link href="/login">
                <Button size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg">
                  Ingresar
                </Button>
              </Link>
            )}

            {/* Admin Sidebar Trigger */}
            {user?.role === 'admin' && (
              <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="icon" className="bg-black/40 backdrop-blur-md border-white/10 text-white hover:bg-white/20">
                    <Menu className="h-5 w-5" />
                  </Button>
                </SheetTrigger>
                <SheetContent className="bg-background/95 backdrop-blur-xl border-l border-border w-[400px] sm:w-[540px] overflow-y-auto">
                  <SheetHeader className="mb-6">
                    <SheetTitle className="text-2xl font-bold text-primary">Panel de Control</SheetTitle>
                    <SheetDescription>
                      Estado del sistema y métricas en tiempo real.
                    </SheetDescription>
                  </SheetHeader>

                  <div className="space-y-6">
                    {/* Worker Status */}
                    <MetricCard
                      title="Estado del Worker"
                      icon={<Server className="h-4 w-4 text-muted-foreground" />}
                      value={status?.status ?? "..."}
                      subtext={status?.status}
                      statusColor={status?.status === "IDLE" ? "text-green-600 dark:text-green-400" : "text-blue-600 dark:text-blue-400"}
                    />

                    {/* Buffer Status */}
                    <Card className="bg-card border-border">
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-center">
                          <CardTitle className="text-sm font-medium text-muted-foreground">Buffer de Entrada</CardTitle>
                          <Database className="h-4 w-4 text-muted-foreground" />
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="flex justify-between items-end mb-2">
                          <span className="text-2xl font-bold text-foreground">{bufferSize}</span>
                          <span className="text-xs text-muted-foreground mb-1">/ {bufferMaxSize} frames</span>
                        </div>
                        <Progress value={(bufferSize / bufferMaxSize) * 100} className="h-1 bg-muted" />
                      </CardContent>
                    </Card>

                    {/* Pipeline Steps */}
                    <Card className="bg-card border-border">
                      <CardHeader>
                        <CardTitle className="text-sm font-medium text-muted-foreground">Pipeline Activo</CardTitle>
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
                    <div className="text-center pt-4 border-t border-border">
                      <p className="text-xs text-muted-foreground font-mono">
                        Última actualización: {lastPredictionTime}
                      </p>
                    </div>
                  </div>
                </SheetContent>
              </Sheet>
            )}
          </div>
        </div>
      </div>

      {/* Error Toast (Floating) */}
      {error && (
        <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-50 w-[90%] max-w-md">
          <Alert variant="destructive" className="bg-red-900/80 backdrop-blur-md border-red-500/50 text-white shadow-xl">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}
    </div>
  )
}

function MetricCard({ title, icon, value, subtext, statusColor = "text-slate-100" }: any) {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
          {icon}
        </div>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${statusColor}`}>{value}</div>
        {subtext && <p className="text-xs text-muted-foreground mt-1 truncate">{subtext}</p>}
      </CardContent>
    </Card>
  )
}

function PipelineStep({ label, active, icon }: any) {
  return (
    <div className={`flex items-center justify-between p-2 rounded-lg transition-colors ${active ? 'bg-primary/10 border border-primary/20' : 'bg-transparent'}`}>
      <div className="flex items-center space-x-3">
        <div className={`p-1.5 rounded-md ${active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
          {icon}
        </div>
        <span className={`text-sm ${active ? 'text-primary font-medium' : 'text-muted-foreground'}`}>{label}</span>
      </div>
      {active && <Activity className="h-3 w-3 text-primary animate-pulse" />}
    </div>
  )
}
