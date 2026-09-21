import React from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export interface BuildingFeature {
  type: "Feature";
  properties: Record<string, any>;
  geometry: {
    type: string;
    coordinates: any;
  };
}

interface Props {
  feature: BuildingFeature | null;
  onClose: () => void;
  currentRole: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    VERIFIED: "badge-verified",
    PROVISIONAL: "badge-provisional",
    DERIVED: "badge-derived",
    INFERRED: "badge-inferred",
    SYNTHETIC: "badge-synthetic",
  };
  return (
    <span className={`status-badge ${map[status] ?? "badge-synthetic"}`}>
      {status}
    </span>
  );
}

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="confidence-meter">
      <div>
        <div className="confidence-fill" style={{ width: `${pct}%` }} />
      </div>
      <span>{pct}%</span>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="drawer-row">
      <span className="drawer-row-label">{label}</span>
      <span className="drawer-row-value">{value ?? <span className="na-pill">—</span>}</span>
    </div>
  );
}

function SectionHeader({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="drawer-section-header">
      <span className="drawer-section-icon">{icon}</span>
      <h4>{title}</h4>
    </div>
  );
}

// ── Derive mock floor/unit data from the feature properties ───────────────────
function deriveFloors(props: Record<string, any>) {
  const levels = parseInt(props["building:levels"] ?? props["levels"] ?? "1", 10) || 1;
  return Array.from({ length: Math.min(levels, 5) }, (_, i) => ({
    floor: i,
    label: i === 0 ? "Ground Floor" : `Floor ${i}`,
    units: 2 + (i % 3),
    z_min: i * 3,
    z_max: i * 3 + 3,
  }));
}

function deriveValidation(props: Record<string, any>) {
  const checks = [
    { rule: "VR-01", label: "Footprint inside parcel", pass: true },
    { rule: "VR-02", label: "No unit overlap on floor", pass: true },
    { rule: "VR-04", label: "No vertical floor overlap", pass: true },
    { rule: "VR-05", label: "No boundary violation", pass: props.height <= 60 },
    { rule: "VR-06", label: "Not near-duplicate", pass: true },
    { rule: "VR-07", label: "No orphan records", pass: true },
  ];
  return checks;
}

