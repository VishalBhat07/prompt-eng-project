import { useEffect, useState } from 'react';
import './Benchmark.css';

const reportUrl = `${import.meta.env.BASE_URL}data/session-benchmark-v3.json`;
const methods = [
  ['single_output', 'Single-output detector', 'Checks each output preview on its own.'],
  ['session_rule', 'Session rule', 'Checks previews and alerts when restricted output precedes an external-transfer proposal.'],
  ['graph_without_dependencies', 'Graph without dependency links', 'Runs CrossToolGuard after removing recorded parent links.'],
  ['cross_tool_guard', 'CrossToolGuard', 'Uses output signals and recorded dependency paths to assess the session.'],
] as const;

type Method = typeof methods[number][0];
type Rate = { numerator: number; denominator: number; value: number };
type Metrics = {
  recall: Rate; false_alerts: Rate; signals_found?: Rate; false_signals?: Rate;
  paths_found?: Rate; false_paths?: Rate; verdict_agreement?: Rate;
};
type Outcome = {
  alert: boolean; signal?: boolean; path?: boolean; verdict?: string;
  findings?: Array<{ pattern: string; tool_sequence: string[] }>;
};
type BenchmarkCase = {
  id: string; group: string; example?: string;
  expected: { title: string; alert: boolean | null; signal: boolean; path: boolean | null; verdict: string | null };
  methods: Record<Method, Outcome>;
  events: Array<{
    event_id: string; event_type: string; server: string; tool: string; data_class: string;
    capabilities: string[]; output_preview: string; parent_id: string | null;
  }>;
};
type Report = {
  schema_version: number; label_review: string;
  counts: { total: number; groups: number; standalone: number; pairs: number; positive: number; negative: number; unclear: number };
  summary: Record<Method, Metrics>; cases: BenchmarkCase[];
  pair_alert_agreement: Record<Method, Pick<Rate, 'numerator' | 'denominator'>>;
  references: Record<string, string>;
};

function RateCell({ rate, adverse = false }: { rate: Rate; adverse?: boolean }) {
  const percent = rate.value * 100;
  return <div className="benchmark-rate">
    <div><strong>{Number(percent.toFixed(1))}%</strong> <span className="benchmark-muted">({rate.numerator}/{rate.denominator})</span></div>
    <div className="benchmark-bar" aria-hidden="true">
      <span className={adverse ? 'benchmark-bar-adverse' : undefined} style={{ width: `${percent}%` }} />
    </div>
  </div>;
}

function CaseDetails({ row }: { row: BenchmarkCase }) {
  return <details className="card benchmark-case">
    <summary><strong>{row.expected.title}</strong><span>{row.example}</span></summary>
    <div className="benchmark-case-body">
    <p>Expected alert {row.expected.alert === null ? 'uncertain' : row.expected.alert ? 'yes' : 'no'}
      {' · '}Output signal {row.expected.signal ? 'yes' : 'no'}
      {' · '}Risk path {row.expected.path === null ? 'uncertain' : row.expected.path ? 'yes' : 'no'}
      {' · '}Policy {row.expected.verdict ?? 'unscored'}</p>
    <ol className="benchmark-flow">
      {row.events.map((event) => {
        const parent = row.events.findIndex((candidate) => candidate.event_id === event.parent_id);
        const isOutput = event.event_type === 'TOOL_OUTPUT';
        return <li key={event.event_id}>
          <strong>{isOutput ? 'Output' : 'Proposed call'} · {event.server}/{event.tool}</strong>
          <p className="benchmark-muted">
            {isOutput ? event.data_class : event.capabilities.join(', ') || 'No declared capability'}
            {parent >= 0 && ` · References step ${parent + 1}`}
          </p>
          {event.output_preview && <p>{event.output_preview}</p>}
        </li>;
      })}
    </ol>
    <ul className="benchmark-outcomes">
      {methods.map(([id, label]) => {
        const outcome = row.methods[id];
        return <li key={id}>
          <strong>{label}</strong>
          <span>{outcome.alert ? 'Alert' : 'No alert'}
            {outcome.path !== undefined && (outcome.path ? ' · Risk path found' : ' · No risk path')}
            {outcome.verdict && ` · ${outcome.verdict}`}</span>
          {outcome.findings?.map((finding, index) => <small key={`${finding.pattern}-${index}`}>
            {finding.pattern.replace(/_/g, ' ')} · {finding.tool_sequence.join(' → ')}
          </small>)}
        </li>;
      })}
    </ul>
    </div>
  </details>;
}

