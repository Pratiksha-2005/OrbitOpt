import React, { useState, useEffect, useCallback } from 'react';
import type {
  Dataset,
  ScheduleRunResponse,
  HealthCheckResponse,
} from './types/api';
import {
  checkHealth,
  runBaseline,
  runOptimize,
  getDataset,
  createDataset,
  listDatasets,
  getApiErrorMessage,
} from './services/orbitOptApi';
import {
  MOCK_DATASETS,
  MOCK_BASELINE_RUN,
  MOCK_OPTIMIZED_RUN,
} from './services/mockData';

import { Navbar } from './components/layout/Navbar';
import { Sidebar, type NavTab } from './components/layout/Sidebar';
import { LiveStatusBanner } from './components/dashboard/LiveStatusBanner';
import { OperationalCards } from './components/dashboard/OperationalCards';
import { QuickActions } from './components/dashboard/QuickActions';
import { ScheduleTimeline } from './components/timeline/ScheduleTimeline';
import { AlgorithmComparison } from './components/comparison/AlgorithmComparison';
import { InteractiveOrbitalSimulator } from './components/dashboard/InteractiveOrbitalSimulator';
import { PassList } from './components/passes/PassList';
import { GroundStationsView } from './components/stations/GroundStationsView';
import { LoadingState } from './components/common/LoadingState';
import { ErrorAlert } from './components/common/ErrorAlert';
import { useAuth } from './contexts/AuthContext';
import { AuthScreen } from './components/auth/AuthScreen';
import { LandingPage } from './components/landing/LandingPage';
import { Starfield } from './components/common/Starfield';
import { ArrowLeft } from 'lucide-react';

import './App.css';

