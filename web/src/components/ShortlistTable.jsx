import { useState } from "react";
import { C } from "../constants.js";
import InfoTooltip from "./InfoTooltip.jsx";

const TOOLTIPS = {
  score:
    "Composite score (0–1), normalised within this candidate pool.\nWeighted sum: Relevance 35% · Productivity 20% · Impact 25% · Network Centrality 15%.\nScores are relative to this pool, not absolute across runs.",
  inScope:
    "Count of works in the scoring window whose primary OpenAlex topic matches the journal scope vector.\nHigh count = broad output in field — not a quality signal.\nExpand the card and click work titles to verify topical fit.",
  fwci:
    "Field-Weighted Citation Impact — mean across in-scope works only.\n1.0 = field average · >1.0 = above average.\n⚠ OpenAlex FWCI reads ~15–20% higher than SciVal/Scopus.\nCompare values within this list only.",
  breakdown:
    "Rel = topic overlap with scope vector (fraction of recent works matching).\nProd = in-scope work count, recency-decayed (recent papers weighted more).\nImp = normalised mean FWCI across in-scope works.\nBars show normalised values within this pool; % = per-author score.",
  rel: "Fraction of recent works matching the scope topic set.\n100% = all recent works match.",
  prod: "In-scope work count, recency-decayed.\nRecent papers count more than older ones (half-life ~3 yrs).",
  imp: "Normalised mean FWCI across in-scope works.\nFew highly-cited works can outscore many average-impact ones.",
};

function HeaderCell({ children, tooltip }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 0 }}>
      {children}
      {tooltip ? <InfoTooltip text={tooltip} /> : null}
    </span>
  );
}

const workLinkBase = {
  color: C.blue,
  textDecoration: "none",
  // TODO: replace with design-token rgba when --accent-rgb exists
  borderBottom: "1px solid rgba(99, 179, 237, 0.3)",
  transition: "border-color 0.15s",
};

const workLinkHover = {
  borderBottomColor: C.blue,
};

function WorkLink({ work }) {
  const href = work.doi
    ? `https://doi.org/${work.doi}`
    : work.openalex_id
      ? `https://openalex.org/${work.openalex_id}`
      : null;

  if (!href) return <span>{work.title}</span>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={workLinkBase}
      onMouseEnter={(e) => Object.assign(e.currentTarget.style, workLinkHover)}
      onMouseLeave={(e) => Object.assign(e.currentTarget.style, workLinkBase)}
      onClick={(e) => e.stopPropagation()}
    >
      {work.title}
    </a>
  );
}

const wileyPillStyle = {
  display: "inline-block",
  marginTop: 4,
  fontSize: "0.68rem",
  color: C.greenDark,
  background: "rgba(104, 211, 145, 0.12)",
  border: "1px solid rgba(104, 211, 145, 0.3)",
  borderRadius: 4,
  padding: "1px 6px",
  whiteSpace: "nowrap",
};

function WileyPill({ count, journal }) {
  if (!count || count <= 0) return null;
  const label = count === 1 ? "work" : "works";
  const journalPart = journal ? ` · ${journal}` : "";
  return (
    <span style={wileyPillStyle} title="Wiley AI/Comp portfolio">
      AI/Comp · {count} {label}
      {journalPart}
    </span>
  );
}

function ScoreBar({ label, value, color, tooltip }) {
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
        <span style={{ display: "inline-flex", alignItems: "center" }}>
          {label}
          {tooltip ? <InfoTooltip text={tooltip} /> : null}
        </span>
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
  const yearWindow = doc?.publication_year_window;
  const wileyWindowLabel =
    yearWindow?.from != null && yearWindow?.to != null
      ? `${yearWindow.from}–${yearWindow.to}`
      : null;

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
        <HeaderCell tooltip={TOOLTIPS.score}>Score</HeaderCell>
        <HeaderCell tooltip={TOOLTIPS.inScope}>In-scope</HeaderCell>
        <span className="hide-mobile">
          <HeaderCell tooltip={TOOLTIPS.fwci}>FWCI</HeaderCell>
        </span>
        <span className="hide-mobile">
          <HeaderCell tooltip={TOOLTIPS.breakdown}>Breakdown</HeaderCell>
        </span>
      </div>

      {rows.map((row) => {
        const b = row.score_breakdown || {};
        const open = expanded === row.openalex_id;
        const pwu = row.published_with_us;
        return (
          <div key={row.openalex_id}>
            <div
              className="shortlist-grid-row"
              onClick={() => setExpanded(open ? null : row.openalex_id)}
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
                <WileyPill count={row.wiley_count} journal={row.wiley_journal} />
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
                <ScoreBar label="Rel" value={b.relevance} color={C.blue} tooltip={TOOLTIPS.rel} />
                <ScoreBar label="Prod" value={b.productivity} color={C.amber} tooltip={TOOLTIPS.prod} />
                <ScoreBar label="Imp" value={b.impact} color={C.green} tooltip={TOOLTIPS.imp} />
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
                        Latest: <WorkLink work={pwu.latest_work} />
                        {pwu.latest_work.source_display_name && (
                          <span style={{ fontStyle: "italic" }}>
                            {" "}
                            · {pwu.latest_work.source_display_name}
                          </span>
                        )}
                        {pwu.latest_work.publication_year &&
                          ` (${pwu.latest_work.publication_year})`}
                      </div>
                    )}
                  </div>
                )}
                {(row.wiley_count ?? 0) > 0 ? (
                  <div style={{ marginTop: 6, fontSize: "0.75rem", color: C.textMuted }}>
                    Wiley AI/Comp portfolio
                    {wileyWindowLabel ? ` (${wileyWindowLabel})` : ""}:
                    <span style={{ color: C.textPrimary, marginLeft: 4 }}>
                      {row.wiley_count} {row.wiley_count === 1 ? "work" : "works"}
                      {row.wiley_journal
                        ? ` in ${row.wiley_journal}`
                        : row.wiley_friendly
                          ? " in Wiley AI/Comp portfolio"
                          : ""}
                    </span>
                  </div>
                ) : (
                  <div style={{ marginTop: 6, fontSize: "0.75rem", color: C.textMuted }}>
                    No Wiley AI/Comp portfolio publications in window
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
                          {w.publication_year}
                          {" · "}
                          <WorkLink work={w} />
                          {w.source_display_name && (
                            <span style={{ color: C.textMuted, fontStyle: "italic" }}>
                              {" · "}
                              {w.source_display_name}
                            </span>
                          )}
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
