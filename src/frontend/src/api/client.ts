export type PropertyType = "parcel" | "building" | "floor" | "unit";
export type PropertyStatus = "SYNTHETIC" | "INFERRED" | "DERIVED" | "PROVISIONAL" | "VERIFIED";

export interface PropertySummary {
  three_d_property_id: string;
  type: PropertyType;
  status: PropertyStatus;
  confidence: number;
}

export interface PropertyDetail {
  id: string;
  three_d_property_id: string;
  type: PropertyType;
  parent_id?: string | null;
  geometry?: any;
  z_min?: number | null;
  z_max?: number | null;
  attributes?: Record<string, any> | null;
  confidence: number;
  status: PropertyStatus;
  source_list?: string[] | null;
  created_at: string;
}

export interface ChangeEvent {
  id: string;
  event_type: string;
  old_state?: any;
  new_state?: any;
  actor_id?: string | null;
  evidence_id?: string | null;
  created_at: string;
}

export interface PropertyHistory {
  three_d_property_id: string;
  events: ChangeEvent[];
}

export interface EncumbranceItem {
  type: string;
  description: string;
  recorded_date?: string | null;
  amount?: number | null;
  beneficiary?: string | null;
  status: string;
}

export interface PropertyRecord {
  id: string;
  property_object_id: string;
  three_d_property_id: string;
  ulpin: string;
  owner_party_id?: string | null;
  registration_number?: string | null;
  registration_date?: string | null;
  rights_type: string;
  encumbrances: EncumbranceItem[];
  linkage_status: "LINKED" | "PENDING" | "DISPUTED" | "UNLINKED";
  source_system: string;
  sync_time: string;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  is_redacted?: boolean;
}

export interface PropertyRecordCreate {
  property_object_id: string;
  ulpin: string;
  owner_party_id: string;
  registration_number?: string;
  registration_date?: string;
  rights_type?: string;
  encumbrances?: EncumbranceItem[];
  linkage_status?: string;
  source_system?: string;
}

export interface PropertyRecordUpdate {
  ulpin?: string;
  owner_party_id?: string;
  registration_number?: string;
  registration_date?: string;
  rights_type?: string;
  encumbrances?: EncumbranceItem[];
  linkage_status?: string;
  source_system?: string;
}

export interface ConflictRecord {
  id: string;
  property_object_id: string;
  rule_code: string;
  description?: string | null;
  severity: string;
  status: string;
  created_at: string;
  resolved_at?: string | null;
}

