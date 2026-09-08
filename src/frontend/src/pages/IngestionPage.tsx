import React, { useEffect, useState } from "react";
import { api, IngestionJob } from "../api/client";

interface IngestionPageProps {
  currentRole?: string;
  authToken?: string;
}

export const IngestionPage: React.FC<IngestionPageProps> = () => {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [sourceSystem, setSourceSystem] = useState("municipal_gis_portal");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchJobs = async () => {
    try {
      const data = await api.listJobs();
      setJobs(data);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadMsg({ type: "error", text: "Please select a GeoJSON or CSV file to ingest." });
      return;
    }
    setUploading(true);
    setUploadMsg(null);
    try {
      const job = await api.uploadFile(file, sourceSystem);
      setUploadMsg({
        type: "success",
        text: `Ingestion job completed! Parsed ${job.record_count ?? 0} property records with provenance.`,
      });
      setFile(null);
      fetchJobs();
    } catch (err: any) {
      setUploadMsg({ type: "error", text: err.message || "Ingestion failed" });
    } finally {
      setUploading(false);
    }
  };

  // Preset sample loader helper
  const handleLoadSample = async (sampleName: string, format: string, source: string) => {
    setUploading(true);
    setUploadMsg(null);
    try {
      // Create a synthetic file object with sample data
      let content = "";
      if (sampleName === "ward_pilot_footprints.geojson") {
        content = JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: {
                type: "Polygon",
                coordinates: [[[75.80, 26.90], [75.81, 26.90], [75.81, 26.91], [75.80, 26.91], [75.80, 26.90]]]
              },
              properties: { ulpin: "INMH0234567", type: "parcel" }
            },
            {
              type: "Feature",
              geometry: {
                type: "Polygon",
                coordinates: [[[75.802, 26.902], [75.808, 26.902], [75.808, 26.908], [75.802, 26.908], [75.802, 26.902]]]
              },
              properties: { ulpin: "INMH0234567", type: "building", building_seq: 1, height: 24.5 }
            }
          ]
        });
      } else if (sampleName === "conflicting_observations.csv") {
        content = "ulpin,type,building_seq,floor_seq,unit_seq,height,source_confidence,source_id\nINMH0234567,building,1,,,42.0,0.92,lidar_drone_2026\nINMH0234567,building,1,,,24.5,0.70,municipal_survey_2023\n";
      } else {
        content = "ulpin,type,building_seq,floor_seq,unit_seq,floor_number,unit_number,area_sqm\nINMH0234567,floor,1,1,,1,,420\nINMH0234567,unit,1,1,1,1,101,120\nINMH0234567,unit,1,1,2,1,102,140\n";
      }

      const blob = new Blob([content], { type: format === "geojson" ? "application/json" : "text/csv" });
      const sampleFile = new File([blob], sampleName, { type: blob.type });

      const job = await api.uploadFile(sampleFile, source);
      setUploadMsg({
        type: "success",
        text: `Loaded preset sample "${sampleName}". Ingested ${job.record_count ?? 0} record(s) into database.`,
      });
      fetchJobs();
    } catch (err: any) {
      setUploadMsg({ type: "error", text: err.message || "Failed to load sample dataset" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="header-actions">
        <div>
          <h2>Sensor-Agnostic Ingestion Engine</h2>
          <p className="subtitle">
            Ingest GeoJSON cadastral footprints, Shapefiles, or tabular survey CSVs. Raw observations are preserved, normalized, and provenance-tracked.
          </p>
        </div>
      </div>

      {uploadMsg && (
        <div className={`alert-banner ${uploadMsg.type}`}>
          {uploadMsg.text}
        </div>
      )}

      <div className="layout-split">
        <div className="upload-card">
          <h3>Upload Cadastral / Survey Dataset</h3>
          <form onSubmit={handleUpload} className="upload-form">
            <div className="form-group">
              <label>Select Dataset File (.geojson, .json, .csv):</label>
              <input
                type="file"
                accept=".geojson,.json,.csv"
                onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
                className="file-input"
              />
            </div>

            <div className="form-group">
              <label>Authoritative Source System Reference:</label>
              <input
                type="text"
                value={sourceSystem}
                onChange={(e) => setSourceSystem(e.target.value)}
                className="input-field"
                placeholder="e.g. municipal_survey_2026, drone_lidar_ward12"
              />
            </div>

            <button type="submit" className="btn btn-primary" disabled={uploading}>
              {uploading ? "Ingesting & Standardizing..." : "Start Ingestion Job"}
            </button>
          </form>

          {/* Quick Preset Data Loaders */}
          <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid var(--border)" }}>
            <h4>Quick Load Sample Pilot Datasets (PRD §3)</h4>
            <p className="subtle">Click to immediately ingest verified test fixtures:</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "8px" }}>
              <button
                className="btn btn-outline"
                style={{ textAlign: "left" }}
                onClick={() => handleLoadSample("ward_pilot_footprints.geojson", "geojson", "jaipur_gis_pilot")}
                disabled={uploading}
              >
                🗺️ <strong>ward_pilot_footprints.geojson</strong> — Parcel & Building Footprints
              </button>
              <button
                className="btn btn-outline"
                style={{ textAlign: "left" }}
                onClick={() => handleLoadSample("ward_pilot_survey.csv", "csv", "jaipur_survey_ward12")}
                disabled={uploading}
              >
                📋 <strong>ward_pilot_survey.csv</strong> — Floor & Unit Tabular Hierarchy
              </button>
              <button
                className="btn btn-outline"
                style={{ textAlign: "left" }}
                onClick={() => handleLoadSample("conflicting_observations.csv", "csv", "lidar_vs_municipal_2026")}
                disabled={uploading}
              >
                ⚠️ <strong>conflicting_observations.csv</strong> — Contradictory Height Evidence
              </button>
            </div>
          </div>
        </div>

        <div className="table-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3>Recent Ingestion Jobs & Provenance Logs</h3>
            <button className="btn btn-sm btn-secondary" onClick={fetchJobs}>Refresh</button>
          </div>

          {loading ? (
            <div className="loader">Loading job status...</div>
          ) : jobs.length === 0 ? (
            <div className="empty-state">No ingestion jobs executed yet. Upload or quick-load a dataset.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>File Name</th>
                  <th>Format</th>
                  <th>Status</th>
                  <th>Records Ingested</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td className="mono">{j.id.slice(0, 8)}...</td>
                    <td><strong>{j.filename}</strong></td>
                    <td><span className="type-tag">{j.format}</span></td>
                    <td>
                      <span className={`status-badge badge-${j.status.toLowerCase()}`}>
                        {j.status}
                      </span>
                    </td>
                    <td>{j.record_count ?? 0} record(s)</td>
                    <td>{new Date(j.created_at).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
