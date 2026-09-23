import React, { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { ObjectDetailDrawer, BuildingFeature } from "../components/ObjectDetailDrawer";
import { MultiSensorIngestModal } from "../components/MultiSensorIngestModal";
import { AiCadastralStudioModal } from "../components/AiCadastralStudioModal";
import { API_BASE } from "../api/client";

// ── Props ─────────────────────────────────────────────────────────────────────
interface MapPageProps {
  currentRole?: string;
}

type MapViewMode = "2d" | "3d_extruded" | "3d_units" | "cesium";
type StratumFilter = "ALL" | "SUBTERRANEAN" | "SURFACE" | "ABOVE_GROUND";

// ── Pune pilot extent (Savitribai Phule Pune University SCMS Campus) ─────────
export const PUNE_PILOT_CENTER: [number, number] = [73.82934, 18.54866];
export const PUNE_PILOT_ZOOM = 17.5;
export const PUNE_PILOT_PITCH = 58;
export const PUNE_PILOT_BEARING = -22;

export const MapPage: React.FC<MapPageProps> = ({ currentRole = "VERIFYING_OFFICER" }) => {
  const [geoData, setGeoData]           = useState<any>(null);
  const [unitsData, setUnitsData]       = useState<any>(null);
  const [undergroundData, setUndergroundData] = useState<any>(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [viewMode, setViewMode]         = useState<MapViewMode>("3d_units");
  const [stratumFilter, setStratumFilter] = useState<StratumFilter>("ALL");
  const [selectedFeature, setSelectedFeature] = useState<BuildingFeature | null>(null);
  const [webglSupported, setWebglSupported]   = useState(true);
  const [layerBuildings, setLayerBuildings]   = useState(true);
  const [layerUnderground, setLayerUnderground] = useState(false);
  const [mapLoaded, setMapLoaded]             = useState(false);
  const [searchQuery, setSearchQuery]         = useState("");
  const [explosionGap, setExplosionGap] = useState<number>(0); // default 0m Stacked view matching Photo 1
  const [selectedFloor, setSelectedFloor] = useState<string>("ALL"); // "ALL", "-1", "1", "2", "3", "4+"

  const [dataSource, setDataSource]   = useState<"api" | "static">("api");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [uploading, setUploading]     = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const [showMultiSensorModal, setShowMultiSensorModal] = useState(false);
  const [showAiStudioModal, setShowAiStudioModal] = useState(false);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef          = useRef<maplibregl.Map | null>(null);

  // ── 1. Load cadastral buildings & units (Parallel, bounded API first) ─────
  const loadMapData = async () => {
    setLoading(true);
    setError(null);

    // Pilot bounding box around Pune SCMS campus: [minLon, minLat, maxLon, maxLat]
    const pilotBbox = "73.815,18.535,73.845,18.565";

    // A. Building footprints (fast static local GeoJSON)
    const bldgPromise = fetch("/cadastral_3d_buildings.geojson")
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setGeoData(data);
          return data;
        }
        return null;
      })
      .catch((e) => {
        console.warn("Buildings file not reachable:", e);
        return null;
      });

    // B. Live 3D Units fetch: use bounded viewport request to prevent 502/OOM
    const unitsPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/map/units?bbox=${pilotBbox}&limit=1000`);
        if (res.ok) {
          const json = await res.json();
          if (json && json.features && json.features.length > 0) {
            setUnitsData(json);
            setDataSource("api");
            console.log(`Loaded ${json.features.length} units from Live Database API (bbox).`);
            return json;
          }
        }
      } catch (e) {
        console.warn("Targeted /map/units request failed:", e);
      }

      // Fallback: bounded general limit (500) if bbox query returned 0 features
      try {
        const res = await fetch(`${API_BASE}/map/units?limit=500`);
        if (res.ok) {
          const json = await res.json();
          if (json && json.features && json.features.length > 0) {
            setUnitsData(json);
            setDataSource("api");
            console.log(`Loaded ${json.features.length} units from Live Database API (limit=500).`);
            return json;
          }
        }
      } catch (e) {
        console.warn("Fallback /map/units request failed:", e);
      }
      return null;
    })();

    // C. Underground infrastructure (API first, static fallback)
    const ugPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/map/underground?limit=5000`);
        if (res.ok) {
          const json = await res.json();
          if (json && json.features && json.features.length > 0) {
            setUndergroundData(json);
            return json;
          }
        }
      } catch (e) {
        console.warn("Underground API endpoint not reachable:", e);
      }

      try {
        const res = await fetch("/underground_infrastructure.geojson");
        if (res.ok) {
          const json = await res.json();
          setUndergroundData(json);
          return json;
        }
      } catch (e) {
        console.warn("Static underground file not reachable:", e);
      }
      return null;
    })();

    const [bldgData, uData] = await Promise.all([bldgPromise, unitsPromise, ugPromise]);
    if (!bldgData && !uData) {
      setError("Could not load cadastral datasets from API or static storage.");
    }
    setLoading(false);
  };

  useEffect(() => {
    loadMapData();
  }, []);

  // ── Refresh data from Database API ───────────────────────────────────────
  const refreshFromDb = async () => {
    setIsRefreshing(true);
    setUploadStatus("Querying fresh 3D property records & subterranean assets from database...");
    const pilotBbox = "73.815,18.535,73.845,18.565";
    try {
      const res = await fetch(`${API_BASE}/map/units?bbox=${pilotBbox}&limit=1000`);
      if (res.ok) {
        const json = await res.json();
        if (json && json.features && json.features.length > 0) {
          setUnitsData(json);
          setDataSource("api");
        }
      }

      // Also refresh underground infrastructure
      const ugRes = await fetch(`${API_BASE}/map/underground?limit=5000`).catch(() => null);
      if (ugRes && ugRes.ok) {
        const ugJson = await ugRes.json();
        if (ugJson && ugJson.features) {
          setUndergroundData(ugJson);
        }
      }

      setUploadStatus("Refreshed! Synchronized 3D cadastre & underground infrastructure from live database.");
      setTimeout(() => setUploadStatus(null), 5000);
    } catch (err: any) {
      setUploadStatus(`Refresh error: ${err.message}`);
      setTimeout(() => setUploadStatus(null), 5000);
    } finally {
      setIsRefreshing(false);
    }
  };

  // ── Quick Ingestion from Map View ─────────────────────────────────────────
  const handleQuickIngest = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadStatus(`Uploading ${file.name} to ingestion pipeline...`);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_system", "field_survey_upload");

    try {
      const res = await fetch(`${API_BASE}/ingestion/jobs?async_exec=false`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with HTTP ${res.status}`);
      }
      const job = await res.json();
      setUploadStatus(
        `✅ Ingestion complete! Job #${job.id.slice(0, 8)}: ${job.record_count ?? 0} records fused with provenance.`
      );
      await refreshFromDb();
    } catch (err: any) {
      setUploadStatus(`❌ Ingestion failed: ${err.message}`);
      setTimeout(() => setUploadStatus(null), 7000);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };


  // ── 2. Initialise MapLibre GL (Independent lifecycle, mounted once) ───────
  useEffect(() => {
    if (!mapContainerRef.current || viewMode === "cesium") return;

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
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
          layers: [{ id: "osm-tiles", type: "raster", source: "osm" }],
        },
        center: PUNE_PILOT_CENTER,
        zoom: PUNE_PILOT_ZOOM,
        pitch: viewMode === "2d" ? 0 : PUNE_PILOT_PITCH,
        bearing: viewMode === "2d" ? 0 : PUNE_PILOT_BEARING,
      });

      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

      map.on("load", () => {
        setMapLoaded(true);
        map.jumpTo({
          center: PUNE_PILOT_CENTER,
          zoom: PUNE_PILOT_ZOOM,
          pitch: viewMode === "2d" ? 0 : PUNE_PILOT_PITCH,
          bearing: viewMode === "2d" ? 0 : PUNE_PILOT_BEARING,
        });
      });

      mapRef.current = map;
    } catch (err) {
      console.warn("WebGL init failed, using fallback:", err);
      setWebglSupported(false);
    }

    return () => {
      setMapLoaded(false);
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode === "cesium"]);

  // ── 2a. Sync Buildings Source & Layers ────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !geoData) return;

    const existingSource = map.getSource("cadastral_3d_buildings") as maplibregl.GeoJSONSource;
    if (existingSource) {
      existingSource.setData(geoData);
    } else {
      map.addSource("cadastral_3d_buildings", {
        type: "geojson",
        data: geoData,
      });

      // 1. Black dashed outlines (Standard cadastral footprint styling for 2D mode)
      if (!map.getLayer("cadastral-buildings-dashed-outline")) {
        map.addLayer({
          id: "cadastral-buildings-dashed-outline",
          type: "line",
          source: "cadastral_3d_buildings",
          paint: {
            "line-color": "#000000",
            "line-width": 1.5,
            "line-dasharray": [3, 2],
          },
          layout: {
            visibility: viewMode === "2d" ? "visible" : "none",
          },
        });
      }

      // 2. Standard 3D Building Envelopes (Clean architectural massing)
      if (!map.getLayer("cadastral-buildings-3d")) {
        const showBuildingFallback =
          (viewMode === "3d_extruded" ||
            (viewMode === "3d_units" && (!unitsData || !unitsData.features || unitsData.features.length === 0))) &&
          layerBuildings;
        map.addLayer({
          id: "cadastral-buildings-3d",
          type: "fill-extrusion",
          source: "cadastral_3d_buildings",
          paint: {
            "fill-extrusion-color": "#94a3b8",
            "fill-extrusion-height": ["coalesce", ["get", "height"], 3],
            "fill-extrusion-base": 0,
            "fill-extrusion-opacity": 0.85,
          },
          layout: {
            visibility: showBuildingFallback ? "visible" : "none",
          },
        });
      }

      // 3. Flat footprint highlight for 2D mode
      if (!map.getLayer("cadastral-buildings-flat")) {
        map.addLayer({
          id: "cadastral-buildings-flat",
          type: "fill",
          source: "cadastral_3d_buildings",
          paint: {
            "fill-color": "#94a3b8",
            "fill-opacity": 0.65,
          },
          layout: {
            visibility: viewMode === "2d" ? "visible" : "none",
          },
        });
      }

      // 4. Translucent Glass Building Envelope (for Unit Explorer)
      if (!map.getLayer("cadastral-building-envelope-glass")) {
        map.addLayer({
          id: "cadastral-building-envelope-glass",
          type: "fill-extrusion",
          source: "cadastral_3d_buildings",
          paint: {
            "fill-extrusion-color": "#38bdf8",
            "fill-extrusion-height": ["coalesce", ["get", "height"], 9],
            "fill-extrusion-base": 0,
            "fill-extrusion-opacity": 0.16,
          },
          layout: {
            visibility: viewMode === "3d_units" && layerBuildings ? "visible" : "none",
          },
        });
      }

      // 6. Selected building outline
      if (!map.getLayer("cadastral-buildings-selected")) {
        map.addLayer({
          id: "cadastral-buildings-selected",
          type: "line",
          source: "cadastral_3d_buildings",
          filter: ["==", "three_d_property_id", ""],
          paint: {
            "line-color": "#b91c1c",
            "line-width": 3,
          },
        });
      }

      // Click & hover handlers on buildings
      ["cadastral-buildings-3d", "cadastral-buildings-flat"].forEach((layer) => {
        map.on("click", layer, (e: any) => {
          const feat = e.features?.[0];
          if (!feat) return;

          const three_d_property_id = feat.properties?.three_d_property_id;
          const ulpin = feat.properties?.ULPIN;

          if (three_d_property_id && map.getLayer("cadastral-buildings-selected")) {
            map.setFilter("cadastral-buildings-selected", ["==", "three_d_property_id", three_d_property_id]);
          }

          const fullFeature = geoData?.features?.find(
            (f: any) =>
              (three_d_property_id && f.properties?.three_d_property_id === three_d_property_id) ||
              (ulpin && f.properties?.ULPIN === ulpin)
          );

          setSelectedFeature(fullFeature ?? (feat as BuildingFeature));
        });

        map.on("mouseenter", layer, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layer, () => {
          map.getCanvas().style.cursor = "";
        });
      });
    }
  }, [mapLoaded, geoData]);

  // ── 2b. Sync Units Source & Layers ────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !unitsData) return;

    const existingSource = map.getSource("cadastral_3d_units") as maplibregl.GeoJSONSource;
    if (existingSource) {
      existingSource.setData(unitsData);
    } else {
      map.addSource("cadastral_3d_units", {
        type: "geojson",
        data: unitsData,
      });

      const gap = explosionGap;
      // 5. 3D Floor & Unit Extrusion with Exploded Separation
      if (!map.getLayer("cadastral-units-3d")) {
        map.addLayer({
          id: "cadastral-units-3d",
          type: "fill-extrusion",
          source: "cadastral_3d_units",
          paint: {
            "fill-extrusion-color": ["coalesce", ["get", "color"], "#f59e0b"],
            "fill-extrusion-base": [
              "+",
              ["coalesce", ["get", "z_min"], 0],
              [
                "*",
                [
                  "case",
                  ["==", ["get", "floor_number"], -1], -1,
                  [">", ["get", "floor_number"], 0], ["-", ["get", "floor_number"], 1],
                  0,
                ],
                gap,
              ],
            ],
            "fill-extrusion-height": [
              "+",
              ["coalesce", ["get", "z_max"], 3],
              [
                "*",
                [
                  "case",
                  ["==", ["get", "floor_number"], -1], -1,
                  [">", ["get", "floor_number"], 0], ["-", ["get", "floor_number"], 1],
                  0,
                ],
                gap,
              ],
            ],
            "fill-extrusion-opacity": 0.92,
          },
          layout: {
            visibility: viewMode === "3d_units" ? "visible" : "none",
          },
        });
      }

      // Unit line boundary
      if (!map.getLayer("cadastral-units-outline")) {
        map.addLayer({
          id: "cadastral-units-outline",
          type: "line",
          source: "cadastral_3d_units",
          paint: {
            "line-color": "#0f172a",
            "line-width": 1.2,
            "line-opacity": 0.5,
          },
          layout: {
            visibility: viewMode === "3d_units" ? "visible" : "none",
          },
        });
      }

      // Unit selected highlight layer
      if (!map.getLayer("cadastral-unit-selected")) {
        map.addLayer({
          id: "cadastral-unit-selected",
          type: "line",
          source: "cadastral_3d_units",
          filter: ["==", "three_d_property_id", ""],
          paint: {
            "line-color": "#ef4444",
            "line-width": 3,
          },
        });
      }

      // Click & hover on units
      map.on("click", "cadastral-units-3d", (e: any) => {
        const feat = e.features?.[0];
        if (!feat) return;

        const uipin = feat.properties?.UIPIN || feat.properties?.three_d_property_id;
        console.log("3D Unit clicked:", {
          uipin,
          unit_number: feat.properties?.unit_number,
          floor_name: feat.properties?.floor_name,
          z_min: feat.properties?.z_min,
          z_max: feat.properties?.z_max,
        });

        if (uipin && map.getLayer("cadastral-unit-selected")) {
          map.setFilter("cadastral-unit-selected", ["==", "three_d_property_id", uipin]);
        }

        const unitFeature: BuildingFeature = {
          type: "Feature",
          properties: { ...feat.properties, three_d_property_id: uipin },
          geometry: feat.geometry,
        };
        setSelectedFeature(unitFeature);
      });

      map.on("mouseenter", "cadastral-units-3d", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "cadastral-units-3d", () => {
        map.getCanvas().style.cursor = "";
      });
    }

    // When unit data arrives, if in 3d_units mode, hide solid building extrusion fallback
    // and show units extrusion
    if (viewMode === "3d_units") {
      if (map.getLayer("cadastral-buildings-3d")) {
        map.setLayoutProperty("cadastral-buildings-3d", "visibility", "none");
      }
      if (map.getLayer("cadastral-units-3d")) {
        map.setLayoutProperty("cadastral-units-3d", "visibility", layerBuildings ? "visible" : "none");
      }
      if (map.getLayer("cadastral-units-outline")) {
        map.setLayoutProperty("cadastral-units-outline", "visibility", layerBuildings ? "visible" : "none");
      }
      if (map.getLayer("cadastral-building-envelope-glass")) {
        map.setLayoutProperty("cadastral-building-envelope-glass", "visibility", layerBuildings ? "visible" : "none");
      }
    }

    // Pre-select Unit 1B of SCMS building if available
    const defaultUnitId = "27-21-13-255-000022-B001-F01-U012";
    const defaultUnit = unitsData?.features?.find(
      (f: any) => f.properties?.three_d_property_id === defaultUnitId
    );
    if (defaultUnit) {
      setSelectedFeature(defaultUnit as BuildingFeature);
      if (map.getLayer("cadastral-unit-selected")) {
        map.setFilter("cadastral-unit-selected", ["==", "three_d_property_id", defaultUnitId]);
      }
    }
  }, [mapLoaded, unitsData]);

  // ── 2c. Sync Underground Source & Layers ──────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !undergroundData) return;

    const existingSource = map.getSource("underground_infrastructure") as maplibregl.GeoJSONSource;
    if (existingSource) {
      existingSource.setData(undergroundData);
    } else {
      map.addSource("underground_infrastructure", {
        type: "geojson",
        data: undergroundData,
      });

      if (!map.getLayer("underground-infrastructure-3d")) {
        map.addLayer({
          id: "underground-infrastructure-3d",
          type: "fill-extrusion",
          source: "underground_infrastructure",
          paint: {
            "fill-extrusion-color": ["coalesce", ["get", "color"], "#ef4444"],
            "fill-extrusion-height": [
              "+",
              ["abs", ["-", ["coalesce", ["get", "z_max"], 0], ["coalesce", ["get", "z_min"], -5]]],
              2,
            ],
            "fill-extrusion-base": 0,
            "fill-extrusion-opacity": 0.85,
          },
          layout: {
            visibility: layerUnderground ? "visible" : "none",
          },
        });
      }

      if (!map.getLayer("underground-infrastructure-outline")) {
        map.addLayer({
          id: "underground-infrastructure-outline",
          type: "line",
          source: "underground_infrastructure",
          paint: {
            "line-color": ["coalesce", ["get", "color"], "#ef4444"],
            "line-width": 2.5,
            "line-dasharray": [2, 1],
          },
          layout: {
            visibility: layerUnderground ? "visible" : "none",
          },
        });
      }

      map.on("click", "underground-infrastructure-3d", (e: any) => {
        const feat = e.features?.[0];
        if (!feat) return;
        const threeD_id = feat.properties?.three_d_property_id || feat.properties?.id;
        setSelectedFeature({
          type: "Feature",
          properties: {
            ...feat.properties,
            three_d_property_id: threeD_id,
            stratum: "SUBTERRANEAN",
          },
          geometry: feat.geometry,
        });
      });

      map.on("mouseenter", "underground-infrastructure-3d", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "underground-infrastructure-3d", () => {
        map.getCanvas().style.cursor = "";
      });
    }
  }, [mapLoaded, undergroundData]);

  // ── 3. Dynamic Exploded View Separation Update ────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !m.isStyleLoaded() || !m.getLayer("cadastral-units-3d")) return;

    const gap = explosionGap;
    const baseExpr: maplibregl.ExpressionSpecification = [
      "+",
      ["coalesce", ["get", "z_min"], 0],
      [
        "*",
        [
          "case",
          ["==", ["get", "floor_number"], -1], -1,
          [">", ["get", "floor_number"], 0], ["-", ["get", "floor_number"], 1],
          0,
        ],
        gap,
      ],
    ];

    const heightExpr: maplibregl.ExpressionSpecification = [
      "+",
      ["coalesce", ["get", "z_max"], 3],
      [
        "*",
        [
          "case",
          ["==", ["get", "floor_number"], -1], -1,
          [">", ["get", "floor_number"], 0], ["-", ["get", "floor_number"], 1],
          0,
        ],
        gap,
      ],
    ];

    try {
      m.setPaintProperty("cadastral-units-3d", "fill-extrusion-base", baseExpr);
      m.setPaintProperty("cadastral-units-3d", "fill-extrusion-height", heightExpr);
    } catch (e) {
      console.warn("Failed to update explosion paint:", e);
    }
  }, [explosionGap]);

  // ── 4. Dynamic Floor Level Filter Update ──────────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !m.isStyleLoaded() || !m.getLayer("cadastral-units-3d")) return;

    try {
      if (selectedFloor === "ALL") {
        m.setFilter("cadastral-units-3d", null);
      } else if (selectedFloor === "4+") {
        m.setFilter("cadastral-units-3d", [">=", ["get", "floor_number"], 4]);
      } else {
        const flNum = parseInt(selectedFloor, 10);
        m.setFilter("cadastral-units-3d", ["==", ["get", "floor_number"], flNum]);
      }
    } catch (e) {
      console.warn("Failed to filter floor:", e);
    }
  }, [selectedFloor]);

  // ── 4b. Subterranean Infrastructure Layer Toggle Sync ─────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !m.isStyleLoaded()) return;
    ["underground-infrastructure-3d", "underground-infrastructure-outline"].forEach((id) => {
      try {
        if (m.getLayer(id)) {
          m.setLayoutProperty(id, "visibility", layerUnderground ? "visible" : "none");
        }
      } catch (_) {}
    });
  }, [layerUnderground]);

  // ── 4c. Stratum Classification Filter (SURFACE, ABOVE_GROUND, SUBTERRANEAN) ──
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !m.isStyleLoaded()) return;

    try {
      const showExtrudedBuildings =
        (viewMode === "3d_extruded" ||
          (viewMode === "3d_units" && (!unitsData || !unitsData.features || unitsData.features.length === 0))) &&
        layerBuildings;

      if (stratumFilter === "ALL") {
        if (m.getLayer("cadastral-units-3d")) m.setLayoutProperty("cadastral-units-3d", "visibility", (viewMode === "3d_units" && layerBuildings) ? "visible" : "none");
        if (m.getLayer("cadastral-units-outline")) m.setLayoutProperty("cadastral-units-outline", "visibility", (viewMode === "3d_units" && layerBuildings) ? "visible" : "none");
        if (m.getLayer("cadastral-building-envelope-glass")) m.setLayoutProperty("cadastral-building-envelope-glass", "visibility", (viewMode === "3d_units" && layerBuildings) ? "visible" : "none");
        if (m.getLayer("cadastral-buildings-3d")) m.setLayoutProperty("cadastral-buildings-3d", "visibility", showExtrudedBuildings ? "visible" : "none");
        if (m.getLayer("underground-infrastructure-3d")) m.setLayoutProperty("underground-infrastructure-3d", "visibility", layerUnderground ? "visible" : "none");
      } else if (stratumFilter === "SUBTERRANEAN") {
        if (m.getLayer("cadastral-units-3d")) m.setLayoutProperty("cadastral-units-3d", "visibility", "none");
        if (m.getLayer("cadastral-units-outline")) m.setLayoutProperty("cadastral-units-outline", "visibility", "none");
        if (m.getLayer("cadastral-building-envelope-glass")) m.setLayoutProperty("cadastral-building-envelope-glass", "visibility", "none");
        if (m.getLayer("cadastral-buildings-3d")) m.setLayoutProperty("cadastral-buildings-3d", "visibility", "none");
        if (m.getLayer("underground-infrastructure-3d")) m.setLayoutProperty("underground-infrastructure-3d", "visibility", "visible");
        m.easeTo({ pitch: 65, duration: 600 });
      } else if (stratumFilter === "SURFACE") {
        if (m.getLayer("cadastral-units-3d")) m.setLayoutProperty("cadastral-units-3d", "visibility", "none");
        if (m.getLayer("cadastral-units-outline")) m.setLayoutProperty("cadastral-units-outline", "visibility", "none");
        if (m.getLayer("cadastral-building-envelope-glass")) m.setLayoutProperty("cadastral-building-envelope-glass", "visibility", "none");
        if (m.getLayer("underground-infrastructure-3d")) m.setLayoutProperty("underground-infrastructure-3d", "visibility", "none");
        if (m.getLayer("cadastral-buildings-flat")) m.setLayoutProperty("cadastral-buildings-flat", "visibility", "visible");
        m.easeTo({ pitch: 0, duration: 600 });
      } else if (stratumFilter === "ABOVE_GROUND") {
        if (m.getLayer("cadastral-units-3d")) m.setLayoutProperty("cadastral-units-3d", "visibility", (viewMode === "3d_units" && layerBuildings) ? "visible" : "none");
        if (m.getLayer("cadastral-units-outline")) m.setLayoutProperty("cadastral-units-outline", "visibility", (viewMode === "3d_units" && layerBuildings) ? "visible" : "none");
        if (m.getLayer("cadastral-building-envelope-glass")) m.setLayoutProperty("cadastral-building-envelope-glass", "visibility", (viewMode === "3d_units" && layerBuildings) ? "visible" : "none");
        if (m.getLayer("cadastral-buildings-3d")) m.setLayoutProperty("cadastral-buildings-3d", "visibility", showExtrudedBuildings ? "visible" : "none");
        if (m.getLayer("underground-infrastructure-3d")) m.setLayoutProperty("underground-infrastructure-3d", "visibility", "none");
        m.easeTo({ pitch: 60, duration: 600 });
      }
    } catch (e) {
      console.warn("Stratum filter update error:", e);
    }
  }, [stratumFilter, viewMode, layerUnderground, layerBuildings, unitsData, mapLoaded]);

  // ── 5. Selection highlight sync ───────────────────────────────────────────
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !m.isStyleLoaded()) return;

    const id = selectedFeature?.properties?.three_d_property_id ?? "";
    if (m.getLayer("cadastral-buildings-selected")) {
      m.setFilter("cadastral-buildings-selected", ["==", "three_d_property_id", id]);
    }
    if (m.getLayer("cadastral-unit-selected")) {
      m.setFilter("cadastral-unit-selected", ["==", "three_d_property_id", id]);
    }
  }, [selectedFeature]);

  // ── 6. Mode Change ────────────────────────────────────────────────────────
  const handleModeChange = (mode: MapViewMode) => {
    setViewMode(mode);
    const m = mapRef.current;
    if (!m || mode === "cesium") return;

    const setLayerVis = (id: string, vis: boolean) => {
      try {
        if (m.getLayer(id)) {
          m.setLayoutProperty(id, "visibility", vis ? "visible" : "none");
        }
      } catch (_) {}
    };

    if (mode === "2d") {
      m.easeTo({ pitch: 0, bearing: 0, duration: 700 });
      setLayerVis("cadastral-buildings-3d", false);
      setLayerVis("cadastral-buildings-dashed-outline", true);
      setLayerVis("cadastral-buildings-flat", true);
      setLayerVis("cadastral-units-3d", false);
      setLayerVis("cadastral-units-outline", false);
      setLayerVis("cadastral-building-envelope-glass", false);
    } else if (mode === "3d_extruded") {
      m.easeTo({ pitch: 55, bearing: -20, duration: 700 });
      setLayerVis("cadastral-buildings-3d", true);
      setLayerVis("cadastral-buildings-dashed-outline", false);
      setLayerVis("cadastral-buildings-flat", false);
      setLayerVis("cadastral-units-3d", false);
      setLayerVis("cadastral-units-outline", false);
      setLayerVis("cadastral-building-envelope-glass", false);
    } else if (mode === "3d_units") {
      m.easeTo({
        center: PUNE_PILOT_CENTER,
        zoom: PUNE_PILOT_ZOOM,
        pitch: PUNE_PILOT_PITCH,
        bearing: PUNE_PILOT_BEARING,
        duration: 700,
      });
      const showBuildingFallback = !unitsData || !unitsData.features || unitsData.features.length === 0;
      setLayerVis("cadastral-buildings-3d", showBuildingFallback && layerBuildings);
      setLayerVis("cadastral-buildings-dashed-outline", false);
      setLayerVis("cadastral-buildings-flat", false);
      setLayerVis("cadastral-units-3d", true);
      setLayerVis("cadastral-units-outline", true);
      setLayerVis("cadastral-building-envelope-glass", true);
    }
  };

  // ── 7. Layer toggle ───────────────────────────────────────────────────────
  const toggleBuildingLayer = (visible: boolean) => {
    setLayerBuildings(visible);
    const m = mapRef.current;
    if (!m) return;
    const targetLayers =
      viewMode === "3d_units"
        ? ["cadastral-units-3d", "cadastral-units-outline", "cadastral-building-envelope-glass", "cadastral-buildings-3d"]
        : ["cadastral-buildings-3d", "cadastral-buildings-flat"];
    targetLayers.forEach((id) => {
      try {
        if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      } catch (_) {}
    });
  };

  // ── 5. Quick search (filter by name / ULPIN / 3D ID) ─────────────────────
  const handleSearch = () => {
    if (!searchQuery.trim() || !geoData) return;
    const q = searchQuery.toLowerCase();
    const hit = geoData.features?.find((f: any) => {
      const p = f.properties;
      return (
        p.name?.toLowerCase().includes(q) ||
        p.ULPIN?.toLowerCase().includes(q) ||
        p.three_d_property_id?.toLowerCase().includes(q) ||
        p["addr:street"]?.toLowerCase().includes(q)
      );
    });
    if (hit) {
      setSelectedFeature(hit as BuildingFeature);
      const coords = hit.geometry?.coordinates?.[0];
      if (coords && mapRef.current) {
        const lngs = coords.map((c: [number, number]) => c[0]);
        const lats = coords.map((c: [number, number]) => c[1]);
        const cx = (Math.min(...lngs) + Math.max(...lngs)) / 2;
        const cy = (Math.min(...lats) + Math.max(...lats)) / 2;
        mapRef.current.flyTo({ center: [cx, cy], zoom: 18, duration: 900 });
      }
    }
  };

  const featureCount = geoData?.features?.length ?? 0;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="page-container">

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="header-actions">
        <div>
          <h2>3D Cadastral Portal: Visualize · Search · Inspect · Download</h2>
          <p className="subtitle">
            MapLibre GL 2D/3D extruded layers • Pune Pilot Ward •{" "}
            {featureCount.toLocaleString()} buildings loaded • PRD §5.10
          </p>
        </div>

        {/* View mode toggle */}
        <div className="tab-group-sm">
          <button
            className={`btn-filter ${viewMode === "2d" ? "active" : ""}`}
            onClick={() => handleModeChange("2d")}
          >
            🗺️ 2D Flat
          </button>
          <button
            className={`btn-filter ${viewMode === "3d_extruded" ? "active" : ""}`}
            onClick={() => handleModeChange("3d_extruded")}
          >
            🏢 3D Building Envelopes
          </button>
          <button
            className={`btn-filter ${viewMode === "3d_units" ? "active" : ""}`}
            onClick={() => handleModeChange("3d_units")}
          >
            🪜 3D Floor & Unit Explorer (Exploded View)
          </button>
          <button
            className={`btn-filter ${viewMode === "cesium" ? "active" : ""}`}
            onClick={() => handleModeChange("cesium")}
          >
            🌐 3D Globe (CesiumJS)
          </button>
        </div>
      </div>

      {/* ── Exploded View Secondary Toolbar (when in 3D Floor & Unit Explorer mode) ── */}
      {viewMode === "3d_units" && (
        <div className="exploded-controls-toolbar">
          <div className="exploded-controls-left">
            <span className="exploded-label">💥 Explode 3D Floors:</span>
            <input
              type="range"
              min="0"
              max="10"
              step="0.5"
              value={explosionGap}
              onChange={(e) => setExplosionGap(parseFloat(e.target.value))}
              className="slider-range"
            />
            <span className="badge-explosion-gap">
              {explosionGap === 0 ? "Stacked (0m)" : `+${explosionGap}m Vertical Lift`}
            </span>
            <div className="preset-buttons">
              <button
                className={`btn-preset ${explosionGap === 0 ? "active" : ""}`}
                onClick={() => setExplosionGap(0)}
              >
                Stacked (0m)
              </button>
              <button
                className={`btn-preset ${explosionGap === 3 ? "active" : ""}`}
                onClick={() => setExplosionGap(3)}
              >
                Subtle (3m)
              </button>
              <button
                className={`btn-preset ${explosionGap === 6 ? "active" : ""}`}
                onClick={() => setExplosionGap(6)}
              >
                Exploded (6m)
              </button>
              <button
                className={`btn-preset ${explosionGap === 10 ? "active" : ""}`}
                onClick={() => setExplosionGap(10)}
              >
                Maximum (10m)
              </button>
            </div>
          </div>

          <div className="exploded-controls-right">
            <span className="floor-filter-label">Filter Floor:</span>
            <select
              className="select-field"
              value={selectedFloor}
              onChange={(e) => setSelectedFloor(e.target.value)}
            >
              <option value="ALL">All Floors (Stacked/Exploded)</option>
              <option value="-1">Basement / Parking (-3m)</option>
              <option value="1">Floor 1 (Amber)</option>
              <option value="2">Floor 2 (Green)</option>
              <option value="3">Floor 3 (Cyan)</option>
              <option value="4+">Upper Floors (4+)</option>
            </select>
          </div>
        </div>
      )}

      {/* ── Stratum Filter Bar (Volumetric, Subterranean, Surface, Above-Ground) ── */}
      <div
        className="stratum-filter-bar"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 16px",
          background: "rgba(15, 23, 42, 0.85)",
          borderBottom: "1px solid var(--border)",
          fontSize: "12px",
          backdropFilter: "blur(8px)",
        }}
      >
        <span style={{ fontWeight: 600, color: "var(--text-subtle)", display: "flex", alignItems: "center", gap: "4px" }}>
          🌐 3D Cadastre Stratum:
        </span>
        <button
          type="button"
          className={`btn-filter ${stratumFilter === "ALL" ? "active" : ""}`}
          onClick={() => setStratumFilter("ALL")}
          style={{ padding: "4px 10px", fontSize: "11px" }}
        >
          All Strata (Volumetric)
        </button>
        <button
          type="button"
          className={`btn-filter ${stratumFilter === "SUBTERRANEAN" ? "active" : ""}`}
          onClick={() => setStratumFilter("SUBTERRANEAN")}
          style={{
            padding: "4px 10px",
            fontSize: "11px",
            borderColor: stratumFilter === "SUBTERRANEAN" ? "#ef4444" : undefined,
            color: stratumFilter === "SUBTERRANEAN" ? "#f87171" : undefined,
          }}
        >
          🚇 Subterranean ({undergroundData?.features?.length ?? 7} Assets)
        </button>
        <button
          type="button"
          className={`btn-filter ${stratumFilter === "SURFACE" ? "active" : ""}`}
          onClick={() => setStratumFilter("SURFACE")}
          style={{ padding: "4px 10px", fontSize: "11px" }}
        >
          🗺️ Surface Land Parcels
        </button>
        <button
          type="button"
          className={`btn-filter ${stratumFilter === "ABOVE_GROUND" ? "active" : ""}`}
          onClick={() => setStratumFilter("ABOVE_GROUND")}
          style={{ padding: "4px 10px", fontSize: "11px" }}
        >
          🏢 Above-Ground Strata Units
        </button>
      </div>

      {/* ── Map Toolbar ──────────────────────────────────────────────────── */}
      <div className="map-controls-toolbar">
        <div className="controls-left">
          <span className="badge-rule-pill">
            📍 Pune Ward Pilot • {featureCount.toLocaleString()} Geometries
          </span>

          {/* Database vs Static Data Source Indicator */}
          {dataSource === "api" ? (
            <span
              className="badge-rule-pill"
              style={{
                background: "#059669",
                color: "#ffffff",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
              }}
              title="Connected to live FastAPI backend + SQLite 3D Cadastral database"
            >
              🟢 Live Database API
            </span>
          ) : (
            <span
              className="badge-rule-pill"
              style={{
                background: "#d97706",
                color: "#ffffff",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
              }}
              title="Falling back to static GeoJSON storage"
            >
              🟠 Static Fallback Mode
            </span>
          )}

          <button
            className="btn btn-secondary btn-sm"
            onClick={refreshFromDb}
            disabled={isRefreshing}
            title="Reload latest 3D unit records from database"
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            {isRefreshing ? "⏳ Syncing..." : "🔄 Refresh DB"}
          </button>

          <label
            className="btn btn-primary btn-sm"
            style={{
              cursor: uploading ? "not-allowed" : "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              opacity: uploading ? 0.7 : 1,
            }}
            title="Ingest raw GeoJSON or CSV survey data directly into backend database pipeline"
          >
            {uploading ? "⏳ Ingesting..." : "📥 Quick Ingest"}
            <input
              type="file"
              accept=".geojson,.json,.csv"
              onChange={handleQuickIngest}
              disabled={uploading}
              style={{ display: "none" }}
            />
          </label>

          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowMultiSensorModal(true)}
            title="Open Multi-Sensor Data Ingestion Center (6 Modalities: Drone, LiDAR, GIS, CAD, GNSS/CORS, DEM/DSM)"
            style={{
              background: "linear-gradient(135deg, #0284c7, #0369a1)",
              border: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontWeight: 600,
            }}
          >
            📡 Multi-Sensor Ingest
          </button>

          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowAiStudioModal(true)}
            title="Launch AI Cadastral Studio (Building Extraction, Floor Segmentation, Vertical Delineation, 3D Topology)"
            style={{
              background: "linear-gradient(135deg, #7c3aed, #6d28d9)",
              border: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontWeight: 600,
            }}
          >
            🧠 AI Cadastral Studio
          </button>

          <label className="checkbox-label" style={{ marginLeft: 6 }}>
            <input
              type="checkbox"
              checked={layerBuildings}
              onChange={(e) => toggleBuildingLayer(e.target.checked)}
            />
            {viewMode === "3d_units" ? "3D Units & Envelopes" : "Buildings"}
          </label>

          <label className="checkbox-label" style={{ marginLeft: 6 }}>
            <input
              type="checkbox"
              checked={layerUnderground}
              onChange={(e) => setLayerUnderground(e.target.checked)}
            />
            <span style={{ color: "#f87171", fontWeight: 600 }}>🚇 Subterranean Assets</span>
          </label>
        </div>

        {/* Quick search bar */}
        <div className="map-search-row">
          <input
            className="input-field"
            style={{ width: 220 }}
            placeholder="Search by name, ULPIN or 3D ID…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button className="btn btn-primary btn-sm" onClick={handleSearch}>
            🔍 Search
          </button>
        </div>

        <div className="controls-right">
          {/* Legend */}
          {viewMode === "3d_units" ? (
            <div className="map-legend">
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "#f59e0b" }} />
                <span>Floor 1</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "#10b981" }} />
                <span>Floor 2</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "#0ea5e9" }} />
                <span>Floor 3</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "rgba(56, 189, 248, 0.4)", border: "1px solid #38bdf8" }} />
                <span>Glass Envelope</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "#ef4444" }} />
                <span>Selected Unit</span>
              </div>
            </div>
          ) : (
            <div className="map-legend">
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "#94a3b8", border: "1px solid #64748b" }} />
                <span>3D Building</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ background: "#b91c1c" }} />
                <span>Selected</span>
              </div>
            </div>
          )}
          {viewMode !== "cesium" && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={() =>
                mapRef.current?.flyTo({
                  center: PUNE_PILOT_CENTER,
                  zoom: PUNE_PILOT_ZOOM,
                  pitch: viewMode === "2d" ? 0 : PUNE_PILOT_PITCH,
                  bearing: viewMode === "2d" ? 0 : PUNE_PILOT_BEARING,
                })
              }
            >
              🎯 Reset View
            </button>
          )}
        </div>
      </div>

      {/* ── Error banner ─────────────────────────────────────────────────── */}
      {error && (
        <div className="alert-banner error">{error}</div>
      )}

      {/* ── Ingestion status notification banner ───────────────────────────── */}
      {uploadStatus && (
        <div
          style={{
            padding: "8px 16px",
            background: uploadStatus.startsWith("❌")
              ? "#fee2e2"
              : uploadStatus.startsWith("✅")
              ? "#dcfce7"
              : "#e0f2fe",
            color: uploadStatus.startsWith("❌")
              ? "#991b1b"
              : uploadStatus.startsWith("✅")
              ? "#166534"
              : "#075985",
            borderBottom: "1px solid rgba(0,0,0,0.1)",
            fontSize: "13px",
            fontWeight: 500,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>{uploadStatus}</span>
          <button
            onClick={() => setUploadStatus(null)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "14px",
              color: "inherit",
              marginLeft: "12px",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Main split layout ─────────────────────────────────────────────── */}
      <div className="layout-split">

        {/* ── Map container ──────────────────────────────────────────────── */}
        <div
          className="map-viewport-card"
          style={{ padding: 0, overflow: "hidden", minHeight: "600px", position: "relative" }}
        >
          {loading ? (
            <div className="loader" style={{ padding: "100px" }}>
              Loading 3D cadastral features…
            </div>
          ) : viewMode === "cesium" ? (
            <CesiumPlaceholder onBack={() => handleModeChange("3d_extruded")} />
          ) : webglSupported ? (
            <div ref={mapContainerRef} style={{ width: "100%", height: "600px" }} />
          ) : (
            <SvgFallback features={geoData?.features ?? []} selected={selectedFeature} onSelect={setSelectedFeature} />
          )}

          {/* Floating selection badge on map */}
          {selectedFeature && (
            <div className="map-selection-badge">
              📌 {selectedFeature.properties?.name ?? selectedFeature.properties?.three_d_property_id?.slice(0, 10)}
            </div>
          )}
        </div>

        {/* ── Object Detail Drawer ──────────────────────────────────────── */}
        <ObjectDetailDrawer
          feature={selectedFeature}
          onClose={() => setSelectedFeature(null)}
          currentRole={currentRole}
        />
      </div>

      {/* ── Multi-Sensor Ingest Modal ── */}
      <MultiSensorIngestModal
        isOpen={showMultiSensorModal}
        onClose={() => setShowMultiSensorModal(false)}
        onSuccess={(msg) => {
          setUploadStatus(msg);
          refreshFromDb();
        }}
      />

      {/* ── AI Cadastral Intelligence Studio Modal ── */}
      <AiCadastralStudioModal
        isOpen={showAiStudioModal}
        onClose={() => setShowAiStudioModal(false)}
        onApplyResults={() => refreshFromDb()}
      />
    </div>
  );
};

// ── CesiumJS placeholder ───────────────────────────────────────────────────────
function CesiumPlaceholder({ onBack }: { onBack: () => void }) {
  return (
    <div className="cesium-viewer-container">
      <div className="cesium-overlay-header">
        <div className="cesium-badge">
          <span className="health-dot online" />
          <strong>CesiumJS 3D Globe Mode</strong>
        </div>
        <div style={{ color: "#e2e8f0", fontSize: "12px" }}>
          3D Tiles · Terrain Engine · Elevation Extents
        </div>
      </div>
      <div className="cesium-globe-viewport">
        <div className="cesium-starfield">
          <div className="cesium-horizon-glow" />
          <div className="cesium-globe-mesh">
            <div className="cesium-pin jaipur-pin">
              <div className="pin-pulse" />
              <div className="pin-label">📍 Pune Pilot Ward (EPSG:4326)</div>
            </div>
          </div>
        </div>
        <div className="cesium-telemetry-panel">
          {[
            ["Target Area", "Pune, Maharashtra"],
            ["Camera Alt", "450 m AMSL"],
            ["Terrain", "WGS84 / GeoTIFF DEM"],
            ["3D Tile LOD", "LOD-2 Building Envelopes"],
          ].map(([k, v]) => (
            <div key={k} className="telemetry-item">
              <span>{k}:</span>
              <strong>{v}</strong>
            </div>
          ))}
        </div>
        <div className="cesium-actions">
          <p style={{ color: "#94a3b8", marginBottom: "8px", fontSize: "12px" }}>
            CesiumJS 3D viewer primed. Switch to 3D Extrusions for interactive inspection.
          </p>
          <button className="btn btn-primary" onClick={onBack}>
            View Interactive 3D Extrusions
          </button>
        </div>
      </div>
    </div>
  );
}

// ── SVG isometric fallback (no WebGL) ─────────────────────────────────────────
function SvgFallback({
  features,
  selected,
  onSelect,
}: {
  features: any[];
  selected: BuildingFeature | null;
  onSelect: (f: BuildingFeature) => void;
}) {
  return (
    <div className="spatial-canvas-container">
      <div className="map-stats-badge">{features.length} Objects (2.5D Fallback)</div>
      <svg className="spatial-svg" viewBox="0 0 800 500">
        <rect width="800" height="500" fill="#f8fafc" />
        {features.slice(0, 24).map((feat: any, idx: number) => {
          const x = 60 + ((idx * 140) % 680);
          const y = 120 + Math.floor((idx * 140) / 680) * 150;
          const h = Math.min((feat.properties.height ?? 9) / 3, 40);
          const isSel = selected?.properties?.three_d_property_id === feat.properties.three_d_property_id;
          return (
            <g key={idx} className="map-object-group" onClick={() => onSelect(feat as BuildingFeature)}>
              <polygon
                points={`${x},${y} ${x + 90},${y} ${x + 110},${y - h} ${x + 20},${y - h}`}
                fill="#fca5a5" fillOpacity={0.7}
                stroke={isSel ? "#b91c1c" : "#111827"} strokeWidth={isSel ? 2.5 : 1}
                strokeDasharray={isSel ? "none" : "3,2"}
              />
              <rect x={x} y={y} width="90" height="70"
                fill="#fca5a5" fillOpacity={0.5}
                stroke={isSel ? "#b91c1c" : "#111827"} strokeWidth={isSel ? 2 : 1}
                strokeDasharray={isSel ? "none" : "3,2"} rx={3} />
              <text x={x + 6} y={y + 30} className="map-label" fontSize="9">
                {feat.properties.three_d_property_id?.slice(-10)}
              </text>
              <text x={x + 6} y={y + 45} className="map-sublabel">
                h:{feat.properties.height ?? 9}m
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
