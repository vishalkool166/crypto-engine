import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from 'next-themes'
import { Toaster } from 'sonner'
import QueryProvider from '@/providers/QueryProvider'
import WebSocketProvider from '@/providers/WebSocketProvider'
import AuthGuard from '@/components/layout/AuthGuard'
import Layout from '@/components/layout/Layout'
import DemoLayout from '@/demo/DemoLayout'
import { useDemoStore } from '@/demo/demoStore'

const Chatbot = lazy(() => import('@/components/Chatbot'))
const Login = lazy(() => import('@/pages/Login'))
const EmailAccess = lazy(() => import('@/pages/EmailAccess'))
const Demo = lazy(() => import('@/pages/Demo'))
const Home = lazy(() => import('@/pages/Home'))
const Signals = lazy(() => import('@/pages/Signals'))
const Trades = lazy(() => import('@/pages/Trades'))
const Performance = lazy(() => import('@/pages/Performance'))
const Users = lazy(() => import('@/pages/Users'))
const Coins = lazy(() => import('@/pages/Coins'))
const System = lazy(() => import('@/pages/System'))
const Audit = lazy(() => import('@/pages/Audit'))
const Settings = lazy(() => import('@/pages/Settings'))
const Profile = lazy(() => import('@/pages/Profile'))
const Pricing = lazy(() => import('@/pages/Pricing'))
const Content = lazy(() => import('@/pages/Content'))
const Engine = lazy(() => import('@/pages/Engine'))
const India = lazy(() => import('@/pages/India'))

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
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
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
          <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-background"><div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-foreground" /></div>}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/account" element={<EmailAccess />} />
            <Route path="/verify-email" element={<EmailAccess fixedMode="verify" />} />
            <Route path="/reset-password" element={<EmailAccess fixedMode="reset" />} />
            <Route path="/demo"  element={<Demo />}  />

            <Route path="/demo" element={<DemoLayout />}>
              <Route path="home"        element={<Home />}        />
              <Route path="signals"     element={<Signals />}     />
              <Route path="trades"      element={<Trades />}      />
              <Route path="performance" element={<Performance />} />
              <Route path="content"     element={<Content />}     />
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
              <Route path="content"     element={<Content />}     />
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
          </Suspense>

        </BrowserRouter>
      </QueryProvider>
    </ThemeProvider>
  )
}
