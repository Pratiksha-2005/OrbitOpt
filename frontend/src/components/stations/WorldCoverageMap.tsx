import React, { useState } from 'react';
import { Radio, Signal } from 'lucide-react';
import type { GroundStation } from '../../types/api';

interface WorldCoverageMapProps {
  stations: GroundStation[];
  activeStationId?: string;
  onSelectStation?: (stationId: string) => void;
}

export const WorldCoverageMap: React.FC<WorldCoverageMapProps> = ({
  stations,
  activeStationId,
  onSelectStation,
}) => {
  const [hoveredStation, setHoveredStation] = useState<GroundStation | null>(null);

  // Convert lat/long to SVG 2D equirectangular coordinates (width 800, height 400)
  // Longitude: [-180, 180] -> [0, 800]
  // Latitude: [90, -90] -> [0, 400]
  const projectCoordinates = (lat: number, lon: number) => {
    const x = ((lon + 180) / 360) * 800;
    const y = ((90 - lat) / 180) * 400;
    return { x, y };
  };

  return (
    <div className="relative rounded-2xl bg-slate-950/80 border border-slate-800 p-4 overflow-hidden">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Signal className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Global Ground Station Tracking Network
          </h3>
        </div>
        <span className="text-[11px] font-mono text-slate-500">
          Equirectangular Orbit Projection (±180° Lon / ±90° Lat)
        </span>
      </div>

      {/* SVG Canvas Map */}
      <div className="relative w-full aspect-[2/1] rounded-xl bg-slate-900/60 border border-slate-850 overflow-hidden flex items-center justify-center">
        {/* World Grid Lines Background */}
        <svg
          viewBox="0 0 800 400"
          className="w-full h-full select-none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="gridGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0f172a" />
              <stop offset="100%" stopColor="#0b1120" />
            </linearGradient>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="rgba(51, 65, 85, 0.25)"
                strokeWidth="0.7"
              />
            </pattern>
            <radialGradient id="antennaPulse">
              <stop offset="0%" stopColor="rgba(6, 182, 212, 0.6)" />
              <stop offset="60%" stopColor="rgba(6, 182, 212, 0.15)" />
              <stop offset="100%" stopColor="rgba(6, 182, 212, 0)" />
            </radialGradient>
          </defs>

          {/* Base rect with grid pattern */}
          <rect width="800" height="400" fill="url(#gridGrad)" />
          <rect width="800" height="400" fill="url(#grid)" />

          {/* Equator & Prime Meridian dashed lines */}
          <line
            x1="0"
            y1="200"
            x2="800"
            y2="200"
            stroke="rgba(100, 116, 139, 0.35)"
            strokeDasharray="4 4"
            strokeWidth="1"
          />
          <line
            x1="400"
            y1="0"
            x2="400"
            y2="400"
            stroke="rgba(100, 116, 139, 0.35)"
            strokeDasharray="4 4"
            strokeWidth="1"
          />

          {/* Continents simplified geometric contours for realistic spatial reference */}
          <g fill="rgba(30, 41, 59, 0.45)" stroke="rgba(71, 85, 105, 0.3)" strokeWidth="0.8">
            {/* North America */}
            <path d="M 120 70 L 220 80 L 260 120 L 220 180 L 160 170 L 120 120 Z" />
            {/* South America */}
            <path d="M 230 210 L 280 230 L 260 330 L 220 350 L 210 260 Z" />
            {/* Europe */}
            <path d="M 380 70 L 450 70 L 460 120 L 390 120 Z" />
            {/* Africa */}
            <path d="M 390 140 L 480 150 L 470 270 L 420 300 L 380 220 Z" />
            {/* Asia */}
            <path d="M 460 60 L 680 80 L 660 180 L 520 170 L 470 120 Z" />
            {/* Australia */}
            <path d="M 640 240 L 720 250 L 710 320 L 630 300 Z" />
            {/* Antarctica */}
            <path d="M 100 370 L 700 370 L 650 395 L 150 395 Z" />
          </g>

          {/* Stations markers & radio coverage horizon rings */}
          {stations.map((st) => {
            const { x, y } = projectCoordinates(st.latitude_deg, st.longitude_deg);
            const isHovered = hoveredStation?.station_id === st.station_id;
            const isSelected = activeStationId === st.station_id;
            const radius = Math.max(25, 45 - (st.elevation_mask_deg || 5) * 2);

            return (
              <g
                key={st.station_id}
                className="cursor-pointer transition-all duration-200"
                onClick={() => onSelectStation?.(st.station_id)}
                onMouseEnter={() => setHoveredStation(st)}
                onMouseLeave={() => setHoveredStation(null)}
              >
                {/* Elevation mask coverage horizon radius */}
                <circle
                  cx={x}
                  cy={y}
                  r={radius}
                  fill="url(#antennaPulse)"
                  stroke={isSelected || isHovered ? '#06b6d4' : 'rgba(6, 182, 212, 0.4)'}
                  strokeWidth="1.2"
                  strokeDasharray="3 3"
                />

                {/* Animated inner ripple */}
                <circle
                  cx={x}
                  cy={y}
                  r="6"
                  fill="#06b6d4"
                  className="animate-ping opacity-60"
                />

                {/* Center marker dot */}
                <circle
                  cx={x}
                  cy={y}
                  r="4"
                  fill={isSelected ? '#38bdf8' : '#22d3ee'}
                  stroke="#0f172a"
                  strokeWidth="1.5"
                />

                {/* Station label */}
                <text
                  x={x}
                  y={y - 12}
                  textAnchor="middle"
                  fill="#e2e8f0"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight="bold"
                  className="pointer-events-none drop-shadow"
                >
                  {st.station_id.replace('GS-', '')}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover detail tooltip */}
        {hoveredStation && (
          <div className="absolute top-3 left-3 bg-slate-900/95 border border-cyan-500/40 rounded-xl p-3 shadow-xl backdrop-blur-md text-xs pointer-events-none z-10 animate-in fade-in duration-150">
            <div className="flex items-center gap-1.5 font-bold text-slate-100">
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span>{hoveredStation.name}</span>
            </div>
            <div className="text-[11px] font-mono text-cyan-300 mt-1">
              {hoveredStation.station_id}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-slate-400 mt-2">
              <span>Lat: {hoveredStation.latitude_deg.toFixed(2)}°</span>
              <span>Lon: {hoveredStation.longitude_deg.toFixed(2)}°</span>
              <span>Elev Mask: {hoveredStation.elevation_mask_deg || 5}°</span>
              <span>Bands: {(hoveredStation.supported_bands || ['X-band']).join(', ')}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
