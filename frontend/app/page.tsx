"use client"

import { useState, useEffect } from "react"
import { Download, Zap, Clock, MapPin, RefreshCw, AlertCircle, CheckCircle, Folder, Server, Activity, Database, Menu, X, Navigation, Settings } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { RadarVisualization } from "@/components/radar-visualization"
import { AdminCommentBar } from "@/components/admin-comment-bar"
import { fetchImages, fetchStatus, ApiStatus, ApiImages, StormCell, fetchReports, WeatherReport, updateLocation } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ReportDialog } from "@/components/report-dialog"
import { PushSubscriptionButton } from "@/components/push-subscription-button"
import { TutorialDialog } from "@/components/tutorial-dialog"
import { SettingsDialog } from "@/components/settings-dialog"

import { WeatherSidebar } from "@/components/weather-sidebar"
import Link from "next/link"
import { useLanguage } from "@/lib/language-context"

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
  const { t } = useLanguage()
  const [status, setStatus] = useState<ApiStatus | null>(null)
  const [images, setImages] = useState<ApiImages>({ input_images: [], prediction_images: [] })
  const [error, setError] = useState<string | null>(null)
  const { user, token, logout } = useAuth()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isReportDialogOpen, setIsReportDialogOpen] = useState(false)
  const [isTutorialOpen, setIsTutorialOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [reports, setReports] = useState<WeatherReport[]>([])
  const [showReports, setShowReports] = useState(true)

  // Geolocation & Storm Logic
  const [userLocation, setUserLocation] = useState<{ lat: number, lon: number } | null>(null)
  const [nearestStorm, setNearestStorm] = useState<{ distance: number, cell: StormCell } | null>(null)
  const [locationError, setLocationError] = useState<string | null>(null)
  const [showStormAlert, setShowStormAlert] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  // Geolocation with Fallback Strategy
  useEffect(() => {
    setIsMounted(true)

    // Check Tutorial Status
    const hasSeenTutorial = localStorage.getItem('hasSeenTutorial');
    if (!hasSeenTutorial) {
      setIsTutorialOpen(true);
      localStorage.setItem('hasSeenTutorial', 'true');
    }

    const getLocation = (highAccuracy = true) => {
      if (!("geolocation" in navigator)) {
        setLocationError(t("Navegador sin soporte GPS", "Browser without GPS support"));
        return;
      }

      // console.log(`Requesting geolocation (High Accuracy: ${highAccuracy})...`);

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          // console.log(`Geolocation success (${highAccuracy ? 'High' : 'Low'}):`, position.coords);
          const { latitude, longitude } = position.coords;
          setUserLocation({ lat: latitude, lon: longitude });
          setLocationError(null);

          // Send to Backend if logged in
          if (user && token) {
            try {
              await updateLocation(latitude, longitude, token);
              console.log("Location sent to backend");
            } catch (e) {
              console.error("Failed to send location", e);
            }
          }
        },
        (error) => {
          console.warn(`Geolocation error (${highAccuracy ? 'High' : 'Low'}):`, error.message);

          // Fallback: If High Accuracy fails (Timeout/Error), try Low Accuracy
          if (highAccuracy) {
            console.log("Retrying with Low Accuracy...");
            getLocation(false);
          } else {
            // Final failure
            let msg = t("Ubicación no disponible", "Location unavailable");
            if (error.code === 1) msg = t("Permiso de GPS denegado", "GPS permission denied");
            if (error.code === 3) msg = t("Tiempo de espera agotado (GPS)", "GPS timeout");
            setLocationError(msg);
          }
        },
        {
          enableHighAccuracy: highAccuracy,
          timeout: highAccuracy ? 5000 : 15000,
          maximumAge: highAccuracy ? 0 : 600000
        }
      );
    }

    getLocation(true);

    // Refresh location every 5 minutes
    const intervalId = setInterval(() => getLocation(true), 1000 * 60 * 5);
    return () => clearInterval(intervalId);
  }, [user]); // Re-run if user logs in



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

    if (closestCell && minDist <= 20) {
      setNearestStorm({
        distance: minDist,
        cell: closestCell
      });
    } else {
      setNearestStorm(null);
    }

  }, [images, userLocation]);

  const fetchData = async () => {
    try {
      const statusData = await fetchStatus()
      const imagesData = await fetchImages()
      const reportsData = await fetchReports()
      setStatus(statusData)
      setImages(imagesData)
      setReports(reportsData)
      setError(null)
    } catch (e) {
      setError(t("Error al conectar con el servidor.", "Failed to connect to the backend API. Is it running?"))
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
          reports={showReports ? reports : undefined}
          userLocation={userLocation}
          onReportUpdate={fetchData}
        />

        {/* Weather Sidebar */}
        <WeatherSidebar userLocation={userLocation} />
      </div>

      {/* Floating Navbar & Alerts - Z-Index Higher than Map */}
      <div className="absolute top-0 left-0 right-0 z-50 pointer-events-none flex flex-col items-center">

        {/* TOP BAR: Alerts (Left) -- Login/Menu (Right) */}
        <div className="w-full max-w-[1700px] mx-auto flex justify-between items-center pointer-events-auto p-4 z-50">

          {/* LEFT: Alerts Center */}
          <div className="flex items-center">
            <AdminCommentBar />

            {/* Reports Toggle */}
            <div className="flex items-center gap-2 ml-4 bg-black/40 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-full shadow-sm">
              <Switch
                checked={showReports}
                onCheckedChange={setShowReports}
                className="data-[state=checked]:bg-primary h-5 w-9"
              />
              <span className="text-xs text-gray-300 font-medium ml-1">{t("Reportes", "Reports")}</span>
              <MapPin className={`h-3 w-3 ${showReports ? 'text-primary' : 'text-gray-500'}`} />
            </div>
          </div>

          {/* RIGHT: Status | Auth | Menu */}
          <div className="flex items-center gap-1 sm:gap-2">
            {/* System Status (Admin Only) */}
            {user?.role === 'admin' && (
              <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-black/40 backdrop-blur-md border border-white/10 h-9">
                <div className={`w-2 h-2 rounded-full ${status ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
                <span className="text-xs text-gray-300">
                  {status ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
            )}

            {/* Auth Buttons */}
            {user ? (
              <div className="flex items-center gap-1 sm:gap-2 bg-black/40 backdrop-blur-md border border-white/10 p-1 sm:p-1.5 rounded-xl">
                <span className="text-xs text-gray-300 px-2 hidden sm:inline-block">{t(`Hola, ${user.username}`, `Hello, ${user.username}`)}</span>
                <Button variant="ghost" size="sm" onClick={logout} className="h-6 px-2 text-xs hover:bg-white/10 text-white shrink-0">
                  {t("Salir", "Logout")}
                </Button>
              </div>
            ) : (
              <Link href="/login">
                <Button size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg h-8 sm:h-9 text-xs sm:text-sm px-2 sm:px-3">
                  {t("Ingresar", "Login")}
                </Button>
              </Link>
            )}

            {/* Admin Sidebar Trigger */}
            {user?.role === 'admin' && (
              <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="icon" className="bg-black/40 backdrop-blur-md border-white/10 text-white hover:bg-white/20 h-8 w-8 sm:h-9 sm:w-9 shrink-0">
                    <Menu className="h-4 w-4 sm:h-5 sm:w-5" />
                  </Button>
                </SheetTrigger>
                <SheetContent className="bg-black/80 backdrop-blur-xl border-l border-white/10 w-[400px] sm:w-[540px] overflow-y-auto text-white">
                  <SheetHeader className="mb-6">
                    {/* LOGO IN SIDEBAR */}
                    <div className="flex flex-col items-center justify-center mb-6 pt-4">
                      <img src="/logo.png" alt="Hailcast Logo" className="w-24 h-24 object-contain drop-shadow-lg" />
                      <h2 className="text-xl font-bold mt-2 text-center text-red-500">HAILCAST</h2>
                      <p className="text-xs text-red-200 font-medium bg-red-900/30 px-2 py-0.5 rounded-full mt-1 border border-red-500/20">
                        {t("Sistema de Predicción Meteorológica", "Weather Prediction System")}
                      </p>
                    </div>

                    <div className="flex justify-between items-center bg-red-950/30 p-2 rounded-lg border border-red-500/10">
                      <SheetTitle className="text-xl font-bold text-red-100">{t("Panel de Control", "Control Panel")}</SheetTitle>
                      <Badge variant={userLocation ? "outline" : "destructive"} className="border-red-500/50 text-red-200">
                        {userLocation ? t("GPS Activo", "GPS Active") : t("Sin GPS", "No GPS")}
                      </Badge>
                    </div>
                    <SheetDescription className="text-center mt-2 text-red-300">
                      {t("Métricas y estado del sistema.", "System metrics and status.")}
                    </SheetDescription>
                  </SheetHeader>

                  <div className="space-y-6">
                    {/* Worker Status */}
                    <MetricCard
                      title={t("Estado del Worker", "Worker Status")}
                      icon={<Server className="h-4 w-4" />} // Icon color handled in component
                      value={status?.status ?? "..."}
                      subtext={status?.status}
                      statusColor={status?.status === "IDLE" ? "text-green-400" : "text-blue-400"}
                    />
                    {/* Buffer Status */}
                    <Card className="bg-white/5 border-white/10 text-white">
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-center">
                          <CardTitle className="text-sm font-medium text-red-200">{t("Buffer de Entrada", "Input Buffer")}</CardTitle>
                          <Database className="h-4 w-4 text-red-400" />
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
                    <Card className="bg-white/5 border-white/10 text-white">
                      <CardHeader>
                        <CardTitle className="text-sm font-medium text-red-200">{t("Pipeline Activo", "Active Pipeline")}</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <PipelineStep
                          label={t("Ingesta MDV", "MDV Ingestion")}
                          active={!!status?.status}
                          icon={<Folder className="h-3 w-3" />}
                        />
                        <PipelineStep
                          label={t("Conversión NetCDF", "NetCDF Conversion")}
                          active={status?.status === "PROCESSING"}
                          icon={<RefreshCw className="h-3 w-3" />}
                        />
                        <PipelineStep
                          label={t("Inferencia convLSTM", "convLSTM Inference")}
                          active={status?.status === "PREDICTING"}
                          icon={<Zap className="h-3 w-3" />}
                        />
                        <PipelineStep
                          label={t("Post-procesamiento", "Post-processing")}
                          active={false} // Usually instant
                          icon={<Download className="h-3 w-3" />}
                        />
                      </CardContent>
                    </Card>

                    {/* Last Update */}
                    <div className="text-center pt-4 border-t border-border">
                      <p className="text-xs text-muted-foreground font-mono">
                        {t("Última actualización: ", "Last update: ")}{lastPredictionTime}
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

      {/* Storm Alert Section */}
      {nearestStorm && (
        <div className="absolute bottom-96 left-4 z-50 flex flex-col items-start gap-2">

          {/* Detailed Card (Toggled) */}
          {showStormAlert && (
            <div className="mb-2 ml-14 animate-in fade-in slide-in-from-bottom-2">
              <div className="flex items-center gap-3 px-4 py-3 bg-red-950/90 backdrop-blur-xl text-white rounded-xl shadow-2xl border border-red-500/50 w-64">
                <Zap className="h-8 w-8 text-yellow-400 fill-yellow-400 animate-pulse" />
                <div className="flex flex-col">
                  <span className="text-xs font-bold uppercase tracking-wider text-red-200">{t("Tormenta Detectada", "Storm Detected")}</span>
                  <span className="text-lg font-black tracking-tight">{nearestStorm.distance.toFixed(1)} km</span>
                  <span className="text-[10px] text-red-300">{t("Se recomienda precaución.", "Caution is recommended.")}</span>
                </div>
              </div>
            </div>
          )}

          {/* Toggle Button (Red Circle) */}
          <Button
            onClick={() => setShowStormAlert(!showStormAlert)}
            className={`h-14 w-14 rounded-full shadow-[0_0_20px_rgba(220,38,38,0.6)] border-2 flex flex-col items-center justify-center gap-0.5 transition-all duration-300 ${showStormAlert ? 'bg-white text-red-600 border-white' : 'bg-red-600 hover:bg-red-700 text-white border-red-400/50'}`}
          >
            <Zap className={`h-6 w-6 ${showStormAlert ? 'text-red-600 fill-current' : 'text-yellow-300 fill-yellow-300 animate-pulse'}`} />
            <span className="text-[8px] font-bold uppercase">{showStormAlert ? t('Cerrar', 'Close') : t('Alerta', 'Alert')}</span>
          </Button>
        </div>
      )}

      {/* FAB - Report Button (Bottom Left) */}
      <div className="absolute bottom-80 left-4 z-50">
        <Button
          onClick={() => {
            if (!user) {
              setError(t("Por favor crea una cuenta para reportar.", "Please create an account to report."));
              // Auto-clear error after 3 seconds
              setTimeout(() => setError(null), 3000);
              return;
            }
            setIsReportDialogOpen(true);
          }}
          className="h-14 w-14 rounded-full bg-blue-600 hover:bg-blue-700 shadow-[0_0_20px_rgba(37,99,235,0.5)] border-2 border-blue-400/50 flex flex-col items-center justify-center gap-0.5"
        >
          <AlertCircle className="h-6 w-6 text-white" />
          <span className="text-[9px] font-bold text-white uppercase">{t("Reportar", "Report")}</span>
        </Button>
      </div>

      {/* Push Notifications Switch (Below Report Button) */}
      <div className="absolute bottom-64 left-4 z-50 flex justify-center w-14">
        <div className="bg-black/60 backdrop-blur-md rounded-full p-2 border border-white/10 shadow-lg hover:bg-black/80 transition-all">
          {isMounted && <PushSubscriptionButton onClick={() => setIsSettingsOpen(true)} />}
        </div>
      </div>

      {/* Tutorial / Help Button (Below Push Button) */}
      <div className="absolute bottom-48 left-4 z-50 flex justify-center w-14">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsTutorialOpen(true)}
          className="rounded-full h-12 w-12 bg-black/60 backdrop-blur-md border border-white/10 shadow-lg hover:bg-black/80 text-zinc-400 hover:text-white transition-all"
        >
          <div className="flex flex-col items-center justify-center -space-y-0.5">
            <span className="text-xl font-bold">?</span>
          </div>
        </Button>
      </div>

      {/* Report Dialog */}
      {isMounted && (
        <ReportDialog
          open={isReportDialogOpen}
          onOpenChange={setIsReportDialogOpen}
          userLocation={userLocation}
        />
      )}

      {/* Tutorial Dialog */}
      {isMounted && (
        <TutorialDialog
          open={isTutorialOpen}
          onOpenChange={setIsTutorialOpen}
        />
      )}

      {/* Settings Dialog */}
      {isMounted && (
        <SettingsDialog
          open={isSettingsOpen}
          onOpenChange={setIsSettingsOpen}
        />
      )}
    </div>
  )
}

function MetricCard({ title, icon, value, subtext, statusColor = "text-slate-100" }: any) {
  return (
    <Card className="bg-white/5 border-white/10 text-white">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-sm font-medium text-red-200">{title}</CardTitle>
          <div className="text-red-400">
            {icon}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${statusColor}`}>{value}</div>
        {subtext && <p className="text-xs text-red-300 mt-1 truncate">{subtext}</p>}
      </CardContent>
    </Card>
  )
}

function PipelineStep({ label, active, icon }: any) {
  return (
    <div className={`flex items-center justify-between p-2 rounded-lg transition-colors ${active ? 'bg-red-500/20 border border-red-500/40' : 'bg-transparent'}`}>
      <div className="flex items-center space-x-3">
        <div className={`p-1.5 rounded-md ${active ? 'bg-red-600 text-white' : 'bg-white/10 text-red-300'}`}>
          {icon}
        </div>
        <span className={`text-sm ${active ? 'text-red-100 font-bold' : 'text-red-400/80'}`}>{label}</span>
      </div>
      {active && <Activity className="h-3 w-3 text-red-500 animate-pulse" />}
    </div>
  )
}
