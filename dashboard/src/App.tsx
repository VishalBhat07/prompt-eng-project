import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Shell from './components/Shell';
import Home from './pages/Home';
import Sessions from './pages/Sessions';
import GraphExplorer from './pages/GraphExplorer';
import Findings from './pages/Findings';
import Approvals from './pages/Approvals';
import Benchmark from './pages/Benchmark';
import Demo from './pages/Demo';

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/sessions', element: <Sessions /> },
      { path: '/graph', element: <GraphExplorer /> },
      { path: '/findings', element: <Findings /> },
      { path: '/approvals', element: <Approvals /> },
      { path: '/benchmark', element: <Benchmark /> },
      { path: '/demo', element: <Demo /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
