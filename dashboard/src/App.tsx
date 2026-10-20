import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from 'next-themes'
import { Toaster } from 'sonner'
import QueryProvider from '@/providers/QueryProvider'
import WebSocketProvider from '@/providers/WebSocketProvider'
import AuthGuard from '@/components/layout/AuthGuard'
import Layout from '@/components/layout/Layout'
import DemoLayout from '@/demo/DemoLayout'
import Chatbot from '@/components/Chatbot'
import Login from '@/pages/Login'
import Landing from '@/pages/Landing'
import Demo from '@/pages/Demo'
import Home from '@/pages/Home'
import Signals from '@/pages/Signals'
import Trades from '@/pages/Trades'
import Performance from '@/pages/Performance'
import Users from '@/pages/Users'
import Coins from '@/pages/Coins'
import System from '@/pages/System'
import Audit from '@/pages/Audit'
import Settings from '@/pages/Settings'
import Profile from '@/pages/Profile'
import Pricing from '@/pages/Pricing'
import Engine from '@/pages/Engine'
import India from '@/pages/India'
import { useDemoStore } from '@/demo/demoStore'

function ChatbotGuard() {
  const { isDemoMode } = useDemoStore()
  if (isDemoMode) return null
  return (
    <AuthGuard>
      <Chatbot />
    </AuthGuard>
  )
}

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <QueryProvider>
        <BrowserRouter basename="/">
          <Toaster
            position     = "top-right"
            toastOptions = {{
              classNames: {
                toast:       'bg-card border border-border text-foreground shadow-lg',
                title:       'text-foreground text-sm font-medium',
                description: 'text-muted-foreground text-xs',
                error:       'border-[hsl(var(--chart-2)/0.4)]',
                success:     'border-[hsl(var(--chart-1)/0.4)]',
                warning:     'border-[hsl(var(--chart-4)/0.4)]',
              },
            }}
          />
          <Routes>
            <Route path="/welcome" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/plans" element={<Pricing />} />
            <Route path="/demo"  element={<Demo />}  />

            <Route path="/demo" element={<DemoLayout />}>
              <Route path="home"        element={<Home />}        />
              <Route path="signals"     element={<Signals />}     />
              <Route path="trades"      element={<Trades />}      />
              <Route path="performance" element={<Performance />} />
              <Route path="coins"       element={<Coins />}       />
              <Route path="system"      element={<System />}      />
              <Route path="audit"       element={<Audit />}       />
              <Route path="settings"    element={<Settings />}    />
              <Route path="profile"     element={<Profile />}     />
              <Route path="pricing"     element={<Pricing />}     />
              <Route path="*"           element={<Navigate to="/demo/home" replace />} />
            </Route>

            <Route
              path    = "/"
              element = {
                <AuthGuard>
                  <WebSocketProvider>
                    <Layout />
                  </WebSocketProvider>
                </AuthGuard>
              }
            >
              <Route index              element={<Home />}        />
              <Route path="signals"     element={<Signals />}     />
              <Route path="trades"      element={<Trades />}      />
              <Route path="performance" element={<Performance />} />
              <Route path="engine"      element={<Engine />}      />
              <Route path="india"       element={<India />}       />
              <Route path="users"       element={<Users />}       />
              <Route path="coins"       element={<Coins />}       />
              <Route path="system"      element={<System />}      />
              <Route path="audit"       element={<Audit />}       />
              <Route path="settings"    element={<Settings />}    />
              <Route path="profile"     element={<Profile />}     />
              <Route path="pricing"     element={<Pricing />}     />
              <Route path="*"           element={<Navigate to="/" replace />} />
            </Route>
          </Routes>

          <ChatbotGuard />

        </BrowserRouter>
      </QueryProvider>
    </ThemeProvider>
  )
}
