import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import type { Bucket } from '../lib/api';

// ── Types ──────────────────────────────────────────────────────────────────────

type ProjectType = 'solar' | 'bess' | 'wind' | 'generic';
type SiteStatus = 'pending' | 'scoring' | 'done' | 'error';

interface Site {
  id: string;
  address: string;
  note: string;
  addedAt: string;
  status: SiteStatus;
  score?: number;
  bucket?: Bucket;
  reportId?: number | string;
  errorMsg?: string;
}

interface Folder {
  id: string;
  name: string;
  projectType: ProjectType;
  createdAt: string;
  sites: Site[];
}

// ── localStorage ───────────────────────────────────────────────────────────────

const STORE_KEY = 'civo.portfolio.v1';

function loadFolders(): Folder[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveFolders(folders: Folder[]): void {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(folders));
  } catch { /* ignore */ }
}

function uid(): string {
  return Math.random().toString(36).slice(2, 9) + Date.now().toString(36);
}

// ── Constants ──────────────────────────────────────────────────────────────────

const PT_LABELS: Record<ProjectType, string> = {
  solar: 'Solar',
  bess: 'BESS',
  wind: 'Wind',
  generic: 'Generic',
};

const PT_API: Record<ProjectType, string> = {
  solar: 'solar_ground_mount',
  bess: 'bess_standalone',
  wind: 'generic',
  generic: 'generic',
};

const BUCKET_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  'SUITABLE':               { color: '#2d4a26', bg: '#dfeeda', label: 'Suitable' },
  'CONDITIONALLY SUITABLE': { color: '#7a5520', bg: '#f5e8d4', label: 'Conditional' },
  'CONSTRAINED':            { color: '#7a2a22', bg: '#f5e2e0', label: 'Constrained' },
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function ScoreChip({ score, bucket }: { score: number; bucket: Bucket }) {
  const s = BUCKET_STYLE[bucket] ?? { color: 'var(--text-mid)', bg: 'var(--border-soft)', label: bucket };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 999,
      background: s.bg, color: s.color,
      fontSize: 11.5, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      <span style={{ fontFamily: "'Fraunces', Georgia, serif", fontWeight: 500, fontSize: 13 }}>{score}</span>
      <span style={{ opacity: 0.7 }}>·</span>
      {s.label}
    </span>
  );
}

