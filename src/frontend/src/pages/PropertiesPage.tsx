import React, { useEffect, useState } from "react";
import {
  api,
  PropertySummary,
  PropertyDetail,
  PropertyHistory,
  SourceObservation,
  HierarchyNode,
  ConflictRecord,
  PropertyAnalysisResponse,
  PropertyRecord,
} from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

interface PropertiesPageProps {
  currentRole?: string;
  authToken?: string;
  initialSelectedId?: string | null;
}

export const PropertiesPage: React.FC<PropertiesPageProps> = ({
  currentRole = "VERIFYING_OFFICER",
  authToken = "",
  initialSelectedId = null,
}) => {
  const [properties, setProperties] = useState<PropertySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(initialSelectedId);
  const [detail, setDetail] = useState<PropertyDetail | null>(null);
  const [history, setHistory] = useState<PropertyHistory | null>(null);
  const [evidenceList, setEvidenceList] = useState<any[]>([]);
  const [observations, setObservations] = useState<SourceObservation[]>([]);
  const [hierarchy, setHierarchy] = useState<HierarchyNode | null>(null);
  const [propertyConflicts, setPropertyConflicts] = useState<ConflictRecord[]>([]);
  const [refuseLoading, setRefuseLoading] = useState(false);
  const [verifyNotes, setVerifyNotes] = useState("");
  const [actionMsg, setActionMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // AI Analysis state (PRD §5.4 / Phase 6)
  const [aiDsm, setAiDsm] = useState("45.0");
  const [aiDem, setAiDem] = useState("30.0");
  const [aiUseType, setAiUseType] = useState("residential");
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState<PropertyAnalysisResponse | null>(null);

  // Legal Linkage state (Phase 7)
  const [legalRecords, setLegalRecords] = useState<PropertyRecord[]>([]);
  const [showLegalForm, setShowLegalForm] = useState(false);
  const [legalUlpin, setLegalUlpin] = useState("");
  const [legalOwnerPartyId, setLegalOwnerPartyId] = useState("");
  const [legalRegNo, setLegalRegNo] = useState("");
  const [legalRightsType, setLegalRightsType] = useState("freehold");
  const [legalSourceSystem, setLegalSourceSystem] = useState("BHOOMI_KAVERI");
  const [legalLinkageStatus, setLegalLinkageStatus] = useState("LINKED");
  const [legalEncumbranceDesc, setLegalEncumbranceDesc] = useState("");
  const [legalSubmitting, setLegalSubmitting] = useState(false);

  const isOfficer = currentRole === "VERIFYING_OFFICER" || currentRole === "ADMIN";

  const fetchProperties = async () => {
    setLoading(true);
    try {
      if (searchQuery.trim()) {
        const res = await api.search(searchQuery.trim());
        setProperties(res);
      } else {
        const res = await api.listProperties(
          statusFilter || undefined,
          typeFilter || undefined
        );
        setProperties(res);
      }
    } catch {
      setProperties([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProperties();
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    if (initialSelectedId) {
      handleSelectProperty(initialSelectedId);
    }
  }, [initialSelectedId]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProperties();
  };

  const handleSelectProperty = async (id: string) => {
    setSelectedId(id);
    setActionMsg(null);
    setShowLegalForm(false);
    try {
      const [d, h, ev, obs, conflicts, legal] = await Promise.all([
        api.getProperty(id),
        api.getHistory(id),
        api.getEvidence(id),
        api.getObservations(id),
        api.listConflicts("OPEN"),
        api.getLegalRecordsByProperty(id, authToken),
      ]);
      setDetail(d);
      setHistory(h);
      setEvidenceList(ev);
      setObservations(obs);
      setLegalRecords(legal);

      const matchedConflicts = conflicts.filter((c) => c.property_object_id === d.id);
      setPropertyConflicts(matchedConflicts);

      // Pre-fill legal form ULPIN if available from 3D Property ID
      if (d.three_d_property_id) {
        const parts = d.three_d_property_id.split("-");
        if (parts.length >= 4) {
          setLegalUlpin(`${parts[0]}-${parts[1]}-${parts[2]}-${parts[3]}`);
        }
      }

      // Try fetching hierarchy tree
      try {
        const hierRes = await api.getHierarchy(id);
        setHierarchy(hierRes.root);
      } catch {
        setHierarchy(null);
      }
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Failed to load details" });
    }
  };

  const handleCreateLegalRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    if (!isOfficer) {
      setActionMsg({ type: "error", text: "Access Denied: Only Verifying Officers or Admins can link legal records." });
      return;
    }
    if (!legalOwnerPartyId.trim()) {
      setActionMsg({ type: "error", text: "Owner Party ID is required (must be an explicit external reference, cannot be inferred)." });
      return;
    }
    setLegalSubmitting(true);
    setActionMsg(null);
    try {
      const encumbrances = legalEncumbranceDesc.trim()
        ? [{ type: "general", description: legalEncumbranceDesc.trim(), status: "ACTIVE" }]
        : [];
      const newRecord = await api.createLegalRecord(
        {
          property_object_id: detail.id,
          ulpin: legalUlpin.trim() || detail.three_d_property_id.slice(0, 16),
          owner_party_id: legalOwnerPartyId.trim(),
          registration_number: legalRegNo.trim() || undefined,
          rights_type: legalRightsType,
          source_system: legalSourceSystem,
          linkage_status: legalLinkageStatus,
          encumbrances,
        },
        authToken
      );
      setLegalRecords((prev) => [newRecord, ...prev]);
      setShowLegalForm(false);
      setLegalOwnerPartyId("");
      setLegalEncumbranceDesc("");
      setActionMsg({
        type: "success",
        text: `✓ Legal record linked (ULPIN: ${newRecord.ulpin}). Change event logged to audit history.`,
      });
      // Refresh history
      const updatedHistory = await api.getHistory(detail.id);
      setHistory(updatedHistory);
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Failed to link legal record" });
    } finally {
      setLegalSubmitting(false);
    }
  };

  const handleUnlinkLegalRecord = async (recordId: string) => {
    if (!detail) return;
    if (!isOfficer) {
      setActionMsg({ type: "error", text: "Access Denied: Only Verifying Officers or Admins can unlink legal records." });
      return;
    }
    setLegalSubmitting(true);
    try {
      await api.unlinkLegalRecord(recordId, authToken);
      const updatedLegal = await api.getLegalRecordsByProperty(detail.id, authToken);
      setLegalRecords(updatedLegal);
      const updatedHistory = await api.getHistory(detail.id);
      setHistory(updatedHistory);
      setActionMsg({ type: "success", text: "✓ Legal record unlinked. Audit event logged." });
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Failed to unlink legal record" });
    } finally {
      setLegalSubmitting(false);
    }
  };

  const handleRefuse = async () => {
    if (!selectedId) return;
    setRefuseLoading(true);
    setActionMsg(null);
    try {
      const res = await api.refuseProperty(selectedId);
      const [d, h, obs] = await Promise.all([
        api.getProperty(selectedId),
        api.getHistory(selectedId),
        api.getObservations(selectedId),
      ]);
      setDetail(d);
      setHistory(h);
      setObservations(obs);
      fetchProperties();
      if (res.has_conflict) {
        setActionMsg({
          type: "error",
          text: `Observation Conflict Detected: ${res.conflict_reason}`,
        });
      } else {
        setActionMsg({
          type: "success",
          text: `Multi-source consensus updated across ${res.observations_count} observations. Fused height: ${res.fused_height}m (Confidence: ${Math.round(res.fused_confidence * 100)}%)`,
        });
      }
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Re-fusion calculation failed" });
    } finally {
      setRefuseLoading(false);
    }
  };

  const handleRunAiAnalysis = async () => {
    if (!selectedId) return;
    setAiAnalyzing(true);
    setActionMsg(null);
    try {
      const res = await api.analyzeProperty(selectedId, authToken, {
        elevation_data: {
          dsm: parseFloat(aiDsm) || 45.0,
          dem: parseFloat(aiDem) || 30.0,
          sensor_type: "LiDAR_or_Photogrammetry",
        },
        use_type: aiUseType,
      });
      setAiResult(res);
      setActionMsg({
        type: "success",
        text: `AI spatial analysis executed. Derived status: ${res.status} (${Math.round(res.confidence * 100)}% confidence). Evidence ID: ${res.evidence_id.slice(0, 8)}... (Status Gating: Officer verification required to promote to VERIFIED)`,
      });
      // Refresh property details, observations, evidence, and history
      const [d, h, ev, obs] = await Promise.all([
        api.getProperty(selectedId),
        api.getHistory(selectedId),
        api.getEvidence(selectedId),
        api.getObservations(selectedId),
      ]);
      setDetail(d);
      setHistory(h);
      setEvidenceList(ev);
      setObservations(obs);
      fetchProperties();
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "AI Analysis failed" });
    } finally {
      setAiAnalyzing(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedId) return;
    if (!isOfficer) {
      setActionMsg({
        type: "error",
        text: "Access Denied: Only authenticated Verifying Officers may promote records to VERIFIED (PRD §5.11).",
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
        text: `✓ Property ${selectedId} verified successfully by authority! Audit event logged.`,
      });
      fetchProperties();
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
        text: "Access Denied: Only authenticated Verifying Officers may reject records.",
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
        text: `Record ${selectedId} marked as rejected. Change event recorded in history.`,
      });
      fetchProperties();
    } catch (err: any) {
      setActionMsg({ type: "error", text: err.message || "Rejection failed" });
    } finally {
      setSubmitting(false);
    }
  };

  const renderHierarchyNode = (node: HierarchyNode) => {
    const isCurrent = node.three_d_property_id === selectedId;
    return (
      <div key={node.id} className={`tree-node ${isCurrent ? "tree-node-current" : ""}`}>
        <div className="tree-node-header">
          <span className="type-tag">{node.type}</span>
          <span className="mono" style={{ fontSize: "11px", fontWeight: isCurrent ? 700 : 500 }}>
            {node.three_d_property_id}
          </span>
          <StatusBadge status={node.status as any} />
        </div>
        {node.children && node.children.length > 0 && (
          <div className="tree-node-children">
            {node.children.map((child) => renderHierarchyNode(child))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="page-container">
      <div className="header-actions">
        <div>
          <h2>Cadastral Spatial Registry</h2>
          <p className="subtitle">
            3D Property Identification (ULPIN-B-F-U hierarchy). Search by ULPIN, inspect provenance evidence, and review change events.
          </p>
        </div>
        <form onSubmit={handleSearch} className="search-bar">
          <input
            type="text"
            placeholder="Search by 3D ID or ULPIN..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">Search</button>
        </form>
      </div>

      <div className="filter-row">
        <label>Filter Status:</label>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="PROVISIONAL">PROVISIONAL</option>
          <option value="INFERRED">INFERRED</option>
          <option value="DERIVED">DERIVED</option>
          <option value="VERIFIED">VERIFIED</option>
          <option value="SYNTHETIC">SYNTHETIC</option>
        </select>

        <label>Filter Type:</label>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All Types</option>
          <option value="parcel">Parcel</option>
          <option value="building">Building</option>
          <option value="floor">Floor</option>
          <option value="unit">Unit</option>
        </select>

        <button
          className="btn btn-secondary"
          onClick={() => {
            setSearchQuery("");
            setStatusFilter("");
            setTypeFilter("");
            fetchProperties();
          }}
        >
          Reset Filters
        </button>
      </div>

      <div className="layout-split">
        <div className="table-card">
          {loading ? (
            <div className="loader">Loading registry records...</div>
          ) : properties.length === 0 ? (
            <div className="empty-state">
              <span className="icon-badge">🔍</span>
              <h3>No Properties Found</h3>
              <p>No records match your query. Ingest sample data or clear search filters.</p>
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
                {properties.map((p) => (
                  <tr
                    key={p.three_d_property_id}
                    className={selectedId === p.three_d_property_id ? "row-selected" : ""}
                    onClick={() => handleSelectProperty(p.three_d_property_id)}
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
                      <button className="btn btn-sm btn-outline">Inspect</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selectedId && detail ? (
          <div className="detail-drawer">
            <div className="drawer-header">
              <h3>Property Dossier</h3>
              <button className="btn-close" onClick={() => setSelectedId(null)}>✕</button>
            </div>
            <div className="mono-title">{detail.three_d_property_id}</div>

            {actionMsg && (
              <div className={`alert-banner ${actionMsg.type}`}>
                {actionMsg.text}
              </div>
            )}

            {/* VR-09 Conflict Warning */}
            {propertyConflicts.length > 0 && (
              <div className="alert-banner error">
                <strong>VR-09 Conflict Warning:</strong> This property has {propertyConflicts.length} active conflict(s).
                Verification is blocked until resolved.
                <ul style={{ marginTop: "4px", paddingLeft: "16px" }}>
                  {propertyConflicts.map((c) => (
                    <li key={c.id}>
                      <strong>{c.rule_code}:</strong> {c.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Spatial Attributes & Boundaries */}
            <div className="detail-section">
              <h4>Spatial Attributes & Boundaries</h4>
              <div className="attr-grid">
                <div><strong>Type:</strong> <span className="type-tag">{detail.type}</span></div>
                <div><strong>Status:</strong> <StatusBadge status={detail.status} /></div>
                <div><strong>Vertical Extent (z):</strong> {detail.z_min ?? 0}m to {detail.z_max ?? "?"}m</div>
                <div><strong>Confidence:</strong> {Math.round(detail.confidence * 100)}%</div>
                <div><strong>Created At:</strong> {new Date(detail.created_at).toLocaleString()}</div>
                <div><strong>Sources Linked:</strong> {detail.source_list?.length ?? 0} source(s)</div>
              </div>
            </div>

            {/* AI / GIS Spatial Analysis (PRD §5.4 / Phase 6) */}
            <div className="detail-section" style={{ border: "1px solid #6366f1", borderRadius: "8px", padding: "12px", background: "rgba(99, 102, 241, 0.05)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <h4 style={{ margin: 0, color: "#818cf8" }}>🤖 AI / GIS Spatial Analysis (PRD §5.4)</h4>
                <span className="type-tag" style={{ background: "rgba(99, 102, 241, 0.2)", color: "#c7d2fe", fontSize: "11px" }}>
                  AI Derives • Officer Verifies
                </span>
              </div>
              <p className="subtle" style={{ margin: "4px 0 10px 0", fontSize: "12px" }}>
                Derives building height via nDSM (DSM minus DEM) and infers 3D floor intervals using calibrated occupancy heuristics.
                <br />
                <strong style={{ color: "#f59e0b" }}>Status Gating:</strong> AI outputs are marked <code>DERIVED</code> or <code>INFERRED</code>; authority verification is strictly required for <code>VERIFIED</code>.
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", marginBottom: "10px" }}>
                <div>
                  <label style={{ fontSize: "11px", display: "block", marginBottom: "3px", color: "var(--text-secondary)" }}>DSM Surface (m):</label>
                  <input
                    type="number"
                    step="0.1"
                    value={aiDsm}
                    onChange={(e) => setAiDsm(e.target.value)}
                    className="input-field"
                    style={{ width: "100%", padding: "5px 8px", fontSize: "12px" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "11px", display: "block", marginBottom: "3px", color: "var(--text-secondary)" }}>DEM Terrain (m):</label>
                  <input
                    type="number"
                    step="0.1"
                    value={aiDem}
                    onChange={(e) => setAiDem(e.target.value)}
                    className="input-field"
                    style={{ width: "100%", padding: "5px 8px", fontSize: "12px" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "11px", display: "block", marginBottom: "3px", color: "var(--text-secondary)" }}>Occupancy / Use:</label>
                  <select
                    value={aiUseType}
                    onChange={(e) => setAiUseType(e.target.value)}
                    className="input-field"
                    style={{ width: "100%", padding: "5px 8px", fontSize: "12px" }}
                  >
                    <option value="residential">Residential (3.0m)</option>
                    <option value="commercial">Commercial (3.8m)</option>
                    <option value="office">Office (3.6m)</option>
                    <option value="retail">Retail (4.2m)</option>
                    <option value="industrial">Industrial (5.0m)</option>
                  </select>
                </div>
              </div>

              <button
                className="btn btn-outline"
                style={{ width: "100%", padding: "7px 12px", borderColor: "#6366f1", color: "#a5b4fc" }}
                onClick={handleRunAiAnalysis}
                disabled={aiAnalyzing}
              >
                {aiAnalyzing ? "Running AI Adapters..." : "⚡ Execute AI Spatial Pipeline (Height + Floors)"}
              </button>

              {aiResult && (
                <div style={{ marginTop: "10px", padding: "10px", background: "rgba(0,0,0,0.25)", borderRadius: "6px", fontSize: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <span><strong>Assigned Status:</strong> <StatusBadge status={aiResult.status as any} /></span>
                    <span><strong>Confidence:</strong> {Math.round(aiResult.confidence * 100)}%</span>
                  </div>
                  <div style={{ marginBottom: "4px" }}>
                    <strong>Vertical Bounds:</strong> {aiResult.z_min ?? 0}m to {aiResult.z_max ?? 0}m (Height: {((aiResult.z_max ?? 0) - (aiResult.z_min ?? 0)).toFixed(1)}m)
                  </div>
                  <div className="mono-subtle" style={{ fontSize: "11px", marginBottom: "6px" }}>
                    Evidence ID: {aiResult.evidence_id}
                  </div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                    {aiResult.adapters_executed.map((ad, idx) => (
                      <span key={idx} className="type-tag" style={{ fontSize: "10px", background: "rgba(255,255,255,0.08)" }}>
                        {ad.adapter} ({ad.status}, {Math.round(ad.confidence * 100)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Legal Linkage & Cadastral Registration (Phase 7) */}
            <div className="detail-section" style={{ border: "1px solid #10b981", borderRadius: "8px", padding: "12px", background: "rgba(16, 185, 129, 0.05)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <h4 style={{ margin: 0, color: "#34d399" }}>🏛️ Legal & Land Registry Linkage (Phase 7)</h4>
                {isOfficer && (
                  <button
                    className="btn btn-sm btn-outline"
                    style={{ borderColor: "#10b981", color: "#6ee7b7", fontSize: "11px", padding: "3px 8px" }}
                    onClick={() => setShowLegalForm(!showLegalForm)}
                  >
                    {showLegalForm ? "Cancel" : "➕ Link Registry Record"}
                  </button>
                )}
              </div>
              <p className="subtle" style={{ margin: "4px 0 10px 0", fontSize: "12px" }}>
                Separates spatial coordinates (space) from legal ownership (rights). Owner identity is protected behind role-based access control and immutable audit logging.
              </p>

              {/* Legal Linkage Form (Officer only) */}
              {showLegalForm && isOfficer && (
                <form onSubmit={handleCreateLegalRecord} style={{ background: "rgba(0,0,0,0.3)", padding: "12px", borderRadius: "6px", marginBottom: "12px", border: "1px dashed #10b981" }}>
                  <h5 style={{ margin: "0 0 8px 0", color: "#6ee7b7", fontSize: "12px" }}>Link Authoritative Land Record</h5>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                    <div>
                      <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>ULPIN (Bhu-Aadhaar):</label>
                      <input
                        type="text"
                        value={legalUlpin}
                        onChange={(e) => setLegalUlpin(e.target.value)}
                        className="input-field"
                        placeholder="e.g. KA123456789012"
                        required
                        style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>Owner Party ID (External Ref):</label>
                      <input
                        type="text"
                        value={legalOwnerPartyId}
                        onChange={(e) => setLegalOwnerPartyId(e.target.value)}
                        className="input-field"
                        placeholder="e.g. PARTY-IND-KA-2024-001"
                        required
                        style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>Deed / Reg. Number:</label>
                      <input
                        type="text"
                        value={legalRegNo}
                        onChange={(e) => setLegalRegNo(e.target.value)}
                        className="input-field"
                        placeholder="e.g. REG/BLR/2024/991"
                        style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>Rights Type:</label>
                      <select
                        value={legalRightsType}
                        onChange={(e) => setLegalRightsType(e.target.value)}
                        className="input-field"
                        style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                      >
                        <option value="freehold">Freehold (Absolute)</option>
                        <option value="leasehold">Leasehold (Tenancy)</option>
                        <option value="strata_title">Strata Title (Unit)</option>
                        <option value="easement">Easement / Servitude</option>
                        <option value="usufruct">Usufruct</option>
                        <option value="occupancy_right">Occupancy Right</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>Source Registry:</label>
                      <input
                        type="text"
                        value={legalSourceSystem}
                        onChange={(e) => setLegalSourceSystem(e.target.value)}
                        className="input-field"
                        style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>Linkage Status:</label>
                      <select
                        value={legalLinkageStatus}
                        onChange={(e) => setLegalLinkageStatus(e.target.value)}
                        className="input-field"
                        style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                      >
                        <option value="LINKED">LINKED</option>
                        <option value="PENDING">PENDING</option>
                        <option value="DISPUTED">DISPUTED</option>
                      </select>
                    </div>
                  </div>
                  <div style={{ marginBottom: "8px" }}>
                    <label style={{ fontSize: "11px", display: "block", color: "var(--text-secondary)" }}>Encumbrances / Liens / Mortgages (Optional):</label>
                    <input
                      type="text"
                      value={legalEncumbranceDesc}
                      onChange={(e) => setLegalEncumbranceDesc(e.target.value)}
                      className="input-field"
                      placeholder="e.g. Mortgage charge registered with SBI / Bank loan"
                      style={{ width: "100%", padding: "4px 8px", fontSize: "12px" }}
                    />
                  </div>
                  <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={() => setShowLegalForm(false)}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-sm btn-success"
                      disabled={legalSubmitting}
                    >
                      {legalSubmitting ? "Linking..." : "Save Legal Linkage"}
                    </button>
                  </div>
                </form>
              )}

              {legalRecords.length === 0 ? (
                <div style={{ padding: "8px", background: "rgba(0,0,0,0.15)", borderRadius: "4px", fontSize: "12px", color: "var(--text-secondary)" }}>
                  No legal title or ULPIN linkage currently registered for this 3D spatial object.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {legalRecords.map((rec) => (
                    <div
                      key={rec.id}
                      style={{
                        padding: "10px",
                        background: "rgba(0,0,0,0.25)",
                        borderRadius: "6px",
                        fontSize: "12px",
                        borderLeft: rec.linkage_status === "LINKED" ? "3px solid #10b981" : rec.linkage_status === "DISPUTED" ? "3px solid #ef4444" : "3px solid #f59e0b",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <div>
                          <strong>ULPIN:</strong> <span className="mono" style={{ color: "#34d399" }}>{rec.ulpin}</span>
                          <span style={{ marginLeft: "8px", fontSize: "11px" }} className="type-tag">{rec.rights_type.toUpperCase()}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontSize: "10px",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontWeight: "bold",
                              background: rec.linkage_status === "LINKED" ? "rgba(16,185,129,0.2)" : rec.linkage_status === "DISPUTED" ? "rgba(239,68,68,0.2)" : "rgba(245,158,11,0.2)",
                              color: rec.linkage_status === "LINKED" ? "#34d399" : rec.linkage_status === "DISPUTED" ? "#f87171" : "#fbbf24",
                            }}
                          >
                            {rec.linkage_status}
                          </span>
                          {isOfficer && rec.linkage_status !== "UNLINKED" && (
                            <button
                              className="btn btn-sm btn-danger"
                              style={{ padding: "1px 6px", fontSize: "10px" }}
                              onClick={() => handleUnlinkLegalRecord(rec.id)}
                              disabled={legalSubmitting}
                            >
                              Unlink
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Owner Identity Section (Role-Aware) */}
                      <div style={{ margin: "6px 0", padding: "6px 8px", background: "rgba(255,255,255,0.03)", borderRadius: "4px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ color: "var(--text-secondary)" }}>Owner Identity:</span>
                          {rec.is_redacted || !isOfficer ? (
                            <span style={{ color: "#f59e0b", fontStyle: "italic", fontSize: "11px" }}>
                              🔒 Protected by Cadastral Privacy RBAC
                            </span>
                          ) : (
                            <span className="mono" style={{ color: "#a7f3d0", fontWeight: "600" }}>
                              {rec.owner_party_id} <span style={{ fontSize: "10px", color: "#6ee7b7" }}>(Officer View)</span>
                            </span>
                          )}
                        </div>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", color: "var(--text-secondary)", fontSize: "11px" }}>
                        {rec.registration_number && <div><strong>Reg No:</strong> {rec.registration_number}</div>}
                        <div><strong>Source:</strong> {rec.source_system}</div>
                        <div><strong>Synced:</strong> {new Date(rec.sync_time).toLocaleDateString()}</div>
                        <div><strong>Encumbrances:</strong> {rec.encumbrances?.length || 0} active</div>
                      </div>

                      {rec.encumbrances && rec.encumbrances.length > 0 && (
                        <div style={{ marginTop: "6px", padding: "4px 8px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "4px", fontSize: "11px" }}>
                          <strong style={{ color: "#fbbf24" }}>⚠️ Registered Encumbrances:</strong>
                          <ul style={{ margin: "2px 0 0 0", paddingLeft: "14px" }}>
                            {rec.encumbrances.map((enc, eIdx) => (
                              <li key={eIdx}>
                                <strong>{enc.type?.toUpperCase()}:</strong> {enc.description}
                                {enc.amount ? ` (Claim: ₹${enc.amount.toLocaleString()})` : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Hierarchy Tree (FR-3D-01) */}
            {hierarchy && (
              <div className="detail-section">
                <h4>3D Spatial Hierarchy (PRD §5.5)</h4>
                <div className="tree-container">
                  {renderHierarchyNode(hierarchy)}
                </div>
              </div>
            )}

            {/* Evidence & Provenance Panel */}
            <div className="detail-section">
              <h4>Provenance & Source Metadata (PRD §5.7)</h4>
              {evidenceList.length === 0 ? (
                <p className="subtle">No provenance records linked.</p>
              ) : (
                <div className="evidence-list">
                  {evidenceList.map((ev) => (
                    <div key={ev.id} className="evidence-item">
                      <div><strong>Source System:</strong> {ev.source_system}</div>
                      <div><strong>File:</strong> {ev.file_reference} ({ev.original_format?.toUpperCase()})</div>
                      <div><strong>Original CRS:</strong> {ev.original_crs}</div>
                      {ev.file_hash && (
                        <div className="mono-subtle">SHA256: {ev.file_hash.slice(0, 16)}...</div>
                      )}
                      <div className="timestamp">Captured: {new Date(ev.created_at).toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Preserved Raw Observations & Multi-Source Fusion */}
            <div className="detail-section">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h4>Preserved Observations & Fusion (PRD §5.3)</h4>
                <button
                  className="btn btn-sm btn-outline"
                  onClick={handleRefuse}
                  disabled={refuseLoading || observations.length === 0}
                >
                  {refuseLoading ? "Calculating..." : "Re-run Multi-Source Fusion"}
                </button>
              </div>
              <p className="subtle">
                Raw observations are append-only. Contradictory evidence triggers conflict alerts without losing historical records.
              </p>
              {observations.length === 0 ? (
                <p className="subtle">No raw observations recorded yet.</p>
              ) : (
                <div className="evidence-list">
                  {observations.map((obs) => (
                    <div key={obs.id} className="evidence-item">
                      <div><strong>Attribute:</strong> <span className="mono">{obs.attribute_name}</span></div>
                      <div>
                        <strong>Measured:</strong>{" "}
                        {typeof obs.observed_value === "object"
                          ? JSON.stringify(obs.observed_value)
                          : String(obs.observed_value)}
                      </div>
                      <div><strong>Reliability Weight:</strong> {Math.round(obs.source_confidence * 100)}%</div>
                      {obs.source_id && <div><strong>Source Sensor:</strong> {obs.source_id}</div>}
                      <div className="timestamp">Observed: {new Date(obs.observed_at).toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Semantic Attributes */}
            {detail.attributes && (
              <div className="detail-section">
                <h4>Semantic Attributes (JSONB)</h4>
                <pre className="code-block">{JSON.stringify(detail.attributes, null, 2)}</pre>
              </div>
            )}

            {/* Event-Sourced History Timeline */}
            <div className="detail-section">
              <h4>Event History Timeline (PRD §5.9)</h4>
              {history?.events.length === 0 ? (
                <p className="subtle">No history events logged.</p>
              ) : (
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
              )}
            </div>

            {/* Authority Verification Box (Role-Aware) */}
            <div className="detail-section verification-box">
              <h4>Authority Verification Action (PRD §5.7)</h4>
              {!isOfficer ? (
                <p className="subtle alert-warning-text">
                  🔒 Viewing as <strong>{currentRole.replace("_", " ")}</strong>. Only authenticated Verifying Officers may promote records to VERIFIED. Use the header role switcher to authorize.
                </p>
              ) : (
                <p className="subtle">
                  Only authenticated Verifying Officers may promote PROVISIONAL records to VERIFIED. Blocked if unresolved conflicts exist (VR-09).
                </p>
              )}

              <textarea
                placeholder="Official verification notes / survey reference..."
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
        ) : (
          <div className="detail-drawer empty-drawer">
            <div className="empty-state">
              <span style={{ fontSize: "32px" }}>📋</span>
              <h4>Select a Property Record</h4>
              <p className="subtle">
                Click "Inspect" on any property record to view its full dossier, provenance evidence, preserved observations, and event-sourced timeline.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
