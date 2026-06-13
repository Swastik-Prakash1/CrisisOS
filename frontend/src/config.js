// All environment variables live here.
// On Netlify, set these in Site Settings → Environment Variables.
// Locally, create frontend/.env and put them there.

export const CONFIG = {
  // Backend API base URL
  API_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000',

  // WebSocket URL for real-time simulation events
  WS_URL:  import.meta.env.VITE_WS_URL  || 'ws://localhost:8000/ws',

  // Simulation settings
  DEMO_MODE: import.meta.env.VITE_DEMO_MODE === 'true' || false,
}
