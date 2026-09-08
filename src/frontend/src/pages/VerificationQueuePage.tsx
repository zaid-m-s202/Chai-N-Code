import React, { useEffect, useState } from "react";
import {
  api,
  PropertySummary,
  PropertyDetail,
  PropertyHistory,
  SourceObservation,
  ConflictRecord,
} from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

interface VerificationQueuePageProps {
  currentRole: string;
  authToken: string;
  onNavigateToProperty?: (propertyId: string) => void;
}

export const VerificationQueuePage: React.FC<VerificationQueuePageProps> = ({
  currentRole,
  authToken,
  onNavigateToProperty,
}) => {
  const [queue, setQueue] = useState<PropertySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [conflictFilter, setConflictFilter] = useState<"all" | "clean" | "conflicts">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PropertyDetail | null>(null);
  const [history, setHistory] = useState<PropertyHistory | null>(null);
  const [evidenceList, setEvidenceList] = useState<any[]>([]);
  const [observations, setObservations] = useState<SourceObservation[]>([]);
  const [propertyConflicts, setPropertyConflicts] = useState<ConflictRecord[]>([]);
  const [verifyNotes, setVerifyNotes] = useState("");
  const [actionMsg, setActionMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isOfficer = currentRole === "VERIFYING_OFFICER" || currentRole === "ADMIN";

  const fetchQueue = async () => {
    setLoading(true);
    try {
      let filterParam: boolean | undefined = undefined;
      if (conflictFilter === "clean") filterParam = false;
      if (conflictFilter === "conflicts") filterParam = true;

      const data = await api.getVerificationQueue(filterParam);
      setQueue(data);
    } catch {
      setQueue([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [conflictFilter]);

  const handleSelect = async (id: string) => {
    setSelectedId(id);
    setActionMsg(null);
    try {
      const [d, h, ev, obs, conflicts] = await Promise.all([
        api.getProperty(id),
        api.getHistory(id),
        api.getEvidence(id),
        api.getObservations(id),
        api.listConflicts("OPEN"),
      ]);
      setDetail(d);
      setHistory(h);
      setEvidenceList(ev);
      setObservations(obs);
      // Filter conflicts matching this property
      const matched = conflicts.filter((c) => c.property_object_id === d.id);
      setPropertyConflicts(matched);
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Failed to load property details" });
    }
  };

  const handleVerify = async () => {
    if (!selectedId) return;
    if (!isOfficer) {
      setActionMsg({
        type: "error",
        text: "Permission Denied: Only authenticated Verifying Officers may promote records to VERIFIED (PRD §5.11).",
      });
      return;
    }
    setSubmitting(true);
    setActionMsg(null);
    try {
      const updated = await api.verifyProperty(selectedId, authToken, verifyNotes);
      setDetail(updated);
      setActionMsg({
        type: "success",
        text: `✓ Property ${selectedId} successfully VERIFIED by authority! Audit event logged.`,
      });
      fetchQueue();
    } catch (err: any) {
      setActionMsg({
        type: "error",
        text: err.message || "Verification rejected by system rule.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!selectedId) return;
    if (!isOfficer) {
      setActionMsg({
        type: "error",
        text: "Permission Denied: Only authenticated Verifying Officers may reject records.",
      });
      return;
    }
    setSubmitting(true);
    setActionMsg(null);
    try {
      const updated = await api.rejectProperty(selectedId, authToken, verifyNotes || "Rejected upon review");
      setDetail(updated);
      setActionMsg({
        type: "success",
        text: `Record ${selectedId} marked as rejected by officer. Audit event logged.`,
      });
      fetchQueue();
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Rejection failed" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-container">
      <div className="header-actions">
        <div>
          <h2>Officer Verification & Sign-Off Queue</h2>
          <p className="subtitle">
            Authoritative review queue (PRD §5.7 & §5.10). Move provisional cadastral records to VERIFIED against ground evidence.
          </p>
        </div>
        <div className="role-status-badge">
          {isOfficer ? (
            <span className="badge-officer-active">
              🛡️ Verifying Officer Mode (Authorized to Sign)
            </span>
          ) : (
            <span className="badge-officer-restricted">
              👁️ View-Only Mode ({currentRole.replace("_", " ")})
            </span>
          )}
        </div>
      </div>

      <div className="filter-row">
        <label>Filter Review Queue:</label>
        <div className="tab-group-sm">
          <button
            className={`btn-filter ${conflictFilter === "all" ? "active" : ""}`}
            onClick={() => setConflictFilter("all")}
          >
            All Provisional ({queue.length})
          </button>
          <button
            className={`btn-filter ${conflictFilter === "clean" ? "active" : ""}`}
            onClick={() => setConflictFilter("clean")}
          >
            ✓ Ready for Sign-off (Clean)
          </button>
          <button
            className={`btn-filter ${conflictFilter === "conflicts" ? "active" : ""}`}
            onClick={() => setConflictFilter("conflicts")}
          >
            ⚠️ Blocked by Conflicts
          </button>
        </div>
        <button className="btn btn-secondary" onClick={fetchQueue}>
          Refresh Queue
        </button>
      </div>

      <div className="layout-split">
        <div className="table-card">
          {loading ? (
            <div className="loader">Loading officer review queue...</div>
          ) : queue.length === 0 ? (
            <div className="empty-state">
              <span className="icon-badge">✓</span>
              <h3>No Provisional Properties in Queue</h3>
              <p>
                All ingested records are currently verified or no provisional objects match the selected filter.
              </p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>3D Property ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((p) => (
                  <tr
                    key={p.three_d_property_id}
                    className={selectedId === p.three_d_property_id ? "row-selected" : ""}
                    onClick={() => handleSelect(p.three_d_property_id)}
                  >
                    <td className="mono">{p.three_d_property_id}</td>
                    <td><span className="type-tag">{p.type}</span></td>
                    <td><StatusBadge status={p.status} /></td>
                    <td>
                      <div className="confidence-meter">
                        <div
                          className="confidence-fill"
                          style={{ width: `${Math.round(p.confidence * 100)}%` }}
                        />
                        <span>{Math.round(p.confidence * 100)}%</span>
                      </div>
                    </td>
                    <td>
                      <button className="btn btn-sm btn-outline">Review</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selectedId && detail && (
          <div className="detail-drawer">
            <div className="drawer-header">
              <h3>Officer Review Dossier</h3>
              <button className="btn-close" onClick={() => setSelectedId(null)}>✕</button>
            </div>
            <div className="mono-title">{detail.three_d_property_id}</div>

            {actionMsg && (
              <div className={`alert-banner ${actionMsg.type}`}>
                {actionMsg.text}
              </div>
            )}

            {/* Conflict Warning Banner */}
            {propertyConflicts.length > 0 && (
              <div className="alert-banner error">
                <strong>VR-09 Conflict Warning:</strong> This property has {propertyConflicts.length} active conflict(s).
                Verification is blocked until conflicts are resolved or waived.
                <ul style={{ marginTop: "6px", paddingLeft: "18px" }}>
                  {propertyConflicts.map((c) => (
                    <li key={c.id}>
                      <strong>{c.rule_code}:</strong> {c.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="detail-section">
              <h4>Spatial Geometry & Bounds</h4>
              <div className="attr-grid">
                <div><strong>Object Type:</strong> {detail.type.toUpperCase()}</div>
                <div><strong>Status:</strong> <StatusBadge status={detail.status} /></div>
                <div><strong>Vertical Extent:</strong> {detail.z_min ?? 0}m – {detail.z_max ?? "?"}m</div>
                <div><strong>Model Confidence:</strong> {Math.round(detail.confidence * 100)}%</div>
                <div><strong>Created:</strong> {new Date(detail.created_at).toLocaleString()}</div>
              </div>
            </div>

            <div className="detail-section">
              <h4>Provenance Evidence ({evidenceList.length})</h4>
              {evidenceList.length === 0 ? (
                <p className="subtle">No provenance file metadata linked.</p>
              ) : (
                <div className="evidence-list">
                  {evidenceList.map((ev) => (
                    <div key={ev.id} className="evidence-item">
                      <div><strong>Source:</strong> {ev.source_system} ({ev.original_format?.toUpperCase()})</div>
                      <div><strong>File:</strong> {ev.file_reference}</div>
                      <div><strong>Original CRS:</strong> {ev.original_crs}</div>
                      {ev.file_hash && (
                        <div className="mono-subtle">SHA256: {ev.file_hash.slice(0, 20)}...</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="detail-section">
              <h4>Preserved Source Observations ({observations.length})</h4>
              {observations.length === 0 ? (
                <p className="subtle">No raw observations preserved.</p>
              ) : (
                <div className="evidence-list">
                  {observations.map((obs) => (
                    <div key={obs.id} className="evidence-item">
                      <div><strong>{obs.attribute_name}:</strong> {JSON.stringify(obs.observed_value)}</div>
                      <div><strong>Reliability:</strong> {Math.round(obs.source_confidence * 100)}%</div>
                      <div className="timestamp">{new Date(obs.observed_at).toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="detail-section">
              <h4>Event-Sourced Change History</h4>
              <div className="timeline">
                {history?.events.map((e) => (
                  <div key={e.id} className="timeline-item">
                    <div className="timeline-dot" />
                    <div className="timeline-content">
                      <strong>{e.event_type}</strong>
                      <span className="timestamp">{new Date(e.created_at).toLocaleTimeString()}</span>
                      {e.new_state && <div className="subtle">{JSON.stringify(e.new_state)}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Officer Action Card */}
            <div className="detail-section verification-box">
              <h4>Officer Verification Action</h4>
              {!isOfficer ? (
                <p className="subtle alert-warning-text">
                  🔒 You are viewing as <strong>{currentRole}</strong>. Verification requires <strong>VERIFYING_OFFICER</strong> role. Switch role in the header to authorize.
                </p>
              ) : (
                <p className="subtle">
                  As authorized Verifying Officer, sign off on spatial boundaries against field evidence.
                </p>
              )}

              <textarea
                placeholder="Official verification notes / survey file reference..."
                value={verifyNotes}
                onChange={(e) => setVerifyNotes(e.target.value)}
                className="input-field"
                rows={2}
                disabled={!isOfficer || detail.status === "VERIFIED"}
              />

              <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
                <button
                  className="btn btn-success"
                  onClick={handleVerify}
                  disabled={!isOfficer || submitting || detail.status === "VERIFIED" || propertyConflicts.length > 0}
                  style={{ flex: 1 }}
                >
                  {detail.status === "VERIFIED"
                    ? "✓ Record Verified"
                    : propertyConflicts.length > 0
                    ? "⚠️ Blocked by Conflicts"
                    : "Sign & Authorize (Verify)"}
                </button>

                <button
                  className="btn btn-danger"
                  onClick={handleReject}
                  disabled={!isOfficer || submitting || detail.status === "VERIFIED"}
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
