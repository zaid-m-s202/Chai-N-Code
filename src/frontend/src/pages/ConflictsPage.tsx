import React, { useEffect, useState } from "react";
import { api, ConflictRecord } from "../api/client";

interface ConflictsPageProps {
  currentRole?: string;
  authToken?: string;
}

export const ConflictsPage: React.FC<ConflictsPageProps> = ({
  currentRole = "VERIFYING_OFFICER",
  authToken = "",
}) => {
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("OPEN");
  const [ruleFilter, setRuleFilter] = useState("");
  const [actionMsg, setActionMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [runningValidation, setRunningValidation] = useState(false);
  const [validationSummary, setValidationSummary] = useState<any>(null);

  const isOfficer = currentRole === "VERIFYING_OFFICER" || currentRole === "ADMIN";

  const fetchConflicts = async () => {
    setLoading(true);
    try {
      const data = await api.listConflicts(
        statusFilter === "ALL" ? undefined : statusFilter,
        ruleFilter || undefined
      );
      setConflicts(data);
    } catch {
      setConflicts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConflicts();
  }, [statusFilter, ruleFilter]);

  const handleRunTopology = async () => {
    if (!isOfficer) {
      setActionMsg({
        type: "error",
        text: "Permission Denied: Only authenticated Verifying Officers may trigger batch topology validation.",
      });
      return;
    }
    setRunningValidation(true);
    setActionMsg(null);
    try {
      const res = await api.runTopologyValidation(authToken);
      setValidationSummary(res);
      setActionMsg({
        type: "success",
        text: `Topology Validation Executed: ${res.total_violations} rule violation(s) evaluated and recorded as conflicts (VR-08).`,
      });
      fetchConflicts();
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Topology execution failed" });
    } finally {
      setRunningValidation(false);
    }
  };

  const handleResolve = async (id: string) => {
    if (!isOfficer) {
      setActionMsg({
        type: "error",
        text: "Permission Denied: Only Verifying Officers may resolve conflicts.",
      });
      return;
    }
    try {
      await api.resolveConflict(id, authToken);
      setActionMsg({ type: "success", text: `Conflict ${id.slice(0, 8)}... marked as RESOLVED.` });
      fetchConflicts();
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Failed to resolve conflict" });
    }
  };

  const handleWaive = async (id: string) => {
    if (!isOfficer) {
      setActionMsg({
        type: "error",
        text: "Permission Denied: Only Verifying Officers may waive conflicts.",
      });
      return;
    }
    try {
      await api.waiveConflict(id, authToken);
      setActionMsg({ type: "success", text: `Conflict ${id.slice(0, 8)}... WAIVED by officer review.` });
      fetchConflicts();
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Failed to waive conflict" });
    }
  };

  return (
    <div className="page-container">
      <div className="header-actions">
        <div>
          <h2>Validation & Topology Conflict Dashboard</h2>
          <p className="subtitle">
            Deterministic spatial validation engine (VR-01 through VR-09). Failed rules create open conflicts that block VERIFIED status.
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className="btn btn-primary"
            onClick={handleRunTopology}
            disabled={runningValidation || !isOfficer}
          >
            {runningValidation ? "Executing Topology Rules..." : "⚡ Run Topology Validation"}
          </button>
          <button className="btn btn-secondary" onClick={fetchConflicts}>
            Refresh
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className={`alert-banner ${actionMsg.type}`}>
          {actionMsg.text}
        </div>
      )}

      {validationSummary && (
        <div className="alert-banner success" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <strong>Latest Run Summary:</strong> {validationSummary.total_violations} violation(s) logged across database objects.
            {Object.keys(validationSummary.violations_by_rule || {}).length > 0 && (
              <span style={{ marginLeft: "12px" }}>
                Violations by Rule: {JSON.stringify(validationSummary.violations_by_rule)}
              </span>
            )}
          </div>
          <span className="mono-subtle" style={{ color: "#166534" }}>
            {new Date(validationSummary.checked_at).toLocaleTimeString()}
          </span>
        </div>
      )}

      <div className="filter-row">
        <label>Status Filter:</label>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="OPEN">OPEN (Blocking)</option>
          <option value="RESOLVED">RESOLVED</option>
          <option value="WAIVED">WAIVED</option>
          <option value="ALL">All Statuses</option>
        </select>

        <label>Rule Code:</label>
        <select value={ruleFilter} onChange={(e) => setRuleFilter(e.target.value)}>
          <option value="">All Rule Codes</option>
          <option value="VR-01">VR-01: Footprint Inside Parcel</option>
          <option value="VR-02">VR-02: Unit Overlap on Floor</option>
          <option value="VR-03">VR-03: Unexpected Floor Gap</option>
          <option value="VR-04">VR-04: Floor Vertical Overlap</option>
          <option value="VR-05">VR-05: Boundary Violation</option>
          <option value="VR-06">VR-06: Near-Duplicate Geometry</option>
          <option value="VR-07">VR-07: Orphan Record</option>
          <option value="VR-FUS-01">VR-FUS-01: Multi-Source Fusion Dispute</option>
        </select>

        <button
          className="btn btn-secondary"
          onClick={() => {
            setStatusFilter("OPEN");
            setRuleFilter("");
            fetchConflicts();
          }}
        >
          Reset
        </button>
      </div>

      <div className="table-card">
        {loading ? (
          <div className="loader">Checking conflict registry...</div>
        ) : conflicts.length === 0 ? (
          <div className="empty-state">
            <span className="icon-badge">✓</span>
            <h3>No Conflicts Matching Filter</h3>
            <p>All evaluated property records satisfy topological rules or all matching conflicts have been resolved.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Rule Code</th>
                <th>Severity</th>
                <th>Description / Anomaly Detail</th>
                <th>Status</th>
                <th>Detected At</th>
                <th>Officer Resolution</th>
              </tr>
            </thead>
            <tbody>
              {conflicts.map((c) => (
                <tr key={c.id}>
                  <td><span className="badge-rule">{c.rule_code}</span></td>
                  <td>
                    <span className={`severity-tag ${c.severity.toLowerCase()}`}>
                      {c.severity}
                    </span>
                  </td>
                  <td style={{ maxWidth: "420px" }}>
                    <div>{c.description || "Topology anomaly detected"}</div>
                    <div className="mono-subtle" style={{ marginTop: "4px" }}>
                      Target Object UUID: {c.property_object_id}
                    </div>
                  </td>
                  <td>
                    <span className={`status-tag ${c.status.toLowerCase()}`}>
                      {c.status}
                    </span>
                  </td>
                  <td>{new Date(c.created_at).toLocaleString()}</td>
                  <td>
                    {c.status === "OPEN" ? (
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => handleResolve(c.id)}
                          disabled={!isOfficer}
                          title={!isOfficer ? "Verifying Officer only" : "Mark as resolved"}
                        >
                          Resolve
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => handleWaive(c.id)}
                          disabled={!isOfficer}
                          title={!isOfficer ? "Verifying Officer only" : "Waive conflict"}
                        >
                          Waive
                        </button>
                      </div>
                    ) : (
                      <span className="mono-subtle">
                        {c.resolved_at ? `Done ${new Date(c.resolved_at).toLocaleDateString()}` : c.status}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Rules Reference Guide Card */}
      <div className="table-card" style={{ marginTop: "24px" }}>
        <h3>Deterministic Topology Rules Reference (PRD §5.6)</h3>
        <div className="rules-grid">
          <div className="rule-card">
            <strong>VR-01 / VR-05: Parcel Containment</strong>
            <p className="subtle">Building footprint must be fully within parcel boundary within configured tolerance.</p>
          </div>
          <div className="rule-card">
            <strong>VR-02: Unit Overlap (IoU)</strong>
            <p className="subtle">Units on the same floor cannot intersect beyond the 1% area overlap threshold.</p>
          </div>
          <div className="rule-card">
            <strong>VR-03: Gap / Discontinuity</strong>
            <p className="subtle">Detects unexpected vacant floor gaps or disconnected unit clusters on a floor.</p>
          </div>
          <div className="rule-card">
            <strong>VR-04: Vertical Consistency</strong>
            <p className="subtle">Detects vertical interval overlap [z_min, z_max] between floors in the same building.</p>
          </div>
          <div className="rule-card">
            <strong>VR-06: Near-Duplicate Geometry</strong>
            <p className="subtle">Flags geometries with Hausdorff distance below 0.5m and area ratio over 95%.</p>
          </div>
          <div className="rule-card">
            <strong>VR-07: Orphan Hierarchy Detection</strong>
            <p className="subtle">Detects buildings without parcels, floors without buildings, or units without floors.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
