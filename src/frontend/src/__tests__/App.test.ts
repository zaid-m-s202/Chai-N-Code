import React from "react";
import App from "../App";
import { PropertiesPage } from "../pages/PropertiesPage";
import { VerificationQueuePage } from "../pages/VerificationQueuePage";
import { MapPage } from "../pages/MapPage";
import { IngestionPage } from "../pages/IngestionPage";
import { ConflictsPage } from "../pages/ConflictsPage";
import { api } from "../api/client";

export function testComponentExports() {
  if (typeof App !== "function") throw new Error("App must be a component");
  if (typeof PropertiesPage !== "function") throw new Error("PropertiesPage must be a component");
  if (typeof VerificationQueuePage !== "function") throw new Error("VerificationQueuePage must be a component");
  if (typeof MapPage !== "function") throw new Error("MapPage must be a component");
  if (typeof IngestionPage !== "function") throw new Error("IngestionPage must be a component");
  if (typeof ConflictsPage !== "function") throw new Error("ConflictsPage must be a component");
}

export function testApiClientEndpoints() {
  const requiredMethods = [
    "listProperties",
    "getProperty",
    "getHistory",
    "getEvidence",
    "getObservations",
    "refuseProperty",
    "verifyProperty",
    "rejectProperty",
    "getVerificationQueue",
    "search",
    "listConflicts",
    "runTopologyValidation",
    "resolveConflict",
    "waiveConflict",
    "getQuickToken",
    "listJobs",
    "uploadFile",
    "getMapObjects",
    "getHierarchy",
    "splitUnit",
    "mergeUnits",
    "getAnalysisAdapters",
    "runDsmDemHeight",
    "runFloorEstimator",
    "runFootprintExtractor",
    "analyzeProperty",
  ];

  for (const m of requiredMethods) {
    if (typeof (api as any)[m] !== "function") {
      throw new Error(`api.${m} is missing from client`);
    }
  }
}
