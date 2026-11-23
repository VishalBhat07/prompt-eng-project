import { Link } from 'react-router-dom';

export default function Benchmark() {
  return <section style={{ padding: '56px 0 28px' }}>
    <h1>Benchmark</h1>
    <p>No benchmark results to display.</p>
    <Link to="/sessions">Open sessions to compare a task run</Link>
  </section>;
}
