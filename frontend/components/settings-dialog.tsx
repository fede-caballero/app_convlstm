'use client'

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Switch } from "@/components/ui/switch"
import { usePush } from "@/lib/push-context"
import { useLanguage } from "@/lib/language-context"
import { Bell, AlertTriangle, Plane, Globe, Settings as SettingsIcon } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SettingsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
    const { isSubscribed, preferences, updatePreferences, isSupported } = usePush()
    const { language, setLanguage, t } = useLanguage()

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md bg-[#1c1c1e] text-white border-none shadow-2xl overflow-hidden rounded-xl">
                <DialogHeader className="pt-2">
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        <SettingsIcon className="h-5 w-5 text-gray-400" />
                        {t('Configuración', 'Settings')}
                    </DialogTitle>
                    <DialogDescription className="text-gray-400">
                        {t('Personalizá la aplicación y tus alertas.', 'Customize the application and your alerts.')}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-8 py-2">
                    {/* Language Settings */}
                    <div className="space-y-4">
                        <h4 className="text-xs font-bold tracking-wider text-gray-500 uppercase flex items-center gap-2">
                            <Globe className="h-4 w-4" />
                            {t('Idioma', 'Language')}
                        </h4>
                        <div className="grid grid-cols-2 gap-3">
                            <Button
                                variant={language === 'es' ? 'default' : 'outline'}
                                className={`transition-all ${language === 'es' ? 'bg-sky-500 hover:bg-sky-600 border-sky-500 shadow-md shadow-sky-500/20' : 'bg-[#2c2c2e] hover:bg-[#3c3c3e] border-transparent text-gray-300'}`}
                                onClick={() => setLanguage('es')}
                            >
                                Español (ES)
                            </Button>
                            <Button
                                variant={language === 'en' ? 'default' : 'outline'}
                                className={`transition-all ${language === 'en' ? 'bg-sky-500 hover:bg-sky-600 border-sky-500 shadow-md shadow-sky-500/20' : 'bg-[#2c2c2e] hover:bg-[#3c3c3e] border-transparent text-gray-300'}`}
                                onClick={() => setLanguage('en')}
                            >
                                English (US)
                            </Button>
                        </div>
                    </div>

                    {/* Push Notifications Settings */}
                    <div className="space-y-4">
                        <h4 className="text-xs font-bold tracking-wider text-gray-500 uppercase flex items-center gap-2">
                            <Bell className="h-4 w-4" />
                            {t('Notificaciones', 'Notifications')}
                        </h4>

                        {!isSupported ? (
                            <p className="text-sm text-yellow-500 bg-yellow-500/10 p-3 rounded-lg border border-yellow-500/20">
                                {t('Tu dispositivo no soporta notificaciones web.', 'Your device does not support web push notifications.')}
                            </p>
                        ) : !isSubscribed ? (
                            <p className="text-sm text-amber-500 bg-amber-500/10 p-3 rounded-lg border border-amber-500/20 font-medium">
                                {t('⚠️ Debes suscribirte primero usando el ícono de la campana en la pantalla principal o el radar.', '⚠️ You must subscribe first using the bell icon on the main screen or map.')}
                            </p>
                        ) : null}

                        <div className={`space-y-5 bg-[#2c2c2e] p-4 rounded-xl ${!isSubscribed ? 'opacity-50 pointer-events-none grayscale-[0.5]' : ''}`}>
                            {/* Alertas Manuales */}
                            <div className="flex items-center justify-between">
                                <div className="space-y-1 max-w-[80%] pr-4">
                                    <div className="flex items-center gap-2">
                                        <Bell className="h-4 w-4 text-sky-400" />
                                        <span className="font-semibold text-sm">
                                            {t('Avisos Oficiales', 'Official Alerts')}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-400 leading-snug">
                                        {t('Avisos de administradores sobre situaciones meteorológicas especiales.', 'Alerts sent by administrators during special weather situations.')}
                                    </p>
                                </div>
                                <Switch
                                    checked={preferences.alert_admin}
                                    onCheckedChange={(c) => updatePreferences({ alert_admin: c })}
                                    className="data-[state=checked]:bg-sky-500"
                                />
                            </div>

                            <div className="h-[1px] w-full bg-[#3c3c3e]" />

                            {/* Alertas de Proximidad */}
                            <div className="flex items-center justify-between">
                                <div className="space-y-1 max-w-[80%] pr-4">
                                    <div className="flex items-center gap-2">
                                        <AlertTriangle className="h-4 w-4 text-rose-500" />
                                        <span className="font-semibold text-sm">
                                            {t('Alertas de Proximidad', 'Proximity Alerts')}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-400 leading-snug">
                                        {t('Avisos automáticos cuando hay tormenta a menos de 20km.', 'Automatic warnings when severe storms approach within 20km.')}
                                    </p>
                                </div>
                                <Switch
                                    checked={preferences.alert_proximity}
                                    onCheckedChange={(c) => updatePreferences({ alert_proximity: c })}
                                    className="data-[state=checked]:bg-sky-500"
                                />
                            </div>

                            <div className="h-[1px] w-full bg-[#3c3c3e]" />

                            {/* Despegue de Aviones */}
                            <div className="flex items-center justify-between">
                                <div className="space-y-1 max-w-[80%] pr-4">
                                    <div className="flex items-center gap-2">
                                        <Plane className="h-4 w-4 text-emerald-400" />
                                        <span className="font-semibold text-sm">
                                            {t('Despegue de Aviones', 'Aircraft Takeoffs')}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-400 leading-snug">
                                        {t('Recibí confirmación cuando aviones de mitigación entran al radar.', 'Get notified when hail mitigation aircraft start operating.')}
                                    </p>
                                </div>
                                <Switch
                                    checked={preferences.alert_aircraft}
                                    onCheckedChange={(c) => updatePreferences({ alert_aircraft: c })}
                                    className="data-[state=checked]:bg-sky-500"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}
