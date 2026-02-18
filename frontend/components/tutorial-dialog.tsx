import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Bot, MapPin, AlertCircle, Zap, Bell, BellRing, Play } from "lucide-react"

interface TutorialDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function TutorialDialog({ open, onOpenChange }: TutorialDialogProps) {
    const steps = [
        {
            icon: <Bot className="h-6 w-6 text-blue-400" />,
            title: "Inteligencia Artificial",
            description: "Nuestra app utiliza un modelo de IA avanzado para escanear imágenes de radar y predecir el movimiento de tormentas a corto plazo."
        },
        {
            icon: <MapPin className="h-6 w-6 text-green-400" />,
            title: "Tu Ubicación",
            description: "Al activar tu GPS, el sistema puede localizarte en el mapa y calcular distancias exactas a las celdas de tormenta cercanas."
        },
        {
            icon: <AlertCircle className="h-6 w-6 text-blue-500" />,
            title: "Reportes Ciudadanos",
            description: "¡Colaborá! Podes enviar reportes del estado del tiempo (granizo, lluvia, viento) en tu ubicación actual para alertar a otros usuarios."
        },
        {
            icon: <Zap className="h-6 w-6 text-red-500" />,
            title: "Alertas de Proximidad",
            description: "Si el sistema detecta una celda de tormenta severa a menos de 20km de vos, recibirás una notificación automática de alerta."
        },
        {
            icon: <Bell className="h-6 w-6 text-red-500" />,
            title: "Notificaciones Generales",
            description: "Los administradores pueden enviar alertas manuales a toda la comunidad en caso de eventos climáticos extremos."
        },
        {
            icon: <BellRing className="h-6 w-6 text-green-500" />,
            title: "Gestión de Alertas",
            description: "Usa la campanita en la pantalla principal para activar o desactivar la recepción de notificaciones en tu dispositivo."
        }
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md bg-black/90 border-white/10 text-white backdrop-blur-xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        <Bot className="h-5 w-5 text-blue-500" />
                        Bienvenido a HailCast
                    </DialogTitle>
                    <DialogDescription className="text-zinc-400">
                        Guía rápida de funcionalidades
                    </DialogDescription>
                </DialogHeader>
                <ScrollArea className="h-[60vh] pr-4">
                    <div className="flex flex-col gap-6 py-4">
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
            </DialogContent>
        </Dialog>
    )
}
