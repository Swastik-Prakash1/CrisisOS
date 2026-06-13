import React from 'react';
import useWebSocket from './hooks/useWebSocket';
import Header from './components/layout/Header';
import LeftPanel from './components/layout/LeftPanel';
import RightPanel from './components/layout/RightPanel';
import BottomBar from './components/layout/BottomBar';
import CrisisMap from './components/map/CrisisMap';
import { HumanOverride, JudgeReplay, AfterAction } from './components/overlays/Overlays';
import './styles/globals.css';
import './styles/map.css';

export default function App() {
  // Initialize WebSocket connection
  useWebSocket();

  return (
    <div className="app-layout">
      <Header />
      <div className="main-content">
        <LeftPanel />
        <CrisisMap />
        <RightPanel />
      </div>
      <BottomBar />

      {/* Overlays */}
      <HumanOverride />
      <JudgeReplay />
      <AfterAction />
    </div>
  );
}
