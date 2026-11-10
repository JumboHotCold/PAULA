import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { CAMPUS_NODES, resolveLocationFromText } from '../data/campusGraph';
import { fetchCampusRoute, sessionStatus, fetchCampusNodes, createCampusNode } from '../api/chatApi';
import MaterialIcon from './MaterialIcon';
import CampusLocationIcon from './CampusLocationIcon';
import { campusLocationChoices, sortCampusLocations } from '../data/campusPresentation';
import useMapViewport from '../hooks/useMapViewport';

// =============================================================================
// NODE TYPE ICONS
// =============================================================================
const TYPE_COLORS = {
  office: '#2563eb',
  building: '#7c3aed',
  facility: '#059669',
  landmark: '#d97706',
  college: '#dc2626',
};

// =============================================================================
// MapModule Component
// =============================================================================
export default function MapModule({ className = "", destination = null, user = null }) {
  const [customNodes, setCustomNodes] = useState({});
  const nodes = useMemo(() => ({ ...CAMPUS_NODES, ...customNodes }), [customNodes]);
  const [nodesError, setNodesError] = useState('');
  const [nodesAttempt, setNodesAttempt] = useState(0);
  const [nodeName, setNodeName] = useState('');
  const [placingNode, setPlacingNode] = useState(false);
  const [newNodePosition, setNewNodePosition] = useState(null);
  const [nodeMessage, setNodeMessage] = useState('');
  const [nodeError, setNodeError] = useState('');
  const [savingNode, setSavingNode] = useState(false);
  const savingNodeRef = useRef(false);
  const [verifiedAdmin, setVerifiedAdmin] = useState(null);
  const account = user?.id;
  const eligibleAdmin = user?.type === 'ADMIN' && user?.is_superuser === true;
  const canUseMapTools = eligibleAdmin && account != null && verifiedAdmin === account;
  useEffect(() => {
    let cancelled = false;
    setVerifiedAdmin(null);
    if (eligibleAdmin && account != null) {
      sessionStatus().then(session => {
        if (!cancelled && session.authenticated && session.is_superuser === true && String(session.id) === String(account)) {
          setVerifiedAdmin(account);
        }
      }).catch(() => { /* Fail closed; navigation remains available. */ });
    }
    return () => { cancelled = true; };
  }, [eligibleAdmin, account]);
  // ── State ──
  const [requestedMode, setMode] = useState('navigate'); // 'navigate' | 'mapper'
  const mode = canUseMapTools ? requestedMode : 'navigate';
  useEffect(() => { if (!canUseMapTools) setMode('navigate'); }, [canUseMapTools]);
  const [origin, setOrigin] = useState(null);
  const [selectedDestination, setSelectedDestination] = useState(destination);
  const [pathResult, setPathResult] = useState(null);
  const [showDirections, setShowDirections] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showOriginPicker, setShowOriginPicker] = useState(!!destination);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [aspectRatio, setAspectRatio] = useState(1.6);
  const [isRouting, setIsRouting] = useState(false);
  const [routeError, setRouteError] = useState('');
  const [routeAttempt, setRouteAttempt] = useState(0);
  const viewport = useMapViewport(aspectRatio);
  
  // ── Coordinate Mapper State ──
  const [mapperCoords, setMapperCoords] = useState(() => {
    // Initialize from nodes
    const coords = {};
    Object.entries(nodes).forEach(([id, node]) => {
      coords[id] = { x: node.x, y: node.y };
    });
    return coords;
  });
  const [activeMapperNode, setActiveMapperNode] = useState(null);
  
  const imgRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setNodesError('');
    fetchCampusNodes().then(saved => {
      if (cancelled) return;
      setCustomNodes(current => ({ ...current, ...Object.fromEntries(saved.map(node => [node.id, node])) }));
      setMapperCoords(current => ({ ...current, ...Object.fromEntries(
        saved.map(node => [node.id, { x: node.x, y: node.y }])
      ) }));
    }).catch(error => { if (!cancelled) setNodesError(error.message); });
    return () => { cancelled = true; };
  }, [nodesAttempt]);

  useEffect(() => {
    if (mode !== 'mapper') {
      setPlacingNode(false); setNewNodePosition(null); setActiveMapperNode(null);
      setNodeName(''); setNodeError(''); setNodeMessage('');
    }
  }, [mode, account]);

  const beginNewNode = event => {
    event.preventDefault();
    if (!canUseMapTools || savingNodeRef.current) return;
    const name = nodeName.trim().replace(/\s+/g, ' ');
    if (!name || Object.values(nodes).some(node => node.name.toLowerCase() === name.toLowerCase())) {
      setNodeError(name ? 'A location with this name already exists.' : 'Enter a node name.');
      return;
    }
    setNodeName(name); setNodeError(''); setNodeMessage('');
    setActiveMapperNode(null); setNewNodePosition(null); setPlacingNode(true);
  };

  const saveNewNode = async () => {
    if (!canUseMapTools || !newNodePosition || savingNodeRef.current) return;
    savingNodeRef.current = true;
    setSavingNode(true); setNodeError('');
    try {
      const node = await createCampusNode({ name: nodeName.trim(), ...newNodePosition });
      setCustomNodes(current => ({ ...current, [node.id]: node }));
      setMapperCoords(current => ({ ...current, [node.id]: { x: node.x, y: node.y } }));
      setNewNodePosition(null); setPlacingNode(false); setNodeName('');
      setNodeMessage(`${node.name} was saved and is available on the map.`);
    } catch (error) {
      setNodeError(error.message);
    } finally {
      savingNodeRef.current = false; setSavingNode(false);
    }
  };

  // ── Sync destination prop ──
  useEffect(() => {
    if (destination) {
      const resolvedId = nodes[destination] ? destination : Object.values(customNodes).find(node => node.name.toLowerCase() === destination.toLowerCase())?.id || resolveLocationFromText(destination);
      if (nodes[resolvedId]) {
        setSelectedDestination(resolvedId);
        setShowOriginPicker(true);
        setOrigin(null);
        setPathResult(null);
      }
    }
  }, [destination, nodes, customNodes]);

  // ── Calculate path when origin & destination are both set ──
  useEffect(() => {
    let cancelled = false;
    async function getRoute() {
      if (origin && selectedDestination && origin !== selectedDestination) {
        setIsRouting(true);
        setRouteError('');
        setPathResult(null);
        try {
          const start = nodes[origin];
          const end = nodes[selectedDestination];
          
          if (!start || !end) return;
          
          const result = await fetchCampusRoute(start.x, start.y, end.x, end.y);
          if (cancelled) return;
          
          if (result.status === 'success') {
            setPathResult(result);
            setShowDirections(true);
            setShowOriginPicker(false);
          } else {
            console.error(result.error);
            setPathResult(null);
            setRouteError('No route was found. Please choose another starting point.');
          }
        } catch (error) {
          if (cancelled) return;
          console.error("Failed to fetch route:", error);
          setPathResult(null);
          setRouteError('The route could not be loaded. Please try again.');
        } finally {
          if (!cancelled) setIsRouting(false);
        }
      } else {
        setPathResult(null);
        setIsRouting(false);
        setRouteError('');
      }
    }
    
    getRoute();
    return () => { cancelled = true; };
  }, [origin, selectedDestination, routeAttempt, nodes]);

  // ── Image click handler ──
  const handleImageClick = useCallback((e) => {
    if (viewport.moved.current) return;
    const rect = e.target.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const xPercent = parseFloat(((x / rect.width) * 100).toFixed(2));
    const yPercent = parseFloat(((y / rect.height) * 100).toFixed(2));

    if (mode === 'mapper' && placingNode && !savingNodeRef.current) {
      setNewNodePosition({ x: xPercent, y: yPercent });
      return;
    }
    if (mode === 'mapper' && activeMapperNode) {
      // Save coordinate for active node
      setMapperCoords(prev => ({
        ...prev,
        [activeMapperNode]: { x: xPercent, y: yPercent }
      }));
      
      // Advance to next unmapped node
      const nodeIds = Object.keys(nodes);
      const currentIdx = nodeIds.indexOf(activeMapperNode);
      const nextUnmapped = nodeIds.find((id, idx) => {
        if (idx <= currentIdx) return false;
        const c = { ...mapperCoords, [activeMapperNode]: { x: xPercent, y: yPercent } };
        return c[id].x === 0 && c[id].y === 0;
      });
      setActiveMapperNode(nextUnmapped || null);
    }
  }, [mode, activeMapperNode, mapperCoords, viewport.moved, placingNode, nodes]);

  // ── Node click for navigation ──
  const handleNodeClick = useCallback((nodeId) => {
    if (mode === 'navigate') {
      if (showOriginPicker && !origin) {
        setOrigin(nodeId);
      } else if (!selectedDestination) {
        setSelectedDestination(nodeId);
        setShowOriginPicker(true);
      }
    }
  }, [mode, showOriginPicker, origin, selectedDestination]);

  // ── Reset navigation ──
  const resetNavigation = () => {
    setOrigin(null);
    setPathResult(null);
    setShowDirections(false);
    setShowOriginPicker(!!selectedDestination);
    setRouteError('');
    setSearchQuery('');
  };

  const changeDestination = () => {
    resetNavigation(); setSelectedDestination(null); setShowOriginPicker(false);
  };

  // ── Copy mapper JSON ──
  const copyMapperJSON = () => {
    if (!canUseMapTools) return;
    const output = {};
    Object.entries(mapperCoords).forEach(([id, coords]) => {
      if (customNodes[id] || coords.x !== 0 || coords.y !== 0) {
        output[id] = customNodes[id] ? { ...customNodes[id], ...coords } : coords;
      }
    });
    navigator.clipboard.writeText(JSON.stringify(output, null, 2));
    alert('Coordinates copied to clipboard! Paste them into campusGraph.js');
  };

  // ── Helper: check if node is a waypoint (invisible routing node) ──
  const isWaypoint = (nodeId) => nodes[nodeId]?.type === 'waypoint';

  // ── Filter nodes by search (excluding waypoints from UI) ──
  const filteredNodes = campusLocationChoices(nodes, searchQuery);

  // ── Check if coordinates are mapped ──
  const hasCoordinates = (nodeId) => {
    const node = nodes[nodeId];
    return node && (customNodes[nodeId] || node.x !== 0 || node.y !== 0);
  };

  // Use mapper coordinates if in mapper mode, otherwise use nodes
  const getNodeCoords = (nodeId) => {
    if (mode === 'mapper') {
      return mapperCoords[nodeId] || { x: 0, y: 0 };
    }
    return { x: nodes[nodeId]?.x || 0, y: nodes[nodeId]?.y || 0 };
  };

  // ── Get path polyline points ──
  const getPathPoints = () => {
    if (!pathResult || !pathResult.path) return '';
    // The backend now returns an array of {x: percentage, y: percentage}
    return pathResult.path
      .map(coords => `${coords.x},${coords.y}`)
      .join(' ');
  };

  const visibleNodes = sortCampusLocations(nodes);
  const mappedCount = visibleNodes.filter(node => customNodes[node.id] || mapperCoords[node.id]?.x || mapperCoords[node.id]?.y).length;
  const totalCount = visibleNodes.length;

  return (
    <div className={`campus-nav-container ${className}`}>
      {/* ── Header Bar ── */}
      <div className="campus-nav-header">
        <div className="campus-nav-header-left">
          <span className="campus-nav-badge">Campus Nav</span>
          <span className="campus-nav-title">Saint Paul University Surigao</span>
        </div>
        {canUseMapTools && <div className="campus-nav-header-right">
          <button
            className={`campus-nav-mode-btn ${mode === 'mapper' ? 'active' : ''}`}
            onClick={() => setMode(mode === 'mapper' ? 'navigate' : 'mapper')}
            disabled={savingNode}
            aria-pressed={mode === 'mapper'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            <MaterialIcon name={mode === 'mapper' ? 'explore' : 'tune'} size={18} /> {mode === 'mapper' ? 'Back to map' : 'Map tools'}
          </button>
        </div>}
      </div>

      {/* ── Map Area ── */}
      <div className="campus-nav-map-area">
        {nodesError && <div className="campus-nav-nodes-error" role="alert">
          {nodesError} <button type="button" onClick={() => setNodesAttempt(value => value + 1)}>Try again</button>
        </div>}
        <div className="campus-nav-zoom-controls" role="group" aria-label="Map zoom controls">
          <span className="campus-nav-touch-hint">Drag to move · Pinch or use + / −</span>
          <button type="button" aria-label="Zoom out" disabled={viewport.zoom <= 1} onClick={() => viewport.zoomAt(viewport.zoom - .5)}>−</button>
          <span className="campus-nav-zoom-value">{Math.round(viewport.zoom * 100)}%</span>
          <button type="button" aria-label="Zoom in" disabled={viewport.zoom >= 4} onClick={() => viewport.zoomAt(viewport.zoom + .5)}>+</button>
          <button type="button" aria-label="Fit map to screen" onClick={viewport.reset}><MaterialIcon name="fullscreen_exit" size={20} /></button>
        </div>
        <div className="campus-nav-viewport" ref={viewport.viewportRef} {...viewport.handlers} tabIndex={0}
             role="region" aria-label="Campus map. Drag to move, pinch to zoom, or use the zoom buttons.">
        <div className="campus-nav-map-stage">
        <div className="campus-nav-map-wrapper" ref={viewport.canvasRef}
             style={{ width: viewport.size.width * viewport.zoom, height: viewport.size.height * viewport.zoom }}>
          {/* The map image */}
          <img
            ref={imgRef}
            src="/images/2D_Mapping/ST.PAUL-2D MAP.jpg"
            alt="SPUS Campus Map"
            className="campus-nav-map-img"
            onClick={handleImageClick}
            draggable={false}
            onLoad={e => setAspectRatio(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)}
          />

          {/* ── SVG Overlay for nodes, path, pins ── */}
          <svg className="campus-nav-svg-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
            {/* Animated path line */}
            {pathResult && pathResult.path.length > 1 && (
              <>
                {/* Shadow/glow for path */}
                <polyline
                  points={getPathPoints()}
                  fill="none"
                  stroke="rgba(0,107,63,0.3)"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {/* Main animated path */}
                <polyline
                  className="campus-nav-path-line"
                  points={getPathPoints()}
                  fill="none"
                  stroke="#006B3F"
                  strokeWidth="0.6"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  strokeDasharray="1.5 0.8"
                />
              </>
            )}

            {/* Node dots */}
            {Object.values(nodes).map(node => {
              if (node.type === 'waypoint') return null; // Hide corridor waypoints
              const coords = getNodeCoords(node.id);
              if (!customNodes[node.id] && coords.x === 0 && coords.y === 0) return null;

              const isOrigin = origin === node.id;
              const isDest = selectedDestination === node.id;
              const isHovered = hoveredNode === node.id;
              
              // We no longer highlight waypoints array for dots as the path draws over them

              let fillColor = '#9ca3af';
              let radius = 0.6;
              let strokeColor = 'white';
              let strokeWidth = 0.15;

              if (isOrigin) {
                fillColor = '#22c55e';
                radius = 1;
                strokeWidth = 0.25;
              } else if (isDest) {
                fillColor = '#ef4444';
                radius = 1;
                strokeWidth = 0.25;
              } else if (isHovered) {
                fillColor = TYPE_COLORS[node.type] || '#6b7280';
                radius = 0.8;
              }

              return (
                <g key={node.id}>
                  {/* Pulse animation for destination */}
                  {isDest && (
                    <circle
                      cx={coords.x}
                      cy={coords.y}
                      r={1.5}
                      fill="none"
                      stroke="#ef4444"
                      strokeWidth="0.15"
                      className="campus-nav-pulse"
                    />
                  )}
                  {/* Pulse animation for origin */}
                  {isOrigin && (
                    <circle
                      cx={coords.x}
                      cy={coords.y}
                      r={1.5}
                      fill="none"
                      stroke="#22c55e"
                      strokeWidth="0.15"
                      className="campus-nav-pulse"
                    />
                  )}
                  {/* Node circle */}
                  <circle
                    cx={coords.x}
                    cy={coords.y}
                    r={radius}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    className="campus-nav-node-dot"
                    style={{ pointerEvents: 'none' }}
                  />
                  <circle cx={coords.x} cy={coords.y}
                    r={Math.min(4, 16 / (viewport.size.width * viewport.zoom) * 100)}
                    fill="transparent" className="campus-nav-node-hit" data-map-node={node.id}
                    role="button" tabIndex={mode === 'navigate' ? 0 : -1} aria-label={node.name}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onFocus={() => setHoveredNode(node.id)} onBlur={() => setHoveredNode(null)}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleNodeClick(node.id); } }}
                    onClick={(e) => { e.stopPropagation(); if (!viewport.moved.current) handleNodeClick(node.id); }}
                    style={{ cursor: 'pointer', pointerEvents: mode === 'mapper' ? 'none' : 'auto' }}
                  />
                </g>
              );
            })}

            {mode === 'mapper' && newNodePosition && (
              <circle data-map-draft="true" cx={newNodePosition.x} cy={newNodePosition.y}
                r={1} fill="#2563eb" stroke="white" strokeWidth="0.25" style={{ pointerEvents: 'none' }}>
                <title>{nodeName} (unsaved)</title>
              </circle>
            )}

            {/* Waypoint numbers on path (only for real locations, not corridor bends) */}
            {/* The python backend does not currently output turn-by-turn text nodes. */}
          </svg>

          {/* ── Hover tooltip (not for waypoints) ── */}
          {hoveredNode && !isWaypoint(hoveredNode) && (() => {
            const coords = getNodeCoords(hoveredNode);
            const node = nodes[hoveredNode];
            if (!customNodes[node.id] && coords.x === 0 && coords.y === 0) return null;
            return (
              <div
                className="campus-nav-tooltip"
                style={{
                  left: `${coords.x}%`,
                  top: `${coords.y}%`,
                  transform: 'translate(-50%, -130%)',
                }}
              >
                <span className="campus-nav-tooltip-icon">
                  <CampusLocationIcon node={node} size={18} color={TYPE_COLORS[node.type]} />
                </span>
                <span className="campus-nav-tooltip-name">{node.name}</span>
              </div>
            );
          })()}
        </div>
        </div>
        </div>
      </div>

      {/* ── NAVIGATE MODE: Origin Picker Panel ── */}
      {mode === 'navigate' && showOriginPicker && !pathResult && (
        <div className="campus-nav-origin-panel">
          <div className="campus-nav-origin-panel-header">
            <span className="campus-nav-origin-icon">
              <MaterialIcon name="location_on" size={16} color="var(--spus-gold)" />
            </span>
            <div>
              <div className="campus-nav-origin-dest-label">
                Destination: <strong>{nodes[selectedDestination]?.name}</strong>
              </div>
              <div className="campus-nav-origin-prompt">Where are you right now?</div>
            </div>
            <button type="button" className="campus-nav-change-destination" onClick={changeDestination}>Change destination</button>
          </div>
          
          <input
            type="text"
            className="campus-nav-search-input"
            placeholder="Search your starting location"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search starting locations" autoComplete="off"
          />
          
          <div className="campus-nav-location-list">
            {isRouting && <p className="campus-nav-status" role="status">Finding your route…</p>}
            {routeError && <div className="campus-nav-status" role="alert">{routeError} <button type="button" onClick={() => setRouteAttempt(attempt => attempt + 1)}>Try again</button></div>}
            {!filteredNodes.some(n => n.id !== selectedDestination && hasCoordinates(n.id)) && <p className="campus-nav-status">No locations found. Try an office or building name.</p>}
            {filteredNodes
              .filter(n => n.id !== selectedDestination && hasCoordinates(n.id))
              .map(node => (
              <button
                key={node.id}
                className="campus-nav-location-item"
                onClick={() => setOrigin(node.id)}
              >
                <span className="campus-nav-location-item-icon">
                  <CampusLocationIcon node={node} size={20} color={TYPE_COLORS[node.type]} />
                </span>
                <span>{node.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── NAVIGATE MODE: No destination selected ── */}
      {mode === 'navigate' && !selectedDestination && !pathResult && (
        <div className="campus-nav-origin-panel">
          <div className="campus-nav-origin-panel-header">
            <span className="campus-nav-origin-icon">
              <MaterialIcon name="explore" size={16} color="var(--spus-gold)" />
            </span>
            <div>
              <div className="campus-nav-origin-prompt">Select a destination</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-light, #6b7280)' }}>
                Click a location on the map or search below
              </div>
            </div>
          </div>
          
          <input
            type="text"
            className="campus-nav-search-input"
            placeholder="Search for a location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search destinations" autoComplete="off"
          />
          
          <div className="campus-nav-location-list">
            {!filteredNodes.some(n => hasCoordinates(n.id)) && <p className="campus-nav-status">No locations found. Try an office or building name.</p>}
            {filteredNodes.filter(n => hasCoordinates(n.id)).map(node => (
              <button
                key={node.id}
                className="campus-nav-location-item"
                onClick={() => {
                  setSelectedDestination(node.id);
                  setShowOriginPicker(true);
                  setSearchQuery('');
                }}
              >
                <span className="campus-nav-location-item-icon"><CampusLocationIcon node={node} size={20} color={TYPE_COLORS[node.type]} /></span>
                <span>{node.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── NAVIGATE MODE: Directions Panel ── */}
      {mode === 'navigate' && pathResult && (
        <div className={`campus-nav-directions-panel ${showDirections ? 'open' : 'collapsed'}`}>
          <button
            className="campus-nav-directions-toggle"
            onClick={() => setShowDirections(!showDirections)}
            aria-expanded={showDirections}
          >
            <div className="campus-nav-directions-summary">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <MaterialIcon name="location_on" size={15} color="var(--spus-gold)" />
                {nodes[origin]?.name} → {nodes[selectedDestination]?.name}
              </span>
              <span className="campus-nav-directions-time">
                Route ready · Follow the highlighted path
              </span>
            </div>
            <span className="campus-nav-directions-chevron">{showDirections ? '▼' : '▲'}</span>
          </button>
          
          {showDirections && (
            <div className="campus-nav-directions-steps">
              <div className="campus-nav-step start end">
                <span className="campus-nav-step-icon">
                  <MaterialIcon name="near_me" size={16} color="var(--spus-green)" />
                </span>
                <span className="campus-nav-step-text">Follow the highlighted path on the map.</span>
              </div>
              
              <button className="campus-nav-reset-btn" onClick={resetNavigation} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                <MaterialIcon name="refresh" size={15} style={{ marginRight: '6px' }} /> Change Starting Point
              </button>
              <button className="campus-nav-reset-btn" onClick={changeDestination}>Change destination</button>
            </div>
          )}
        </div>
      )}

      {/* ── MAPPER MODE Panel ── */}
      {mode === 'mapper' && (
        <div className="campus-nav-mapper-panel">
          <div className="campus-nav-mapper-header">
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <MaterialIcon name="map" size={18} /> Coordinate Mapper
            </h3>
            <span className="campus-nav-mapper-progress">{mappedCount}/{totalCount} mapped</span>
          </div>
          
          <p className="campus-nav-mapper-instructions">
            {placingNode ? <>Click on the map to place <strong>{nodeName}</strong>. Click again to adjust it, then save.</> : activeMapperNode
              ? <>Click on the map to place <strong>{nodes[activeMapperNode]?.name}</strong></>
              : 'Select a node below, then click the map to set its position.'
            }
          </p>
          <p className="campus-nav-mapper-instructions">New nodes are saved for everyone. Moving existing pins here is a preview; export coordinates to apply those changes.</p>

          <form className="campus-nav-add-node" onSubmit={beginNewNode}>
            <label htmlFor="campus-node-name">New node name</label>
            <input id="campus-node-name" value={nodeName} maxLength={120} required
              placeholder="e.g. Admissions Office" disabled={placingNode || savingNode}
              onChange={event => { setNodeName(event.target.value); setNodeError(''); setNodeMessage(''); }} />
            {!placingNode ? <button type="submit" disabled={savingNode}>Add node</button> : (
              <div className="campus-nav-add-node-actions">
                <button type="button" disabled={!newNodePosition || savingNode} onClick={saveNewNode}>
                  {savingNode ? 'Saving...' : 'Save node'}
                </button>
                <button type="button" disabled={savingNode} onClick={() => {
                  setPlacingNode(false); setNewNodePosition(null); setNodeError('');
                }}>Cancel</button>
              </div>
            )}
            {nodeError && <p role="alert">{nodeError}</p>}
            {nodeMessage && <p role="status">{nodeMessage}</p>}
          </form>

          <div className="campus-nav-mapper-list">
            {visibleNodes
              .map(node => {
              const coords = mapperCoords[node.id];
              const isMapped = coords && (customNodes[node.id] || coords.x !== 0 || coords.y !== 0);
              const isActive = activeMapperNode === node.id;
              
              return (
                <button
                  key={node.id}
                  className={`campus-nav-mapper-item ${isActive ? 'active' : ''} ${isMapped ? 'mapped' : ''}`}
                  disabled={savingNode}
                  onClick={() => {
                    setPlacingNode(false); setNewNodePosition(null); setNodeError(''); setNodeMessage('');
                    setActiveMapperNode(node.id);
                  }}
                >
                  <span className="campus-nav-mapper-status" style={{ display: 'flex', alignItems: 'center' }}>
                    <MaterialIcon name={isMapped ? "check_circle" : "circle"} size={14} color={isMapped ? "#10B981" : "#D1D5DB"} />
                  </span>
                  <CampusLocationIcon node={node} size={18} color={TYPE_COLORS[node.type]} />
                  <span className="campus-nav-mapper-name">{node.name}</span>
                  {isMapped && (
                    <span className="campus-nav-mapper-coords">
                      ({coords.x.toFixed(1)}, {coords.y.toFixed(1)})
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <button className="campus-nav-mapper-copy-btn" onClick={copyMapperJSON} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <MaterialIcon name="assignment" size={15} style={{ marginRight: '6px' }} /> Copy All Coordinates as JSON
          </button>
        </div>
      )}
    </div>
  );
}
