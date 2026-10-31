import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
export function formatDate(value: string, options?: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', ...options, timeZone: 'UTC' }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`))
}
export function initials(value: string) { return value.trim().split(/\s+/).map((s) => s[0]).join('').slice(0, 2) || '?' }
export function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'Something went wrong. Please try again.' }
