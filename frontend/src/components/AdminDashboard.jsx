import { useState, useEffect, useCallback } from 'react';
import ThemeToggle from './ThemeToggle';
import MaterialIcon from './MaterialIcon';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import {
  fetchAdminMetrics,
  fetchCampusPulse,
  fetchTrendingConfusion,
  fetchStudentNeeds,
  patchStudentNeed,
  getPrintReportUrl,
  getExportCsvUrl,
  getExportPdfUrl,
} from '../api/chatApi';

/* ═══════════════════════════════════════════════════════
   CONSTANTS
   ═══════════════════════════════════════════════════════ */

const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const URGENCY_COLORS = {
  Critical: '#DC2626',
  High: '#F59E0B',
  Medium: '#3B82F6',
  Low: '#22C55E',
};
const STATUS_DOTS = {
  Open: '#DC2626',
  'In Progress': '#F59E0B',
  Resolved: '#22C55E',
};

/* ═══════════════════════════════════════════════════════
   SKELETON LOADER
   ═══════════════════════════════════════════════════════ */

function SkeletonCard({ width = '100%', height = '120px' }) {
  return (
    <div className="admin-skeleton" style={{ width, height, borderRadius: '8px' }} />
  );
}

/* ═══════════════════════════════════════════════════════
   CUSTOM TOOLTIP
   ═══════════════════════════════════════════════════════ */

function CustomBarTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="admin-tooltip">
      <p style={{ fontWeight: 600, marginBottom: 2 }}>{label}</p>
      <p style={{ color: 'var(--spus-green)' }}>
        Queries: <strong>{payload[0].value}</strong>
      </p>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   HEATMAP COMPONENT (inline SVG)
   ═══════════════════════════════════════════════════════ */

