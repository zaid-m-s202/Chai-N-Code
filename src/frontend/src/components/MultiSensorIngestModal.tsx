import React, { useState } from "react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (resultMsg: string) => void;
}

type SensorModality = "drone" | "lidar" | "gis" | "floor_plan" | "gnss" | "dem";

interface ModalityInfo {
  id: SensorModality;
  name: string;
  icon: string;
  formatTag: string;
  description: string;
  acceptedFiles: string;
  samplePath: string;
}

const MODALITIES: ModalityInfo[] = [
  {
    id: "drone",
    name: "Drone Imagery & Orthomosaic",
    icon: "🚁",
    formatTag: "drone",
    description: "Ingests high-resolution UAV orthomosaic coverage polygons, GSD (cm/px), flight altitude, and Ground Control Points (GCPs).",
    acceptedFiles: ".json,.geojson",
    samplePath: "/samples/drone_imagery_sample.json",
  },
  {
    id: "lidar",
    name: "LiDAR / 3D Point Cloud",
    icon: "🌐",
    formatTag: "lidar",
    description: "Ingests aerial/terrestrial LiDAR point cloud metadata, LAS/LAZ headers, point density (pts/m²), and classified structure clusters.",
    acceptedFiles: ".json,.geojson",
    samplePath: "/samples/lidar_point_cloud_sample.json",
  },
  {
    id: "gis",
    name: "GIS Cadastral Parcel Layers",
    icon: "🗺️",
    formatTag: "gis",
    description: "Ingests official cadastral boundary shapefiles/GeoJSON, Khasra/survey numbers, village/tehsil codes, and surface freehold parcels.",
    acceptedFiles: ".json,.geojson",
    samplePath: "/samples/gis_cadastral_parcels.json",
  },
  {
    id: "floor_plan",
    name: "Building Floor Plans (CAD/BIM)",
    icon: "🏢",
    formatTag: "floor_plan",
    description: "Ingests vector CAD/DXF/BIM architectural floor plans with unit layouts, carpet areas, ceiling heights, and basement levels.",
    acceptedFiles: ".json,.geojson",
    samplePath: "/samples/building_floor_plan_cad.json",
  },
  {
    id: "gnss",
    name: "GNSS / CORS-Based Coordinates",
    icon: "📍",
    formatTag: "gnss",
    description: "Ingests millimeter-precision RTK GNSS survey monuments and boundary control stations tied to national CORS networks.",
    acceptedFiles: ".json,.geojson",
    samplePath: "/samples/gnss_cors_survey.json",
  },
  {
    id: "dem",
    name: "DEM / DSM Elevation Models",
    icon: "🏔️",
    formatTag: "dem",
    description: "Ingests bare-earth Digital Elevation Models (DEM), surface models (DSM), and calculates normalized nDSM building heights.",
    acceptedFiles: ".json,.geojson",
    samplePath: "/samples/dem_dsm_elevation_grid.json",
  },
];

