import { useState } from "react";

// Civo Parcel Report — light, calm, Probe-inspired dashboard
// The stress test: can a 7-criterion scoring report feel minimal?

const C = {
  bg: "#fafaf7",
  surface: "#ffffff",
  surfaceAlt: "#f5f2ea",
  border: "#ececec",
  borderHover: "#d4d1c7",
  text: "#1a1a1a",
  textMid: "#6b6b6b",
  textDim: "#9b9b9b",
  textFaint: "#b8b8b8",
  accent: "#8b7355",
  accentSoft: "#f0ede5",
  good: "#4a7c4f",
  goodSoft: "#eaf2e7",
  warn: "#c08a3e",
  warnSoft: "#f7efe0",
  bad: "#a85a4a",
  badSoft: "#f5e8e4",
};

const FONT_DISPLAY = "'Fraunces', Georgia, serif";
const FONT_SANS = "'Inter', -apple-system, system-ui, sans-serif";

const parcel = {
  address: "50 Nagog Park",
  town: "Acton, Massachusetts 01720",
  acres: 11.2,
  parcelId: "M_224501_910",
  zone: "LI — Light Industrial",
  coords: "42.4856°N, 71.4328°W",
  total: 65,
  bucket: "Conditionally Suitable",
  projectType: "Battery Storage",
  config: "ma-eea-2026-v1",
};

const criteria = [
  { n: 1, name: "Grid alignment", weight: 20, score: 7, bucket: "ok", finding: "0.8 miles to the planned New North Acton Substation (Eversource ESMP #29, in-service 2033). Interconnection path is favorable." },
  { n: 2, name: "Climate resilience", weight: 15, score: 9, bucket: "ok", finding: "FEMA Zone X — outside the 500-year floodplain. No coastal or riverine exposure concerns." },
  { n: 3, name: "Carbon storage", weight: 15, score: 6, bucket: "caution", finding: "Forest canopy extends into the parcel along the eastern boundary. Development would reduce local sequestration capacity modestly." },
  { n: 4, name: "Biodiversity", weight: 20, score: 3, bucket: "bad", finding: "Nagog Brook BioMap Core Habitat intersects the northeast corner of the parcel. NHESP Priority Habitat for rare wildlife overlaps partially. This is the limiting constraint." },
  { n: 5, name: "Environmental burdens", weight: 10, score: 8, bucket: "ok", finding: "Lower quartile cumulative burden score. Not designated as an Environmental Justice community. No CIA requirement triggered." },
  { n: 6, name: "Environmental benefits", weight: 10, score: 6, bucket: "ok", finding: "Partially developed parcel with existing impervious surface. Brownfield credit applies to the built portion." },
  { n: 7, name: "Agricultural production", weight: 10, score: 8.5, bucket: "ok", finding: "Non-prime farmland soils. No Chapter 61A classification. No active agricultural use observed." },
];

const mitigation = [
  { tier: "Avoid", text: "Relocate the project footprint to the western two-thirds of the parcel to entirely avoid the Nagog Brook Core Habitat overlap." },
  { tier: "Minimize", text: "Reduce the total footprint to under 5 acres. Maintain a 100-foot buffer from the wetland resource edge. Preserve the existing forested corridor." },
  { tier: "Mitigate", text: "Contribute to an offsite habitat restoration fund. Estimated cost is approximately $50,000 per acre under SMART 3.0 benchmarks." },
];

const precedents = [
  { applicant: "GreenPoint Solar LLC", date: "November 2024", project: "3.2 MW ground-mount solar", decision: "Approved with conditions", conditions: "Stormwater management plan, 75ft wetland buffer, biannual monitoring" },
  { applicant: "Acton BESS Partners", date: "June 2024", project: "5 MW battery storage", decision: "Denied", conditions: "Insufficient setback from Nagog Brook; opposition from residents at public hearing" },
  { applicant: "Nagog Woods Ltd", date: "September 2023", project: "Commercial development", decision: "Approved with conditions", conditions: "Limit disturbance to 40% of parcel; retain perimeter vegetation" },
];

