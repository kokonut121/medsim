export function SectionHeader({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div>
      <div className="eyebrow">{eyebrow}</div>
      <h2 style={{ margin: "8px 0 12px" }}>{title}</h2>
      <p className="muted" style={{ maxWidth: 780 }}>
        {body}
      </p>
    </div>
  );
}

