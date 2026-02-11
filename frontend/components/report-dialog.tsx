'use client'

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogFooter,
    DialogClose
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { CloudRain, CloudLightning, CloudHail, Sun, AlertTriangle, MapPin, Camera, X, Wind } from "lucide-react" // Icons
import { submitReport, updateReport, WeatherReport } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useToast } from "@/components/ui/use-toast" // Assuming we have toast, otherwise alert/console

interface ReportDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    userLocation: { lat: number, lon: number } | null
    existingReport?: WeatherReport | null // Optional: if provided, we are editing
}

// Report Types Configuration
const REPORT_TYPES = [
    { id: 'lluvia_debil', label: 'Lluvia Débil', icon: CloudRain, color: 'bg-blue-500/20 text-blue-400 border-blue-500/50' },
    { id: 'lluvia_fuerte', label: 'Lluvia Fuerte', icon: CloudLightning, color: 'bg-indigo-600/30 text-indigo-300 border-indigo-500/50' },
    { id: 'granizo_pequeno', label: 'Granizo Pequeño', icon: CloudHail, color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50' },
    { id: 'granizo_grande', label: 'Granizo Dañino', icon: AlertTriangle, color: 'bg-red-600/30 text-red-400 border-red-500/50' },
    { id: 'viento_fuerte', label: 'Viento Fuerte', icon: Wind, color: 'bg-slate-500/20 text-slate-300 border-slate-500/50' },
    { id: 'cielo_despejado', label: 'Cielo Despejado', icon: Sun, color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50' },
]

export function ReportDialog({ open, onOpenChange, userLocation, existingReport }: ReportDialogProps) {
    const [selectedType, setSelectedType] = useState<string | null>(null)
    const [description, setDescription] = useState("")
    const [selectedImage, setSelectedImage] = useState<File | null>(null)
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const { token } = useAuth()

    // Populate form if editing
    useEffect(() => {
        if (open && existingReport) {
            setSelectedType(existingReport.report_type)
            setDescription(existingReport.description || "")
            if (existingReport.image_url) {
                setPreviewUrl(`${process.env.NEXT_PUBLIC_API_URL || ''}${existingReport.image_url}`)
            } else {
                setPreviewUrl(null)
            }
            setSelectedImage(null) // Reset file input
        } else if (open && !existingReport) {
            // Reset if opening in create mode
            setSelectedType(null)
            setDescription("")
            setSelectedImage(null)
            setPreviewUrl(null)
        }
    }, [open, existingReport])

    const handleSubmit = async () => {
        if (!selectedType || !token) return;
        // If creating, we need location. If editing, we keep original location (userLocation might be current user loc, not report loc)
        if (!existingReport && !userLocation) return;

        setIsSubmitting(true);
        try {
            if (existingReport) {
                // UPDATE MODE
                await updateReport(
                    existingReport.id!,
                    {
                        description,
                        image: selectedImage || undefined // Only send image if new one selected
                    },
                    token
                );
                alert("Reporte actualizado con éxito.");
            } else {
                // CREATE MODE
                const report: WeatherReport = {
                    report_type: selectedType,
                    description: description,
                    latitude: userLocation!.lat,
                    longitude: userLocation!.lon,
                    image: selectedImage
                };
                await submitReport(report, token);
                alert("Reporte enviado con éxito. ¡Gracias por colaborar!");
            }

            // Success cleanup
            setSelectedType(null);
            setDescription("");
            setSelectedImage(null);
            setPreviewUrl(null);
            onOpenChange(false);

        } catch (error) {
            console.error("Error submitting report:", error);
            alert("Error al procesar el reporte. Inténtalo de nuevo.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800 text-zinc-100">
                <DialogHeader>
                    <DialogTitle>{existingReport ? "Editar Reporte" : "Reportar Clima"}</DialogTitle>
                    <DialogDescription>
                        {existingReport ? "Modifica la descripción o la foto." : "¿Qué está pasando en tu ubicación ahora?"}
                    </DialogDescription>
                </DialogHeader>

                <div className="grid grid-cols-2 gap-3 py-4">
                    {REPORT_TYPES.map((type) => {
                        const Icon = type.icon
                        const isSelected = selectedType === type.id
                        // In edit mode, maybe disable changing type? Or allow it? Backend supports it?
                        // Backend update only looks for description and image in my implementation!
                        // "description = request.form.get..."
                        // "image_url = ..."
                        // It does NOT update report_type! 
                        // So I should disable type selection in edit mode or warn user it won't change.
                        // Let's visualy disable it or just hide the grid if editing to simplify?
                        // Or just disable interaction.
                        const isDisabled = !!existingReport;

                        return (
                            <button
                                key={type.id}
                                disabled={isDisabled}
                                onClick={() => !isDisabled && setSelectedType(type.id)}
                                className={`
                  flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all
                  ${isSelected ? `${type.color} ring-2 ring-offset-2 ring-offset-black ring-white/20` : 'bg-zinc-900 border-zinc-800 hover:bg-zinc-800'}
                  ${isDisabled && !isSelected ? 'opacity-50 cursor-not-allowed' : ''}
                  ${isDisabled && isSelected ? 'cursor-default' : ''}
                `}
                            >
                                <Icon className={`w-8 h-8 mb-2 ${isSelected ? 'animate-pulse' : 'text-zinc-400'}`} />
                                <span className="text-xs font-bold">{type.label}</span>
                            </button>
                        )
                    })}
                </div>

                <Textarea
                    placeholder="Comentario opcional (ej. tamaño del granizo)"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="bg-zinc-900 border-zinc-800 resize-none h-20 text-sm mb-3"
                />

                {/* Image Upload */}
                <div className="mb-4">
                    {!previewUrl ? (
                        <div className="flex items-center gap-3">
                            <input
                                type="file"
                                accept="image/*"
                                id="report-image-upload"
                                className="hidden"
                                onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) {
                                        setSelectedImage(file);
                                        setPreviewUrl(URL.createObjectURL(file));
                                    }
                                }}
                            />
                            <label
                                htmlFor="report-image-upload"
                                className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg cursor-pointer text-sm text-zinc-300 transition-colors border border-zinc-700"
                            >
                                <Camera className="w-4 h-4" />
                                <span>{existingReport ? "Cambiar Foto" : "Adjuntar Foto"}</span>
                            </label>
                            <span className="text-xs text-zinc-500 italic">Opcional</span>
                        </div>
                    ) : (
                        <div className="relative w-full h-32 bg-zinc-900 rounded-lg overflow-hidden border border-zinc-700 group">
                            <img src={previewUrl} alt="Preview" className="w-full h-full object-cover" />
                            <button
                                onClick={() => {
                                    setSelectedImage(null);
                                    setPreviewUrl(null);
                                }}
                                className="absolute top-2 right-2 p-1 bg-black/50 hover:bg-black/80 rounded-full text-white transition-colors"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    )}
                </div>

                <DialogFooter className="sm:justify-between gap-2">
                    <DialogClose asChild>
                        <Button type="button" variant="ghost" className="text-zinc-400 hover:text-white">Cancelar</Button>
                    </DialogClose>
                    <Button
                        type="button"
                        onClick={handleSubmit}
                        disabled={!selectedType || isSubmitting || (!existingReport && !userLocation)}
                        className="bg-primary hover:bg-primary/90 text-white"
                    >
                        {isSubmitting ? "Enviando..." : (existingReport ? "Guardar Cambios" : "Enviar Reporte")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
