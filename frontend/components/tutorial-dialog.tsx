import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Bot, LocateFixed, AlertCircle, Zap, Bell, BellRing, Play, Layers, Cloud, Info } from "lucide-react"
import { useLanguage } from "@/lib/language-context"

interface TutorialDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function TutorialDialog({ open, onOpenChange }: TutorialDialogProps) {
    const { t } = useLanguage()
    const steps = [
        {
            icon: <Bot className="h-6 w-6 text-blue-400" />,
            title: t("Inteligencia Artificial", "Artificial Intelligence"),
            description: t("Nuestra app utiliza un modelo de IA avanzado para escanear imágenes de radar y predecir el movimiento de tormentas a corto plazo.", "Our app uses an advanced AI model to scan radar images and predict short-term storm movement.")
        },
        {
            icon: <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-400 text-black shadow-md shadow-green-500/30"><Play className="h-4 w-4 ml-0.5" /></div>,
            title: t("Control del Tiempo", "Time Control"),
            description: t("Dale 'Play' al reproductor inferior para ver la animación: primero verás los datos observados (pasado) y luego la predicción (futuro).", "Hit 'Play' on the bottom player to see the animation: first you'll see observed data (past) followed by the prediction (future).")
        },
        {
            icon: <LocateFixed className="h-6 w-6 text-green-400" />,
            title: t("Tu Ubicación", "Your Location"),
            description: t("Al activar tu GPS, el sistema puede localizarte en el mapa y calcular distancias exactas a las celdas de tormenta cercanas.", "By enabling GPS, the system can locate you on the map and calculate exact distances to nearby storm cells.")
        },
        {
            icon: <AlertCircle className="h-6 w-6 text-blue-500" />,
            title: t("Reportes Ciudadanos", "Citizen Reports"),
            description: t("¡Colaborá! Podes enviar reportes del estado del tiempo (granizo, lluvia, viento) en tu ubicación actual para alertar a otros usuarios.", "Collaborate! You can send weather reports (hail, rain, wind) from your current location to alert other users.")
        },
        {
            icon: <Zap className="h-6 w-6 text-red-500" />,
            title: t("Alertas de Proximidad", "Proximity Alerts"),
            description: t("Si el sistema detecta una celda de tormenta severa a menos de 20km de vos, recibirás una notificación automática de alerta.", "If the system detects a severe storm cell within 20km, you'll receive an automatic alert notification.")
        },
        {
            icon: <Bell className="h-6 w-6 text-red-500" />,
            title: t("Notificaciones Generales", "General Notifications"),
            description: t("Los administradores pueden enviar alertas manuales a toda la comunidad en caso de eventos climáticos extremos.", "Administrators can send manual alerts to the entire community during extreme weather events.")
        },
        {
            icon: <BellRing className="h-6 w-6 text-green-500" />,
            title: t("Gestión de Alertas", "Alert Management"),
            description: t("Usa la campanita en la pantalla principal para activar o desactivar la recepción de notificaciones en tu dispositivo.", "Use the bell icon on the main screen to enable or disable notifications on your device.")
        },
        {
            icon: <Layers className="h-6 w-6 text-sky-400" />,
            title: t("Capas Satelitales", "Satellite Layers"),
            description: t("Tocá el botón de capas en el mapa para superponer imágenes satelitales GOES-East en tiempo real: visible (VIS) o infrarrojo (IR).", "Tap the layers button on the map to overlay real-time GOES-East satellite images: visible (VIS) or infrared (IR).")
        },
        {
            icon: (
                <svg viewBox="0 0 24 24" width="24" height="24" fill="#00ffff" stroke="rgba(0,0,0,0.4)" strokeWidth="0.5">
                    <circle cx="12" cy="12" r="6" />
                </svg>
            ),
            title: t("Aviones de Siembra", "Seeding Aircraft"),
            description: t("Los círculos de colores sobre el mapa representan aviones de siembra de nubes rastreados en tiempo real por el sistema TITAN. Tocá uno para ver su matrícula, altitud y velocidad.", "Colored circles on the map represent cloud seeding aircraft tracked in real-time by TITAN. Tap one to see its tail number, altitude, and speed.")
        }
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md bg-black/90 border-white/10 text-white backdrop-blur-xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        <img src="/logo.png" alt="Hailcast Logo" className="w-6 h-6 object-contain" />
                        {t("Bienvenido a HailCast", "Welcome to HailCast")}
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400">
                        {t("Guía rápida de funciones", "Quick feature guide")}
                    </DialogDescription>
                </DialogHeader>
                <Tabs defaultValue="features" className="w-full">
                    <TabsList className="grid w-full grid-cols-2 bg-black/90 mb-2">
                        <TabsTrigger value="features" className="data-[state=active]:bg-gray-600 data-[state=active]:text-primary-foreground">
                            <Info className="w-4 h-4 mr-2" />
                            {t("Funciones", "Features")}
                        </TabsTrigger>
                        <TabsTrigger value="scale" className="data-[state=active]:bg-gray-600 data-[state=active]:text-primary-foreground">
                            <Cloud className="w-4 h-4 mr-2" />
                            {t("Radar", "Radar Scale")}
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="features" className="m-0 mt-2">
                        <ScrollArea className="h-[55vh] pr-4">
                            <div className="flex flex-col gap-6 py-2">
                                {steps.map((step, index) => (
                                    <div key={index} className="flex gap-4 items-start">
                                        <div className="mt-1 bg-white/5 p-2 rounded-lg">
                                            {step.icon}
                                        </div>
                                        <div className="space-y-1">
                                            <h4 className="font-semibold text-sm text-zinc-100 leading-none">{step.title}</h4>
                                            <p className="text-sm text-zinc-400 leading-snug">
                                                {step.description}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </TabsContent>

                    <TabsContent value="scale" className="m-0 mt-2">
                        <ScrollArea className="h-[55vh] pr-4">
                            <div className="flex flex-col gap-4 py-2">
                                <p className="text-sm text-zinc-400 mb-2">
                                    {t("Esta escala indica la intensidad de la precipitación (en decibelios de reflectividad - dBZ) detectada por el radar meteorológico TITAN.", "This scale indicates the precipitation intensity (in reflectivity decibels - dBZ) detected by the TITAN weather radar.")}
                                </p>
                                <div className="space-y-3 bg-black/40 rounded-xl p-4 border border-white/5">
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col gap-1 w-6">
                                            <div className="w-full h-2 rounded bg-[#007000] shadow-[0_0_5px_rgba(0,112,0,0.5)]" />
                                            <div className="w-full h-2 rounded bg-[#087fdb] shadow-[0_0_5px_rgba(8,127,219,0.5)]" />
                                            <div className="w-full h-2 rounded bg-[#1c47e8] shadow-[0_0_5px_rgba(28,71,232,0.5)]" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-zinc-200">{"< 36 dBZ"}</p>
                                            <p className="text-xs text-zinc-400">{t("Lluvia débil", "Light rain")}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col gap-1 w-6">
                                            <div className="w-full h-3 rounded bg-[#6e0dc6] shadow-[0_0_5px_rgba(110,13,198,0.5)]" />
                                            <div className="w-full h-3 rounded bg-[#c80f86] shadow-[0_0_5px_rgba(200,15,134,0.5)]" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-zinc-200">{"36 - 42 dBZ"}</p>
                                            <p className="text-xs text-zinc-400">{t("Lluvia moderada", "Moderate rain")}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col gap-0.5 w-6">
                                            <div className="w-full h-2 rounded bg-[#c06487] shadow-[0_0_5px_rgba(192,100,135,0.5)]" />
                                            <div className="w-full h-2 rounded bg-[#d2883b] shadow-[0_0_5px_rgba(210,136,59,0.5)]" />
                                            <div className="w-full h-2 rounded bg-[#fac431] shadow-[0_0_5px_rgba(250,196,49,0.5)]" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-zinc-200">{"42 - 51 dBZ"}</p>
                                            <p className="text-xs text-zinc-400">{t("Lluvia fuerte", "Heavy rain")}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col gap-1 w-6">
                                            <div className="w-full h-3 rounded bg-[#fefa03] shadow-[0_0_5px_rgba(254,250,3,0.5)]" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-zinc-200">{"51 - 54 dBZ"}</p>
                                            <p className="text-xs text-zinc-400">{t("Lluvia torrencial y probable granizo", "Torrential rain, probable hail")}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <div className="flex flex-col gap-0.5 w-6">
                                            <div className="w-full h-1.5 rounded bg-[#fe9a58] shadow-[0_0_5px_rgba(254,154,88,0.5)]" />
                                            <div className="w-full h-1.5 rounded bg-[#fe5f05] shadow-[0_0_5px_rgba(254,95,5,0.5)]" />
                                            <div className="w-full h-1.5 rounded bg-[#fd341c] shadow-[0_0_5px_rgba(253,52,28,0.5)]" />
                                            <div className="w-full h-1.5 rounded bg-[#bebebe] shadow-[0_0_5px_rgba(190,190,190,0.5)]" />
                                        </div>
                                        <div className="flex-1">
                                            <p className="text-sm font-semibold text-zinc-200">{"> 55 dBZ"}</p>
                                            <p className="text-xs text-zinc-400">{t("Lluvia torrencial y granizo seguro", "Torrential rain and definite hail")}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </ScrollArea>
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    )
}
