import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import AgentsPage from './pages/Agents';
import WorkflowsPage from './pages/Workflows';
import MonitorPage from './pages/Monitor';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <aside className="sidebar">
          <h1>Yuno Agents</h1>
          <nav>
            <NavLink to="/" end>Agents</NavLink>
            <NavLink to="/workflows">Workflows</NavLink>
            <NavLink to="/monitor">Monitor</NavLink>
          </nav>
        </aside>
        <main className="main">
          <Routes>
            <Route path="/" element={<AgentsPage />} />
            <Route path="/workflows" element={<WorkflowsPage />} />
            <Route path="/monitor" element={<MonitorPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
