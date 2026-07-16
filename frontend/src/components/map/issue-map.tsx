"use client";

import { useEffect, useRef } from "react";
import type { Map as MLMap, MapMouseEvent, StyleSpecification } from "maplibre-gl";
import { DEMO_MUNICIPALITY } from "@/lib/brand";
import { DAMAGE_COLORS, BRAND_HEX } from "@/lib/tokens";
import type { DamageClassCode, District, RoadIssue } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Replaceable map-data layer (MapLibre, no API key required).
 *
 * Two free basemaps ship with the prototype:
 * - "streets": CARTO's OSM-based raster tiles at @2x resolution (crisp on
 *   retina displays, modern muted cartography).
 * - "satellite": Esri World Imagery — real aerial/satellite imagery.
 *
 * Issue data arrives as props and is converted to GeoJSON here — swapping
 * in live vector layers later only touches this file.
 */

export type Basemap = "streets" | "satellite";

function baseStyle(basemap: Basemap): StyleSpecification {
  return {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      streets: {
        type: "raster",
        tiles: ["a", "b", "c", "d"].map(
          (s) =>
            `https://${s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png`,
        ),
        tileSize: 256,
        attribution:
          "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>",
        maxzoom: 20,
      },
      satellite: {
        type: "raster",
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        ],
        tileSize: 256,
        attribution:
          "Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        maxzoom: 19,
      },
    },
    layers: [
      {
        id: "basemap-streets",
        type: "raster",
        source: "streets",
        layout: { visibility: basemap === "streets" ? "visible" : "none" },
      },
      {
        id: "basemap-satellite",
        type: "raster",
        source: "satellite",
        layout: { visibility: basemap === "satellite" ? "visible" : "none" },
      },
    ],
  };
}

export interface IssueMapProps {
  issues: RoadIssue[];
  districts?: District[];
  showDistricts?: boolean;
  showHeatmap?: boolean;
  cluster?: boolean;
  visibleClasses?: DamageClassCode[];
  /** Only show detections captured at or before this epoch ms. */
  maxTimestamp?: number;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  center?: [number, number];
  zoom?: number;
  interactive?: boolean;
  /** "streets" (crisp CARTO/OSM tiles) or "satellite" (Esri World Imagery). */
  basemap?: Basemap;
  className?: string;
}

function toGeoJSON(issues: RoadIssue[]) {
  return {
    type: "FeatureCollection" as const,
    features: issues.map((i) => ({
      type: "Feature" as const,
      properties: {
        id: i.id,
        classCode: i.classCode,
        severity: i.severity,
        priority: i.priorityScore,
        road: i.roadName,
        ts: new Date(i.capturedAt).getTime(),
      },
      geometry: { type: "Point" as const, coordinates: i.coordinates },
    })),
  };
}

function districtsGeoJSON(districts: District[]) {
  return {
    type: "FeatureCollection" as const,
    features: districts.map((d) => ({
      type: "Feature" as const,
      properties: { id: d.id, name: d.name },
      geometry: { type: "Polygon" as const, coordinates: [d.boundary] },
    })),
  };
}

const CLASS_COLOR_EXPR = [
  "match",
  ["get", "classCode"],
  "D00", DAMAGE_COLORS.D00,
  "D10", DAMAGE_COLORS.D10,
  "D20", DAMAGE_COLORS.D20,
  "D40", DAMAGE_COLORS.D40,
  "#64748b",
] as unknown as string;

