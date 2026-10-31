import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { Layout } from './layout'
import { Empty, Loading } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router-dom'
import { DEMO_THREAD } from '@/mocks/fixtures'
import { useMocks } from '@/api'

const Home = lazy(() => import('@/home/Home'))
const Capture = lazy(() => import('@/pages/capture'))
const Run = lazy(() => import('@/pages/run'))
const Review = lazy(() => import('@/pages/review'))
const Memory = lazy(() => import('@/pages/memory'))
const Ask = lazy(() => import('@/pages/ask'))
const Board = lazy(() => import('@/pages/board'))
const Digest = lazy(() => import('@/pages/digest'))
const suspense = (component: React.ReactNode) => <Suspense fallback={<Loading />}>{component}</Suspense>

function ReviewEntry() {
  let lastRun: string | null = null
  try { lastRun = localStorage.getItem('quorum-last-run') } catch { /* Direct review links remain available without storage. */ }
  const id = lastRun ?? (useMocks ? DEMO_THREAD : null)
  return id ? <Navigate to={`/review/${encodeURIComponent(id)}`} replace /> : <><Empty title="Your next decision starts with a conversation.">Capture a meeting debrief first. Your review will be waiting here.</Empty><Button asChild><Link to="/capture">Capture a debrief</Link></Button></>
}

const router = createBrowserRouter([
  { index: true, element: suspense(<Home />) },
  { element: <Layout />, children: [
  { path: 'capture', element: suspense(<Capture />) },
  { path: 'runs/:threadId', element: suspense(<Run />) },
  { path: 'review', element: <ReviewEntry /> },
  { path: 'review/:threadId', element: suspense(<Review />) },
  { path: 'memory', element: suspense(<Memory />) },
  { path: 'ask', element: suspense(<Ask />) },
  { path: 'board', element: suspense(<Board />) },
  { path: 'digest', element: suspense(<Digest />) },
  { path: '*', element: <><Empty title="This page slipped out of the meeting.">Head back to capture to pick up where you left off.</Empty><Button asChild variant="outline"><Link to="/capture">Back to capture</Link></Button></> },
] },
])
export function AppRouter() { return <RouterProvider router={router} /> }
