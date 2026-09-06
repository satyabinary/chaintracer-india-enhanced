import React from "react";
import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";

const ROLE_COLORS = {
  victim: { bg: "#2A3344", border: "#4A5568" },
  source: { bg: "#C98A3E", border: "#E0AE72" },
  intermediate: { bg: "#161D2B", border: "#3A465C" },
  exchange: { bg: "#2FA37D", border: "#4FC79E" },
  mixer: { bg: "#E5484D", border: "#F17A7E" },
  decoy: { bg: "#10151F", border: "#232B3A" },
};

function buildStylesheet() {
  return [
    {
      selector: "node",
      style: {
        "background-color": "#161D2B",
        "border-width": 1.5,
        "border-color": "#3A465C",
        label: "data(label)",
        color: "#E6E9EF",
        "font-family": '"IBM Plex Mono", monospace',
        "font-size": 10,
        "text-valign": "bottom",
        "text-margin-y": 6,
        width: 26,
        height: 26,
      },
    },
    ...Object.entries(ROLE_COLORS).map(([role, c]) => ({
      selector: `node[role = "${role}"]`,
      style: {
        "background-color": c.bg,
        "border-color": c.border,
        width: role === "decoy" ? 16 : role === "source" ? 32 : 26,
        height: role === "decoy" ? 16 : role === "source" ? 32 : 26,
        "border-style": role === "decoy" ? "dashed" : "solid",
      },
    })),
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#3A465C",
        "target-arrow-color": "#3A465C",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(label)",
        "font-family": '"IBM Plex Mono", monospace',
        "font-size": 9,
        color: "#8792A6",
        "text-background-color": "#0D1219",
        "text-background-opacity": 1,
        "text-background-padding": 2,
      },
    },
    {
      selector: 'edge[kind = "main"]',
      style: { "line-color": "#C98A3E", "target-arrow-color": "#C98A3E", width: 3 },
    },
    {
      selector: 'edge[kind = "sweeper"]',
      style: { "line-color": "#2FA37D", "target-arrow-color": "#2FA37D", width: 3 },
    },
    {
      selector: 'edge[kind = "decoy"]',
      style: {
        "line-color": "#232B3A",
        "target-arrow-color": "#232B3A",
        "line-style": "dashed",
        width: 1.5,
        opacity: 0.7,
      },
    },
    {
      selector: "node:selected",
      style: { "border-width": 3, "border-color": "#E6E9EF" },
    },
  ];
}

export default function TraceGraph({ graph, onSelectNode }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return undefined;

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: graph?.nodes || [],
        edges: graph?.edges || [],
      },
      style: buildStylesheet(),
      layout: {
        name: "breadthfirst",
        directed: true,
        spacingFactor: 1.3,
        padding: 30,
      },
      minZoom: 0.4,
      maxZoom: 2.5,
      wheelSensitivity: 0.25,
    });

    cy.on("tap", "node", (evt) => {
      onSelectNode?.(evt.target.data());
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) onSelectNode?.(null);
    });

    cyRef.current = cy;
    setReady(true);

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  const isEmpty = !graph || (graph.nodes || []).length === 0;

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {ready && isEmpty && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-parchment-500">
          No trace data to show yet.
        </div>
      )}
    </div>
  );
}
