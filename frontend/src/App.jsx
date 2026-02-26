import React, { useState } from 'react';
import TechnicianView from './components/TechnicianView.jsx';
import ManagerView from './components/ManagerView.jsx';

export default function App() {
  const [activeView, setActiveView] = useState('technician');

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-brand">
          <span className="header-logo">⚙</span>
          <div>
            <h1>Cummins AI Diagnostic Agent</h1>
            <p>Multi-Agent Engine Fault Analysis System</p>
          </div>
        </div>
        <nav className="header-nav">
          <button
            className={activeView === 'technician' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setActiveView('technician')}
          >
            Technician
          </button>
          <button
            className={activeView === 'manager' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setActiveView('manager')}
          >
            Manager Review
          </button>
        </nav>
      </header>
      <main className="app-main">
        {activeView === 'technician' ? <TechnicianView /> : <ManagerView />}
      </main>
    </div>
  );
}
