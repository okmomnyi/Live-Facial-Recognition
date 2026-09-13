import { useEffect, useState } from "react";
import { UserPlus, Users, AlertTriangle } from "lucide-react";
import { listPersons, deletePerson } from "../api.js";
import PersonCard from "./PersonCard.jsx";
import EnrollForm from "./EnrollForm.jsx";

export default function WatchlistPage() {
  const [persons, setPersons] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [showEnroll, setShowEnroll] = useState(false);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const data = await listPersons();
      setPersons(data);
      setStatus("ready");
    } catch (err) {
      setError(err.message || "Could not load the watchlist");
      setStatus("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleDelete(id) {
    // Optimistic removal, rolled back on failure.
    const prev = persons;
    setPersons((p) => p.filter((x) => x.id !== id));
    try {
      await deletePerson(id);
    } catch (err) {
      setPersons(prev);
      alert(`Failed to remove: ${err.message}`);
    }
  }

  function handleEnrolled() {
    setShowEnroll(false);
    load(); // refresh counts + thumbnails
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Watchlist</h1>
          <p>
            People enrolled for matching at checkpoints. Each person needs at least one clear
            reference photograph to generate a face embedding.
          </p>
        </div>
        <button className="btn btn--primary" onClick={() => setShowEnroll(true)}>
          <UserPlus size={18} aria-hidden="true" />
          Enroll person
        </button>
      </div>

      {status === "loading" && (
        <div className="state">
          <div className="spinner" aria-hidden="true" />
          <p>Loading watchlist…</p>
        </div>
      )}

      {status === "error" && (
        <div className="state state--error" role="alert">
          <AlertTriangle size={36} aria-hidden="true" />
          <h3>Couldn&apos;t load the watchlist</h3>
          <p>{error}</p>
          <button className="btn" onClick={load}>
            Try again
          </button>
        </div>
      )}

      {status === "ready" && persons.length === 0 && (
        <div className="state">
          <Users size={40} aria-hidden="true" />
          <h3>No one enrolled yet</h3>
          <p>Enroll a person with one or more reference photos to start matching.</p>
          <button className="btn btn--primary" onClick={() => setShowEnroll(true)}>
            <UserPlus size={18} aria-hidden="true" />
            Enroll the first person
          </button>
        </div>
      )}

      {status === "ready" && persons.length > 0 && (
        <div className="grid">
          {persons.map((p) => (
            <PersonCard key={p.id} person={p} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {showEnroll && <EnrollForm onClose={() => setShowEnroll(false)} onEnrolled={handleEnrolled} />}
    </div>
  );
}
