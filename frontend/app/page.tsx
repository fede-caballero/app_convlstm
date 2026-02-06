"use client"

import { useState, useEffect } from "react"
import { Download, Zap, Clock, MapPin, RefreshCw, AlertCircle, CheckCircle, Folder, Server, Activity, Database, Menu, X, Navigation } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { RadarVisualization } from "@/components/radar-visualization"
import { AdminCommentBar } from "@/components/admin-comment-bar"
import { fetchImages, fetchStatus, ApiStatus, ApiImages, StormCell } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import Link from "next/link"

function getDistanceFromLatLonInKm(lat1: number, lon1: number, lat2: number, lon2: number) {
  var R = 6371; // Radius of the earth in km
  var dLat = deg2rad(lat2 - lat1);  // deg2rad below
  var dLon = deg2rad(lon2 - lon1);
  var a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2)
    ;
  var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  var d = R * c; // Distance in km
  return d;
}

function deg2rad(deg: number) {
  return deg * (Math.PI / 180)
}

export default function RadarPredictionRealtime() {
  const [status, setStatus] = useState<ApiStatus | null>(null)
  const [images, setImages] = useState<ApiImages>({ input_images: [], prediction_images: [] })
  const [error, setError] = useState<string | null>(null)
  const { user, logout } = useAuth()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  // Geolocation & Storm Logic
  const [userLocation, setUserLocation] = useState<{ lat: number, lon: number } | null>(null)
  const [nearestStorm, setNearestStorm] = useState<{ distance: number, cell: StormCell } | null>(null)
  const [locationError, setLocationError] = useState<string | null>(null)

  useEffect(() => {
    if ("geolocation" in navigator) {
      console.log("Requesting geolocation...");
      navigator.geolocation.getCurrentPosition(
        (position) => {
          console.log("Geolocation success:", position.coords);
          setUserLocation({
            lat: position.coords.latitude,
            lon: position.coords.longitude
          });
        },
        (error) => {
          console.error("Geolocation error:", error);
          let msg = "Ubicación no disponible";
          if (error.code === 1) msg = "Permiso de GPS denegado";
          if (error.code === 2) msg = "Posición no disponible (red/satélite)";
          if (error.code === 3) msg = "Tiempo de espera agotado";
          setLocationError(msg);
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0
        }
      );
    } else {
      console.error("Geolocation not supported by browser");
      setLocationError("Navegador sin soporte GPS");
    }
  }, []);

  // Update nearest storm when images or userLocation changes
  useEffect(() => {
    if (!userLocation) return;

    // Combine cells from latest input (Observed) and latest prediction (Forecast)
    // We prioritize detected cells in the latest Input for immediate reality
    // But also check recent predictions if input is old? Let's stick to latest Input for now to be safe.
    // Or better: Check the LATEST available image (Input or Pred).

    let allCells: StormCell[] = [];

    // Get cells from latest input image
    const lastInput = images.input_images[images.input_images.length - 1];
    if (lastInput?.cells) {
      allCells.push(...lastInput.cells);
    }

    // Get cells from latest prediction frames (to see approaching storms)
    const latestPreds = images.prediction_images;
    latestPreds.forEach(img => {
      if (img.cells) allCells.push(...img.cells);
    });

    if (allCells.length === 0) {
      setNearestStorm(null);
      return;
    }

    let minDist = Infinity;
    let closestCell: StormCell | null = null;

    allCells.forEach(cell => {
      const d = getDistanceFromLatLonInKm(userLocation.lat, userLocation.lon, cell.lat, cell.lon);
      if (d < minDist) {
        minDist = d;
        closestCell = cell;
      }
    });

    if (closestCell) {
      setNearestStorm({
        distance: minDist,
        cell: closestCell
      });
    }

  }, [images, userLocation]);

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
      <div className="absolute top-0 left-0 right-0 z-50 pointer-events-none flex flex-col items-center">

        {/* Storm Proximity Alert */}
        {nearestStorm && (
          <div className="pointer-events-auto w-full max-w-lg mb-2 mt-20 md:mt-4 px-4 animate-in slide-in-from-top-4 fade-in duration-500">
            <Alert className={`${nearestStorm.distance < 10
              ? "bg-red-950/90 border-red-500 text-red-50"
              : nearestStorm.distance < 50
                ? "bg-orange-950/90 border-orange-500 text-orange-50"
                : "bg-green-950/90 border-green-500 text-green-50"
              } backdrop-blur-md shadow-2xl border`}>
              {nearestStorm.distance < 10 ? <AlertCircle className="h-5 w-5 !text-red-400" /> : <Navigation className="h-5 w-5" />}
              <div className="ml-2">
                <AlertTitle className="text-lg font-bold flex justify-between items-center w-full">
                  <span>{nearestStorm.distance < 10 ? "¡ALERTA DE TORMENTA!" : "Proximidad de Tormenta"}</span>
                  <span className="text-2xl font-mono">{nearestStorm.distance.toFixed(1)} km</span>
                </AlertTitle>
                <AlertDescription className="text-sm opacity-90 font-light mt-1">
                  Se detectó un núcleo de <strong>{nearestStorm.cell.type}</strong> ({nearestStorm.cell.max_dbz} dBZ) cerca de su ubicación.
                  {nearestStorm.distance < 10 && " ¡Tome precauciones!"}
                </AlertDescription>
              </div>
            </Alert>
          </div>
        )}

        <div className="w-full max-w-[1700px] mx-auto flex flex-wrap justify-between items-start pointer-events-auto p-4 md:p-6 gap-y-2">

          {/* Logo & Title - Hidden on mobile potentially */}
          <div className="hidden md:block"></div>

          {/* Right Actions: Alerts | Login | Menu */}
          {/* Mobile: Pushed down (mt-24) to sit BELOW the centered Logo */}
          <div className="w-full md:w-auto flex justify-center md:justify-end items-center gap-3 mt-24 md:mt-0">

            {/* Alerts Center (Bell) */}
            <AdminCommentBar />

            {/* System Status Indicator (Admin Only) */}
            {user?.role === 'admin' && (
              <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-black/40 backdrop-blur-md border border-white/10 h-9">
                <div className={`w-2 h-2 rounded-full ${status ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
                <span className="text-xs font-mono text-gray-300">
                  {status ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
            )}

            {/* Auth Buttons */}
            {user ? (
              <div className="flex items-center gap-2 bg-black/40 backdrop-blur-md border border-white/10 p-1.5 rounded-xl">
                {/* Username hidden on small mobile to save space */}
                <span className="text-xs text-gray-300 px-2 hidden sm:inline-block">Hola, {user.username}</span>
                <Button variant="ghost" size="sm" onClick={logout} className="h-6 text-xs hover:bg-white/10 text-white">
                  Salir
                </Button>
              </div>
            ) : (
              <Link href="/login">
                <Button size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg h-9">
                  Ingresar
                </Button>
              </Link>
            )}

            {/* Admin Sidebar Trigger */}
            {user?.role === 'admin' && (
              <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="icon" className="bg-black/40 backdrop-blur-md border-white/10 text-white hover:bg-white/20 h-9 w-9">
                    <Menu className="h-5 w-5" />
                  </Button>
                </SheetTrigger>
                <SheetContent className="bg-background/95 backdrop-blur-xl border-l border-border w-[400px] sm:w-[540px] overflow-y-auto">
                  <SheetHeader className="mb-6">
                    <div className="flex justify-between items-center">
                      <SheetTitle className="text-2xl font-bold text-primary">Panel de Control</SheetTitle>
                      {/* Location Status in Sidebar */}
                      <Badge variant={userLocation ? "outline" : "destructive"}>
                        {userLocation ? "GPS Activo" : "Sin GPS"}
                      </Badge>
                    </div>
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
