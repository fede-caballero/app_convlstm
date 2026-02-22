import type { Metadata, Viewport } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import './globals.css'
import 'leaflet/dist/leaflet.css'
import { AuthProvider } from '@/lib/auth-context'
import { ServiceWorkerRegister } from '@/components/sw-register'
import ErrorBoundary from '@/components/error-boundary'

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
    <html lang="es" translate="no">
      <head>
        <style>{`
html {
  font-family: ${GeistSans.style.fontFamily};
  --font-sans: ${GeistSans.variable};
  --font-mono: ${GeistMono.variable};
}
        `}</style>
      </head>
      <body className="bg-black text-white antialiased overflow-hidden overscroll-none touch-none">
        <ErrorBoundary>
          <AuthProvider>
            <ServiceWorkerRegister />
            {children}
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  )
}
