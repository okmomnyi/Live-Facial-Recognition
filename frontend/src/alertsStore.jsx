// Shared live-alert store. Owns the single WebSocket connection for the whole
// app so the nav badge, live monitor feed, and alerts page all react to the
// same stream. New alerts are prepended; the pending count drives the badge.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createAlertSocket } from "./ws.js";

const AlertsContext = createContext(null);

export function AlertsProvider({ children }) {
  const [liveAlerts, setLiveAlerts] = useState([]); // newest first, this session
  const [wsStatus, setWsStatus] = useState("connecting");
  const [pendingCount, setPendingCount] = useState(0);
  const seen = useRef(new Set());

  const addAlert = useCallback((alert) => {
    if (seen.current.has(alert.id)) return;
    seen.current.add(alert.id);
    setLiveAlerts((prev) => [{ ...alert, _new: true }, ...prev].slice(0, 100));
    if (alert.status === "pending") setPendingCount((c) => c + 1);
  }, []);

  // Called after an officer reviews an alert, to keep the badge accurate.
  const markReviewed = useCallback((id) => {
    setLiveAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: "reviewed-local" } : a))
    );
    setPendingCount((c) => Math.max(0, c - 1));
  }, []);

  // Let pages seed the pending count from a REST fetch (e.g. on load).
  const setPending = useCallback((n) => setPendingCount(n), []);

  useEffect(() => {
    const conn = createAlertSocket({
      onAlert: addAlert,
      onStatus: setWsStatus,
    });
    return () => conn.close();
  }, [addAlert]);

  const value = {
    liveAlerts,
    wsStatus,
    pendingCount,
    addAlert,
    markReviewed,
    setPending,
  };
  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlerts() {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error("useAlerts must be used within AlertsProvider");
  return ctx;
}
