export default function Stub({ name }: { name: string }) {
  return (
    <div>
      <h1>{name}</h1>
      <p style={{ color: 'var(--muted)' }}>
        Designed in pass 2. This route is reserved in the nav and router already.
      </p>
    </div>
  );
}
