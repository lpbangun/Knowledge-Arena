import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
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

function NotFound() {
  return (
    <div className="max-w-lg mx-auto px-4 py-16 text-center">
      <h1 className="font-heading text-[56px] font-medium text-arena-muted mb-4">404</h1>
      <p className="text-arena-muted mb-6">This page doesn't exist.</p>
      <Link to="/" className="px-6 py-2.5 bg-arena-blue text-white rounded-lg font-semibold hover:opacity-90 transition">
        Back to Arena
      </Link>
    </div>
  );
}

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
          <Route path="*" element={<NotFound />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
