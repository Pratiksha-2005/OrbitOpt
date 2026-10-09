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
import { PassList } from './components/passes/PassList';
import { GroundStationsView } from './components/stations/GroundStationsView';
import { LoadingState } from './components/common/LoadingState';
import { ErrorAlert } from './components/common/ErrorAlert';

import './App.css';

export const App: React.FC = () => {
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
    MOCK_DATASETS[0].dataset_id
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
        for (const s of summaries.slice(0, 5)) {
          try {
            const full = await getDataset(s.dataset_id);
            fullDatasets.push(full);
          } catch {
            // Ignore individual fetch failure
          }
        }
        if (fullDatasets.length > 0) {
          setDatasets((prev) => {
            const existingIds = new Set(fullDatasets.map((d) => d.dataset_id));
            const remainingMocks = prev.filter((d) => !existingIds.has(d.dataset_id));
            return [...fullDatasets, ...remainingMocks];
          });
          setSelectedDatasetId(fullDatasets[0].dataset_id);
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
      // Auto-register scenario on backend
      const created = await createDataset({
        name: dataset.name,
        description: dataset.description,
        ground_stations: dataset.ground_stations,
        satellite_passes: dataset.satellite_passes,
      });
      return created.dataset_id;
    }
  };

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
        const oResult = await runOptimize(datasetId, timeLimitSeconds);
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

  return (
    <div className="min-h-screen bg-[#070a13] text-slate-100 flex flex-col font-sans">
      {/* Top Mission Control Header */}
      <Navbar
        health={health}
        isBackendConnected={isBackendConnected}
        isCheckingHealth={isCheckingHealth}
        onRefreshHealth={testHealthConnection}
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
  );
};

export default App;
