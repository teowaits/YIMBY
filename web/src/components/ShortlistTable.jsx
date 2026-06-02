import { useState } from "react";
import { C } from "../constants.js";

function ScoreBar({ label, value, color }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div style={{ marginBottom: 4 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 9,
          color: C.textMuted,
          marginBottom: 2,
        }}
      >
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div
        style={{
          height: 3,
          background: C.border2,
          borderRadius: 99,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 99,
          }}
        />
      </div>
    </div>
  );
}

export default function ShortlistTable({ doc }) {
  const [expanded, setExpanded] = useState(null);
  const rows = doc?.shortlist || [];
  const enrich = doc?.published_with_us;

  if (!rows.length) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: C.textMuted }}>
        No shortlist rows.
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 28px" }}>
      {enrich && (
        <div
          style={{
            fontSize: 11,
            color: C.textMuted,
            marginBottom: 16,
            padding: "10px 14px",
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
          }}
        >
          Published-with-us:{" "}
          <span style={{ color: C.blueLight }}>{enrich.target_journal_name}</span>
          {" · "}
          {enrich.year_from}–{enrich.year_to}
          {enrich.credits_used != null && ` · ${enrich.credits_used} enrich credits`}
        </div>
      )}

      <div
        className="shortlist-grid-header"
        style={{
          display: "grid",
          gridTemplateColumns: "32px 1.4fr 72px 72px 72px 1fr",
          gap: 10,
          padding: "8px 12px",
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: C.textMuted,
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <span>#</span>
        <span>Researcher</span>
        <span>Score</span>
        <span>In-scope</span>
        <span className="hide-mobile" title="OpenAlex FWCI may read ~15–20% higher than SciVal/Scopus">
          FWCI
        </span>
        <span className="hide-mobile">Breakdown</span>
      </div>

      {rows.map((row) => {
        const b = row.score_breakdown || {};
        const open = expanded === row.openalex_id;
        const pwu = row.published_with_us;
        return (
          <div key={row.openalex_id}>
            <div
              className="shortlist-grid-row"
              onClick={() =>
                setExpanded(open ? null : row.openalex_id)
              }
              style={{
                display: "grid",
                gridTemplateColumns: "32px 1.4fr 72px 72px 72px 1fr",
                gap: 10,
                padding: "12px",
                borderBottom: `1px solid ${C.border}`,
                cursor: "pointer",
                background: open ? C.surface2 : "transparent",
                animation: "fadeIn 0.25s ease",
              }}
            >
              <span style={{ color: C.blue, fontWeight: 700 }}>{row.rank}</span>
              <div>
                <div style={{ fontWeight: 600, color: C.textPrimary }}>
                  {row.display_name}
                </div>
                <div style={{ fontSize: 10, color: C.textMuted, marginTop: 2 }}>
                  {row.institution_name || "—"}
                </div>
                <div style={{ fontSize: 10, color: C.border2 }}>{row.openalex_id}</div>
              </div>
              <span
                style={{
                  fontVariantNumeric: "tabular-nums",
                  color: C.greenDark,
                  fontWeight: 600,
                }}
              >
                {(row.composite_score ?? 0).toFixed(3)}
              </span>
              <span style={{ fontVariantNumeric: "tabular-nums" }}>
                {row.in_scope_work_count ?? 0}
              </span>
              <span className="hide-mobile" style={{ fontVariantNumeric: "tabular-nums" }}>
                {row.mean_fwci != null ? row.mean_fwci.toFixed(1) : "—"}
              </span>
              <div className="hide-mobile" style={{ fontSize: 10 }}>
                <ScoreBar label="Rel" value={b.relevance} color={C.blue} />
                <ScoreBar label="Prod" value={b.productivity} color={C.amber} />
                <ScoreBar label="Imp" value={b.impact} color={C.green} />
              </div>
            </div>

            {open && (
              <div
                style={{
                  padding: "12px 16px 16px 44px",
                  background: C.surface,
                  borderBottom: `1px solid ${C.border}`,
                  fontSize: 11,
                  color: C.textSecondary,
                  lineHeight: 1.6,
                }}
              >
                {pwu && (
                  <div style={{ marginBottom: 10 }}>
                    <span
                      style={{
                        color: pwu.published ? C.greenDark : C.amber,
                        fontWeight: 600,
                      }}
                    >
                      {pwu.published ? "Published in target journal" : "Prospect"}
                    </span>
                    {pwu.latest_work && (
                      <div style={{ marginTop: 4, color: C.textMuted }}>
                        Latest: <em style={{ color: C.textPrimary }}>{pwu.latest_work.title}</em>
                        {pwu.latest_work.source_display_name &&
                          ` · ${pwu.latest_work.source_display_name}`}
                        {pwu.latest_work.publication_year &&
                          ` (${pwu.latest_work.publication_year})`}
                      </div>
                    )}
                  </div>
                )}
                {(row.in_scope_works || []).length > 0 && (
                  <div>
                    <div
                      style={{
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                        color: C.textMuted,
                        marginBottom: 6,
                      }}
                    >
                      In-scope works
                    </div>
                    <ul style={{ paddingLeft: 16, margin: 0 }}>
                      {row.in_scope_works.map((w) => (
                        <li key={w.openalex_id || w.title} style={{ marginBottom: 4 }}>
                          {w.publication_year} · {w.title}
                          {w.fwci != null && ` (FWCI ${w.fwci})`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div style={{ marginTop: 8 }}>
                  <a
                    href={`https://openalex.org/${row.openalex_id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: C.blue }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    Open in OpenAlex →
                  </a>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
