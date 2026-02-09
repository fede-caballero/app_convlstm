'use client'

import React, { useEffect, useRef } from 'react'

export function LightningBackground() {
    const canvasRef = useRef<HTMLCanvasElement>(null)

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        let width = window.innerWidth
        let height = window.innerHeight

        const setSize = () => {
            width = window.innerWidth
            height = window.innerHeight
            canvas.width = width
            canvas.height = height
        }
        setSize()
        window.addEventListener('resize', setSize)

        // State
        let mouseX = width / 2
        let mouseY = height / 2
        let lightnings: any[] = []

        const handleMove = (e: MouseEvent | TouchEvent) => {
            if ('touches' in e) {
                mouseX = e.touches[0].clientX
                mouseY = e.touches[0].clientY
            } else {
                mouseX = (e as MouseEvent).clientX
                mouseY = (e as MouseEvent).clientY
            }
        }

        window.addEventListener('mousemove', handleMove)
        window.addEventListener('touchmove', handleMove)

        // Lighting Logic
        class Lightning {
            x: number
            y: number
            xEnd: number
            yEnd: number
            alpha: number
            life: number
            bifurcations: any[]

            constructor(x: number, y: number, xEnd: number, yEnd: number, life: number) {
                this.x = x
                this.y = y
                this.xEnd = xEnd
                this.yEnd = yEnd
                this.alpha = 1
                this.life = life
                this.bifurcations = []
            }

            draw() {
                ctx!.strokeStyle = `rgba(100, 200, 255, ${this.alpha})`
                ctx!.lineWidth = 2 * this.alpha
                ctx!.beginPath()
                ctx!.moveTo(this.x, this.y)

                // Jagged line
                let currentX = this.x
                let currentY = this.y
                const segments = 10
                const dx = (this.xEnd - this.x) / segments
                const dy = (this.yEnd - this.y) / segments

                for (let i = 0; i < segments; i++) {
                    currentX += dx + (Math.random() - 0.5) * 20
                    currentY += dy + (Math.random() - 0.5) * 20
                    ctx!.lineTo(currentX, currentY)
                }
                ctx!.lineTo(this.xEnd, this.yEnd)
                ctx!.stroke()

                this.alpha -= 0.05
            }
        }

        const animate = () => {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.1)' // Trail effect
            ctx.fillRect(0, 0, width, height)

            // Randomly spawn lightning towards mouse
            if (Math.random() > 0.92) {
                // Start from random top position or random side
                const startX = Math.random() * width
                const startY = Math.random() * (height / 3) // Top third
                lightnings.push(new Lightning(startX, startY, mouseX, mouseY, 20))
            }

            // Draw lightnings
            lightnings.forEach((l, index) => {
                l.draw()
                if (l.alpha <= 0) {
                    lightnings.splice(index, 1)
                }
            })

            requestAnimationFrame(animate)
        }

        animate()

        return () => {
            window.removeEventListener('resize', setSize)
            window.removeEventListener('mousemove', handleMove)
            window.removeEventListener('touchmove', handleMove)
        }
    }, [])

    return (
        <canvas
            ref={canvasRef}
            className="fixed inset-0 z-0 pointer-events-none"
            style={{ background: 'linear-gradient(to bottom, #020617, #1e1b4b)' }} // Deep Space Gradient
        />
    )
}
