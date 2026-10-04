import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Shell from './components/Shell';
import Home from './pages/Home';
import Stub from './pages/Stub';

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/sessions', element: <Stub name="Sessions" /> },
      { path: '/graph', element: <Stub name="Graph explorer" /> },
      { path: '/findings', element: <Stub name="Findings" /> },
      { path: '/approvals', element: <Stub name="Approval queue" /> },
      { path: '/benchmark', element: <Stub name="Benchmark" /> },
      { path: '/demo', element: <Stub name="Demo runner" /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
