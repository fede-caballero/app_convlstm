'use client'

import { useState } from "react"
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
import { CloudRain, CloudLightning, CloudHail, Sun, AlertTriangle } from "lucide-react" // Icons

interface ReportDialogProps {
    isOpen: boolean
    onOpenChange: (open: boolean) => void
    onSubmit: (type: string, description: string) => void
    isSubmitting: boolean
}

// Report Types Configuration
const REPORT_TYPES = [
    { id: 'lluvia_debil', label: 'Lluvia Débil', icon: CloudRain, color: 'bg-blue-500/20 text-blue-400 border-blue-500/50' },
    { id: 'lluvia_fuerte', label: 'Lluvia Fuerte', icon: CloudLightning, color: 'bg-indigo-600/30 text-indigo-300 border-indigo-500/50' },
    { id: 'granizo_pequeno', label: 'Granizo Pequeño', icon: CloudHail, color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50' },
    { id: 'granizo_grande', label: 'Granizo Dañino', icon: AlertTriangle, color: 'bg-red-600/30 text-red-400 border-red-500/50' },
    { id: 'cielo_despejado', label: 'Cielo Despejado', icon: Sun, color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50' },
]

export function ReportDialog({ isOpen, onOpenChange, onSubmit, isSubmitting }: ReportDialogProps) {
    const [selectedType, setSelectedType] = useState<string | null>(null)
    const [description, setDescription] = useState("")

    const handleSubmit = () => {
        if (selectedType) {
            onSubmit(selectedType, description)
            // Reset
            setSelectedType(null)
            setDescription("")
            onOpenChange(false)
        }
    }

    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800 text-zinc-100">
                <DialogHeader>
                    <DialogTitle>Reportar Clima</DialogTitle>
                    <DialogDescription>
                        ¿Qué está pasando en tu ubicación ahora?
                    </DialogDescription>
                </DialogHeader>

                <div className="grid grid-cols-2 gap-3 py-4">
                    {REPORT_TYPES.map((type) => {
                        const Icon = type.icon
                        const isSelected = selectedType === type.id
                        return (
                            <button
                                key={type.id}
                                onClick={() => setSelectedType(type.id)}
                                className={`
                  flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all
                  ${isSelected ? `${type.color} ring-2 ring-offset-2 ring-offset-black ring-white/20` : 'bg-zinc-900 border-zinc-800 hover:bg-zinc-800'}
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
                    className="bg-zinc-900 border-zinc-800 resize-none h-20 text-sm"
                />

                <DialogFooter className="sm:justify-between gap-2">
                    <DialogClose asChild>
                        <Button type="button" variant="ghost" className="text-zinc-400 hover:text-white">Cancelar</Button>
                    </DialogClose>
                    <Button
                        type="button"
                        onClick={handleSubmit}
                        disabled={!selectedType || isSubmitting}
                        className="bg-primary hover:bg-primary/90 text-white"
                    >
                        {isSubmitting ? "Enviando..." : "Enviar Reporte"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
