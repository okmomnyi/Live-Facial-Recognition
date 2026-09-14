import { Routes, Route, Navigate } from "react-router-dom";
import { AlertsProvider } from "./alertsStore.jsx";
import NavBar from "./components/NavBar.jsx";
import WatchlistPage from "./components/WatchlistPage.jsx";
import LiveMonitorPage from "./components/LiveMonitorPage.jsx";
import AlertsPage from "./components/AlertsPage.jsx";
import CameraWallPage from "./components/CameraWallPage.jsx";
import StationPage from "./components/StationPage.jsx";

export default function App() {
  return (
    <AlertsProvider>
      <div className="app-shell">
        <NavBar />
        <main style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<WatchlistPage />} />
            <Route path="/monitor" element={<LiveMonitorPage />} />
            <Route path="/wall" element={<CameraWallPage />} />
            <Route path="/station" element={<StationPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <footer className="footer">
          <p className="disclaimer">
            Research prototype for academic evaluation only. Uses pretrained
            open-source models on consented sample data; contains no government
            or law-enforcement records. Every match is a proposal an officer must
            review — no automated action is taken. See the project README for the
            data-handling and consent notes.
          </p>
        </footer>
      </div>
    </AlertsProvider>
  );
}
