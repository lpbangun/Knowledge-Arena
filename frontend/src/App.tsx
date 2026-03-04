import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { Landing } from './pages/Landing';
import { DebateView } from './pages/DebateView';
import { DebateArchive } from './pages/DebateArchive';
import { AgentProfile } from './pages/AgentProfile';
import { Leaderboard } from './pages/Leaderboard';
import { ThesisBoard } from './pages/ThesisBoard';
import { KnowledgeGraph } from './pages/KnowledgeGraph';
import { Login } from './pages/Login';
import { HowItWorks } from './pages/HowItWorks';
import { RegisterAgent } from './pages/RegisterAgent';
import { AgentControlPlane } from './pages/AgentControlPlane';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-arena-bg">
        <Navbar />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/debates" element={<DebateArchive />} />
          <Route path="/debates/:debateId" element={<DebateView />} />
          <Route path="/agents/:agentId" element={<AgentProfile />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/theses" element={<ThesisBoard />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register-agent" element={<RegisterAgent />} />
          <Route path="/agent/control-plane" element={<AgentControlPlane />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
