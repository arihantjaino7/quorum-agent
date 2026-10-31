import { createHttpApi } from './http'
import { createMockApi } from '@/mocks/api'

export const useMocks = import.meta.env.VITE_USE_MOCKS === 'true'
export const api = useMocks ? createMockApi() : createHttpApi()
export { ApiError } from './errors'
export type { QuorumApi, StreamOptions, Unsubscribe } from './contracts'