function Spinner() {
  return (
    <span style={{
      display: 'inline-block', width: 13, height: 13,
      border: '2px solid var(--border-soft)',
      borderTopColor: 'var(--accent)',
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
      flexShrink: 0,
    }} />
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Portfolio() {
  const [folders, setFolders] = useState<Folder[]>(loadFolders);
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    const loaded = loadFolders();
    return loaded.length > 0 ? loaded[0].id : null;
  });

  // Persist on every change
  useEffect(() => { saveFolders(folders); }, [folders]);

  // Auto-select first folder when created
  const selectedFolder = folders.find(f => f.id === selectedId) ?? null;

  // ── Folder actions ──

  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderPt, setNewFolderPt] = useState<ProjectType>('solar');
  const [creatingFolder, setCreatingFolder] = useState(false);
  const newFolderRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (creatingFolder) newFolderRef.current?.focus();
  }, [creatingFolder]);

  function createFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    const f: Folder = {
      id: uid(),
      name,
      projectType: newFolderPt,
      createdAt: new Date().toISOString(),
      sites: [],
    };
    setFolders(prev => [...prev, f]);
    setSelectedId(f.id);
    setNewFolderName('');
    setCreatingFolder(false);
  }

  function deleteFolder(folderId: string) {
    const folder = folders.find(f => f.id === folderId);
    if (!folder) return;
    const msg = folder.sites.length > 0
      ? `Delete "${folder.name}" and its ${folder.sites.length} site(s)? This cannot be undone.`
      : `Delete "${folder.name}"?`;
    if (!window.confirm(msg)) return;
    setFolders(prev => prev.filter(f => f.id !== folderId));
    setSelectedId(prev => {
      if (prev !== folderId) return prev;
      const remaining = folders.filter(f => f.id !== folderId);
      return remaining.length > 0 ? remaining[0].id : null;
    });
  }

  // ── Rename folder ──

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState('');
  const renameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renamingId) renameRef.current?.focus();
  }, [renamingId]);

  function commitRename() {
    const val = renameVal.trim();
    if (val && renamingId) {
      setFolders(prev => prev.map(f => f.id === renamingId ? { ...f, name: val } : f));
    }
    setRenamingId(null);
  }

  // ── Site actions ──

  const [addingAddr, setAddingAddr] = useState('');
  const [addNote, setAddNote] = useState('');
  const addRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function addSite(folderId: string, address: string, note = '') {
    const addr = address.trim();
    if (!addr) return;
    const site: Site = {
      id: uid(),
      address: addr,
      note,
      addedAt: new Date().toISOString(),
      status: 'pending',
    };
    setFolders(prev => prev.map(f =>
      f.id === folderId ? { ...f, sites: [...f.sites, site] } : f
    ));
  }

  function deleteSite(folderId: string, siteId: string) {
    setFolders(prev => prev.map(f =>
      f.id === folderId ? { ...f, sites: f.sites.filter(s => s.id !== siteId) } : f
    ));
  }

  function handleAddSubmit(folderId: string) {
    if (!addingAddr.trim()) return;
    addSite(folderId, addingAddr, addNote);
    setAddingAddr('');
    setAddNote('');
    addRef.current?.focus();
  }

  function handleCSV(folderId: string, file: File) {
    const reader = new FileReader();
    reader.onload = e => {
      const text = e.target?.result as string;
      const lines = text.split(/[\r\n,]+/).map(l => l.trim()).filter(Boolean);
      lines.forEach(addr => addSite(folderId, addr));
    };
    reader.readAsText(file);
  }

  // ── Run analysis ──

  const runAnalysis = useCallback(async (folderId: string, siteId: string) => {
    const folder = folders.find(f => f.id === folderId);
    const site = folder?.sites.find(s => s.id === siteId);
    if (!site) return;

    setFolders(prev => prev.map(f =>
      f.id !== folderId ? f : {
        ...f,
        sites: f.sites.map(s =>
          s.id !== siteId ? s : { ...s, status: 'scoring', errorMsg: undefined }
        ),
      }
    ));

    try {
      const ptCode = PT_API[folder!.projectType];
      const result = await api.score(site.address, ptCode);
      setFolders(prev => prev.map(f =>
        f.id !== folderId ? f : {
          ...f,
          sites: f.sites.map(s =>
            s.id !== siteId ? s : {
              ...s,
              status: 'done',
              score: Math.round(result.report.total_score),
              bucket: result.report.bucket,
              reportId: result.report_id,
            }
          ),
        }
      ));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      // Extract the human-readable detail from the API error
      const detail = msg.match(/"detail":"([^"]+)"/)
        ? msg.match(/"detail":"([^"]+)"/)![1]
        : msg.split(':').slice(1).join(':').trim() || msg;
      setFolders(prev => prev.map(f =>
        f.id !== folderId ? f : {
          ...f,
          sites: f.sites.map(s =>
            s.id !== siteId ? s : { ...s, status: 'error', errorMsg: detail }
          ),
        }
      ));
    }
  }, [folders]);

  function runAll(folderId: string) {
    const folder = folders.find(f => f.id === folderId);
    if (!folder) return;
    folder.sites
      .filter(s => s.status === 'pending' || s.status === 'error')
      .forEach(s => runAnalysis(folderId, s.id));
  }

  // ── Render ──

  const pendingCount = selectedFolder
    ? selectedFolder.sites.filter(s => s.status === 'pending' || s.status === 'error').length
    : 0;

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', fontFamily: 'var(--sans)', overflow: 'hidden' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* ── Left: Folder panel ── */}
      <aside style={{
        width: 240, flexShrink: 0,
        borderRight: '1px solid var(--border-soft)',
        display: 'flex', flexDirection: 'column',
        background: 'var(--surface, #faf9f7)',
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 16px 10px',
          borderBottom: '1px solid var(--border-soft)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text)', letterSpacing: '0.03em', textTransform: 'uppercase' }}>
            Portfolio
          </span>
          <button
            onClick={() => setCreatingFolder(true)}
            title="New folder"
            style={{
              fontSize: 18, lineHeight: 1, border: 'none', background: 'none',
              color: 'var(--accent)', cursor: 'pointer', padding: '0 2px',
              fontWeight: 300,
            }}
          >+</button>
        </div>

        {/* Folder list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '6px 8px' }}>
          {folders.length === 0 && !creatingFolder && (
            <div style={{ padding: '20px 8px', textAlign: 'center', color: 'var(--text-soft)', fontSize: 12 }}>
              No folders yet.<br />
              <button
                onClick={() => setCreatingFolder(true)}
                style={{ marginTop: 8, fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
              >Create one</button>
            </div>
          )}
          {folders.map(f => {
            const isActive = f.id === selectedId;
            const doneCount = f.sites.filter(s => s.status === 'done').length;
            return (
              <button
                key={f.id}
                onClick={() => setSelectedId(f.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  width: '100%', padding: '7px 10px', borderRadius: 6,
                  border: 'none', textAlign: 'left', cursor: 'pointer',
                  background: isActive ? 'var(--accent)' : 'transparent',
                  color: isActive ? '#fff' : 'var(--text)',
                  marginBottom: 1, transition: 'background 120ms',
                  fontFamily: 'var(--sans)',
                }}
                onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'var(--border-soft)'; }}
                onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
              >
                {/* Folder icon */}
                <svg width="13" height="11" viewBox="0 0 13 11" fill="none" style={{ flexShrink: 0, opacity: 0.75 }}>
                  <path d="M0.5 2.5C0.5 1.948 0.948 1.5 1.5 1.5H4.586C4.851 1.5 5.105 1.605 5.293 1.793L6.207 2.707C6.395 2.895 6.649 3 6.914 3H11.5C12.052 3 12.5 3.448 12.5 4V9.5C12.5 10.052 12.052 10.5 11.5 10.5H1.5C0.948 10.5 0.5 10.052 0.5 9.5V2.5Z"
                    fill={isActive ? 'rgba(255,255,255,0.35)' : 'var(--border)'} stroke={isActive ? 'rgba(255,255,255,0.7)' : 'var(--accent)'} strokeWidth="0.75" />
                </svg>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {f.name}
                  </div>
                  <div style={{ fontSize: 10.5, opacity: 0.65, marginTop: 1 }}>
                    {PT_LABELS[f.projectType]} · {f.sites.length} site{f.sites.length !== 1 ? 's' : ''}
                    {doneCount > 0 && ` · ${doneCount} scored`}
                  </div>
                </div>
              </button>
            );
          })}

          {/* New folder inline form */}
          {creatingFolder && (
            <div style={{
              padding: '8px 10px', borderRadius: 6,
              background: 'var(--border-soft)', marginTop: 4,
            }}>
              <input
                ref={newFolderRef}
                value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') createFolder(); if (e.key === 'Escape') setCreatingFolder(false); }}
                placeholder="Folder name…"
                style={{
                  width: '100%', padding: '4px 0', border: 'none',
                  background: 'transparent', fontSize: 12.5,
                  color: 'var(--text)', outline: 'none',
                  fontFamily: 'var(--sans)',
                }}
              />
              <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                {(['solar', 'bess', 'wind', 'generic'] as ProjectType[]).map(pt => (
                  <button
                    key={pt}
                    onClick={() => setNewFolderPt(pt)}
                    style={{
                      padding: '2px 7px', borderRadius: 999, border: '1px solid',
                      fontSize: 10.5, cursor: 'pointer', fontFamily: 'var(--sans)',
                      background: newFolderPt === pt ? 'var(--accent)' : 'transparent',
                      color: newFolderPt === pt ? '#fff' : 'var(--text-soft)',
                      borderColor: newFolderPt === pt ? 'var(--accent)' : 'var(--border)',
                    }}
                  >{PT_LABELS[pt]}</button>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <button onClick={createFolder} style={{
                  padding: '4px 12px', borderRadius: 5,
                  background: 'var(--accent)', color: '#fff',
                  border: 'none', fontSize: 11.5, cursor: 'pointer', fontFamily: 'var(--sans)',
                }}>Create</button>
                <button onClick={() => setCreatingFolder(false)} style={{
                  padding: '4px 8px', borderRadius: 5,
                  background: 'transparent', color: 'var(--text-soft)',
                  border: '1px solid var(--border)', fontSize: 11.5, cursor: 'pointer', fontFamily: 'var(--sans)',
                }}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Right: Sites panel ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>

        {selectedFolder === null ? (
          /* Empty state — no folder selected */
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-soft)',
          }}>
            <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.3 }}>
              <svg width="48" height="40" viewBox="0 0 48 40" fill="none">
                <path d="M2 8C2 6.343 3.343 5 5 5H16.586C17.116 5 17.625 5.211 18 5.586L21.414 9C21.789 9.375 22.298 9.586 22.828 9.586H43C44.657 9.586 46 10.929 46 12.586V35C46 36.657 44.657 38 43 38H5C3.343 38 2 36.657 2 35V8Z" fill="var(--border-soft)" stroke="var(--border)" strokeWidth="1.5" />
              </svg>
            </div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>No folder selected</div>
            <div style={{ fontSize: 12.5, marginTop: 4 }}>
              Create a folder in the panel on the left to get started.
            </div>
          </div>
        ) : (
          <>
            {/* Folder header */}
            <div style={{
              padding: '14px 24px 12px',
              borderBottom: '1px solid var(--border-soft)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              flexShrink: 0,
            }}>
              <div>
                {renamingId === selectedFolder.id ? (
                  <input
                    ref={renameRef}
                    value={renameVal}
                    onChange={e => setRenameVal(e.target.value)}
                    onBlur={commitRename}
                    onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenamingId(null); }}
                    style={{
                      fontFamily: "'Fraunces', Georgia, serif",
                      fontSize: 20, fontWeight: 500, letterSpacing: '-0.018em',
                      border: 'none', borderBottom: '2px solid var(--accent)',
                      background: 'transparent', color: 'var(--text)', outline: 'none',
                      minWidth: 180,
                    }}
                  />
                ) : (
                  <div
                    style={{
                      fontFamily: "'Fraunces', Georgia, serif",
                      fontSize: 20, fontWeight: 500, letterSpacing: '-0.018em',
                      color: 'var(--text)', cursor: 'text', display: 'inline-flex', alignItems: 'center', gap: 6,
                    }}
                    onClick={() => { setRenamingId(selectedFolder.id); setRenameVal(selectedFolder.name); }}
                    title="Click to rename"
                  >
                    {selectedFolder.name}
                    <span style={{ fontSize: 11, color: 'var(--text-soft)', fontFamily: 'var(--sans)', fontWeight: 400 }}>✎</span>
                  </div>
                )}
                <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 2 }}>
                  {PT_LABELS[selectedFolder.projectType]} · {selectedFolder.sites.length} site{selectedFolder.sites.length !== 1 ? 's' : ''}
                  {selectedFolder.sites.filter(s => s.status === 'done').length > 0 && (
                    <> · {selectedFolder.sites.filter(s => s.status === 'done').length} scored</>
                  )}
                  {' · '}created {new Date(selectedFolder.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {pendingCount > 0 && (
                  <button
                    onClick={() => runAll(selectedFolder.id)}
                    style={{
                      padding: '6px 14px', borderRadius: 6,
                      background: 'var(--accent)', color: '#fff',
                      border: 'none', fontSize: 12.5, cursor: 'pointer',
                      fontFamily: 'var(--sans)', fontWeight: 500,
                    }}
                  >
                    Run all ({pendingCount})
                  </button>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.txt"
                  style={{ display: 'none' }}
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleCSV(selectedFolder.id, file);
                    e.target.value = '';
                  }}
                />
                <button
                  onClick={() => fileRef.current?.click()}
                  title="Import addresses from CSV or TXT — one address per line"
                  style={{
                    padding: '6px 12px', borderRadius: 6,
                    background: 'transparent', color: 'var(--text-mid)',
                    border: '1px solid var(--border)', fontSize: 12, cursor: 'pointer',
                    fontFamily: 'var(--sans)',
                  }}
                >Import CSV</button>
                <button
                  onClick={() => deleteFolder(selectedFolder.id)}
                  title="Delete folder"
                  style={{
                    padding: '6px 10px', borderRadius: 6,
                    background: 'transparent', color: '#a85a4a',
                    border: '1px solid #e0c5c2', fontSize: 12, cursor: 'pointer',
                    fontFamily: 'var(--sans)',
                  }}
                >Delete</button>
              </div>
            </div>

            {/* Add site input */}
            <div style={{
              padding: '10px 24px',
              borderBottom: '1px solid var(--border-soft)',
              display: 'flex', gap: 8, alignItems: 'center',
              background: 'var(--surface, #faf9f7)',
              flexShrink: 0,
            }}>
              <input
                ref={addRef}
                value={addingAddr}
                onChange={e => setAddingAddr(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleAddSubmit(selectedFolder.id); }}
                placeholder="Add a site address…"
                style={{
                  flex: 1, padding: '7px 12px', borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'var(--bg)', color: 'var(--text)',
                  fontSize: 13, fontFamily: 'var(--sans)', outline: 'none',
                }}
                onFocus={e => (e.target.style.borderColor = 'var(--accent)')}
                onBlur={e => (e.target.style.borderColor = 'var(--border)')}
              />
              <input
                value={addNote}
                onChange={e => setAddNote(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleAddSubmit(selectedFolder.id); }}
                placeholder="Note (optional)"
                style={{
                  width: 160, padding: '7px 10px', borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'var(--bg)', color: 'var(--text)',
                  fontSize: 12.5, fontFamily: 'var(--sans)', outline: 'none',
                }}
                onFocus={e => (e.target.style.borderColor = 'var(--accent)')}
                onBlur={e => (e.target.style.borderColor = 'var(--border)')}
              />
              <button
                onClick={() => handleAddSubmit(selectedFolder.id)}
                disabled={!addingAddr.trim()}
                style={{
                  padding: '7px 16px', borderRadius: 6,
                  background: addingAddr.trim() ? 'var(--accent)' : 'var(--border-soft)',
                  color: addingAddr.trim() ? '#fff' : 'var(--text-soft)',
                  border: 'none', fontSize: 12.5, cursor: addingAddr.trim() ? 'pointer' : 'default',
                  fontFamily: 'var(--sans)', fontWeight: 500, whiteSpace: 'nowrap',
                }}
              >Add site</button>
            </div>

            {/* Site list */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {selectedFolder.sites.length === 0 ? (
                <div style={{
                  padding: '48px 24px', textAlign: 'center',
                  color: 'var(--text-soft)', fontSize: 13,
                }}>
                  No sites yet. Type an address above or import a CSV.
                </div>
              ) : (
                <>
                  {/* Table header */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 180px 90px 100px 32px',
                    padding: '8px 24px',
                    borderBottom: '1px solid var(--border-soft)',
                    background: 'var(--surface, #faf9f7)',
                  }}>
                    {['Address', 'Score', 'Added', '', ''].map((h, i) => (
                      <div key={i} style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-soft)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {h}
                      </div>
                    ))}
                  </div>

                  {selectedFolder.sites.map(site => (
                    <SiteRow
                      key={site.id}
                      site={site}
                      folderId={selectedFolder.id}
                      onRun={() => runAnalysis(selectedFolder.id, site.id)}
                      onDelete={() => deleteSite(selectedFolder.id, site.id)}
                    />
                  ))}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── SiteRow ────────────────────────────────────────────────────────────────────

function SiteRow({
  site,
  folderId: _folderId,
  onRun,
  onDelete,
}: {
  site: Site;
  folderId: string;
  onRun: () => void;
  onDelete: () => void;
}) {
  const addedDate = new Date(site.addedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 180px 90px 100px 32px',
      alignItems: 'center',
      padding: '11px 24px',
      borderBottom: '1px solid var(--border-soft)',
      transition: 'background 80ms',
    }}
      onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.background = 'var(--surface, #faf9f7)'}
      onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.background = 'transparent'}
    >
      {/* Address + note */}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {site.address}
        </div>
        {site.note && (
          <div style={{ fontSize: 11.5, color: 'var(--text-soft)', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {site.note}
          </div>
        )}
        {site.status === 'error' && (
          <div style={{ fontSize: 11, color: '#a85a4a', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={site.errorMsg}>
            {site.errorMsg}
          </div>
        )}
      </div>

      {/* Score / status */}
      <div>
        {site.status === 'done' && site.score !== undefined && site.bucket ? (
          <ScoreChip score={site.score} bucket={site.bucket} />
        ) : site.status === 'scoring' ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-soft)' }}>
            <Spinner /> Scoring…
          </span>
        ) : site.status === 'error' ? (
          <span style={{ fontSize: 11.5, color: '#a85a4a', fontWeight: 500 }}>Error</span>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--text-soft)' }}>—</span>
        )}
      </div>

      {/* Date added */}
      <div style={{ fontSize: 11.5, color: 'var(--text-soft)' }}>{addedDate}</div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {site.status === 'done' && site.reportId ? (
          <Link
            to={`/report/${site.reportId}`}
            style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 500, textDecoration: 'none', whiteSpace: 'nowrap' }}
          >
            View →
          </Link>
        ) : site.status !== 'scoring' ? (
          <button
            onClick={onRun}
            style={{
              padding: '4px 10px', borderRadius: 5,
              background: site.status === 'error' ? '#f5e2e0' : 'var(--border-soft)',
              color: site.status === 'error' ? '#7a2a22' : 'var(--text-mid)',
              border: 'none', fontSize: 11.5, cursor: 'pointer', fontFamily: 'var(--sans)',
              whiteSpace: 'nowrap',
            }}
          >
            {site.status === 'error' ? 'Retry' : 'Run'}
          </button>
        ) : null}
      </div>

      {/* Delete */}
      <button
        onClick={onDelete}
        title="Remove site"
        style={{
          width: 24, height: 24, borderRadius: 4,
          border: 'none', background: 'transparent',
          color: 'var(--text-soft)', cursor: 'pointer',
          fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--sans)',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = '#a85a4a'; (e.currentTarget as HTMLButtonElement).style.background = '#f5e2e0'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-soft)'; (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
      >×</button>
    </div>
  );
}
