import type { Metadata, Viewport } from 'next'
import localFont from 'next/font/local'
import './globals.css'
import 'leaflet/dist/leaflet.css'
import { AuthProvider } from '@/lib/auth-context'
import { ServiceWorkerRegister } from '@/components/sw-register'
import ErrorBoundary from '@/components/error-boundary'
import { PushProvider } from '@/lib/push-context'
import { LanguageProvider } from '@/lib/language-context'
import { Analytics } from "@vercel/analytics/react"
import { SpeedInsights } from "@vercel/speed-insights/next"

const montserrat = localFont({
  src: [
    {
      path: '../public/fonts/Montserrat/Montserrat-VariableFont_wght.ttf',
      style: 'normal',
    },
    {
      path: '../public/fonts/Montserrat/Montserrat-Italic-VariableFont_wght.ttf',
      style: 'italic',
    }
  ],
  variable: '--font-sans',
})

export const metadata: Metadata = {
  title: 'Hailcast Alert',
  description: 'Alertas de tormentas severas en tiempo real.',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Hailcast',
  },
}

export const viewport: Viewport = {
  themeColor: '#0f172a',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es" translate="no" className={`${montserrat.variable}`}>
      <head>
        <link rel="icon" type="image/png" href="/favicon-32.png" sizes="32x32" />
        <link rel="shortcut icon" href="/favicon-32.png" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </head>
      <body className="font-sans bg-black text-white antialiased overflow-hidden overscroll-none touch-none">
        <ErrorBoundary>
          <LanguageProvider>
            <AuthProvider>
              <PushProvider>
                <ServiceWorkerRegister />
                {children}
                <Analytics />
                <SpeedInsights />
              </PushProvider>
            </AuthProvider>
          </LanguageProvider>
        </ErrorBoundary>
      </body>
    </html>
  )
}