function CampusPulseHeatmap({ data }) {
  // Build a 7x24 grid from the API data
  const grid = {};
  let maxCount = 1;
  data.forEach(({ day, hour, count }) => {
    const key = `${day}-${hour}`;
    grid[key] = count;
    if (count > maxCount) maxCount = count;
  });

  const cellSize = 18;
  const gap = 2;
  const labelWidth = 40;
  const topLabelHeight = 22;
  const totalW = labelWidth + 24 * (cellSize + gap);
  const totalH = topLabelHeight + 7 * (cellSize + gap);

  return (
    <svg viewBox={`0 0 ${totalW} ${totalH}`} width="100%" style={{ maxWidth: totalW }}>
      {/* Hour labels */}
      {Array.from({ length: 24 }, (_, h) => (
        <text
          key={`hl-${h}`}
          x={labelWidth + h * (cellSize + gap) + cellSize / 2}
          y={14}
          textAnchor="middle"
          fontSize="7"
          fill="var(--text-light)"
        >
          {h}
        </text>
      ))}
      {/* Day rows */}
      {Array.from({ length: 7 }, (_, d) => (
        <g key={`row-${d}`}>
          <text
            x={labelWidth - 5}
            y={topLabelHeight + d * (cellSize + gap) + cellSize / 2 + 3}
            textAnchor="end"
            fontSize="8"
            fill="var(--text-light)"
          >
            {DAY_LABELS[d]}
          </text>
          {Array.from({ length: 24 }, (_, h) => {
            // Django's ExtractWeekDay: 1=Sunday … 7=Saturday
            const count = grid[`${d + 1}-${h}`] || 0;
            const intensity = count / maxCount;
            const r = 10, g2 = 77, b = 46; // --spus-green RGB
            const alpha = Math.max(0.05, intensity);
            return (
              <rect
                key={`cell-${d}-${h}`}
                x={labelWidth + h * (cellSize + gap)}
                y={topLabelHeight + d * (cellSize + gap)}
                width={cellSize}
                height={cellSize}
                rx={3}
                fill={count === 0 ? 'var(--border-color)' : `rgba(${r}, ${g2}, ${b}, ${alpha})`}
                className="heatmap-cell"
              >
                <title>{DAY_LABELS[d]} {h}:00 — {count} queries</title>
              </rect>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════
   ADMIN DASHBOARD COMPONENT
   ═══════════════════════════════════════════════════════ */

export default function AdminDashboard({ user, onBackToChat }) {
  // Role guard — admin = superuser
  if (!user || !user.is_superuser) {
    return null;
  }

  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState(null);
  const [pulseData, setPulseData] = useState([]);
  const [trendingData, setTrendingData] = useState([]);
  const [needsData, setNeedsData] = useState({ results: [], count: 0, num_pages: 1, current_page: 1 });
  const [filters, setFilters] = useState({ urgency: '', need_type: '', status: '', search: '', page: 1 });

  // ─── Fetch all data ───
  const loadAllData = useCallback(async () => {
    setLoading(true);
    try {
      const [m, p, t, n] = await Promise.all([
        fetchAdminMetrics(),
        fetchCampusPulse(),
        fetchTrendingConfusion(),
        fetchStudentNeeds(filters),
      ]);
      setMetrics(m);
      setPulseData(p);
      setTrendingData(t);
      setNeedsData(n);
    } catch (err) {
      console.error('Admin dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAllData(); }, [loadAllData]);

  // ─── Reload needs when filters change ───
  const loadNeeds = useCallback(async () => {
    try {
      const n = await fetchStudentNeeds(filters);
      setNeedsData(n);
    } catch (err) {
      console.error('Failed to load student needs:', err);
    }
  }, [filters]);

  useEffect(() => { loadNeeds(); }, [loadNeeds]);

  // ─── Action handlers ───
  const handleResolve = async (id) => {
    try {
      await patchStudentNeed(id, { status: 'Resolved' });
      loadNeeds();
      // Refresh metrics too
      const m = await fetchAdminMetrics();
      setMetrics(m);
    } catch (err) {
      console.error('Failed to resolve:', err);
    }
  };

  const handleAssign = async (id) => {
    const advisor = prompt('Enter advisor name:');
    if (!advisor) return;
    try {
      await patchStudentNeed(id, { assigned_advisor: advisor });
      loadNeeds();
    } catch (err) {
      console.error('Failed to assign:', err);
    }
  };

  // ─── RENDER ───
  return (
    <div className="admin-dashboard">
      {/* Header */}
      <div className="admin-header">
        <div>
          <h1 className="admin-title">Institutional Analytics</h1>
          <p className="admin-subtitle">Campus-wide student needs overview — Real-time monitoring</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <ThemeToggle />
          <a 
            href="http://localhost:8000/admin/" 
            target="_blank" 
            rel="noopener noreferrer"
            className="admin-action-btn primary"
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <MaterialIcon name="shield" size={18} color="#ffffff" /> Full Power Admin (Unfold)
          </a>
          <button className="admin-back-btn" onClick={onBackToChat}>
            ← Back to Chat
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="admin-metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))' }}>
        {loading ? (
          <>
            <SkeletonCard height="110px" />
            <SkeletonCard height="110px" />
            <SkeletonCard height="110px" />
            <SkeletonCard height="110px" />
            <SkeletonCard height="110px" />
            <SkeletonCard height="110px" />
          </>
        ) : (
          <>
            <div className="admin-metric-card">
              <div className="metric-icon-wrap" style={{ background: 'rgba(10, 77, 46, 0.1)', color: 'var(--spus-green)' }}>
                <MaterialIcon name="school" size={22} color="var(--spus-green)" />
              </div>
              <div className="metric-value">{metrics?.total_enrolled ?? 0}</div>
              <div className="metric-label">Total Enrolled</div>
            </div>
            <div className="admin-metric-card">
              <div className="metric-icon-wrap" style={{ background: 'rgba(5, 150, 105, 0.1)', color: '#059669' }}>
                <MaterialIcon name="chat" size={22} color="#059669" />
              </div>
              <div className="metric-value">{metrics?.total_queries ?? 0}</div>
              <div className="metric-label">Total Inquiries</div>
            </div>
            <div className="admin-metric-card">
              <div className="metric-icon-wrap" style={{ background: 'rgba(212, 175, 55, 0.15)', color: 'var(--spus-gold)' }}>
                <MaterialIcon name="sentiment_satisfied" size={22} color="var(--spus-gold)" />
              </div>
              <div className="metric-value">{metrics?.satisfaction_rate != null ? `${metrics.satisfaction_rate}%` : '100%'}</div>
              <div className="metric-label">Satisfaction Rate</div>
            </div>
            <div className="admin-metric-card">
              <div className="metric-icon-wrap" style={{ background: 'rgba(220, 38, 38, 0.1)', color: '#DC2626' }}>
                <MaterialIcon name="warning" size={22} color="#DC2626" />
              </div>
              <div className="metric-value">{metrics?.at_risk ?? 0}</div>
              <div className="metric-label">At-Risk Students</div>
            </div>
            <div className="admin-metric-card">
              <div className="metric-icon-wrap" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#F59E0B' }}>
                <MaterialIcon name="assignment" size={22} color="#F59E0B" />
              </div>
              <div className="metric-value">{metrics?.unresolved_requests ?? 0}</div>
              <div className="metric-label">Unresolved Requests</div>
            </div>
            <div className="admin-metric-card">
              <div className="metric-icon-wrap" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3B82F6' }}>
                <MaterialIcon name="edit_note" size={22} color="#3B82F6" />
              </div>
              <div className="metric-value">{metrics?.pending_enrollments ?? 0}</div>
              <div className="metric-label">Pending Enrollments</div>
            </div>
          </>
        )}
      </div>

      {/* Reports & Export Toolbar */}
      <div className="admin-reports-card" style={{
        backgroundColor: 'var(--card-bg, rgba(255, 255, 255, 0.8))',
        backdropFilter: 'blur(10px)',
        borderRadius: '12px',
        padding: '16px 20px',
        border: '1px solid var(--border-color)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px',
        marginBottom: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-dark)' }}>
            <MaterialIcon name="summarize" size={20} color="var(--spus-green)" />
            Institutional Reports & Exports
          </h3>
          <p style={{ margin: '3px 0 0', fontSize: '0.8rem', color: 'var(--text-light)' }}>
            Ready-to-print official university analytics with PDF and CSV export capabilities.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <a
            href={getPrintReportUrl('summary')}
            target="_blank"
            rel="noopener noreferrer"
            className="admin-action-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              textDecoration: 'none',
              background: 'var(--spus-green)',
              color: '#ffffff',
              fontWeight: 600,
              padding: '8px 14px',
              borderRadius: '8px'
            }}
          >
            <MaterialIcon name="print" size={16} color="#ffffff" />
            Ready to Print
          </a>
          <a
            href={getExportPdfUrl('summary')}
            download
            className="admin-action-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              textDecoration: 'none',
              fontWeight: 600,
              padding: '8px 14px',
              borderRadius: '8px'
            }}
          >
            <MaterialIcon name="picture_as_pdf" size={16} color="#DC2626" />
            Export PDF
          </a>
          <a
            href={getExportCsvUrl('summary')}
            download
            className="admin-action-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              textDecoration: 'none',
              fontWeight: 600,
              padding: '8px 14px',
              borderRadius: '8px'
            }}
          >
            <MaterialIcon name="table_chart" size={16} color="#059669" />
            Summary CSV
          </a>
          <a
            href={getExportCsvUrl('student_needs')}
            download
            className="admin-action-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              textDecoration: 'none',
              fontWeight: 600,
              padding: '8px 14px',
              borderRadius: '8px'
            }}
          >
            <MaterialIcon name="file_download" size={16} color="#2563EB" />
            Needs Log CSV
          </a>
        </div>
      </div>

      {/* Charts Row */}
      <div className="admin-charts-grid">
        {/* Campus Pulse Heatmap */}
        <div className="admin-chart-card">
          <h3>Campus Pulse — Chat Volume Heatmap</h3>
          {loading ? (
            <SkeletonCard height="200px" />
          ) : pulseData.length === 0 ? (
            <p className="admin-empty">No chat data yet. Heatmap will populate as students interact with PAULA.</p>
          ) : (
            <div style={{ overflowX: 'auto', padding: '10px 0' }}>
              <CampusPulseHeatmap data={pulseData} />
            </div>
          )}
        </div>

        {/* Trending Confusion */}
        <div className="admin-chart-card">
          <h3>Trending Confusion — Query Categories</h3>
          {loading ? (
            <SkeletonCard height="200px" />
          ) : trendingData.length === 0 ? (
            <p className="admin-empty">No queries categorized yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(200, trendingData.length * 36)}>
              <BarChart data={trendingData} layout="vertical" margin={{ top: 5, right: 20, left: 80, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis type="number" tick={{ fill: 'var(--text-light)', fontSize: 11 }} />
                <YAxis dataKey="category" type="category" tick={{ fill: 'var(--text-dark)', fontSize: 12 }} width={75} />
                <Tooltip content={<CustomBarTooltip />} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Queries">
                  {trendingData.map((_, i) => (
                    <Cell key={i} fill={i === 0 ? 'var(--spus-green)' : i < 3 ? '#0d5f39' : '#4ade80'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Student Needs Table */}
      <div className="admin-table-card">
        <div className="admin-table-header">
          <h3>Flagged Student Cases</h3>
          <div className="admin-filters">
            <input
              type="text"
              placeholder="Search name or ID..."
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value, page: 1 }))}
              className="admin-filter-input"
            />
            <select
              value={filters.urgency}
              onChange={e => setFilters(f => ({ ...f, urgency: e.target.value, page: 1 }))}
              className="admin-filter-select"
            >
              <option value="">All Urgency</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
            <select
              value={filters.need_type}
              onChange={e => setFilters(f => ({ ...f, need_type: e.target.value, page: 1 }))}
              className="admin-filter-select"
            >
              <option value="">All Types</option>
              <option value="Financial">Financial</option>
              <option value="Academic">Academic</option>
              <option value="Enrollment">Enrollment</option>
              <option value="Mental Health">Mental Health</option>
            </select>
            <select
              value={filters.status}
              onChange={e => setFilters(f => ({ ...f, status: e.target.value, page: 1 }))}
              className="admin-filter-select"
            >
              <option value="">All Status</option>
              <option value="Open">Open</option>
              <option value="In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 20 }}>
            <SkeletonCard height="40px" />
            <div style={{ height: 8 }} />
            <SkeletonCard height="40px" />
            <div style={{ height: 8 }} />
            <SkeletonCard height="40px" />
          </div>
        ) : needsData.results.length === 0 ? (
          <div className="admin-table-empty">
            No student cases match your filters.
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="admin-data-table">
                <thead>
                  <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Need Type</th>
                    <th>Urgency</th>
                    <th>Status</th>
                    <th>Advisor</th>
                    <th>Date Filed</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {needsData.results.map(c => (
                    <tr key={c.id}>
                      <td style={{ fontWeight: 600, fontFamily: 'monospace', fontSize: '0.85em' }}>{c.student_id}</td>
                      <td style={{ fontWeight: 500 }}>{c.name}</td>
                      <td>{c.need_type}</td>
                      <td>
                        <span className="admin-urgency-badge" style={{
                          background: `${URGENCY_COLORS[c.urgency]}18`,
                          color: URGENCY_COLORS[c.urgency],
                        }}>
                          {c.urgency}
                        </span>
                      </td>
                      <td>
                        <span className="admin-status-badge">
                          <span className="admin-status-dot" style={{ background: STATUS_DOTS[c.status] || '#9CA3AF' }} />
                          {c.status}
                        </span>
                      </td>
                      <td style={{ color: c.assigned_advisor === 'Unassigned' ? '#9CA3AF' : 'var(--text-dark)' }}>
                        {c.assigned_advisor}
                      </td>
                      <td style={{ color: 'var(--text-light)', fontSize: '0.85em' }}>{c.date}</td>
                      <td className="admin-actions-cell">
                        <button className="admin-action-btn" onClick={() => handleAssign(c.id)}>Assign</button>
                        {c.status !== 'Resolved' && (
                          <button className="admin-action-btn primary" onClick={() => handleResolve(c.id)}>Resolve</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="admin-pagination">
              <span>
                Showing page {needsData.current_page} of {needsData.num_pages} ({needsData.count} total)
              </span>
              <div className="pagination-btns">
                <button
                  disabled={needsData.current_page <= 1}
                  onClick={() => setFilters(f => ({ ...f, page: f.page - 1 }))}
                >
                  ← Prev
                </button>
                <button
                  disabled={needsData.current_page >= needsData.num_pages}
                  onClick={() => setFilters(f => ({ ...f, page: f.page + 1 }))}
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
