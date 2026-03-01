'use client'

import { useState, useEffect, useMemo } from 'react'
import { Cloud, CloudRain, Thermometer, Wind, Droplets, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useLanguage } from "@/lib/language-context"

interface WeatherData {
    current: {
        temperature_2m: number
        relative_humidity_2m: number
        apparent_temperature: number
        precipitation: number
        weather_code: number
        wind_speed_10m: number
    }
    hourly: {
        time: string[]
        temperature_2m: number[]
        precipitation_probability: number[]
    }
}

export function WeatherSidebar({ userLocation }: { userLocation: { lat: number, lon: number } | null }) {
    const { t } = useLanguage()
    const [weather, setWeather] = useState<WeatherData | null>(null)
    const [loading, setLoading] = useState(true)
    const [isOpen, setIsOpen] = useState(false) // Collapsible state

    const location = useMemo(() => {
        return userLocation
            ? { lat: userLocation.lat, lon: userLocation.lon, name: t("Mi Ubicación", "My Location") }
            : { lat: -34.6177, lon: -68.3301, name: "San Rafael" } // Fallback
    }, [userLocation?.lat, userLocation?.lon])

    useEffect(() => {
        if (!location) return;

        async function fetchWeather() {
            setLoading(true)
            try {
                const res = await fetch(
                    `https://api.open-meteo.com/v1/forecast?latitude=${location.lat}&longitude=${location.lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&hourly=temperature_2m,precipitation_probability&timezone=auto&forecast_days=2`
                )
                const data = await res.json()
                setWeather(data)
            } catch (error) {
                console.error("Error fetching weather:", error)
            } finally {
                setLoading(false)
            }
        }

        fetchWeather()
    }, [location])

    if (loading) {
        return <div className="absolute top-[85px] left-4 z-40 bg-black/50 p-4 rounded-xl text-white backdrop-blur-md w-64">
            <Skeleton className="h-6 w-3/4 mb-4 bg-white/20" />
            <Skeleton className="h-20 w-full bg-white/10" />
        </div>
    }

    if (!weather) return null

    const { current, hourly } = weather

    // Find start index for current time
    const now = new Date()
    const currentHourIndex = hourly.time.findIndex((t) => new Date(t) >= now)
    const startIndex = currentHourIndex === -1 ? 0 : currentHourIndex
    const nextHours = hourly.time.slice(startIndex, startIndex + 24) // Show next 24 hours

    return (
        <div className={`absolute top-[85px] left-4 z-[90] transition-all duration-300 ${isOpen ? 'w-80' : 'w-auto'}`}>
            <Card className="bg-black/40 backdrop-blur-md border-white/10 text-white shadow-2xl overflow-hidden">
                <div
                    className={`flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors ${isOpen ? 'p-3' : 'p-2'}`}
                    onClick={() => setIsOpen(!isOpen)}
                >
                    <div className="flex items-center gap-2">
                        <div className="bg-white/10 p-1.5 rounded-full">
                            <Cloud className={`${isOpen ? 'w-6 h-6' : 'w-5 h-5'} text-blue-300`} />
                            {/* Logic to change icon based on weather_code would be better */}
                        </div>
                        <div>
                            <div className={`${isOpen ? 'text-2xl' : 'text-xl'} font-bold leading-none`}>{Math.round(current.temperature_2m)}°C</div>
                            {isOpen && <div className="text-xs text-zinc-300 mt-1">{location.name}</div>}
                        </div>
                    </div>

                    {isOpen && (
                        <div className="text-right">
                            <div className="text-xs text-zinc-400">{t("Sensación", "Feels like")}</div>
                            <div className="font-semibold">{Math.round(current.apparent_temperature)}°C</div>
                        </div>
                    )}
                </div>

                {isOpen && (
                    <CardContent className="p-4 pt-0 space-y-4 animate-in slide-in-from-top-4 duration-300">
                        {/* Grid Stats */}
                        <div className="grid grid-cols-3 gap-2 py-4 border-t border-white/10 mt-2">
                            <div className="flex flex-col items-center p-2 bg-white/5 rounded-lg">
                                <Wind className="w-4 h-4 text-zinc-400 mb-1" />
                                <span className="text-sm font-bold">{current.wind_speed_10m}</span>
                                <span className="text-[10px] text-zinc-500">km/h</span>
                            </div>
                            <div className="flex flex-col items-center p-2 bg-white/5 rounded-lg">
                                <Droplets className="w-4 h-4 text-zinc-400 mb-1" />
                                <span className="text-sm font-bold">{current.relative_humidity_2m}%</span>
                                <span className="text-[10px] text-zinc-500">{t("Humedad", "Humidity")}</span>
                            </div>
                            <div className="flex flex-col items-center p-2 bg-white/5 rounded-lg">
                                <CloudRain className="w-4 h-4 text-zinc-400 mb-1" />
                                <span className="text-sm font-bold">{current.precipitation}</span>
                                <span className="text-[10px] text-zinc-500">mm</span>
                            </div>
                        </div>

                        {/* Hourly Forecast (Mini) */}
                        <div>
                            <h4 className="text-xs font-bold uppercase text-zinc-500 mb-2">{t("Próximas 24 Horas", "Next 24 Hours")}</h4>
                            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                                {nextHours.map((t, i) => {
                                    const date = new Date(t)
                                    // Index in original array
                                    const originalIndex = startIndex + i

                                    return (
                                        <div key={t} className="flex-shrink-0 flex flex-col items-center gap-1 min-w-[3rem] p-2 rounded-md hover:bg-white/5">
                                            <span className="text-xs text-zinc-400">{date.getHours()}:00</span>
                                            <Cloud className="w-4 h-4 text-zinc-500" />
                                            <span className="text-sm font-bold">{Math.round(hourly.temperature_2m[originalIndex])}°</span>
                                            <div className="flex items-center text-[10px] text-blue-300">
                                                <Droplets className="w-2 h-2 mr-0.5" />
                                                {hourly.precipitation_probability[originalIndex]}%
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    </CardContent>
                )}
            </Card>
        </div>
    )
}
