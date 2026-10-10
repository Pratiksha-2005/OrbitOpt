import React, { useState, useEffect } from 'react';
import { Map as MapIcon, RefreshCw, Satellite as SatelliteIcon, Radio, Layers } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GroundStation } from '../../types/api';
import { fetchLiveSatellites, type LiveSatellite } from '../../services/satelliteApi';

// Fix Leaflet's default icon path issues in React
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom station icon (cyan glowing dot)
const stationIcon = new L.DivIcon({
  html: `<div class="relative w-4 h-4">
          <div class="absolute inset-0 bg-cyan-400 rounded-full animate-ping opacity-60"></div>
          <div class="absolute inset-1 bg-cyan-400 rounded-full border-2 border-slate-900"></div>
         </div>`,
  className: 'custom-leaflet-icon',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

// Custom satellite icon
const satelliteIcon = new L.DivIcon({
  html: `<div class="relative w-3 h-3">
          <div class="absolute inset-0 bg-rose-400 rounded-full border-2 border-slate-900 shadow-[0_0_8px_rgba(251,113,133,0.8)]"></div>
         </div>`,
  className: 'custom-leaflet-icon',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

const MapController = ({ activeStationId, stations, activeSatId, satellites }: { activeStationId?: string, stations: GroundStation[], activeSatId?: string, satellites: LiveSatellite[] }) => {
  const map = useMap();
  
  useEffect(() => {
    // Invalidate size on mount to fix tile rendering offsets
    setTimeout(() => {
      map.invalidateSize();
    }, 100);
  }, [map]);

  useEffect(() => {
    if (activeStationId) {
      const st = stations.find(s => s.station_id === activeStationId);
      if (st) {
        const targetZoom = Math.max(map.getZoom(), 8);
        map.setView([st.latitude_deg, st.longitude_deg], targetZoom, { animate: true });
      }
    }
  }, [activeStationId, stations, map]);

  useEffect(() => {
    if (activeSatId) {
      const sat = satellites.find(s => s.id === activeSatId);
      if (sat) {
        // Zoom in to level 6 if currently zoomed out, otherwise keep current zoom
        const targetZoom = Math.max(map.getZoom(), 6);
        map.setView([sat.lat, sat.lng], targetZoom, { animate: true });
      }
    }
  }, [activeSatId, satellites, map]);
  
  return null;
};

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
  const [satellites, setSatellites] = useState<LiveSatellite[]>([]);
  const [activeSatId, setActiveSatId] = useState<string | undefined>();
  const [localActiveStationId, setLocalActiveStationId] = useState<string | undefined>(activeStationId);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // eslint-disable-next-line react/set-state-in-effect
  useEffect(() => {
    if (activeStationId) {
      setLocalActiveStationId(activeStationId);
    }
  }, [activeStationId]);
  
  // Controls
  const [showStations, setShowStations] = useState(true);
  const [showSatellites, setShowSatellites] = useState(true);
  const [showCoverage, setShowCoverage] = useState(true);
  const [liveTracking, setLiveTracking] = useState(true);

  const fetchSats = async () => {
    setIsLoading(true);
    const data = await fetchLiveSatellites();
    setSatellites(data);
    setLastUpdated(new Date());
    setIsLoading(false);
  };

  // eslint-disable-next-line react/set-state-in-effect
  useEffect(() => {
    fetchSats();
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (liveTracking) {
      interval = setInterval(() => {
        // Fetch new positions every 10 seconds (in a real app we'd just re-propagate the TLE locally to save network, but re-fetching is fine for this demo if cached)
        fetchSats();
      }, 10000);
    }
    return () => clearInterval(interval);
  }, [liveTracking]);

  return (
    <div className="relative rounded-2xl bg-slate-950/80 border border-slate-800 p-4 flex flex-col gap-3">
      {/* Header and Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MapIcon className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Global Ground Station Tracking Network
          </h3>
        </div>
        
        {/* Map Toolbar */}
        <div className="flex flex-wrap items-center gap-2 text-[10px] sm:text-xs">
          <button 
            onClick={() => setLiveTracking(!liveTracking)}
            className={`px-2.5 py-1.5 rounded-md border flex items-center gap-1.5 transition-colors ${liveTracking ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300' : 'bg-slate-900 border-slate-700 text-slate-400'}`}
          >
            <div className={`w-1.5 h-1.5 rounded-full ${liveTracking ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            Live Tracking
          </button>
          
          <button onClick={() => setShowStations(!showStations)} className={`px-2 py-1 rounded border ${showStations ? 'bg-cyan-950/30 border-cyan-800 text-cyan-300' : 'bg-slate-900 border-slate-800 text-slate-500'}`}>
            <Radio className="w-3 h-3 inline mr-1"/> Stations
          </button>
          <button onClick={() => setShowSatellites(!showSatellites)} className={`px-2 py-1 rounded border ${showSatellites ? 'bg-rose-950/30 border-rose-800 text-rose-300' : 'bg-slate-900 border-slate-800 text-slate-500'}`}>
            <SatelliteIcon className="w-3 h-3 inline mr-1"/> Satellites
          </button>
          <button onClick={() => setShowCoverage(!showCoverage)} className={`px-2 py-1 rounded border ${showCoverage ? 'bg-indigo-950/30 border-indigo-800 text-indigo-300' : 'bg-slate-900 border-slate-800 text-slate-500'}`}>
            <Layers className="w-3 h-3 inline mr-1"/> Coverage
          </button>
          
          <button onClick={fetchSats} disabled={isLoading} className="p-1.5 rounded bg-slate-900 border border-slate-700 text-slate-300 hover:bg-slate-800 ml-auto disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Map Container */}
      <div className="relative w-full h-[400px] rounded-xl overflow-hidden border border-slate-800 z-0 bg-slate-900">
        <MapContainer 
          center={[20, 0]} 
          zoom={2} 
          minZoom={2}
          className="w-full h-full"
          worldCopyJump={true}
        >
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
          />
          
          <MapController activeStationId={localActiveStationId} stations={stations} activeSatId={activeSatId} satellites={satellites} />

          {/* Render Coverage Areas */}
          {showCoverage && showStations && stations.map((st) => (
            <Circle
              key={`cov-${st.station_id}`}
              center={[st.latitude_deg, st.longitude_deg]}
              radius={Math.max(1000000, 3000000 - (st.elevation_mask_deg || 5) * 50000)} // Approximate visibility radius based on elevation mask
              pathOptions={{
                color: activeStationId === st.station_id ? '#06b6d4' : 'rgba(6, 182, 212, 0.4)',
                fillColor: activeStationId === st.station_id ? '#06b6d4' : 'transparent',
                fillOpacity: 0.05,
                weight: 1,
                dashArray: '4 4'
              }}
            />
          ))}

          {/* Render Ground Stations */}
          {showStations && stations.map((st) => (
            <Marker
              key={`st-${st.station_id}`}
              position={[st.latitude_deg, st.longitude_deg]}
              icon={stationIcon}
              eventHandlers={{
                click: () => {
                  setLocalActiveStationId(st.station_id);
                  onSelectStation?.(st.station_id);
                },
              }}
            >
              <Tooltip direction="top" offset={[0, -10]} opacity={1} className="orbitopt-popup">
                <div className="text-slate-900 font-sans p-1">
                  <div className="font-bold text-sm mb-1">{st.name}</div>
                  <div className="text-[11px] font-mono text-slate-500 mb-2">{st.station_id}</div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                    <div><b>Lat:</b> {st.latitude_deg.toFixed(2)}°</div>
                    <div><b>Lon:</b> {st.longitude_deg.toFixed(2)}°</div>
                    <div><b>Mask:</b> {st.elevation_mask_deg}°</div>
                    <div><b>Bands:</b> {(st.supported_bands || ['X']).join(',')}</div>
                  </div>
                </div>
              </Tooltip>
              <Popup className="orbitopt-popup">
                <div className="text-slate-900 font-sans p-1">
                  <div className="font-bold text-sm mb-1">{st.name}</div>
                  <div className="text-[11px] font-mono text-slate-500 mb-2">{st.station_id}</div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                    <div><b>Lat:</b> {st.latitude_deg.toFixed(2)}°</div>
                    <div><b>Lon:</b> {st.longitude_deg.toFixed(2)}°</div>
                    <div><b>Mask:</b> {st.elevation_mask_deg}°</div>
                    <div><b>Bands:</b> {(st.supported_bands || ['X']).join(',')}</div>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Render Live Satellites */}
          {showSatellites && satellites.map((sat) => (
            <Marker
              key={sat.id}
              position={[sat.lat, sat.lng]}
              icon={satelliteIcon}
              eventHandlers={{
                click: () => setActiveSatId(sat.id === activeSatId ? undefined : sat.id),
              }}
            >
              <Popup className="orbitopt-popup">
                <div className="text-slate-900 font-sans p-1">
                  <div className="font-bold text-sm mb-1 text-rose-600 flex items-center gap-1.5">
                    <SatelliteIcon className="w-3.5 h-3.5" />
                    {sat.name}
                  </div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs mt-2">
                    <div><b>Lat:</b> {sat.lat.toFixed(2)}°</div>
                    <div><b>Lon:</b> {sat.lng.toFixed(2)}°</div>
                    <div><b>Alt:</b> {sat.alt.toFixed(0)} km</div>
                    <div><b>Vel:</b> {sat.velocity.toFixed(2)} km/s</div>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
        
        {/* Status Overlay */}
        <div className="absolute bottom-2 left-2 z-[400] flex items-center gap-2 pointer-events-none">
          {isLoading && (
            <span className="px-2 py-1 bg-slate-900/90 border border-cyan-500/30 rounded text-[10px] text-cyan-400 backdrop-blur shadow">
              Loading telemetry...
            </span>
          )}
        </div>
        <div className="absolute bottom-2 right-2 z-[400] text-[9px] text-slate-500 font-mono pointer-events-none bg-slate-950/50 px-1.5 py-0.5 rounded">
          {lastUpdated ? `Data Epoch: ${lastUpdated.toLocaleTimeString()} UTC` : 'Waiting for telemetry...'}
        </div>
      </div>
      
      {/* Required CSS for custom popups */}
      <style>{`
        .orbitopt-popup .leaflet-popup-content-wrapper {
          border-radius: 8px;
          box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
        }
        .orbitopt-popup .leaflet-popup-tip {
          box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
        }
      `}</style>
    </div>
  );
};
