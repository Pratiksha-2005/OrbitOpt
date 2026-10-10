import React, { useRef, Suspense, useMemo } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';

// --- Error Boundary for WebGL Fallback ---
class WebGLErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 text-sm p-4 border border-slate-800 rounded-2xl bg-slate-900/30">
          <div className="w-16 h-16 mb-4 rounded-full border border-slate-700 flex items-center justify-center bg-slate-800/50">
            <span className="text-2xl">🌍</span>
          </div>
          <p>Interactive 3D Earth</p>
          <p className="text-xs text-slate-600 mt-1">WebGL not supported or disabled</p>
        </div>
      );
    }
    return this.props.children;
  }
}

// --- Components ---

const Earth: React.FC = () => {
  const earthRef = useRef<THREE.Group>(null);
  
  // Load textures from Three.js official examples (MIT License)
  const [colorMap, normalMap, specularMap, cloudsMap] = useLoader(THREE.TextureLoader, [
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_atmos_2048.jpg',
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_normal_2048.jpg',
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_specular_2048.jpg',
    'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_clouds_1024.png'
  ]);

  const mouse = useRef({ x: 0, y: 0 });
  const target = useRef({ x: 0, y: 0 });

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouse.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.current.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useFrame((_state, delta) => {
    if (earthRef.current) {
      // Continuous Earth rotation
      earthRef.current.rotation.y += delta * 0.05;
      
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!prefersReducedMotion) {
        // Smooth interpolation using lerp
        target.current.x = THREE.MathUtils.lerp(target.current.x, mouse.current.x, 0.05);
        target.current.y = THREE.MathUtils.lerp(target.current.y, mouse.current.y, 0.05);
        
        // Apply tilt without affecting the continuous Y rotation
        earthRef.current.rotation.x = -target.current.y * 0.15;
        earthRef.current.rotation.z = -target.current.x * 0.15;
      }
    }
  });

  return (
    <group ref={earthRef}>
      {/* Base Earth Sphere */}
      <mesh>
        <sphereGeometry args={[2, 64, 64]} />
        <meshPhongMaterial
          map={colorMap}
          normalMap={normalMap}
          specularMap={specularMap}
          specular={new THREE.Color('grey')}
          shininess={15}
        />
      </mesh>
      
      {/* Cloud Layer (slightly larger) */}
      <mesh>
        <sphereGeometry args={[2.02, 64, 64]} />
        <meshPhongMaterial
          map={cloudsMap}
          transparent={true}
          opacity={0.4}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      
      {/* Atmospheric Glow (Fresnel illusion using a simple gradient shader or rim light) */}
      <mesh>
        <sphereGeometry args={[2.15, 64, 64]} />
        <meshBasicMaterial
          color="#38bdf8"
          transparent={true}
          opacity={0.15}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  );
};

// Represents a satellite and its orbital path
const SatelliteNode: React.FC<{
  radius: number;
  speed: number;
  color: string;
  initialAngle: number;
  tiltX: number;
  tiltZ: number;
}> = ({ radius, speed, color, initialAngle, tiltX, tiltZ }) => {
  const satelliteRef = useRef<THREE.Mesh>(null);
  
  // Create orbital path line
  const orbitPoints = useMemo(() => {
    const points = [];
    for (let i = 0; i <= 64; i++) {
      const angle = (i / 64) * Math.PI * 2;
      points.push(new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius));
    }
    return points;
  }, [radius]);
  
  const orbitGeometry = useMemo(() => {
    const geo = new THREE.BufferGeometry().setFromPoints(orbitPoints);
    return geo;
  }, [orbitPoints]);

  useFrame((state) => {
    if (satelliteRef.current) {
      const time = state.clock.getElapsedTime();
      const angle = initialAngle + time * speed;
      satelliteRef.current.position.x = Math.cos(angle) * radius;
      satelliteRef.current.position.z = Math.sin(angle) * radius;
    }
  });

  return (
    <group rotation={[tiltX, 0, tiltZ]}>
      {/* The Orbit Path */}
      <primitive 
        object={new THREE.LineLoop(
          orbitGeometry, 
          new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.2 })
        )} 
      />
      
      {/* The Satellite Mesh */}
      <mesh ref={satelliteRef}>
        <octahedronGeometry args={[0.06, 0]} />
        <meshBasicMaterial color={color} />
        {/* Glow effect on satellite */}
        <mesh>
          <sphereGeometry args={[0.1, 16, 16]} />
          <meshBasicMaterial color={color} transparent opacity={0.4} blending={THREE.AdditiveBlending} />
        </mesh>
      </mesh>
    </group>
  );
};

export const EarthScene: React.FC = () => {
  return (
    <div className="w-full h-[500px] lg:h-[800px] absolute left-1/2 -translate-x-1/2 bottom-[-5%] lg:bottom-[-10%] pointer-events-none z-0">
      <WebGLErrorBoundary>
        <Canvas camera={{ position: [0, 0, 6], fov: 45 }} dpr={[1, 2]}>
          <ambientLight intensity={0.1} />
          <directionalLight position={[5, 3, 5]} intensity={2} color="#ffffff" />
          <directionalLight position={[-5, -3, -5]} intensity={0.2} color="#38bdf8" />
          
          <Suspense fallback={null}>
            {/* The Earth and Atmosphere */}
            <Earth />
            
            {/* Satellites */}
            <SatelliteNode radius={2.6} speed={0.4} color="#38bdf8" initialAngle={0} tiltX={0.2} tiltZ={0.3} />
            <SatelliteNode radius={2.9} speed={0.3} color="#818cf8" initialAngle={Math.PI} tiltX={-0.4} tiltZ={0.1} />
            <SatelliteNode radius={3.2} speed={0.25} color="#2dd4bf" initialAngle={Math.PI / 2} tiltX={0.6} tiltZ={-0.5} />
            <SatelliteNode radius={2.4} speed={0.5} color="#c084fc" initialAngle={Math.PI * 1.5} tiltX={-0.1} tiltZ={0.8} />
            
            {/* Restrained background stars */}
            <Stars radius={10} depth={50} count={1500} factor={4} saturation={0} fade speed={1} />
            
            {/* Minimal controls allowing limited zooming/panning */}
            <OrbitControls 
              enableZoom={false} 
              enablePan={false}
              enableRotate={true}
              autoRotate={false}
              minPolarAngle={Math.PI / 3}
              maxPolarAngle={Math.PI - Math.PI / 3}
            />
          </Suspense>
        </Canvas>
      </WebGLErrorBoundary>
    </div>
  );
};