export default function CivoParcelReport() {
  const [expandedCriterion, setExpandedCriterion] = useState(4);

  return (
    <div style={{
      fontFamily: FONT_SANS,
      background: C.bg,
      color: C.text,
      minHeight: "100vh",
      fontFeatureSettings: "'ss01', 'cv11'",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600&display=swap" rel="stylesheet" />

      {/* Top app bar — quiet, just the essentials */}
      <div style={{
        padding: "22px 40px",
        borderBottom: `1px solid ${C.border}`,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        background: C.bg,
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
          <div style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 22,
            fontWeight: 500,
            letterSpacing: -0.5,
          }}>Civo</div>
          <div style={{ display: "flex", gap: 28, fontSize: 13, color: C.textMid }}>
            {["Dashboard", "Portfolio", "Towns", "Methodology"].map((l, i) => (
              <span key={i} style={{ cursor: "pointer", color: i === 1 ? C.text : C.textMid, fontWeight: i === 1 ? 500 : 400 }}>{l}</span>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button style={btnGhost()}>Export PDF</button>
          <button style={btnGhost()}>Save to portfolio</button>
          <button style={btnPrimary()}>New analysis</button>
        </div>
      </div>

      {/* Main content area */}
      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "40px 40px 80px" }}>

        {/* Breadcrumb */}
        <div style={{ fontSize: 13, color: C.textDim, marginBottom: 20, display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ cursor: "pointer" }}>Portfolio</span>
          <span>›</span>
          <span style={{ cursor: "pointer" }}>candidate-sites-april-2026</span>
          <span>›</span>
          <span style={{ color: C.text }}>50 Nagog Park</span>
        </div>

        {/* Header — address, metadata, then the score sits to the right */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: 48,
          alignItems: "flex-start",
          marginBottom: 56,
        }}>
          <div>
            <div style={{
              fontSize: 13,
              color: C.accent,
              fontFamily: FONT_DISPLAY,
              fontStyle: "italic",
              marginBottom: 12,
            }}>
              Suitability Report
            </div>
            <h1 style={{
              fontFamily: FONT_DISPLAY,
              fontSize: 54,
              fontWeight: 400,
              lineHeight: 1.05,
              letterSpacing: -1.5,
              color: C.text,
              margin: "0 0 12px",
            }}>
              {parcel.address}
            </h1>
            <div style={{ fontSize: 17, color: C.textMid, marginBottom: 28 }}>
              {parcel.town}
            </div>

            {/* Metadata rail — no boxes, just typography */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, auto)",
              gap: 40,
              paddingTop: 20,
              borderTop: `1px solid ${C.border}`,
            }}>
              {[
                { l: "Area", v: `${parcel.acres} acres` },
                { l: "Zoning", v: parcel.zone },
                { l: "Project type", v: parcel.projectType },
                { l: "Parcel ID", v: parcel.parcelId },
              ].map((m, i) => (
                <div key={i}>
                  <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4, letterSpacing: 0.3, textTransform: "uppercase", fontWeight: 500 }}>{m.l}</div>
                  <div style={{ fontSize: 14, color: C.text, fontWeight: 400 }}>{m.v}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Score card — large, serif, calm */}
          <div style={{
            background: C.surface,
            borderRadius: 20,
            padding: "36px 32px",
            border: `1px solid ${C.border}`,
          }}>
            <div style={{
              fontSize: 12,
              color: C.accent,
              fontFamily: FONT_DISPLAY,
              fontStyle: "italic",
              marginBottom: 8,
            }}>
              Total score
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 16 }}>
              <div style={{
                fontFamily: FONT_DISPLAY,
                fontSize: 96,
                fontWeight: 400,
                color: C.text,
                lineHeight: 0.9,
                letterSpacing: -4,
              }}>
                {parcel.total}
              </div>
              <div style={{ fontSize: 20, color: C.textDim, fontWeight: 300 }}>/ 100</div>
            </div>
            <div style={{
              display: "inline-block",
              padding: "8px 16px",
              background: C.warnSoft,
              borderRadius: 100,
              fontSize: 13,
              color: C.warn,
              fontWeight: 500,
              marginBottom: 20,
            }}>
              {parcel.bucket}
            </div>
            <p style={{
              fontSize: 14,
              color: C.textMid,
              lineHeight: 1.6,
              margin: 0,
              paddingTop: 20,
              borderTop: `1px solid ${C.border}`,
            }}>
              Biodiversity is the limiting criterion. Site is developable with significant mitigation conditions. See precedents below for similar outcomes in Acton.
            </p>
          </div>
        </div>

        {/* Map section — large and breathing */}
        <section style={{ marginBottom: 80 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
            <div>
              <div style={{ fontFamily: FONT_DISPLAY, fontSize: 13, color: C.accent, fontStyle: "italic", marginBottom: 6 }}>Site context</div>
              <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: 32, fontWeight: 400, letterSpacing: -0.8, color: C.text, margin: 0 }}>The parcel and its surroundings</h2>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {["Parcel", "Habitat", "Wetlands", "ESMP"].map((l, i) => (
                <span key={i} style={{
                  fontSize: 12,
                  color: C.textMid,
                  padding: "6px 12px",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 100,
                  cursor: "pointer",
                }}>{l}</span>
              ))}
            </div>
          </div>

          <div style={{
            background: C.surface,
            borderRadius: 16,
            overflow: "hidden",
            border: `1px solid ${C.border}`,
            height: 440,
            position: "relative",
          }}>
            <svg viewBox="0 0 1100 440" style={{ width: "100%", height: "100%", display: "block" }} preserveAspectRatio="xMidYMid slice">
              <defs>
                <pattern id="forest-light" patternUnits="userSpaceOnUse" width="8" height="8">
                  <rect width="8" height="8" fill="#e8ecdf" />
                  <circle cx="3" cy="3" r="1.2" fill="#c8d2b5" />
                  <circle cx="6" cy="6" r="1" fill="#c8d2b5" />
                </pattern>
                <pattern id="wetland-light" patternUnits="userSpaceOnUse" width="12" height="12">
                  <rect width="12" height="12" fill="#e1ecef" />
                  <path d="M 0 6 Q 3 4 6 6 T 12 6" stroke="#a5c4cc" strokeWidth="0.8" fill="none" />
                </pattern>
                <pattern id="pave-light" patternUnits="userSpaceOnUse" width="14" height="14">
                  <rect width="14" height="14" fill="#ddd8d0" />
                  <line x1="0" y1="7" x2="14" y2="7" stroke="#c8c2b5" strokeWidth="0.6" />
                </pattern>
                <pattern id="roof-light" patternUnits="userSpaceOnUse" width="10" height="10">
                  <rect width="10" height="10" fill="#cac4b8" />
                  <line x1="0" y1="0" x2="10" y2="10" stroke="#b5afa2" strokeWidth="0.4" />
                </pattern>
              </defs>

              {/* Base forest */}
              <rect width="1100" height="440" fill="url(#forest-light)" />

              {/* Wetland corridor through NE */}
              <path d="M 1100 50 Q 900 120 720 190 Q 540 260 380 340 L 1100 440 Z" fill="url(#wetland-light)" />

              {/* Road from west */}
              <path d="M 0 260 L 250 255 L 350 270 L 450 280" fill="none" stroke="#c0b8a8" strokeWidth="18" strokeLinecap="round" />

              {/* Parking lot */}
              <polygon points="250,300 250,380 580,380 580,300" fill="url(#pave-light)" />

              {/* Main building */}
              <polygon points="270,200 270,300 580,300 580,200" fill="url(#roof-light)" stroke="#a8a29a" strokeWidth="1.5" />

              {/* Building shadow */}
              <polygon points="580,200 595,215 595,315 580,300" fill="#00000008" />
              <polygon points="270,300 285,315 595,315 580,300" fill="#00000008" />

              {/* BioMap Core overlay */}
              <path d="M 1120 20 Q 920 100 740 170 Q 560 240 400 320 L 1120 460 Z" fill="#a85a4a" fillOpacity="0.08" stroke="#a85a4a" strokeWidth="2" />
              <text x="820" y="150" fontSize="11" fill="#a85a4a" fontFamily={FONT_SANS} fontWeight="500" letterSpacing="0.5">BIOMAP CORE HABITAT</text>

              {/* Wetland overlay */}
              <path d="M 1100 50 Q 900 120 720 190 Q 540 260 380 340 L 1100 440 Z" fill="none" stroke="#5a8a99" strokeWidth="1.5" strokeDasharray="4 3" />

              {/* Parcel boundary — warm accent color */}
              <polygon points="120,155 680,150 705,385 115,395" fill="none" stroke="#8b7355" strokeWidth="2.5" strokeDasharray="10 5" />
              <text x="120" y="140" fontSize="12" fill="#8b7355" fontFamily={FONT_SANS} fontWeight="600" letterSpacing="0.3">50 NAGOG PARK · 11.2 ACRES</text>

              {/* ESMP pin */}
              <g transform="translate(920,370)">
                <circle r="16" fill="#8b7355" fillOpacity="0.15" />
                <circle r="6" fill="#8b7355" />
                <text x="20" y="2" fontSize="11" fill="#8b7355" fontFamily={FONT_SANS} fontWeight="500">ESMP #29 · N. Acton Sub</text>
                <text x="20" y="16" fontSize="10" fill="#a08b6c" fontFamily={FONT_SANS}>Planned · ISD 2033</text>
              </g>

              {/* Scale bar */}
              <g transform="translate(40, 410)">
                <line x1="0" y1="0" x2="100" y2="0" stroke="#6b6b6b" strokeWidth="1.5" />
                <line x1="0" y1="-5" x2="0" y2="5" stroke="#6b6b6b" strokeWidth="1.5" />
                <line x1="100" y1="-5" x2="100" y2="5" stroke="#6b6b6b" strokeWidth="1.5" />
                <text x="50" y="-10" fontSize="11" fill="#6b6b6b" fontFamily={FONT_SANS} textAnchor="middle">200 ft</text>
              </g>

              {/* North */}
              <g transform="translate(1030, 50)">
                <circle r="18" fill="#ffffff" stroke="#d4d1c7" strokeWidth="1" />
                <polygon points="0,-10 4,6 0,3 -4,6" fill="#1a1a1a" />
                <text y="26" fontSize="10" fill="#6b6b6b" textAnchor="middle" fontFamily={FONT_SANS} fontWeight="500">N</text>
              </g>
            </svg>
          </div>
        </section>

        {/* Criteria breakdown — the big one */}
        <section style={{ marginBottom: 80 }}>
          <div style={{ marginBottom: 32 }}>
            <div style={{ fontFamily: FONT_DISPLAY, fontSize: 13, color: C.accent, fontStyle: "italic", marginBottom: 6 }}>How the score breaks down</div>
            <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: 32, fontWeight: 400, letterSpacing: -0.8, color: C.text, margin: "0 0 12px" }}>Seven criteria, weighted.</h2>
            <p style={{ fontSize: 15, color: C.textMid, lineHeight: 1.6, margin: 0, maxWidth: 680 }}>
              Each criterion is evaluated against the 2024 Climate Act methodology codified in 225 CMR 29.00. Click any row to see the full finding and cited sources.
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 1, background: C.border, borderRadius: 16, overflow: "hidden", border: `1px solid ${C.border}` }}>
            {criteria.map((c) => {
              const isExpanded = expandedCriterion === c.n;
              const statusColor = c.bucket === "ok" ? C.good : c.bucket === "caution" ? C.warn : C.bad;
              return (
                <div
                  key={c.n}
                  onClick={() => setExpandedCriterion(isExpanded ? null : c.n)}
                  style={{
                    background: C.surface,
                    padding: "24px 32px",
                    cursor: "pointer",
                    transition: "background 0.15s",
                  }}
                >
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "40px 1fr 200px 60px 40px",
                    gap: 24,
                    alignItems: "center",
                  }}>
                    <div style={{ fontSize: 13, color: C.textDim, fontFamily: FONT_DISPLAY, fontStyle: "italic" }}>
                      0{c.n}
                    </div>
                    <div>
                      <div style={{ fontSize: 17, color: C.text, fontWeight: 500, fontFamily: FONT_DISPLAY }}>{c.name}</div>
                      <div style={{ fontSize: 12, color: C.textDim, marginTop: 4 }}>Weight {c.weight}%</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{ flex: 1, height: 4, background: C.border, borderRadius: 2, overflow: "hidden" }}>
                        <div style={{
                          width: `${c.score * 10}%`,
                          height: "100%",
                          background: statusColor,
                          borderRadius: 2,
                        }} />
                      </div>
                      <div style={{ fontSize: 13, color: C.textMid, minWidth: 30, textAlign: "right" }}>{c.score}/10</div>
                    </div>
                    <div style={{
                      fontSize: 11,
                      color: statusColor,
                      fontWeight: 500,
                      padding: "4px 10px",
                      background: c.bucket === "ok" ? C.goodSoft : c.bucket === "caution" ? C.warnSoft : C.badSoft,
                      borderRadius: 100,
                      textAlign: "center",
                    }}>
                      {c.bucket === "ok" ? "OK" : c.bucket === "caution" ? "Caution" : "Risk"}
                    </div>
                    <div style={{ fontSize: 14, color: C.textDim, textAlign: "right", transform: isExpanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>
                      ⌄
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{
                      marginTop: 20,
                      paddingTop: 20,
                      borderTop: `1px solid ${C.border}`,
                      display: "grid",
                      gridTemplateColumns: "40px 1fr",
                      gap: 24,
                    }}>
                      <div />
                      <div>
                        <div style={{ fontSize: 11, color: C.textDim, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10, fontWeight: 500 }}>Finding</div>
                        <p style={{ fontSize: 15, color: C.text, lineHeight: 1.65, margin: "0 0 20px" }}>{c.finding}</p>
                        <div style={{ fontSize: 11, color: C.textDim, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10, fontWeight: 500 }}>Sources</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                          {["MassGIS BioMap", "NHESP Priority", "225 CMR 29.04"].map((s, i) => (
                            <a key={i} style={{
                              fontSize: 12,
                              color: C.accent,
                              padding: "4px 12px",
                              background: C.accentSoft,
                              borderRadius: 100,
                              textDecoration: "none",
                              cursor: "pointer",
                            }}>{s} ↗</a>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Two-column: Mitigation and Precedents */}
        <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40, marginBottom: 80 }}>

          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontFamily: FONT_DISPLAY, fontSize: 13, color: C.accent, fontStyle: "italic", marginBottom: 6 }}>What you can do about it</div>
              <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: 28, fontWeight: 400, letterSpacing: -0.6, color: C.text, margin: 0 }}>Mitigation hierarchy</h2>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {mitigation.map((m, i) => (
                <div key={i} style={{
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 14,
                  padding: "20px 24px",
                }}>
                  <div style={{
                    fontSize: 12,
                    color: C.accent,
                    fontFamily: FONT_DISPLAY,
                    fontStyle: "italic",
                    marginBottom: 8,
                  }}>
                    {String(i + 1).padStart(2, "0")} · {m.tier}
                  </div>
                  <p style={{ fontSize: 14, color: C.textMid, lineHeight: 1.6, margin: 0 }}>{m.text}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontFamily: FONT_DISPLAY, fontSize: 13, color: C.accent, fontStyle: "italic", marginBottom: 6 }}>What Acton has decided before</div>
              <h2 style={{ fontFamily: FONT_DISPLAY, fontSize: 28, fontWeight: 400, letterSpacing: -0.6, color: C.text, margin: 0 }}>Relevant precedents</h2>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {precedents.map((p, i) => {
                const denied = p.decision === "Denied";
                return (
                  <div key={i} style={{
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    borderRadius: 14,
                    padding: "20px 24px",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8, gap: 12 }}>
                      <div>
                        <div style={{ fontSize: 15, color: C.text, fontWeight: 500, fontFamily: FONT_DISPLAY }}>{p.applicant}</div>
                        <div style={{ fontSize: 12, color: C.textDim, marginTop: 3 }}>{p.date} · {p.project}</div>
                      </div>
                      <div style={{
                        fontSize: 11,
                        color: denied ? C.bad : C.good,
                        background: denied ? C.badSoft : C.goodSoft,
                        padding: "4px 12px",
                        borderRadius: 100,
                        fontWeight: 500,
                        whiteSpace: "nowrap",
                      }}>
                        {p.decision}
                      </div>
                    </div>
                    <p style={{ fontSize: 13, color: C.textMid, lineHeight: 1.55, margin: 0 }}>{p.conditions}</p>
                  </div>
                );
              })}
            </div>

            <a style={{
              display: "inline-block",
              marginTop: 16,
              fontSize: 13,
              color: C.accent,
              cursor: "pointer",
              fontWeight: 500,
            }}>View Acton town profile →</a>
          </div>
        </section>

        {/* Footer provenance — whisper quiet, but visible */}
        <div style={{
          paddingTop: 32,
          borderTop: `1px solid ${C.border}`,
          display: "flex",
          justifyContent: "space-between",
          fontSize: 12,
          color: C.textDim,
          flexWrap: "wrap",
          gap: 16,
        }}>
          <div>Scored on April 14, 2026 · Configuration {parcel.config}</div>
          <div>Data sources: MassGIS · NHESP · FEMA NFHL · Eversource ESMP DPU 24-10</div>
          <div>All scoring traceable to 225 CMR 29.00</div>
        </div>
      </div>
    </div>
  );
}

function btnPrimary() {
  return {
    background: "#1a1a1a",
    color: "#fafaf7",
    border: "none",
    borderRadius: 100,
    padding: "10px 20px",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    fontFamily: FONT_SANS,
  };
}
function btnGhost() {
  return {
    background: "transparent",
    color: "#6b6b6b",
    border: "1px solid #ececec",
    borderRadius: 100,
    padding: "10px 18px",
    fontSize: 13,
    fontWeight: 400,
    cursor: "pointer",
    fontFamily: FONT_SANS,
  };
}
