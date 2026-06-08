import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FinAlly — AI Trading Workstation',
  description: 'AI-powered trading workstation with live market data and portfolio management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="bg-background text-white font-mono antialiased overflow-hidden h-screen">
        {children}
      </body>
    </html>
  )
}
