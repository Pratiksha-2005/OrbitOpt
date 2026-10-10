import * as satellite from 'satellite.js';

export interface LiveSatellite {
  id: string;
  name: string;
  lat: number;
  lng: number;
  alt: number; // km
  velocity: number; // km/s
}

// Fetch TLE data from CelesTrak (Earth Resources satellites as a good subset for OrbitOpt)
export const fetchLiveSatellites = async (): Promise<LiveSatellite[]> => {
  try {
    const response = await fetch('https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle');
    if (!response.ok) {
      throw new Error('Failed to fetch TLE data');
    }
    const data = await response.text();
    return parseTLEData(data);
  } catch (error) {
    console.error('Error fetching satellite data:', error);
    return [];
  }
};

const parseTLEData = (tleData: string): LiveSatellite[] => {
  const lines = tleData.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  const satellites: LiveSatellite[] = [];
  const now = new Date();

  // TLE data comes in 3-line chunks (Name, Line 1, Line 2)
  for (let i = 0; i < lines.length; i += 3) {
    if (i + 2 >= lines.length) break;
    
    const name = lines[i];
    const tleLine1 = lines[i + 1];
    const tleLine2 = lines[i + 2];

    try {
      const satrec = satellite.twoline2satrec(tleLine1, tleLine2);
      
      const positionAndVelocity = satellite.propagate(satrec, now);
      if (!positionAndVelocity) continue;
      
      const positionEci = positionAndVelocity.position;
      const velocityEci = positionAndVelocity.velocity;

      if (positionEci && velocityEci && typeof positionEci !== 'boolean' && typeof velocityEci !== 'boolean') {
        const gmst = satellite.gstime(now);
        const positionGd = satellite.eciToGeodetic(positionEci as satellite.EciVec3<number>, gmst);
        
        const lat = satellite.degreesLat(positionGd.latitude);
        const lng = satellite.degreesLong(positionGd.longitude);
        const alt = positionGd.height;
        
        // Calculate velocity magnitude
        const vx = (velocityEci as satellite.EciVec3<number>).x;
        const vy = (velocityEci as satellite.EciVec3<number>).y;
        const vz = (velocityEci as satellite.EciVec3<number>).z;
        const velocity = Math.sqrt(vx * vx + vy * vy + vz * vz);

        satellites.push({
          id: name.trim() + '-' + i,
          name: name.trim(),
          lat,
          lng,
          alt,
          velocity
        });
      }
    } catch (err) {
      // Skip satellites that fail to propagate
    }
  }

  return satellites;
};
