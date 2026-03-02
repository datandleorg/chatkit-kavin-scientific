import { ThemeProvider } from './context/ThemeContext';
import ChatLayout from './components/ChatLayout';

export default function App() {
  return (
    <ThemeProvider>
      <ChatLayout />
    </ThemeProvider>
  );
}
