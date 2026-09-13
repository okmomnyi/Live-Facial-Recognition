// WebSocket client for /ws/alerts with automatic reconnect + backoff.
// Derives the ws:// or wss:// URL from VITE_API_BASE.

import { API_BASE } from "./api.js";

function wsUrl() {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base.replace(/\/$/, "")}/ws/alerts`;
}

export function createAlertSocket({ onAlert, onStatus }) {
  let socket = null;
  let closedByCaller = false;
  let retry = 0;
  let reconnectTimer = null;

  const setStatus = (s) => onStatus && onStatus(s);

  function connect() {
    setStatus(retry === 0 ? "connecting" : "reconnecting");
    let ws;
    try {
      ws = new WebSocket(wsUrl());
    } catch {
      scheduleReconnect();
      return;
    }
    socket = ws;

    ws.onopen = () => {
      retry = 0;
      setStatus("open");
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return; // ignore malformed frames
      }
      if (msg.type === "alert" && msg.alert) {
        onAlert && onAlert(msg.alert);
      }
      // heartbeat frames just keep the connection warm; nothing to do.
    };

    ws.onclose = () => {
      if (closedByCaller) return;
      setStatus("closed");
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will follow and trigger reconnect.
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }

  function scheduleReconnect() {
    if (closedByCaller) return;
    retry += 1;
    const delay = Math.min(1000 * 2 ** (retry - 1), 15000); // capped backoff
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, delay);
  }

  connect();

  return {
    close() {
      closedByCaller = true;
      clearTimeout(reconnectTimer);
      if (socket) {
        try {
          socket.close();
        } catch {
          /* noop */
        }
      }
    },
  };
}
