import React, { useEffect, useState } from "react";
import { PropertiesPage } from "./pages/PropertiesPage";
import { VerificationQueuePage } from "./pages/VerificationQueuePage";
import { MapPage } from "./pages/MapPage";
import { IngestionPage } from "./pages/IngestionPage";
import { ConflictsPage } from "./pages/ConflictsPage";
import { api } from "./api/client";
import "./styles.css";

type Tab = "properties" | "queue" | "map" | "ingestion" | "conflicts";

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("properties");
  const [currentRole, setCurrentRole] = useState<string>("VERIFYING_OFFICER");
  const [authToken, setAuthToken] = useState<string>("");
  const [navSelectedPropertyId, setNavSelectedPropertyId] = useState<string | null>(null);
  const [apiHealth, setApiHealth] = useState<"checking" | "connected" | "disconnected">("checking");

  // Check health and obtain initial auth token for Verifying Officer
  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(() => setApiHealth("connected"))
      .catch(() => {
        fetch("/health")
          .then((r) => (r.ok ? r.json() : Promise.reject()))
          .then(() => setApiHealth("connected"))
          .catch(() => setApiHealth("disconnected"));
      });

    // Obtain token for initial role
    api.getQuickToken(currentRole)
      .then(setAuthToken)
      .catch(() => setAuthToken(""));
  }, []);

  const handleRoleChange = async (newRole: string) => {
    setCurrentRole(newRole);
    try {
      const token = await api.getQuickToken(newRole);
      setAuthToken(token);
    } catch (err) {
      console.warn("Failed to get token for role:", newRole, err);
      setAuthToken("");
    }
  };

  const handleNavigateToProperty = (propertyId: string) => {
    setNavSelectedPropertyId(propertyId);
    setActiveTab("properties");
  };

  return (
    <div className="app-container">
      <header className="gov-header">
        <div className="gov-branding">
          <div className="emblem-box">🏛️</div>
          <div>
            <h1>3D Cadastral Intelligence & Property Identification</h1>
            <p className="gov-subtitle">
              National Geospatial Cadastral System • Spatial Identity (ULPIN-B-F-U) • Evidence-Backed
            </p>
          </div>
        </div>

        <div className="header-meta">
          {/* Active Role Selector (PRD §2 & §5.11) */}
          <div className="role-switcher-box">
            <span className="role-label">Active Role:</span>
            <select
              value={currentRole}
              onChange={(e) => handleRoleChange(e.target.value)}
              className="role-select"
            >
              <option value="VERIFYING_OFFICER">🛡️ Verifying Officer (Authority)</option>
              <option value="FIELD_SURVEYOR">📐 Field Surveyor (Submitter)</option>
              <option value="PUBLIC_VIEWER">👁️ Public Viewer (Read-Only)</option>
            </select>
          </div>

          <div className="health-indicator">
            <span
              className={`health-dot ${
                apiHealth === "connected" ? "online" : apiHealth === "checking" ? "pending" : "offline"
              }`}
            />
            <span className="health-label">
              API: {apiHealth === "connected" ? "CONNECTED" : apiHealth === "checking" ? "CHECKING..." : "DISCONNECTED"}
            </span>
          </div>

          <span className="badge-rule-pill">AI DERIVES • EVIDENCE SUPPORTS • AUTHORITY VERIFIES</span>
        </div>
      </header>

      <nav className="tab-nav">
        <button
          className={`nav-item ${activeTab === "properties" ? "active" : ""}`}
          onClick={() => {
            setNavSelectedPropertyId(null);
            setActiveTab("properties");
          }}
        >
          📋 Properties Registry
        </button>
        <button
          className={`nav-item ${activeTab === "queue" ? "active" : ""}`}
          onClick={() => setActiveTab("queue")}
        >
          🛡️ Officer Verification Queue
        </button>
        <button
          className={`nav-item ${activeTab === "map" ? "active" : ""}`}
          onClick={() => setActiveTab("map")}
        >
          🗺️ 2D/3D Spatial Map
        </button>
        <button
          className={`nav-item ${activeTab === "ingestion" ? "active" : ""}`}
          onClick={() => setActiveTab("ingestion")}
        >
          📥 Ingestion & Provenance
        </button>
        <button
          className={`nav-item ${activeTab === "conflicts" ? "active" : ""}`}
          onClick={() => setActiveTab("conflicts")}
        >
          ⚠️ Topology Conflicts
        </button>
      </nav>

      <main className="main-content">
        {activeTab === "properties" && (
          <PropertiesPage
            currentRole={currentRole}
            authToken={authToken}
            initialSelectedId={navSelectedPropertyId}
          />
        )}
        {activeTab === "queue" && (
          <VerificationQueuePage
            currentRole={currentRole}
            authToken={authToken}
            onNavigateToProperty={handleNavigateToProperty}
          />
        )}
        {activeTab === "map" && <MapPage />}
        {activeTab === "ingestion" && (
          <IngestionPage
            currentRole={currentRole}
            authToken={authToken}
          />
        )}
        {activeTab === "conflicts" && (
          <ConflictsPage
            currentRole={currentRole}
            authToken={authToken}
          />
        )}
      </main>

      <footer className="gov-footer">
        <div>
          Spatial Identity is strictly separate from legal ownership identity.
          3D Property IDs are immutable and identify space, not owner.
        </div>
        <div>
          Status progression: SYNTHETIC → INFERRED → DERIVED → PROVISIONAL → VERIFIED
        </div>
      </footer>
    </div>
  );
}