export interface IngestionJob {
  id: string;
  filename: string;
  format: string;
  status: string;
  record_count?: number | null;
  error_detail?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface SourceObservation {
  id: string;
  property_object_id: string;
  attribute_name: string;
  observed_value: any;
  source_confidence: number;
  observed_at: string;
  source_id?: string | null;
}

export interface RefuseResult {
  three_d_property_id: string;
  fused_height?: number | null;
  fused_confidence: number;
  has_conflict: boolean;
  conflict_reason?: string | null;
  observations_count: number;
}

export interface HierarchyNode {
  id: string;
  three_d_property_id: string;
  type: string;
  status: string;
  confidence: number;
  z_min?: number | null;
  z_max?: number | null;
  attributes?: Record<string, any> | null;
  children: HierarchyNode[];
}

export interface PropertyHierarchyResponse {
  root: HierarchyNode;
}

export interface AdapterInfo {
  name: string;
  version: string;
  description: string;
  supported_input_types: string[];
}

export interface AnalysisResultResponse {
  adapter_name: string;
  adapter_version: string;
  status: string;
  confidence: number;
  data: any;
  evidence: any;
  warnings: string[];
  executed_at: string;
}

export interface PropertyAnalysisResponse {
  property_id: string;
  three_d_property_id: string;
  status: string;
  confidence: number;
  z_min?: number | null;
  z_max?: number | null;
  evidence_id: string;
  adapters_executed: {
    adapter: string;
    status: string;
    confidence: number;
    warnings: string[];
    data: any;
  }[];
}

const rawBackendUrl = (import.meta.env?.VITE_API_URL || "http://localhost:8000").trim().replace(/\/+$/, "");
export const BACKEND_ROOT = rawBackendUrl.endsWith("/api/v1")
  ? rawBackendUrl.slice(0, -"/api/v1".length)
  : rawBackendUrl;
export const API_BASE = `${BACKEND_ROOT}/api/v1`;

export const api = {
  async checkHealth(): Promise<{ status: string }> {
    const res = await fetch(`${BACKEND_ROOT}/health`);
    if (!res.ok) throw new Error(`Health check returned HTTP ${res.status}`);
    return res.json();
  },

  async getMapUnits(limit: number = 50000): Promise<any> {
    const res = await fetch(`${API_BASE}/map/units?limit=${limit}`);
    if (!res.ok) throw new Error(`Failed to fetch 3D units: HTTP ${res.status}`);
    return res.json();
  },

  async getMapUnderground(limit: number = 5000): Promise<any> {
    const res = await fetch(`${API_BASE}/map/underground?limit=${limit}`);
    if (!res.ok) throw new Error(`Failed to fetch underground infrastructure: HTTP ${res.status}`);
    return res.json();
  },
  async listProperties(status?: string, type?: string): Promise<PropertySummary[]> {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (type) params.append("type", type);
    const res = await fetch(`${API_BASE}/properties?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch properties");
    return res.json();
  },

  async getProperty(id: string): Promise<PropertyDetail> {
    const res = await fetch(`${API_BASE}/properties/${id}`);
    if (!res.ok) throw new Error("Failed to fetch property details");
    return res.json();
  },

  async getHistory(id: string): Promise<PropertyHistory> {
    const res = await fetch(`${API_BASE}/properties/${id}/history`);
    if (!res.ok) throw new Error("Failed to fetch property history");
    return res.json();
  },

  async getEvidence(id: string): Promise<any[]> {
    const res = await fetch(`${API_BASE}/properties/${id}/evidence`);
    if (!res.ok) return [];
    return res.json();
  },

  async getObservations(id: string): Promise<SourceObservation[]> {
    const res = await fetch(`${API_BASE}/properties/${id}/observations`);
    if (!res.ok) return [];
    return res.json();
  },

  async refuseProperty(id: string): Promise<RefuseResult> {
    const res = await fetch(`${API_BASE}/properties/${id}/refuse`, { method: "POST" });
    if (!res.ok) throw new Error("Re-fusion failed");
    return res.json();
  },

  async verifyProperty(id: string, token?: string, notes?: string): Promise<PropertyDetail> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/properties/${id}/verify`, {
      method: "POST",
      headers,
      body: JSON.stringify({ notes }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Verification failed" }));
      throw new Error(err.detail || "Verification failed");
    }
    return res.json();
  },

  async rejectProperty(id: string, token?: string, notes?: string): Promise<PropertyDetail> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/properties/${id}/reject`, {
      method: "POST",
      headers,
      body: JSON.stringify({ notes }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Rejection failed" }));
      throw new Error(err.detail || "Rejection failed");
    }
    return res.json();
  },

  async getVerificationQueue(hasConflicts?: boolean): Promise<PropertySummary[]> {
    const params = new URLSearchParams();
    if (hasConflicts !== undefined) params.append("has_conflicts", String(hasConflicts));
    const res = await fetch(`${API_BASE}/verification-queue?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch verification queue");
    return res.json();
  },

  async search(query: string): Promise<PropertySummary[]> {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error("Search failed");
    return res.json();
  },

  async listConflicts(status?: string, ruleCode?: string): Promise<ConflictRecord[]> {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (ruleCode) params.append("rule_code", ruleCode);
    const res = await fetch(`${API_BASE}/conflicts?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to fetch conflicts");
    return res.json();
  },

  async runTopologyValidation(token?: string): Promise<any> {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/conflicts/run-topology`, {
      method: "POST",
      headers,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Topology run failed" }));
      throw new Error(err.detail || "Topology run failed");
    }
    return res.json();
  },

  async resolveConflict(conflictId: string, token?: string): Promise<ConflictRecord> {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/conflicts/${conflictId}/resolve`, {
      method: "POST",
      headers,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to resolve conflict" }));
      throw new Error(err.detail || "Failed to resolve conflict");
    }
    return res.json();
  },

  async waiveConflict(conflictId: string, token?: string): Promise<ConflictRecord> {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/conflicts/${conflictId}/waive`, {
      method: "POST",
      headers,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to waive conflict" }));
      throw new Error(err.detail || "Failed to waive conflict");
    }
    return res.json();
  },

  async getQuickToken(role: string = "VERIFYING_OFFICER"): Promise<string> {
    const res = await fetch(`${API_BASE}/auth/quick-token?role=${encodeURIComponent(role)}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to get auth token for role");
    const data = await res.json();
    return data.access_token;
  },

  async listJobs(): Promise<IngestionJob[]> {
    const res = await fetch(`${API_BASE}/ingestion/jobs`);
    if (!res.ok) throw new Error("Failed to fetch ingestion jobs");
    return res.json();
  },

  async uploadFile(file: File, sourceSystem?: string): Promise<IngestionJob> {
    const formData = new FormData();
    formData.append("file", file);
    if (sourceSystem) formData.append("source_system", sourceSystem);
    const res = await fetch(`${API_BASE}/ingestion/jobs`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail || "Upload failed");
    }
    return res.json();
  },

  async getMapObjects(): Promise<any> {
    const res = await fetch(`${API_BASE}/map/objects`);
    if (!res.ok) throw new Error("Failed to fetch map objects");
    return res.json();
  },

  async getHierarchy(id: string): Promise<PropertyHierarchyResponse> {
    const res = await fetch(`${API_BASE}/properties/${id}/hierarchy`);
    if (!res.ok) throw new Error("Failed to fetch property hierarchy");
    return res.json();
  },

  async splitUnit(id: string, token: string | undefined, payload: any): Promise<any> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/properties/${id}/split`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Split operation failed" }));
      throw new Error(err.detail || "Split operation failed");
    }
    return res.json();
  },

  async mergeUnits(token: string | undefined, payload: any): Promise<any> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/properties/merge`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Merge operation failed" }));
      throw new Error(err.detail || "Merge operation failed");
    }
    return res.json();
  },

  async getAnalysisAdapters(): Promise<AdapterInfo[]> {
    const res = await fetch(`${API_BASE}/analysis/adapters`);
    if (!res.ok) throw new Error("Failed to fetch analysis adapters");
    return res.json();
  },

  async runDsmDemHeight(payload: { dsm?: number; dem?: number; dsm_samples?: number[]; dem_samples?: number[]; sensor_type?: string }): Promise<AnalysisResultResponse> {
    const res = await fetch(`${API_BASE}/analysis/dsm-dem-height`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Height derivation failed" }));
      throw new Error(err.detail || "Height derivation failed");
    }
    return res.json();
  },

  async runFloorEstimator(payload: { height?: number; floor_count?: number; use_type?: string; base_elevation?: number }): Promise<AnalysisResultResponse> {
    const res = await fetch(`${API_BASE}/analysis/estimate-floors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Floor estimation failed" }));
      throw new Error(err.detail || "Floor estimation failed");
    }
    return res.json();
  },

  async runFootprintExtractor(payload: any): Promise<AnalysisResultResponse> {
    const res = await fetch(`${API_BASE}/analysis/extract-footprints`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Footprint extraction failed" }));
      throw new Error(err.detail || "Footprint extraction failed");
    }
    return res.json();
  },

  async analyzeProperty(
    propertyId: string,
    token: string | undefined,
    payload: { elevation_data?: any; use_type?: string }
  ): Promise<PropertyAnalysisResponse> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/properties/${propertyId}/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Property analysis failed" }));
      throw new Error(err.detail || "Property analysis failed");
    }
    return res.json();
  },

  // --- Phase 7 Legal Linkage Endpoints ---
  async getLegalRecordsByProperty(propertyId: string, token?: string): Promise<PropertyRecord[]> {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/legal/by-property/${propertyId}`, { headers });
    if (!res.ok) return [];
    return res.json();
  },

  async createLegalRecord(payload: PropertyRecordCreate, token: string): Promise<PropertyRecord> {
    const res = await fetch(`${API_BASE}/legal/records`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to create legal linkage" }));
      throw new Error(err.detail || "Failed to create legal linkage");
    }
    return res.json();
  },

  async updateLegalRecord(id: string, payload: PropertyRecordUpdate, token: string): Promise<PropertyRecord> {
    const res = await fetch(`${API_BASE}/legal/records/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to update legal record" }));
      throw new Error(err.detail || "Failed to update legal record");
    }
    return res.json();
  },

  async unlinkLegalRecord(id: string, token: string): Promise<any> {
    const res = await fetch(`${API_BASE}/legal/records/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to unlink legal record" }));
      throw new Error(err.detail || "Failed to unlink legal record");
    }
    return res.json();
  },
};
