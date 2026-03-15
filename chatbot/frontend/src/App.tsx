import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import ChatLayout from './components/ChatLayout';
import Dashboard from './pages/Dashboard';
import KnowledgeBasePage from './pages/KnowledgeBasePage';

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ChatLayout />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
          <Route path="/knowledge-base/:kbId" element={<KnowledgeBasePage />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