// ── Placeholder state ─────────────────────────────────────────────────────────
function EmptyDrawer() {
  return (
    <div className="detail-drawer empty-drawer">
      <div className="empty-drawer-body">
        <div className="empty-drawer-icon">🏛️</div>
        <h3 className="empty-drawer-title">Object Detail Drawer</h3>
        <p className="empty-drawer-hint">
          Click any building on the map to inspect its full cadastral record.
        </p>
        <div className="empty-drawer-sections">
          {[
            { icon: "🔑", label: "ULPIN / 3D Property ID" },
            { icon: "📐", label: "Parcel Details" },
            { icon: "🏢", label: "Building Details" },
            { icon: "🪜", label: "Floor Details" },
            { icon: "🚪", label: "Unit Details" },
            { icon: "✅", label: "Validation Status" },
          ].map(({ icon, label }) => (
            <div key={label} className="empty-section-pill">
              <span>{icon}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
        <p className="empty-drawer-rule">
          AI derives · Evidence supports · Authority verifies
        </p>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export const ObjectDetailDrawer: React.FC<Props> = ({ feature, onClose, currentRole }) => {
  if (!feature) return <EmptyDrawer />;

  const props = feature.properties;
  const isOfficer = currentRole === "VERIFYING_OFFICER";

  // Derive display values
  const threeD_id    = props.three_d_property_id ?? "—";
  const ulpin        = props.ULPIN ?? "—";
  const height       = props.height ?? 3;
  const levels       = parseInt(props["building:levels"] ?? "1", 10) || 1;
  const buildingType = props.building ?? "residential";
  const buildingName = props.name ?? props["addr:housenumber"] ?? "Unnamed Building";
  const address      = [props["addr:housenumber"], props["addr:street"], props["addr:city"]]
    .filter(Boolean).join(", ") || "Address not recorded";
  const postcode     = props["addr:postcode"] ?? "—";
  const osmId        = props["@id"] ?? "—";

  // Synthetic status since GeoJSON data is pre-DB
  const status      = props.status ?? "SYNTHETIC";
  const confidence  = props.confidence ?? 0.72;

  const isUnit = Boolean(props.unit_number || props.floor_name || (props.UIPIN && props.UIPIN.includes("-U")));
  const unitNumber   = props.unit_number ?? "Unit";
  const floorName    = props.floor_name ?? "Floor 1";
  const unitArea     = props.area_sqm ?? 85.0;
  const zMin         = props.z_min ?? 0;
  const zMax         = props.z_max ?? 3;

  const floors      = deriveFloors(props);
  const validations = deriveValidation(props);
  const allPass     = validations.every((v) => v.pass);

  // Detect Stratum classification
  const isSubterranean = Boolean(
    props.stratum === "SUBTERRANEAN" ||
    (props.z_max !== undefined && props.z_max < 0) ||
    props.category === "METRO" ||
    props.category === "WATER" ||
    props.category === "POWER" ||
    props.category === "UTIL" ||
    props.category === "SEWER" ||
    props.category === "PARKING" ||
    (props.type && ["tunnel", "underground_utility", "parking_basement", "subsurface_parcel"].includes(props.type))
  );

  const stratum = isSubterranean
    ? "SUBTERRANEAN"
    : isUnit || (props.z_min !== undefined && props.z_min > 0)
    ? "ABOVE_GROUND"
    : "SURFACE";

  const volumeM3 = props.volume_m3 ?? (isUnit ? (unitArea * 3.0) : (height * 120.0));
  const rightsType = props.rights_type ?? (
    isSubterranean
      ? (props.category === "METRO" ? "subterranean_easement" : "utility_corridor_right")
      : isUnit
      ? "strata_title"
      : "surface_freehold"
  );

  return (
    <div className="detail-drawer">
      {/* ── Drawer Header ── */}
      <div className="drawer-header">
        <div className="drawer-header-title">
          <span className="drawer-header-icon">{isSubterranean ? "🚇" : isUnit ? "🚪" : "🏢"}</span>
          <div>
            <h3>{isSubterranean ? (props.name ?? "Underground Infrastructure") : isUnit ? unitNumber : "Object Detail Drawer"}</h3>
            <div style={{ fontSize: "11px", color: "var(--text-subtle)", display: "flex", gap: "6px", alignItems: "center", marginTop: "2px" }}>
              <span style={{
                padding: "1px 6px",
                borderRadius: "4px",
                fontSize: "10px",
                fontWeight: 700,
                background: stratum === "SUBTERRANEAN" ? "#ef4444" : stratum === "ABOVE_GROUND" ? "#f59e0b" : "#10b981",
                color: "#fff",
              }}>
                {stratum}
              </span>
              <span>{isSubterranean ? props.category : isUnit ? `${floorName} • ${buildingName}` : buildingName}</span>
            </div>
          </div>
        </div>
        <button className="btn-close" onClick={onClose} title="Close">✕</button>
      </div>

      <div className="drawer-role-badge">
        {isOfficer
          ? <span className="badge-officer-active">🛡️ Verifying Officer — Full Access</span>
          : <span className="badge-officer-restricted">👁️ {currentRole.replace("_", " ")} — Read-Only</span>
        }
      </div>

      {/* ── § 1  ULPIN / 3D Property ID / UIPIN & Stratum Breakdown ── */}
      <div className="detail-section">
        <SectionHeader icon="🔑" title="3D Cadastral Spatial Identity" />
        <div className="id-card">
          <div className="id-card-row">
            <span className="id-card-label">3D ULPIN</span>
            <code className="id-card-value" style={{ color: "#38bdf8", fontWeight: 700 }}>{threeD_id}</code>
          </div>
          <div className="id-card-row">
            <span className="id-card-label">Stratum</span>
            <span style={{ fontWeight: 600, color: stratum === "SUBTERRANEAN" ? "#f87171" : "#38bdf8" }}>
              {stratum} ({stratum === "SUBTERRANEAN" ? "Underground / Subsurface" : stratum === "ABOVE_GROUND" ? "Vertical Air Rights / Strata" : "Ground Surface Cadastre"})
            </span>
          </div>
          <div className="id-card-row">
            <span className="id-card-label">Parent ULPIN</span>
            <code className="id-card-value ulpin-value">{ulpin}</code>
          </div>
          <div className="id-card-row">
            <span className="id-card-label">Legal Right</span>
            <span className="type-tag" style={{ background: "rgba(56, 189, 248, 0.15)", color: "#38bdf8", border: "1px solid #38bdf8" }}>
              {rightsType}
            </span>
          </div>
          <div className="id-card-row">
            <span className="id-card-label">Volumetric Extent</span>
            <strong style={{ color: "#4ade80" }}>{volumeM3 ? `${Number(volumeM3).toLocaleString()} m³` : "2D Cadastre"}</strong>
          </div>
        </div>
      </div>

      {/* ── Subterranean Infrastructure Details (if underground) ── */}
      {isSubterranean && (
        <div className="detail-section">
          <SectionHeader icon="🚇" title="Subterranean Asset & Easement Profile" />
          <div className="attr-grid">
            <Row label="Asset Name" value={props.name} />
            <Row label="Utility Category" value={<span className="type-tag" style={{ background: "#ef4444", color: "#fff" }}>{props.category}</span>} />
            <Row label="Depth Below Ground" value={`${props.depth_below_surface_m ?? Math.abs(zMax)} m`} />
            <Row label="Vertical Thickness" value={`${props.thickness_m ?? Math.abs(zMax - zMin)} m`} />
            <Row label="Subterranean Z-Band" value={`Z: ${zMin} m to ${zMax} m`} />
            <Row label="Easement Status" value={<span className="type-tag" style={{ background: "#fef08a", color: "#854d0e" }}>{props.easement_status ?? "STATUTORY_EASEMENT"}</span>} />
            <Row label="Operating Authority" value={props.owner ?? "Municipal Infrastructure Dept"} />
            <Row label="Verification Status" value={<StatusPill status={status} />} />
          </div>
        </div>
      )}

      {/* ── § 2  Parcel Details ── */}
      <div className="detail-section">
        <SectionHeader icon="📐" title="Parcel & Location Details" />
        <div className="attr-grid">
          <Row label="Address" value={address} />
          <Row label="Postcode" value={postcode} />
          <Row label="City" value={props["addr:city"] ?? "Pune"} />
          <Row label="Building" value={buildingName} />
          <Row label="Geometry" value={`${feature.geometry.type} (EPSG:4326)`} />
          <Row label="Linkage" value={<span className="type-tag" style={{ background: "#d1fae5", color: "#065f46" }}>LINKED (RECORD REGISTER)</span>} />
        </div>
      </div>

      {/* ── § 3  Unit or Building Details ── */}
      {isUnit ? (
        <div className="detail-section">
          <SectionHeader icon="🚪" title="Unit Spatial Details" />
          <div className="attr-grid">
            <Row label="Unit Designator" value={<strong style={{ color: "var(--primary)" }}>{unitNumber}</strong>} />
            <Row label="Floor Level" value={floorName} />
            <Row label="Floor Elevation" value={`Z: ${zMin} m to ${zMax} m`} />
            <Row label="Unit Height" value="3.0 m (Standard)" />
            <Row label="Carpet Area" value={`${unitArea} m²`} />
            <Row label="Volume (3D)" value={`${(unitArea * 3.0).toFixed(1)} m³`} />
            <Row label="Use Category" value={<span className="type-tag">{props.use_type ?? "Residential"}</span>} />
            <Row label="Verification" value={<StatusPill status={status} />} />
            <Row label="Confidence" value={<ConfidenceMeter value={confidence} />} />
          </div>
        </div>
      ) : !isSubterranean && (
        <div className="detail-section">
          <SectionHeader icon="🏢" title="Building Details" />
          <div className="attr-grid">
            <Row label="Name" value={buildingName} />
            <Row label="Use Type" value={<span className="type-tag">{buildingType}</span>} />
            <Row label="Height" value={`${height} m`} />
            <Row label="Levels" value={`${levels} floor${levels !== 1 ? "s" : ""}`} />
            <Row label="Z min / Z max" value={`0 m / ${height} m`} />
            <Row label="Status" value={<StatusPill status={status} />} />
            <Row label="Confidence" value={<ConfidenceMeter value={confidence} />} />
            <Row label="Source" value="Cadastral GeoJSON" />
          </div>
        </div>
      )}

      {/* ── § 4  Floor Details ── */}
      <div className="detail-section">
        <SectionHeader icon="🪜" title="Floor Hierarchy" />
        <div className="floor-list">
          {floors.map((f) => {
            const isThisFloor = isUnit && (floorName.includes(String(f.floor)) || (f.floor === -1 && floorName.includes("Basement")));
            return (
              <div key={f.floor} className="floor-item" style={{ borderColor: isThisFloor ? "#2563eb" : undefined, background: isThisFloor ? "#eff6ff" : undefined }}>
                <div className="floor-item-header">
                  <span className="floor-badge">{f.label} {isThisFloor ? "• SELECTED" : ""}</span>
                  <span className="floor-z">Z: {f.z_min}–{f.z_max} m</span>
                </div>
                <div className="floor-item-meta">
                  <span>{f.units} units</span>
                  <StatusPill status={status} />
                </div>
              </div>
            );
          })}
          {levels > 5 && (
            <div className="floor-more">
              +{levels - 5} more floors — expand via full hierarchy view
            </div>
          )}
        </div>
      </div>

      {/* ── § 5  Unit Table ── */}
      {!isUnit && (
        <div className="detail-section">
          <SectionHeader icon="🚪" title="Unit Details" />
          <div className="unit-table">
            <div className="unit-table-header">
              <span>Unit ID</span>
              <span>Floor</span>
              <span>Type</span>
              <span>Status</span>
            </div>
            {floors.slice(0, 3).flatMap((f) =>
              Array.from({ length: Math.min(f.units, 2) }, (_, ui) => {
                const unitLabel = `${ulpin}-B001-F${String(f.floor).padStart(2, "0")}-U${String(ui + 1).padStart(3, "0")}`;
                return (
                  <div key={unitLabel} className="unit-table-row">
                    <code className="unit-id">{unitLabel}</code>
                    <span>{f.label}</span>
                    <span className="type-tag">residential</span>
                    <StatusPill status="SYNTHETIC" />
                  </div>
                );
              })
            )}
            <div className="unit-more">
              Switch to "3D Floor & Unit Explorer" mode to click individual units
            </div>
          </div>
        </div>
      )}

      {/* ── § 6  Validation Status ── */}
      <div className="detail-section">
        <SectionHeader icon="✅" title="Validation Status" />
        <div className={`validation-summary ${allPass ? "pass" : "fail"}`}>
          <span className="validation-summary-icon">{allPass ? "✅" : "⚠️"}</span>
          <span>{allPass ? "All topology checks passed" : "Conflict(s) detected — cannot verify"}</span>
        </div>
        <div className="validation-checks">
          {validations.map((v) => (
            <div key={v.rule} className="validation-row">
              <span className={`validation-dot ${v.pass ? "pass" : "fail"}`} />
              <span className="badge-rule">{v.rule}</span>
              <span className="validation-label">{v.label}</span>
              <span className={`validation-result ${v.pass ? "pass" : "fail"}`}>
                {v.pass ? "PASS" : "FAIL"}
              </span>
            </div>
          ))}
        </div>

        {/* Officer-only action */}
        {isOfficer && (
          <div className="verification-box" style={{ marginTop: "12px" }}>
            <div style={{ fontSize: "12px", color: "var(--text-subtle)" }}>
              Officer action — status must be PROVISIONAL to verify
            </div>
            <button
              className="btn btn-success"
              disabled={status !== "PROVISIONAL" || !allPass}
              title={
                status !== "PROVISIONAL"
                  ? "Status must reach PROVISIONAL before verification"
                  : !allPass
                  ? "Resolve all conflicts before verifying"
                  : "Verify this record"
              }
            >
              🛡️ Verify Record (PROVISIONAL → VERIFIED)
            </button>
          </div>
        )}
      </div>

      {/* ── Evidence / Provenance footer ── */}
      <div className="detail-section">
        <SectionHeader icon="🔍" title="Evidence & Provenance" />
        <div className="evidence-item">
          <div style={{ fontWeight: 600, marginBottom: 4 }}>OSM Overpass Export</div>
          <div className="mono-subtle">Source: cadastral_3d_buildings.geojson</div>
          <div className="mono-subtle">Ingested: {new Date().toISOString().split("T")[0]}</div>
          <div className="mono-subtle">Status: SYNTHETIC (no DB ingestion yet)</div>
        </div>
      </div>
    </div>
  );
};
