// WebRTC mesh for the Camera Wall.
//
// Publishers (phones) send their camera video peer-to-peer to viewers (the
// operator's browser). Media is P2P; the backend only relays SDP/ICE via
// /ws/signal. Convention: the PUBLISHER creates the offer to each viewer, the
// viewer answers. Roles are fixed, so there is no offer glare.

import { API_BASE } from "./api.js";

const ICE_CONFIG = {
  iceServers: [
    { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] },
    // For phones on cellular / strict NAT, add a TURN server here later:
    // { urls: "turn:your-host:3478", username: "...", credential: "..." },
  ],
};

function signalUrl({ room, peerId, role, name }) {
  const base = API_BASE.replace(/^http/, "ws").replace(/\/$/, "");
  const q = new URLSearchParams({ room, peer: peerId, role, name: name || "" });
  return `${base}/ws/signal?${q.toString()}`;
}

export function randomId(prefix = "p") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Create a mesh connection.
 * opts:
 *   room, role ('publisher'|'viewer'), name
 *   localStream        (publishers only) MediaStream to send
 *   onRemoteStream(peerId, stream, name)   (viewers) a publisher's video arrived
 *   onPeerLeft(peerId)
 *   onStatus(status)   'connecting' | 'open' | 'closed'
 * Returns { close() }.
 */
export function createMesh(opts) {
  const { room, role, name, localStream, onRemoteStream, onPeerLeft, onStatus, onPeerState } = opts;
  const peerId = randomId(role === "publisher" ? "pub" : "view");
  const pcs = new Map(); // otherPeerId -> RTCPeerConnection
  const names = new Map(); // otherPeerId -> label
  let ws = null;
  let closed = false;
  let retry = 0;
  let reconnectTimer = null;

  const setStatus = (s) => onStatus && onStatus(s);

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }

  function signalTo(to, payload) {
    send({ type: "signal", to, payload });
  }

  function makePc(otherId) {
    const pc = new RTCPeerConnection(ICE_CONFIG);
    pcs.set(otherId, pc);
    pc.onicecandidate = (e) => {
      if (e.candidate) signalTo(otherId, { kind: "ice", candidate: e.candidate });
    };
    pc.onconnectionstatechange = () => {
      onPeerState && onPeerState(otherId, pc.connectionState);
    };
    pc.oniceconnectionstatechange = () => {
      // "failed" here almost always means no reachable P2P path -> needs TURN.
      onPeerState && onPeerState(otherId, pc.connectionState || pc.iceConnectionState);
    };
    if (role === "publisher" && localStream) {
      localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
    }
    if (role === "viewer") {
      pc.ontrack = (e) => {
        onRemoteStream && onRemoteStream(otherId, e.streams[0], names.get(otherId) || "");
      };
    }
    return pc;
  }

  // Publisher initiates an offer to a viewer.
  async function offerTo(viewerId) {
    const pc = makePc(viewerId);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    signalTo(viewerId, { kind: "offer", sdp: pc.localDescription });
  }

  async function onSignal(from, payload) {
    if (!payload) return;
    let pc = pcs.get(from);
    if (payload.kind === "offer") {
      // Viewer receives an offer from a publisher.
      pc = pc || makePc(from);
      await pc.setRemoteDescription(payload.sdp);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      signalTo(from, { kind: "answer", sdp: pc.localDescription });
    } else if (payload.kind === "answer") {
      if (pc) await pc.setRemoteDescription(payload.sdp);
    } else if (payload.kind === "ice") {
      if (pc && payload.candidate) {
        try {
          await pc.addIceCandidate(payload.candidate);
        } catch {
          /* ignore late/duplicate candidates */
        }
      }
    }
  }

  function considerPeer(p) {
    names.set(p.peer_id, p.name || p.peer_id);
    // A publisher offers to every viewer; a viewer waits for offers.
    if (role === "publisher" && p.role === "viewer") offerTo(p.peer_id);
  }

  function dropPeer(id) {
    const pc = pcs.get(id);
    if (pc) {
      try { pc.close(); } catch { /* noop */ }
      pcs.delete(id);
    }
    names.delete(id);
    onPeerLeft && onPeerLeft(id);
  }

  function connect() {
    setStatus(retry === 0 ? "connecting" : "connecting");
    let sock;
    try {
      sock = new WebSocket(signalUrl({ room, peerId, role, name }));
    } catch {
      scheduleReconnect();
      return;
    }
    ws = sock;
    sock.onopen = () => {
      retry = 0;
      setStatus("open");
    };
    sock.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === "peers") {
        (msg.peers || []).forEach(considerPeer);
      } else if (msg.type === "peer-joined") {
        considerPeer(msg.peer);
      } else if (msg.type === "peer-left") {
        dropPeer(msg.peer_id);
      } else if (msg.type === "signal") {
        onSignal(msg.from, msg.payload);
      }
    };
    sock.onclose = () => {
      if (!closed) { setStatus("closed"); scheduleReconnect(); }
    };
    sock.onerror = () => { try { sock.close(); } catch { /* noop */ } };
  }

  function scheduleReconnect() {
    if (closed) return;
    retry += 1;
    const delay = Math.min(1000 * 2 ** (retry - 1), 15000);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, delay);
  }

  connect();

  return {
    peerId,
    close() {
      closed = true;
      clearTimeout(reconnectTimer);
      pcs.forEach((pc) => { try { pc.close(); } catch { /* noop */ } });
      pcs.clear();
      if (ws) { try { ws.close(); } catch { /* noop */ } }
    },
  };
}

export { ICE_CONFIG };
