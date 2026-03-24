// Spec: TECH_STACK.md — Root component with WebSocket initialization
import { useWebSocket } from '@/hooks/useWebSocket';

export function App() {
  useWebSocket();

  return null;
}