export const MultiSensorIngestModal: React.FC<Props> = ({ isOpen, onClose, onSuccess }) => {
  if (!isOpen) return null;

  const [selectedModality, setSelectedModality] = useState<SensorModality>("drone");
  const [file, setFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  const activeModality = MODALITIES.find((m) => m.id === selectedModality)!;

  const handleLoadSample = async () => {
    setStatusMessage(`Loading sample dataset for ${activeModality.name}...`);
    setIsError(false);
    try {
      // Fetch from data/samples via backend proxy or static
      const filename = `${activeModality.id === "drone" ? "drone_imagery_sample" :
        activeModality.id === "lidar" ? "lidar_point_cloud_sample" :
        activeModality.id === "gis" ? "gis_cadastral_parcels" :
        activeModality.id === "floor_plan" ? "building_floor_plan_cad" :
        activeModality.id === "gnss" ? "gnss_cors_survey" : "dem_dsm_elevation_grid"}.json`;

      // Try reading sample content
      const res = await fetch(`/api/v1/samples/${filename}`).catch(() => null);
      if (res && res.ok) {
        const text = await res.text();
        setJsonText(text);
        setStatusMessage(`✅ Loaded sample for ${activeModality.name}. Ready to ingest.`);
      } else {
        // Fallback embedded sample
        const fallbackSamples: Record<SensorModality, any> = {
          drone: {
            flight_id: "UAV-SURVEY-2026-PUN01",
            sensor: "Zenmuse P1 35mm Full-Frame",
            flight_altitude_agl_m: 80.0,
            gsd_cm_per_pixel: 1.25,
            crs: "EPSG:4326",
            coverage: {
              type: "Polygon",
              coordinates: [[[73.8450, 18.5122], [73.8462, 18.5122], [73.8462, 18.5113], [73.8450, 18.5113], [73.8450, 18.5122]]]
            }
          },
          lidar: {
            dataset_name: "Pune City Aerial LiDAR Survey",
            point_density_pts_m2: 32.5,
            clusters: [{
              id: "lidar-cluster-101",
              classification: "building",
              elevation_min: 558.0,
              elevation_max: 588.0,
              height_m: 30.0,
              volume_m3: 18500.0,
              bbox: [73.8155, 18.6008, 73.8166, 18.6014],
              name: "Kalpataru High-Rise LiDAR Cluster"
            }]
          },
          gis: {
            type: "FeatureCollection",
            features: [{
              type: "Feature",
              properties: {
                khasra_no: "112/4",
                village: "Sadashiv Peth",
                tehsil: "Haveli",
                district: "Pune",
                state: "MH",
                land_use: "Residential",
                area: 1240.5,
                ulpin: "INMH01PUN001124-SURF"
              },
              geometry: {
                type: "Polygon",
                coordinates: [[[73.8450, 18.5120], [73.8458, 18.5121], [73.8457, 18.5114], [73.8451, 18.5113], [73.8450, 18.5120]]]
              }
            }]
          },
          floor_plan: {
            building_id: 1,
            building_name: "Regency Meadows Tower A",
            base_ulpin: "INMH01PUN001124",
            ground_elevation_m: 0.0,
            units: [
              { floor: 1, unit: 101, carpet_area_sqm: 88.5, ceiling_height_m: 3.0, name: "Flat 101" },
              { floor: 2, unit: 201, carpet_area_sqm: 88.5, ceiling_height_m: 3.0, name: "Flat 201" },
              { floor: -1, unit: 1, unit_type: "parking_basement", carpet_area_sqm: 12.5, name: "Basement Slot 1" }
            ]
          },
          gnss: {
            survey_id: "CORS-SVY-2026-088",
            cors_station_id: "CORS-IN-MH-PUN01",
            fix_type: "RTK_FIXED",
            horizontal_accuracy_cm: 1.2,
            vertical_accuracy_cm: 1.8,
            boundary_points: [
              { lon: 73.8451, lat: 18.5113, elevation_m: 558.12 },
              { lon: 73.8457, lat: 18.5113, elevation_m: 558.15 },
              { lon: 73.8457, lat: 18.5119, elevation_m: 558.18 },
              { lon: 73.8451, lat: 18.5119, elevation_m: 558.14 }
            ]
          },
          dem: {
            tiles: [{
              id: "dem-tile-01",
              dem_elevation_m: 558.0,
              dsm_elevation_m: 573.0,
              ndsm_height_m: 15.0,
              vertical_datum: "EGM2008",
              bbox: [73.8452, 18.5115, 73.8458, 18.5121]
            }]
          }
        };
        setJsonText(JSON.stringify(fallbackSamples[selectedModality], null, 2));
        setStatusMessage(`✅ Loaded embedded template for ${activeModality.name}.`);
      }
    } catch (e: any) {
      setIsError(true);
      setStatusMessage(`Failed to load sample: ${e.message}`);
    }
  };

  const handleIngest = async () => {
    setIsSubmitting(true);
    setStatusMessage(`Ingesting ${activeModality.name} via ${activeModality.formatTag} adapter...`);
    setIsError(false);

    try {
      let contentBytes: Blob;
      let uploadFilename = `${selectedModality}_data.json`;

      if (file) {
        contentBytes = file;
        uploadFilename = file.name;
      } else if (jsonText.trim()) {
        contentBytes = new Blob([jsonText], { type: "application/json" });
      } else {
        throw new Error("Please select a file or enter JSON payload.");
      }

      const formData = new FormData();
      formData.append("file", contentBytes, uploadFilename);
      formData.append("source_system", `multi_sensor_${selectedModality}`);

      const res = await fetch(`/api/v1/ingestion/jobs?async_exec=false`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server responded with HTTP ${res.status}`);
      }

      const job = await res.json();
      const successMsg = `Successfully fused ${job.record_count ?? 1} records from ${activeModality.name} into the 3D cadastre (Job #${job.id.slice(0, 8)}).`;
      setStatusMessage(`✅ ${successMsg}`);
      setTimeout(() => {
        onSuccess(successMsg);
        onClose();
      }, 1500);
    } catch (e: any) {
      setIsError(true);
      setStatusMessage(`❌ Ingestion failed: ${e.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" style={{ zIndex: 9999 }}>
      <div className="modal-box" style={{ maxWidth: "780px", width: "95%" }}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "24px" }}>📡</span>
            <div>
              <h3 style={{ margin: 0 }}>Multi-Sensor Data Ingestion Center</h3>
              <div style={{ fontSize: "12px", color: "var(--text-subtle)" }}>
                Interoperable 3D Cadastral Ingestion across 6 Spatial Modalities
              </div>
            </div>
          </div>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        {/* Modality Selector Tabs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", margin: "16px 0" }}>
          {MODALITIES.map((mod) => {
            const isSelected = mod.id === selectedModality;
            return (
              <button
                key={mod.id}
                type="button"
                onClick={() => {
                  setSelectedModality(mod.id);
                  setFile(null);
                  setStatusMessage(null);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  border: isSelected ? "2px solid #38bdf8" : "1px solid var(--border)",
                  background: isSelected ? "rgba(56, 189, 248, 0.15)" : "var(--bg-secondary)",
                  color: isSelected ? "#38bdf8" : "var(--text-main)",
                  cursor: "pointer",
                  textAlign: "left",
                  fontSize: "12px",
                  fontWeight: isSelected ? 600 : 400,
                  transition: "all 0.15s ease",
                }}
              >
                <span style={{ fontSize: "18px" }}>{mod.icon}</span>
                <div>
                  <div>{mod.name.split(" ")[0]}</div>
                  <div style={{ fontSize: "10px", opacity: 0.7 }}>{mod.formatTag.toUpperCase()}</div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Description Banner */}
        <div style={{
          padding: "12px 14px",
          borderRadius: "6px",
          background: "rgba(15, 23, 42, 0.6)",
          border: "1px solid var(--border)",
          marginBottom: "16px",
          fontSize: "12px",
          lineHeight: "1.5",
        }}>
          <strong>{activeModality.icon} {activeModality.name}: </strong>
          <span style={{ color: "var(--text-subtle)" }}>{activeModality.description}</span>
        </div>

        {/* Upload or Text Area Input */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <label style={{ fontSize: "12px", fontWeight: 600 }}>Payload / Metadata (JSON/GeoJSON):</label>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                className="btn-secondary"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={handleLoadSample}
              >
                📄 Load Verified Sample
              </button>
              <label
                className="btn-secondary"
                style={{ fontSize: "11px", padding: "4px 8px", cursor: "pointer" }}
              >
                📁 Choose File
                <input
                  type="file"
                  accept={activeModality.acceptedFiles}
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setFile(f);
                      f.text().then((t) => setJsonText(t));
                      setStatusMessage(`Selected file: ${f.name} (${(f.size / 1024).toFixed(1)} KB)`);
                    }
                  }}
                />
              </label>
            </div>
          </div>

          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            placeholder={`Paste ${activeModality.name} JSON metadata or click 'Load Verified Sample'...`}
            style={{
              width: "100%",
              height: "170px",
              fontFamily: "monospace",
              fontSize: "11px",
              padding: "10px",
              borderRadius: "6px",
              background: "#090d16",
              color: "#e2e8f0",
              border: "1px solid var(--border)",
              resize: "vertical",
            }}
          />
        </div>

        {/* Status Message */}
        {statusMessage && (
          <div style={{
            padding: "10px",
            borderRadius: "6px",
            marginBottom: "16px",
            fontSize: "12px",
            background: isError ? "rgba(239, 68, 68, 0.15)" : "rgba(34, 197, 94, 0.15)",
            color: isError ? "#f87171" : "#4ade80",
            border: `1px solid ${isError ? "#ef4444" : "#22c55e"}`,
          }}>
            {statusMessage}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleIngest}
            disabled={isSubmitting || (!file && !jsonText.trim())}
          >
            {isSubmitting ? "Ingesting & Normalizing..." : `Ingest ${activeModality.name.split(" ")[0]} Dataset`}
          </button>
        </div>
      </div>
    </div>
  );
};
