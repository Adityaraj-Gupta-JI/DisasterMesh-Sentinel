/**
 * Renders the incident's real GPS coordinates (pushed by the phone that filed
 * the report) on an actual interactive map.
 *
 * Built on MapLibre GL — the same open-source engine mapcn.dev's shadcn
 * components wrap — used directly here instead of via mapcn's shadcn CLI,
 * since this project has no Tailwind/shadcn setup for that CLI to plug into;
 * adopting it would mean bootstrapping a second, conflicting styling system
 * on top of the hand-written one already in place. Styled tiles come from
 * OpenStreetMap's free raster tile servers, so this needs **no API key** and
 * no billing setup at all — a real improvement over the previous Google Maps
 * Embed approach, which required a key we don't have.
 *
 * Coarsened/approximate locations (see `shared_precisely` — the same
 * redaction the backend already applies when a caller lacks
 * VIEW_PRECISE_LOCATION) are shown at a wider zoom, never implying more
 * precision than the data actually carries.
 */
import { useEffect, useRef } from "react";
import { Map as MapLibreMap, Marker, NavigationControl, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import type { Incident } from "../lib/api";

// A plain raster style pointed at OpenStreetMap's tile servers — no vector
// style host, no API key, just tiles + required attribution.
const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

function MapCanvas({
  latitude,
  longitude,
  zoom,
}: {
  latitude: number;
  longitude: number;
  zoom: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);

  // Mount the map once per component instance.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [longitude, latitude],
      zoom,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    markerRef.current = new Marker({ color: "#ff5c6c" })
      .setLngLat([longitude, latitude])
      .addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // Intentionally mount-once: re-centering on prop changes is handled below
    // without tearing down and rebuilding the whole GL context.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-center without remounting when a different incident is selected.
  useEffect(() => {
    mapRef.current?.setCenter([longitude, latitude]);
    mapRef.current?.setZoom(zoom);
    markerRef.current?.setLngLat([longitude, latitude]);
  }, [latitude, longitude, zoom]);

  return <div ref={containerRef} className="map-canvas" />;
}

export function LocationMap({ location }: { location: Incident["location"] }) {
  if (!location) {
    return (
      <section className="section">
        <h3>Location</h3>
        <p className="empty">No location shared with this report.</p>
      </section>
    );
  }

  const { latitude, longitude, shared_precisely } = location;

  return (
    <section className="section">
      <h3>Location</h3>
      <div className="map-frame">
        <MapCanvas latitude={latitude} longitude={longitude} zoom={shared_precisely ? 14 : 9} />
      </div>
      <p className="simulated-note" style={{ marginTop: "var(--s2)" }}>
        {latitude.toFixed(5)}, {longitude.toFixed(5)}
        {!shared_precisely && " · approximate — the reporter's precise position was not shared"}
      </p>
    </section>
  );
}
