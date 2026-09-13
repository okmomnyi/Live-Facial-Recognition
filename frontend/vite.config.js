import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_API_BASE controls where the frontend talks to the backend.
// Dev default is http://localhost:8000; overridden per deploy (Vercel env var).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