export function IssueMap({
  issues,
  districts = [],
  showDistricts = false,
  showHeatmap = false,
  cluster = true,
  visibleClasses,
  maxTimestamp,
  selectedId = null,
  onSelect,
  center = DEMO_MUNICIPALITY.center,
  zoom = DEMO_MUNICIPALITY.zoom,
  interactive = true,
  basemap = "streets",
  className,
}: IssueMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const readyRef = useRef(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const basemapRef = useRef(basemap);
  basemapRef.current = basemap;

  const filtered = issues.filter((i) => {
    if (visibleClasses && !visibleClasses.includes(i.classCode)) return false;
    if (maxTimestamp && new Date(i.capturedAt).getTime() > maxTimestamp) return false;
    return true;
  });
  const dataRef = useRef(filtered);
  dataRef.current = filtered;

  /* Create the map once. */
  useEffect(() => {
    let cancelled = false;
    let map: MLMap | null = null;

    (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      if (cancelled || !containerRef.current) return;

      map = new maplibregl.Map({
        container: containerRef.current,
        style: baseStyle(basemapRef.current),
        center,
        zoom,
        interactive,
        attributionControl: { compact: true },
      });
      mapRef.current = map;
      if (interactive) {
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      }

      map.on("load", () => {
        if (!map || cancelled) return;

        map.addSource("districts", { type: "geojson", data: districtsGeoJSON(districts) });
        map.addLayer({
          id: "district-fill",
          type: "fill",
          source: "districts",
          paint: { "fill-color": BRAND_HEX.primary, "fill-opacity": 0.04 },
          layout: { visibility: showDistricts ? "visible" : "none" },
        });
        // White casing keeps boundaries legible over satellite imagery.
        map.addLayer({
          id: "district-line-casing",
          type: "line",
          source: "districts",
          paint: {
            "line-color": "#ffffff",
            "line-opacity": 0.55,
            "line-width": 3.5,
          },
          layout: { visibility: showDistricts ? "visible" : "none" },
        });
        map.addLayer({
          id: "district-line",
          type: "line",
          source: "districts",
          paint: {
            "line-color": BRAND_HEX.primary,
            "line-opacity": 0.55,
            "line-width": 1.5,
            "line-dasharray": [3, 2],
          },
          layout: { visibility: showDistricts ? "visible" : "none" },
        });

        map.addSource("issues", {
          type: "geojson",
          data: toGeoJSON(dataRef.current),
          cluster,
          clusterRadius: 46,
          clusterMaxZoom: 14,
        });

        map.addLayer({
          id: "heat",
          type: "heatmap",
          source: "issues",
          layout: { visibility: showHeatmap ? "visible" : "none" },
          paint: {
            "heatmap-weight": ["interpolate", ["linear"], ["get", "priority"], 0, 0.1, 100, 1],
            "heatmap-intensity": 1.1,
            "heatmap-radius": 34,
            "heatmap-opacity": 0.72,
            "heatmap-color": [
              "interpolate",
              ["linear"],
              ["heatmap-density"],
              0, "rgba(158,197,244,0)",
              0.25, "#9ec5f4",
              0.5, "#5598e7",
              0.75, "#2a78d6",
              1, "#104281",
            ],
          },
        });

        map.addLayer({
          id: "clusters",
          type: "circle",
          source: "issues",
          filter: ["has", "point_count"],
          paint: {
            "circle-color": BRAND_HEX.primary,
            "circle-opacity": 0.85,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
            "circle-radius": ["step", ["get", "point_count"], 14, 5, 18, 12, 24],
          },
        });
        map.addLayer({
          id: "cluster-count",
          type: "symbol",
          source: "issues",
          filter: ["has", "point_count"],
          layout: {
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Noto Sans Regular"],
            "text-size": 12,
          },
          paint: { "text-color": "#ffffff" },
        });
        map.addLayer({
          id: "points",
          type: "circle",
          source: "issues",
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": CLASS_COLOR_EXPR,
            "circle-radius": ["interpolate", ["linear"], ["get", "priority"], 20, 5, 95, 9],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
        map.addLayer({
          id: "selected-ring",
          type: "circle",
          source: "issues",
          filter: ["==", ["get", "id"], selectedId ?? "__none__"],
          paint: {
            "circle-color": "rgba(0,0,0,0)",
            "circle-radius": 13,
            "circle-stroke-width": 2.5,
            "circle-stroke-color": BRAND_HEX.navy,
          },
        });

        if (interactive) {
          map.on("click", "points", (e: MapMouseEvent) => {
            const feature = map!.queryRenderedFeatures(e.point, { layers: ["points"] })[0];
            const id = feature?.properties?.id as string | undefined;
            if (id) onSelectRef.current?.(id);
          });
          map.on("click", "clusters", async (e: MapMouseEvent) => {
            const feature = map!.queryRenderedFeatures(e.point, { layers: ["clusters"] })[0];
            if (!feature) return;
            const source = map!.getSource("issues") as import("maplibre-gl").GeoJSONSource;
            const zoomTo = await source.getClusterExpansionZoom(
              feature.properties!.cluster_id as number,
            );
            map!.easeTo({
              center: (feature.geometry as GeoJSON.Point).coordinates as [number, number],
              zoom: zoomTo + 0.3,
            });
          });
          for (const layer of ["points", "clusters"]) {
            map.on("mouseenter", layer, () => {
              map!.getCanvas().style.cursor = "pointer";
            });
            map.on("mouseleave", layer, () => {
              map!.getCanvas().style.cursor = "";
            });
          }
        }

        readyRef.current = true;
      });
    })();

    return () => {
      cancelled = true;
      readyRef.current = false;
      map?.remove();
      mapRef.current = null;
    };
    // The map is created once; prop updates are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Update data when the filtered set changes. */
  const dataKey = JSON.stringify(filtered.map((i) => i.id));
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const source = map.getSource("issues") as import("maplibre-gl").GeoJSONSource | undefined;
    source?.setData(toGeoJSON(dataRef.current));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey]);

  /* Toggle layers. */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const vis = (v: boolean) => (v ? "visible" : "none");
    if (map.getLayer("basemap-streets")) {
      map.setLayoutProperty("basemap-streets", "visibility", vis(basemap === "streets"));
      map.setLayoutProperty("basemap-satellite", "visibility", vis(basemap === "satellite"));
    }
    if (map.getLayer("heat")) map.setLayoutProperty("heat", "visibility", vis(showHeatmap));
    for (const id of ["district-fill", "district-line", "district-line-casing"]) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vis(showDistricts));
    }
    if (map.getLayer("selected-ring")) {
      map.setFilter("selected-ring", ["==", ["get", "id"], selectedId ?? "__none__"]);
    }
  }, [showHeatmap, showDistricts, selectedId, basemap]);

  /* Follow center changes (e.g. flying to a selected issue). */
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({ center, zoom, duration: 700 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center[0], center[1], zoom]);

  return (
    <div
      ref={containerRef}
      className={cn("h-full w-full overflow-hidden rounded-lg", className)}
      role="application"
      aria-label="Road damage map"
    />
  );
}
