import React, { useState } from "react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onApplyResults?: (results: any) => void;
}

type AiToolTab = "footprint" | "floor_segmentation" | "vertical_delineation" | "topology_validator";

export const AiCadastralStudioModal: React.FC<Props> = ({ isOpen, onClose, onApplyResults }) => {
  if (!isOpen) return null;

  const [activeTab, setActiveTab] = useState<AiToolTab>("vertical_delineation");
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form states
  const [baseUlpin, setBaseUlpin] = useState("INMH01PUN001124");
  const [floorCount, setFloorCount] = useState(6);
  const [unitsPerFloor, setUnitsPerFloor] = useState(4);
  const [basementLevels, setBasementLevels] = useState(2);
  const [ceilingHeight, setCeilingHeight] = useState(3.0);
  const [includeUnderground, setIncludeUnderground] = useState(true);

  // Footprint form states
  const [scaleFactor, setScaleFactor] = useState(0.75);
  const [simplificationTol, setSimplificationTol] = useState(0.00002);

  const runFootprintExtraction = async () => {
    setIsRunning(true);
    setErrorMessage(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/analysis/extract-footprints", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bbox: [73.8450, 18.5113, 73.8462, 18.5122],
          scale_factor: scaleFactor,
          tolerance: simplificationTol,
          model_name: "CadastralMaskRCNN-V2",
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setErrorMessage(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  const runFloorSegmentation = async () => {
    setIsRunning(true);
    setErrorMessage(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/analysis/segment-floors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_ulpin: baseUlpin,
          building_id: 1,
          floor_number: 2,
          units_count: unitsPerFloor,
          ceiling_height_m: ceilingHeight,
          corridor_ratio: 0.12,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setErrorMessage(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  const runVerticalDelineation = async () => {
    setIsRunning(true);
    setErrorMessage(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/analysis/delineate-vertical-parcels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_ulpin: baseUlpin,
          state: "MH",
          district: "PUN",
          floor_count: floorCount,
          units_per_floor: unitsPerFloor,
          basement_levels: basementLevels,
          ceiling_height_m: ceilingHeight,
          ground_elevation_m: 558.0,
          include_underground_utilities: includeUnderground,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setErrorMessage(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  const runTopologyValidation = async () => {
    setIsRunning(true);
    setErrorMessage(null);
    setResult(null);

    try {
      // Use synthesized stack from vertical delineation or sample objects
      const testParcels = [
        {
          three_d_property_id: `${baseUlpin}-SURF`,
          type: "parcel",
          stratum: "SURFACE",
          z_min: 558.0,
          z_max: 558.0,
        },
        {
          three_d_property_id: `${baseUlpin}-B001-B01-P001`,
          type: "parking_basement",
          stratum: "SUBTERRANEAN",
          z_min: 555.0,
          z_max: 558.0,
        },
        {
          three_d_property_id: `${baseUlpin}-B001-F01-U001`,
          type: "unit",
          stratum: "ABOVE_GROUND",
          z_min: 558.0,
          z_max: 561.0,
        },
        {
          three_d_property_id: `${baseUlpin}-UG-METRO-T01`,
          type: "tunnel",
          stratum: "SUBTERRANEAN",
          z_min: 534.0,
          z_max: 540.0,
        },
      ];

      const res = await fetch("/api/v1/analysis/validate-3d-topology", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          parcels: testParcels,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setErrorMessage(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="modal-backdrop" style={{ zIndex: 9999 }}>
      <div className="modal-box" style={{ maxWidth: "860px", width: "95%", maxHeight: "90vh", overflowY: "auto" }}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "24px" }}>🧠</span>
            <div>
              <h3 style={{ margin: 0 }}>AI / ML Cadastral Intelligence Studio</h3>
              <div style={{ fontSize: "12px", color: "var(--text-subtle)" }}>
                Automated 3D Cadastral Synthesis, Vertical Parcel Delineation & Topology Validation
              </div>
            </div>
          </div>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border)", margin: "16px 0 20px" }}>
          {[
            { id: "vertical_delineation", label: "🏢 3D Vertical Parcel Delineation" },
            { id: "floor_segmentation", label: "🚪 Floor Plan Unit Segmentation" },
            { id: "footprint", label: "📐 Drone/LiDAR Footprint Extraction" },
            { id: "topology_validator", label: "🛡️ Intelligent 3D Topology Validator" },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setActiveTab(t.id as AiToolTab);
                setResult(null);
                setErrorMessage(null);
              }}
              style={{
                background: "transparent",
                border: "none",
                borderBottom: activeTab === t.id ? "2px solid #38bdf8" : "2px solid transparent",
                color: activeTab === t.id ? "#38bdf8" : "var(--text-subtle)",
                fontWeight: activeTab === t.id ? 600 : 400,
                padding: "8px 12px",
                cursor: "pointer",
                fontSize: "12px",
                transition: "all 0.15s ease",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab Content: Vertical Delineation */}
        {activeTab === "vertical_delineation" && (
          <div>
            <div style={{ background: "rgba(56, 189, 248, 0.08)", padding: "12px", borderRadius: "6px", marginBottom: "16px", fontSize: "12px" }}>
              <strong>Multi-Stratum 3D Volumetric Cadastre Synthesis: </strong>
              Generates complete spatial identities across subterranean utilities/basements, surface land freehold, above-ground apartment strata units, and rooftop air rights.
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Base Parcel ULPIN:</label>
                <input
                  type="text"
                  value={baseUlpin}
                  onChange={(e) => setBaseUlpin(e.target.value)}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Above-Ground Floors:</label>
                <input
                  type="number"
                  value={floorCount}
                  onChange={(e) => setFloorCount(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Units per Floor:</label>
                <input
                  type="number"
                  value={unitsPerFloor}
                  onChange={(e) => setUnitsPerFloor(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Basement Levels (B1, B2...):</label>
                <input
                  type="number"
                  value={basementLevels}
                  onChange={(e) => setBasementLevels(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <input
                type="checkbox"
                id="chk-ug"
                checked={includeUnderground}
                onChange={(e) => setIncludeUnderground(e.target.checked)}
              />
              <label htmlFor="chk-ug" style={{ fontSize: "12px", cursor: "pointer" }}>
                Synthesize Subterranean Infrastructure (Metro Line Tunnel & High-Pressure Water Trunk Corridor)
              </label>
            </div>

            <button
              type="button"
              className="btn-primary"
              onClick={runVerticalDelineation}
              disabled={isRunning}
              style={{ width: "100%", padding: "10px", fontWeight: 600 }}
            >
              {isRunning ? "Synthesizing 3D Cadastral Volumetric Stack..." : "✨ Run AI Vertical Parcel Delineator"}
            </button>
          </div>
        )}

        {/* Tab Content: Floor Segmentation */}
        {activeTab === "floor_segmentation" && (
          <div>
            <div style={{ background: "rgba(56, 189, 248, 0.08)", padding: "12px", borderRadius: "6px", marginBottom: "16px", fontSize: "12px" }}>
              <strong>AI Architectural Floor Plan Segmentation (PlanNet-V2): </strong>
              Decomposes building floor footprints into strata apartment units, common corridors, and calculates carpet area vs built-up area.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Target Units on Floor:</label>
                <input
                  type="number"
                  value={unitsPerFloor}
                  onChange={(e) => setUnitsPerFloor(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Ceiling Height (meters):</label>
                <input
                  type="number"
                  step="0.1"
                  value={ceilingHeight}
                  onChange={(e) => setCeilingHeight(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={runFloorSegmentation}
              disabled={isRunning}
              style={{ width: "100%", padding: "10px", fontWeight: 600 }}
            >
              {isRunning ? "Partitioning Strata Floor Units..." : "✨ Run AI Floor Plan Unit Segmenter"}
            </button>
          </div>
        )}

        {/* Tab Content: Footprint Extraction */}
        {activeTab === "footprint" && (
          <div>
            <div style={{ background: "rgba(56, 189, 248, 0.08)", padding: "12px", borderRadius: "6px", marginBottom: "16px", fontSize: "12px" }}>
              <strong>Automated Building Footprint Extraction: </strong>
              Uses CadastralMaskRCNN and Douglas-Peucker simplification to infer orthogonal building footprints from Drone imagery or cadastral parcel bounds.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Parcel Setback Scale Factor:</label>
                <input
                  type="number"
                  step="0.05"
                  value={scaleFactor}
                  onChange={(e) => setScaleFactor(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
              <div>
                <label style={{ fontSize: "11px", fontWeight: 600, display: "block", marginBottom: "4px" }}>Simplification Tolerance:</label>
                <input
                  type="number"
                  step="0.00001"
                  value={simplificationTol}
                  onChange={(e) => setSimplificationTol(Number(e.target.value))}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-secondary)", color: "#fff", fontSize: "12px" }}
                />
              </div>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={runFootprintExtraction}
              disabled={isRunning}
              style={{ width: "100%", padding: "10px", fontWeight: 600 }}
            >
              {isRunning ? "Extracting Footprints..." : "✨ Run AI Footprint Extractor"}
            </button>
          </div>
        )}

        {/* Tab Content: Topology Validation */}
        {activeTab === "topology_validator" && (
          <div>
            <div style={{ background: "rgba(56, 189, 248, 0.08)", padding: "12px", borderRadius: "6px", marginBottom: "16px", fontSize: "12px" }}>
              <strong>Intelligent 3D Cadastral Topology Validation Engine: </strong>
              Enforces VR-3D-01 (volumetric collisions), VR-3D-02 (footprint containment), VR-3D-03 (vertical Z-bands), VR-3D-04 (subterranean utility clearance), VR-3D-05 (volume conservation), and VR-3D-06 (3D ULPIN syntax).
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={runTopologyValidation}
              disabled={isRunning}
              style={{ width: "100%", padding: "10px", fontWeight: 600 }}
            >
              {isRunning ? "Evaluating 3D Topology Rules..." : "🛡️ Run 3D Volumetric Topology Validator"}
            </button>
          </div>
        )}

        {/* Error Output */}
        {errorMessage && (
          <div style={{ marginTop: "16px", padding: "12px", borderRadius: "6px", background: "rgba(239, 68, 68, 0.15)", color: "#f87171", border: "1px solid #ef4444", fontSize: "12px" }}>
            ❌ Error: {errorMessage}
          </div>
        )}

        {/* Results Card */}
        {result && (
          <div style={{ marginTop: "20px", padding: "16px", borderRadius: "8px", background: "#090d16", border: "1px solid #38bdf8" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "18px" }}>✅</span>
                <span style={{ fontWeight: 600, fontSize: "14px", color: "#38bdf8" }}>{result.adapter_name}</span>
                <span style={{ fontSize: "11px", padding: "2px 6px", borderRadius: "4px", background: "rgba(245, 158, 11, 0.2)", color: "#f59e0b", border: "1px solid #f59e0b" }}>
                  {result.status}
                </span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-subtle)" }}>
                Confidence: <strong style={{ color: "#4ade80" }}>{(result.confidence * 100).toFixed(0)}%</strong>
              </div>
            </div>

            {/* If Vertical Delineation */}
            {result.data?.parcels && (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", marginBottom: "12px" }}>
                  <div style={{ background: "rgba(255,255,255,0.05)", padding: "8px", borderRadius: "4px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", color: "var(--text-subtle)" }}>Total 3D Parcels</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: "#38bdf8" }}>{result.data.total_parcels_delineated}</div>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.05)", padding: "8px", borderRadius: "4px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", color: "var(--text-subtle)" }}>Total Volume (m³)</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: "#4ade80" }}>{result.data.total_volumetric_envelope_m3?.toLocaleString()}</div>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.05)", padding: "8px", borderRadius: "4px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", color: "var(--text-subtle)" }}>Subterranean</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: "#ef4444" }}>{result.data.stratum_breakdown?.subterranean_count}</div>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.05)", padding: "8px", borderRadius: "4px", textAlign: "center" }}>
                    <div style={{ fontSize: "10px", color: "var(--text-subtle)" }}>Above-Ground</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: "#f59e0b" }}>{result.data.stratum_breakdown?.above_ground_count}</div>
                  </div>
                </div>

                <div style={{ maxHeight: "160px", overflowY: "auto", fontSize: "11px", border: "1px solid var(--border)", borderRadius: "4px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ background: "rgba(255,255,255,0.05)", textAlign: "left" }}>
                        <th style={{ padding: "6px" }}>3D ULPIN</th>
                        <th style={{ padding: "6px" }}>Stratum</th>
                        <th style={{ padding: "6px" }}>Z-Range (m)</th>
                        <th style={{ padding: "6px" }}>Volume (m³)</th>
                        <th style={{ padding: "6px" }}>Right</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.data.parcels.slice(0, 12).map((p: any) => (
                        <tr key={p.three_d_property_id} style={{ borderTop: "1px solid var(--border)" }}>
                          <td style={{ padding: "6px", fontFamily: "monospace", color: "#38bdf8" }}>{p.three_d_property_id}</td>
                          <td style={{ padding: "6px" }}>{p.stratum}</td>
                          <td style={{ padding: "6px" }}>{p.z_min.toFixed(1)} to {p.z_max.toFixed(1)}</td>
                          <td style={{ padding: "6px" }}>{p.volume_m3?.toFixed(1)}</td>
                          <td style={{ padding: "6px", opacity: 0.8 }}>{p.rights_type}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* If Topology Validator */}
            {result.data?.violations !== undefined && (
              <div>
                <div style={{
                  padding: "10px 14px",
                  borderRadius: "6px",
                  marginBottom: "12px",
                  background: result.data.is_valid ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                  color: result.data.is_valid ? "#4ade80" : "#f87171",
                  border: `1px solid ${result.data.is_valid ? "#22c55e" : "#ef4444"}`,
                  fontSize: "13px",
                  fontWeight: 600,
                }}>
                  {result.data.is_valid
                    ? `🛡️ 3D Cadastral Topology Integrity PASS (All ${result.data.total_objects_tested} volumetric objects verified)`
                    : `⚠️ ${result.data.total_violations} Topology Violations Detected`}
                </div>

                {result.data.violations.length > 0 ? (
                  <div style={{ maxHeight: "140px", overflowY: "auto", fontSize: "11px" }}>
                    {result.data.violations.map((v: any, idx: number) => (
                      <div key={idx} style={{ padding: "6px 8px", borderRadius: "4px", background: "rgba(255,255,255,0.03)", marginBottom: "4px", display: "flex", gap: "8px" }}>
                        <span style={{ color: "#ef4444", fontWeight: 700 }}>[{v.rule_code}]</span>
                        <span>{v.description}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: "12px", color: "var(--text-subtle)" }}>
                    Verified VR-3D-01 (Volumetric Disjointness), VR-3D-02 (Parent Containment), VR-3D-03 (Z-Band Validity), VR-3D-04 (Subterranean Clearance), VR-3D-05 (Volumetric Conservation), and VR-3D-06 (3D ULPIN Syntax).
                  </div>
                )}
              </div>
            )}

            {/* If Floor Segmentation or Footprint */}
            {(result.data?.units || result.data?.metrics) && (
              <div style={{ fontSize: "12px" }}>
                <pre style={{ margin: 0, padding: "8px", background: "rgba(0,0,0,0.5)", borderRadius: "4px", maxHeight: "150px", overflowY: "auto" }}>
                  {JSON.stringify(result.data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
