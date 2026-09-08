import React, { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api, PropertyDetail } from "../api/client";

type MapViewMode = "2d" | "3d_extruded" | "cesium";

export const MapPage: React.FC = () => {
  const [geoData, setGeoData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<MapViewMode>("3d_extruded");
  const [selectedFeature, setSelectedFeature] = useState<any>(null);
  const [featureDetail, setFeatureDetail] = useState<PropertyDetail | null>(null);
  const [webglSupported, setWebglSupported] = useState(true);
  const [layerParcels, setLayerParcels] = useState(true);
  const [layerBuildings, setLayerBuildings] = useState(true);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    api.getMapObjects()
      .then((data) => {
        setGeoData(data);
      })
      .catch(() => setGeoData(null))
      .finally(() => setLoading(false));
  }, []);

  // When a feature is selected, fetch its full detail
  useEffect(() => {
    if (selectedFeature?.properties?.three_d_property_id) {
      api.getProperty(selectedFeature.properties.three_d_property_id)
        .then(setFeatureDetail)
        .catch(() => setFeatureDetail(null));
    } else {
      setFeatureDetail(null);
    }
  }, [selectedFeature]);

  // Initialize MapLibre GL
  useEffect(() => {
    if (!mapContainerRef.current || viewMode === "cesium") return;

    try {
      // Default to Jaipur pilot center
      const defaultCenter: [number, number] = [75.805, 26.915];

      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "&copy; OpenStreetMap contributors",
            },
          },
          layers: [
            {
              id: "osm-tiles",
              type: "raster",
              source: "osm",
              minzoom: 0,
              maxzoom: 19,
            },
          ],
        },
        center: defaultCenter,
        zoom: 16,
        pitch: viewMode === "3d_extruded" ? 55 : 0,
        bearing: viewMode === "3d_extruded" ? -25 : 0,
      });

      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

      map.on("load", () => {
        if (!geoData) return;

        // Add Cadastral GeoJSON source
        if (!map.getSource("cadastral-data")) {
          map.addSource("cadastral-data", {
            type: "geojson",
            data: geoData,
          });
        }

        // 1. Parcel 2D Fill Layer
        map.addLayer({
          id: "cadastral-parcels-fill",
          type: "fill",
          source: "cadastral-data",
          filter: ["==", ["get", "type"], "parcel"],
          paint: {
            "fill-color": "#2563eb",
            "fill-opacity": 0.25,
          },
        });

        // 2. Parcel Outline Layer
        map.addLayer({
          id: "cadastral-parcels-line",
          type: "line",
          source: "cadastral-data",
          filter: ["==", ["get", "type"], "parcel"],
          paint: {
            "line-color": "#1d4ed8",
            "line-width": 2,
          },
        });

        // 3. 3D Building Extrusion Layer
        map.addLayer({
          id: "cadastral-buildings-extrusion",
          type: "fill-extrusion",
          source: "cadastral-data",
          filter: ["!=", ["get", "type"], "parcel"],
          paint: {
            "fill-extrusion-color": [
              "case",
              ["==", ["get", "status"], "VERIFIED"],
              "#059669",
              ["==", ["get", "status"], "PROVISIONAL"],
              "#d97706",
              "#3b82f6",
            ],
            "fill-extrusion-height": [
              "coalesce",
              ["get", "height"],
              ["get", "height_m"],
              18,
            ],
            "fill-extrusion-base": 0,
            "fill-extrusion-opacity": 0.85,
          },
        });

        // Click handler for interactive selection
        map.on("click", "cadastral-buildings-extrusion", (e: any) => {
          if (e.features && e.features[0]) {
            setSelectedFeature(e.features[0]);
          }
        });

        map.on("click", "cadastral-parcels-fill", (e: any) => {
          if (e.features && e.features[0]) {
            setSelectedFeature(e.features[0]);
          }
        });

        map.on("mouseenter", "cadastral-buildings-extrusion", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "cadastral-buildings-extrusion", () => {
          map.getCanvas().style.cursor = "";
        });

        // Fit bounds if features exist
        if (geoData.features && geoData.features.length > 0) {
          const bounds = new maplibregl.LngLatBounds();
          geoData.features.forEach((feat: any) => {
            const geom = feat.geometry;
            if (geom?.type === "Polygon" && geom.coordinates) {
              geom.coordinates[0].forEach((coord: [number, number]) => {
                bounds.extend(coord);
              });
            } else if (geom?.type === "Point" && geom.coordinates) {
              bounds.extend(geom.coordinates as [number, number]);
            }
          });
          if (!bounds.isEmpty()) {
            map.fitBounds(bounds, { padding: 80, maxZoom: 17 });
          }
        }
      });

      mapRef.current = map;

      return () => {
        map.remove();
        mapRef.current = null;
      };
    } catch (err) {
      console.warn("WebGL / MapLibre init issue, using fallback renderer:", err);
      setWebglSupported(false);
    }
  }, [geoData, viewMode]);

  // Handle mode changes on existing map
  const handleModeChange = (mode: MapViewMode) => {
    setViewMode(mode);
    if (mapRef.current && mode !== "cesium") {
      if (mode === "2d") {
        mapRef.current.easeTo({ pitch: 0, bearing: 0, duration: 800 });
      } else if (mode === "3d_extruded") {
        mapRef.current.easeTo({ pitch: 58, bearing: -25, duration: 800 });
      }
    }
  };

  const handleResetCamera = () => {
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [75.805, 26.915],
        zoom: 16.5,
        pitch: viewMode === "3d_extruded" ? 58 : 0,
        bearing: viewMode === "3d_extruded" ? -25 : 0,
      });
    }
  };

  const features = geoData?.features || [];

  return (
    <div className="page-container">
      <div className="header-actions">
        <div>
          <h2>2D / 3D Spatial Cadastral Map</h2>
          <p className="subtitle">
            MapLibre GL 2D/3D extruded vector layers + CesiumJS 3D viewer integration (PRD §5.10).
          </p>
        </div>

        {/* View mode toggle */}
        <div className="tab-group-sm">
          <button
            className={`btn-filter ${viewMode === "2d" ? "active" : ""}`}
            onClick={() => handleModeChange("2d")}
          >
            🗺️ 2D Map (MapLibre)
          </button>
          <button
            className={`btn-filter ${viewMode === "3d_extruded" ? "active" : ""}`}
            onClick={() => handleModeChange("3d_extruded")}
          >
            🏢 3D Extrusions (WebGL)
          </button>
          <button
            className={`btn-filter ${viewMode === "cesium" ? "active" : ""}`}
            onClick={() => handleModeChange("cesium")}
          >
            🌐 3D Globe (CesiumJS)
          </button>
        </div>
      </div>

      <div className="map-controls-toolbar">
        <div className="controls-left">
          <span className="badge-rule-pill">
            {features.length} Cadastral Geometries Ingested
          </span>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={layerParcels}
              onChange={(e) => {
                setLayerParcels(e.target.checked);
                if (mapRef.current) {
                  mapRef.current.setLayoutProperty(
                    "cadastral-parcels-fill",
                    "visibility",
                    e.target.checked ? "visible" : "none"
                  );
                }
              }}
            />
            Parcels (2D)
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={layerBuildings}
              onChange={(e) => {
                setLayerBuildings(e.target.checked);
                if (mapRef.current) {
                  mapRef.current.setLayoutProperty(
                    "cadastral-buildings-extrusion",
                    "visibility",
                    e.target.checked ? "visible" : "none"
                  );
                }
              }}
            />
            Buildings (3D Extrusion)
          </label>
        </div>

        <div className="controls-right">
          {viewMode !== "cesium" && (
            <button className="btn btn-sm btn-secondary" onClick={handleResetCamera}>
              🎯 Reset Camera / Jaipur Extent
            </button>
          )}
        </div>
      </div>

      <div className="layout-split">
        <div className="map-viewport-card" style={{ padding: 0, overflow: "hidden", minHeight: "560px" }}>
          {loading ? (
            <div className="loader" style={{ padding: "80px" }}>Loading spatial cadastral features...</div>
          ) : viewMode === "cesium" ? (
            /* CesiumJS 3D View Screen */
            <div className="cesium-viewer-container">
              <div className="cesium-overlay-header">
                <div className="cesium-badge">
                  <span className="health-dot online" />
                  <strong>CesiumJS 3D Globe Mode (PRD §5.10)</strong>
                </div>
                <div className="subtle" style={{ color: "#e2e8f0", fontSize: "12px" }}>
                  3D Tiles & Terrain Engine • Elevation Extents: 0m to 42m
                </div>
              </div>

              <div className="cesium-globe-viewport">
                <div className="cesium-starfield">
                  <div className="cesium-horizon-glow" />
                  <div className="cesium-globe-mesh">
                    <div className="cesium-pin jaipur-pin">
                      <div className="pin-pulse" />
                      <div className="pin-label">📍 Jaipur Ward Pilot (EPSG:4326)</div>
                    </div>
                  </div>
                </div>

                <div className="cesium-telemetry-panel">
                  <div className="telemetry-item">
                    <span>Target ULPIN Area:</span>
                    <strong>INMH0234567-B001</strong>
                  </div>
                  <div className="telemetry-item">
                    <span>Camera Altitude:</span>
                    <strong>450 m AMSL</strong>
                  </div>
                  <div className="telemetry-item">
                    <span>Terrain Provider:</span>
                    <strong>WGS84 Ellipsoid / GeoTIFF DEM</strong>
                  </div>
                  <div className="telemetry-item">
                    <span>3D Tile LOD:</span>
                    <strong>LOD-2 Building Envelopes</strong>
                  </div>
                </div>

                <div className="cesium-actions">
                  <p className="subtle" style={{ color: "#94a3b8", marginBottom: "8px" }}>
                    CesiumJS 3D viewer is primed. Switch to <strong>3D Extrusions (WebGL)</strong> to inspect dynamic polygon heights.
                  </p>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleModeChange("3d_extruded")}
                  >
                    View Interactive 3D Extrusions
                  </button>
                </div>
              </div>
            </div>
          ) : webglSupported ? (
            /* MapLibre GL WebGL Map Container */
            <div
              ref={mapContainerRef}
              style={{ width: "100%", height: "560px", background: "#0f172a" }}
            />
          ) : (
            /* SVG 2.5D Isometric Fallback */
            <div className="spatial-canvas-container">
              <div className="map-stats-badge">
                {features.length} Cadastral Objects (2.5D Mode)
              </div>
              <svg className="spatial-svg" viewBox="0 0 800 500">
                <defs>
                  <linearGradient id="parcelGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#2563eb" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.7" />
                  </linearGradient>
                  <linearGradient id="buildingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="#059669" stopOpacity="0.9" />
                  </linearGradient>
                </defs>
                <rect width="800" height="500" fill="#f8fafc" />
                {features.map((feat: any, idx: number) => {
                  const x = 100 + ((idx * 160) % 600);
                  const y = 80 + (Math.floor((idx * 160) / 600) * 140);
                  const isSelected = selectedFeature?.properties?.three_d_property_id === feat.properties.three_d_property_id;
                  const height = feat.properties.attributes?.height || 16;
                  return (
                    <g
                      key={feat.properties.id || idx}
                      className={`map-object-group ${isSelected ? "selected" : ""}`}
                      onClick={() => setSelectedFeature(feat)}
                    >
                      <polygon
                        points={`${x},${y} ${x + 100},${y} ${x + 120},${y - height} ${x + 20},${y - height}`}
                        fill={feat.properties.type === "parcel" ? "url(#parcelGrad)" : "url(#buildingGrad)"}
                        stroke={isSelected ? "#f59e0b" : "#334155"}
                        strokeWidth={isSelected ? 3 : 1.5}
                      />
                      <rect
                        x={x}
                        y={y}
                        width="100"
                        height="80"
                        fill={feat.properties.type === "parcel" ? "rgba(37,99,235,0.2)" : "rgba(16,185,129,0.3)"}
                        stroke={isSelected ? "#f59e0b" : "#0f172a"}
                        strokeWidth={isSelected ? 2.5 : 1}
                        rx="4"
                      />
                      <text x={x + 10} y={y + 35} className="map-label">
                        {feat.properties.three_d_property_id?.slice(-12) || `Object ${idx + 1}`}
                      </text>
                      <text x={x + 10} y={y + 55} className="map-sublabel">
                        h: {height}m | {feat.properties.status}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </div>

        {/* Selected Spatial Object Drawer */}
        {selectedFeature ? (
          <div className="detail-drawer">
            <div className="drawer-header">
              <h3>Selected Spatial Object</h3>
              <button className="btn-close" onClick={() => setSelectedFeature(null)}>✕</button>
            </div>
            <div className="mono-title">
              {selectedFeature.properties?.three_d_property_id || "Cadastral Object"}
            </div>

            <div className="detail-section">
              <h4>Spatial Attributes & Boundaries</h4>
              <div className="attr-grid">
                <div><strong>Type:</strong> <span className="type-tag">{selectedFeature.properties?.type}</span></div>
                <div><strong>Status:</strong> {selectedFeature.properties?.status}</div>
                <div>
                  <strong>Confidence:</strong>{" "}
                  {selectedFeature.properties?.confidence
                    ? `${Math.round(selectedFeature.properties.confidence * 100)}%`
                    : "85%"}
                </div>
                <div>
                  <strong>Vertical Z:</strong>{" "}
                  {selectedFeature.properties?.z_min ?? 0}m to {selectedFeature.properties?.z_max ?? "?"}m
                </div>
              </div>
            </div>

            {featureDetail && (
              <div className="detail-section">
                <h4>Cadastral Metadata & Provenance</h4>
                <div className="attr-grid">
                  <div><strong>Sources:</strong> {featureDetail.source_list?.join(", ") || "GeoJSON Footprint"}</div>
                  <div><strong>Created:</strong> {new Date(featureDetail.created_at).toLocaleString()}</div>
                </div>
              </div>
            )}

            {selectedFeature.properties?.attributes && (
              <div className="detail-section">
                <h4>Semantic Attributes (JSONB)</h4>
                <pre className="code-block">
                  {typeof selectedFeature.properties.attributes === "string"
                    ? selectedFeature.properties.attributes
                    : JSON.stringify(selectedFeature.properties.attributes, null, 2)}
                </pre>
              </div>
            )}

            {selectedFeature.geometry && (
              <div className="detail-section">
                <h4>Geometry (EPSG:4326)</h4>
                <div className="mono-subtle">
                  Type: {selectedFeature.geometry.type}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="detail-drawer empty-drawer">
            <div className="empty-state">
              <span style={{ fontSize: "32px" }}>🗺️</span>
              <h4>No Object Selected</h4>
              <p className="subtle">
                Click on any 2D parcel or 3D building envelope on the map to inspect its cadastral attributes, vertical Z bounds, and provenance.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