export default function Benchmark() {
  const [report, setReport] = useState<Report | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(reportUrl, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('Benchmark report unavailable');
        const data: Report = await response.json();
        if (data.schema_version !== 2 || !Array.isArray(data.cases) || !data.pair_alert_agreement) throw new Error('Unsupported benchmark report');
        setReport(data);
      })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, []);

  return <section className="benchmark-page">
    <header className="benchmark-heading">
      <div><h1>Benchmark</h1><p className="sub">Compare four methods on the same recorded tool events.</p></div>
      {report && <a href={reportUrl} download>Download results JSON</a>}
    </header>
    {!report && <p role="status">{failed ? 'Benchmark results could not be loaded.' : 'Loading benchmark results…'}</p>}
    {report && <>
      <div className="card benchmark-scope">
        <strong>{report.counts.total} synthetic replay cases</strong>
        <p>{report.counts.standalone} standalone cases and {report.counts.pairs} matched pairs across {report.counts.groups} behavior groups.</p>
        <p className="benchmark-muted">{report.counts.positive} expected alerts · {report.counts.negative} controls · {report.counts.unclear} cases with insufficient evidence for alert, path, or policy scoring.</p>
      </div>
      <section className="benchmark-section" aria-labelledby="benchmark-alerts">
        <h2 id="benchmark-alerts">Alert comparison</h2>
        <p className="benchmark-muted">Each bar shows a percentage of its column’s cases. Higher detection and fewer false alerts are better.</p>
        <div className="card benchmark-table" role="region" aria-label="Alert comparison results" tabIndex={0}>
          <table>
            <thead><tr><th scope="col">Method</th><th scope="col">Expected alerts found</th><th scope="col">Controls falsely flagged</th><th scope="col">Both variants correct</th></tr></thead>
            <tbody>{methods.map(([id, label, description]) => <tr key={id}>
              <th scope="row">{label}<small>{description}</small></th>
              <td><RateCell rate={report.summary[id].recall} /></td>
              <td><RateCell rate={report.summary[id].false_alerts} adverse /></td>
              <td>{report.pair_alert_agreement[id].numerator}/{report.pair_alert_agreement[id].denominator}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="benchmark-muted">A matched pair shares an initial event sequence and varies the evidence or final proposal. Both variants must have a correct alert result to count.</p>
      </section>
      <section className="benchmark-section" aria-labelledby="benchmark-paths">
        <h2 id="benchmark-paths">Graph paths and policy</h2>
        <p className="benchmark-muted">This replay scores the policy decision from recorded events. It runs offline without an agent or MCP server.</p>
        <div className="card benchmark-table" role="region" aria-label="Graph path and policy results" tabIndex={0}>
          <table>
            <thead><tr><th scope="col">Graph method</th><th scope="col">Expected paths found</th><th scope="col">False paths</th><th scope="col">Policy agreement</th></tr></thead>
            <tbody>{methods.slice(2).map(([id, label]) => {
              const result = report.summary[id];
              return <tr key={id}>
                <th scope="row">{label}</th>
                {[result.paths_found, result.false_paths, result.verdict_agreement].map((rate, index) =>
                  <td key={index}>{rate ? <RateCell rate={rate} adverse={index === 1} /> : 'Unavailable'}</td>)}
              </tr>;
            })}</tbody>
          </table>
        </div>
        <p className="benchmark-muted">The labels are authored with the scenario definitions. {report.label_review}. These results describe this replay set and its recorded dependencies.</p>
      </section>
      <section className="benchmark-section" aria-labelledby="benchmark-cases">
        <h2 id="benchmark-cases">What the comparison shows</h2>
        <p className="benchmark-muted">Open an example to see the numbered tool events and each detector’s result.</p>
        {report.cases.filter((row) => row.example).map((row) => <CaseDetails row={row} key={row.id} />)}
      </section>
      <section className="benchmark-section" aria-labelledby="benchmark-references">
        <h2 id="benchmark-references">Research and test data</h2>
        <p className="benchmark-muted">These public projects informed the case designs. Dashboard scores use local synthetic replays.</p>
        <ul className="benchmark-references">
          {Object.entries(report.references).map(([label, url]) => <li key={label}><a href={url}>{label}</a></li>)}
        </ul>
      </section>
    </>}
  </section>;
}
