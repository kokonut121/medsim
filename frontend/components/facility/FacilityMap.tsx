"use client";

import type { Route } from "next";
import Link from "next/link";
import { useEffect, useRef } from "react";

import type { Facility } from "@/types";

export function FacilityMap({ facilities }: { facilities: Facility[] }) {
  const mapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token || !mapRef.current) {
      return;
    }

    let disposed = false;
    let removeMap: (() => void) | undefined;

    void import("mapbox-gl").then((module) => {
      if (disposed || !mapRef.current) {
        return;
      }

      const mapboxgl = module.default;
      mapboxgl.accessToken = token;

      const map = new mapboxgl.Map({
        container: mapRef.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: facilities.length ? [facilities[0].lng, facilities[0].lat] : [-71.104, 42.362],
        zoom: facilities.length ? 12 : 10
      });

      facilities.forEach((facility) => {
        new mapboxgl.Marker({ color: "#c0392b" })
          .setLngLat([facility.lng, facility.lat])
          .setPopup(new mapboxgl.Popup({ offset: 12 }).setHTML(`<strong>${facility.name}</strong><br/>${facility.address}`))
          .addTo(map);
      });

      removeMap = () => {
        map.remove();
      };
    });

    return () => {
      disposed = true;
      removeMap?.();
    };
  }, [facilities]);

  return (
    <div className="panel">
      <div className="eyebrow">Mapbox Facility Selector</div>
      <h2 style={{ marginTop: 8 }}>Facility overview</h2>
      <div className="map" ref={mapRef} />
      <div className="card-grid" style={{ marginTop: 20 }}>
        {facilities.map((facility) => (
          <Link className="feed-card" href={`/facility/${facility.facility_id}` as Route} key={facility.facility_id}>
            <div className="eyebrow">{facility.address}</div>
            <h3 style={{ marginBottom: 8 }}>{facility.name}</h3>
            <p className="muted" style={{ margin: 0 }}>
              Auto-acquire imagery, build 3D world model, deploy six safety agent teams.
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
