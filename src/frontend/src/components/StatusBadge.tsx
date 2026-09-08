import React from "react";
import { PropertyStatus } from "../api/client";

interface StatusBadgeProps {
  status: PropertyStatus | string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getBadgeClass = (s: string) => {
    switch (s.toUpperCase()) {
      case "VERIFIED":
        return "badge-verified";
      case "PROVISIONAL":
        return "badge-provisional";
      case "DERIVED":
        return "badge-derived";
      case "INFERRED":
        return "badge-inferred";
      case "SYNTHETIC":
      default:
        return "badge-synthetic";
    }
  };

  return <span className={`status-badge ${getBadgeClass(status)}`}>{status}</span>;
};