export const App: React.FC = () => {
  const { user } = useAuth();
  const [showAuthScreen, setShowAuthScreen] = useState<boolean>(false);
  
  // Navigation & UI state
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Connection & Health state
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState<boolean>(false);

  // Scenarios state
  const [datasets, setDatasets] = useState<Dataset[]>(MOCK_DATASETS);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>(
    'ds_priority_contention_benchmark'
  );

  // Active scenario object
  const activeDataset =
    datasets.find((d) => d.dataset_id === selectedDatasetId) || datasets[0];

  // Schedule runs state (defaults to calibrated mock benchmark)
  const [baselineRun, setBaselineRun] = useState<ScheduleRunResponse | null>(
    MOCK_BASELINE_RUN
  );
  const [optimizedRun, setOptimizedRun] = useState<ScheduleRunResponse | null>(
    MOCK_OPTIMIZED_RUN
  );
  const [activeRun, setActiveRun] = useState<ScheduleRunResponse | null>(
    MOCK_OPTIMIZED_RUN
  );

  // Solver parameters
  const [setupTimeSeconds, setSetupTimeSeconds] = useState<number>(60);
  const [timeLimitSeconds, setTimeLimitSeconds] = useState<number>(30);

  // Async execution state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  /**
   * Sync datasets from backend when available
   */
  const syncBackendDatasets = useCallback(async () => {
    try {
      const summaries = await listDatasets();
      if (summaries.length > 0) {
        const fullDatasets: Dataset[] = [];
        for (const s of summaries.slice(0, 10)) {
          try {
            const full = await getDataset(s.dataset_id);
            fullDatasets.push(full);
          } catch {
            // Ignore individual fetch failure
          }
        }
        if (fullDatasets.length > 0) {
          setDatasets(fullDatasets);
          setSelectedDatasetId((prev) => {
            const found = fullDatasets.some((d) => d.dataset_id === prev);
            return found ? prev : fullDatasets[0].dataset_id;
          });
        }
      }
    } catch {
      // Keep existing scenarios
    }
  }, []);

  /**
   * Health verification logic
   */
  const testHealthConnection = useCallback(async () => {
    setIsCheckingHealth(true);
    setError(null);
    try {
      const data = await checkHealth();
      setHealth(data);
      setIsBackendConnected(true);
      await syncBackendDatasets();
    } catch {
      setIsBackendConnected(false);
      setHealth(null);
    } finally {
      setIsCheckingHealth(false);
    }
  }, [syncBackendDatasets]);

  // Check health on initial mount
  useEffect(() => {
    let ignore = false;
    const checkInitialHealth = async () => {
      try {
        const data = await checkHealth();
        if (!ignore) {
          setHealth(data);
          setIsBackendConnected(true);
          await syncBackendDatasets();
        }
      } catch {
        if (!ignore) {
          setIsBackendConnected(false);
          setHealth(null);
        }
      }
    };
    checkInitialHealth();
    return () => {
      ignore = true;
    };
  }, [syncBackendDatasets]);

  /**
   * Helper to ensure the active scenario exists on the backend database
   */
  const ensureDatasetOnBackend = async (dataset: Dataset): Promise<string> => {
    try {
      await getDataset(dataset.dataset_id);
      return dataset.dataset_id;
    } catch {
      // Auto-register scenario on backend with explicit dataset_id
      const created = await createDataset({
        dataset_id: dataset.dataset_id,
        name: dataset.name,
        description: dataset.description,
        ground_stations: dataset.ground_stations,
        satellite_passes: dataset.satellite_passes,
      });
      return created.dataset_id;
    }
  };

  // Automatically refresh benchmark comparison when dataset selection changes
  useEffect(() => {
    let ignore = false;
    const runForDataset = async () => {
      if (!activeDataset) return;
      try {
        if (isBackendConnected) {
          const datasetId = await ensureDatasetOnBackend(activeDataset);
          const bResult = await runBaseline(datasetId, setupTimeSeconds);
          const oResult = await runOptimize(datasetId, timeLimitSeconds, setupTimeSeconds);
          if (!ignore) {
            setBaselineRun(bResult);
            setOptimizedRun(oResult);
            setActiveRun(oResult);
          }
        }
      } catch {
        // Fallback gracefully
      }
    };
    runForDataset();
    return () => {
      ignore = true;
    };
  }, [selectedDatasetId, isBackendConnected, setupTimeSeconds, timeLimitSeconds]);

  /**
   * Execute Baseline FCFS Scheduling
   */
  const handleRunBaseline = async () => {
    setIsLoading(true);
    setLoadingMessage('Executing Baseline First-Come-First-Served (FCFS) Schedule...');
    setError(null);

    try {
      if (isBackendConnected) {
        const datasetId = await ensureDatasetOnBackend(activeDataset);
        const result = await runBaseline(datasetId, setupTimeSeconds);
        setBaselineRun(result);
        setActiveRun(result);
      } else {
        // Fallback simulated execution with realistic delay
        await new Promise((resolve) => setTimeout(resolve, 500));
        const simulated = {
          ...MOCK_BASELINE_RUN,
          dataset_id: selectedDatasetId,
          created_at: new Date().toISOString(),
        };
        setBaselineRun(simulated);
        setActiveRun(simulated);
      }
    } catch (err) {
      const msg = getApiErrorMessage(err);
      setError(`Failed to execute Baseline FCFS: ${msg}`);
      // Fallback to calibrated benchmark so demo continues smoothly
      setBaselineRun(MOCK_BASELINE_RUN);
      setActiveRun(MOCK_BASELINE_RUN);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Execute CP-SAT Multi-Satellite Optimizer
   */
  const handleRunOptimizer = async () => {
    setIsLoading(true);
    setLoadingMessage(
      'Solving Multi-Satellite Constraint Model with OR-Tools CP-SAT...'
    );
    setError(null);

    try {
      if (isBackendConnected) {
        const datasetId = await ensureDatasetOnBackend(activeDataset);
        const result = await runOptimize(
          datasetId,
          timeLimitSeconds,
          setupTimeSeconds,
          undefined,
          true
        );
        setOptimizedRun(result);
        setActiveRun(result);
      } else {
        // Fallback simulated execution with realistic solver delay
        await new Promise((resolve) => setTimeout(resolve, 800));
        const simulated = {
          ...MOCK_OPTIMIZED_RUN,
          dataset_id: selectedDatasetId,
          created_at: new Date().toISOString(),
        };
        setOptimizedRun(simulated);
        setActiveRun(simulated);
      }
    } catch (err) {
      const msg = getApiErrorMessage(err);
      setError(`Failed to execute CP-SAT Optimizer: ${msg}`);
      // Fallback to calibrated benchmark
      setOptimizedRun(MOCK_OPTIMIZED_RUN);
      setActiveRun(MOCK_OPTIMIZED_RUN);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Execute Head-to-Head Comparison
   */
  const handleRunComparison = async () => {
    setIsLoading(true);
    setLoadingMessage('Running Head-to-Head Benchmark: FCFS vs CP-SAT Solver...');
    setError(null);

    try {
      if (isBackendConnected) {
        const datasetId = await ensureDatasetOnBackend(activeDataset);
        const bResult = await runBaseline(datasetId, setupTimeSeconds);
        const oResult = await runOptimize(datasetId, timeLimitSeconds, setupTimeSeconds);
        setBaselineRun(bResult);
        setOptimizedRun(oResult);
        setActiveRun(oResult);
      } else {
        await new Promise((resolve) => setTimeout(resolve, 700));
        setBaselineRun({
          ...MOCK_BASELINE_RUN,
          dataset_id: selectedDatasetId,
          created_at: new Date().toISOString(),
        });
        setOptimizedRun({
          ...MOCK_OPTIMIZED_RUN,
          dataset_id: selectedDatasetId,
          created_at: new Date().toISOString(),
        });
        setActiveRun(MOCK_OPTIMIZED_RUN);
      }
      setActiveTab('comparison');
    } catch (err) {
      const msg = getApiErrorMessage(err);
      setError(`Benchmark run failed: ${msg}`);
      setBaselineRun(MOCK_BASELINE_RUN);
      setOptimizedRun(MOCK_OPTIMIZED_RUN);
      setActiveTab('comparison');
    } finally {
      setIsLoading(false);
    }
  };

  if (!user) {
    if (showAuthScreen) {
      return (
        <div className="relative">
          <button 
            onClick={() => setShowAuthScreen(false)}
            className="absolute top-6 left-6 z-50 flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:text-white transition-colors bg-slate-900/50 p-2 rounded-md backdrop-blur-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </button>
          <AuthScreen />
        </div>
      );
    }
    return <LandingPage onNavigateToAuth={() => setShowAuthScreen(true)} />;
  }

  return (
    <div className="min-h-screen bg-[#070a13] text-slate-100 flex flex-col font-sans relative overflow-hidden">
      {/* Subtle background starfield for premium dashboard feel */}
      <div className="absolute inset-0 z-0 opacity-20 pointer-events-none">
        <Starfield />
      </div>
      
      <div className="relative z-10 flex flex-col min-h-screen w-full">
        {/* Top Mission Control Header */}
        <Navbar
          activeScenarioName={activeDataset.name}
        />

        {/* Main App Body */}
        <div className="flex-1 flex overflow-hidden">
          {/* Navigation Sidebar */}
          <Sidebar
            activeTab={activeTab}
            onSelectTab={setActiveTab}
            datasets={datasets}
            selectedDatasetId={selectedDatasetId}
            onSelectDatasetId={setSelectedDatasetId}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            health={health}
            isBackendConnected={isBackendConnected}
            isCheckingHealth={isCheckingHealth}
            onRefreshHealth={testHealthConnection}
          />

          {/* Dynamic Content Viewport */}
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
            {/* Transparent Live vs Demo Status Banner */}
            <LiveStatusBanner
              isBackendConnected={isBackendConnected}
              isMock={activeRun?.is_mock ?? true}
              onRetryConnection={testHealthConnection}
            />

            {/* Error Banner */}
            {error && (
              <ErrorAlert
                title="API Execution Warning"
                message={error}
                onRetry={testHealthConnection}
              />
            )}

            {/* Validation Violations */}
            {activeRun && !activeRun.is_valid && activeRun.validation_violations && activeRun.validation_violations.length > 0 && (
              <div className="bg-amber-950/40 border border-amber-500/50 rounded-lg p-4">
                <h4 className="text-amber-400 font-bold mb-2 flex items-center gap-2">
                  <span>⚠️</span> Schedule Validation Failed
                </h4>
                <ul className="list-disc list-inside text-sm text-amber-200/80 space-y-1">
                  {activeRun.validation_violations.map((violation, idx) => (
                    <li key={idx}>{violation}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Async Loading Overlay */}
            {isLoading && (
              <LoadingState
                message={loadingMessage}
                submessage="Enforcing antenna pointing slew margins and maximum data volume constraints"
              />
            )}

            {/* Active Tab View Rendering */}
            {!isLoading && (
              <>
                {activeTab === 'dashboard' && (
                  <div className="space-y-6">
                    {/* Premium Animated Hero */}
                    <InteractiveOrbitalSimulator 
                      activeDataset={activeDataset} 
                      activeRun={activeRun} 
                      onRunOptimizer={handleRunOptimizer}
                    />

                    {/* Solver Parameter Controls & Actions */}
                    <QuickActions
                      onRunOptimizer={handleRunOptimizer}
                      onRunBaseline={handleRunBaseline}
                      onRunComparison={handleRunComparison}
                      isLoading={isLoading}
                      setupTimeSeconds={setupTimeSeconds}
                      onChangeSetupTime={setSetupTimeSeconds}
                      timeLimitSeconds={timeLimitSeconds}
                      onChangeTimeLimit={setTimeLimitSeconds}
                    />

                    {/* Operational KPI Cards */}
                    <OperationalCards
                      activeRun={activeRun}
                      baselineRun={baselineRun}
                    />

                    {/* Active Schedule Timeline Preview */}
                    <div className="pt-2">
                      <ScheduleTimeline
                        activeRun={activeRun}
                        groundStations={activeDataset.ground_stations}
                        setupTimeSeconds={setupTimeSeconds}
                      />
                    </div>

                    {/* Pass Allocation Overview */}
                    <div className="pt-2">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                          Satellite Pass Allocation Summary
                        </h3>
                        <button
                          onClick={() => setActiveTab('passes')}
                          className="text-xs text-cyan-400 hover:text-cyan-300 font-medium transition"
                        >
                          View Full Filterable Table →
                        </button>
                      </div>
                      <PassList
                        passes={activeDataset.satellite_passes.slice(0, 4)}
                        activeRun={activeRun}
                      />
                    </div>
                  </div>
                )}

                {activeTab === 'timeline' && (
                  <ScheduleTimeline
                    activeRun={activeRun}
                    groundStations={activeDataset.ground_stations}
                    setupTimeSeconds={setupTimeSeconds}
                  />
                )}

                {activeTab === 'comparison' && (
                  <AlgorithmComparison
                    baselineRun={baselineRun || MOCK_BASELINE_RUN}
                    optimizedRun={optimizedRun || MOCK_OPTIMIZED_RUN}
                    onRerunComparison={handleRunComparison}
                    isLoading={isLoading}
                    activeDatasetName={activeDataset.name}
                    datasets={datasets}
                    selectedDatasetId={selectedDatasetId}
                    onSelectDatasetId={setSelectedDatasetId}
                    isBackendConnected={isBackendConnected}
                  />
                )}

                {activeTab === 'passes' && (
                  <PassList
                    passes={activeDataset.satellite_passes}
                    activeRun={activeRun}
                  />
                )}

                {activeTab === 'stations' && (
                  <GroundStationsView
                    stations={activeDataset.ground_stations}
                    activeRun={activeRun}
                  />
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default App;
