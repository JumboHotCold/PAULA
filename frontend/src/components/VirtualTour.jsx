import React, { useState } from 'react';
import { ReactPhotoSphereViewer } from 'react-photo-sphere-viewer';
import { MarkersPlugin } from '@photo-sphere-viewer/markers-plugin';
import '@photo-sphere-viewer/core/index.css';
import '@photo-sphere-viewer/markers-plugin/index.css';
import MaterialIcon from './MaterialIcon';

/**
 * NODES — Virtual Tour locations with 360° panoramas.
 *
 * yaw angles are calibrated from the equirectangular image center (0°):
 *   - Image center = yaw 0° (default forward view when panorama loads)
 *   - Positive yaw = clockwise (right)
 *   - Negative yaw = counter-clockwise (left)
 *   - ±180° = directly behind
 */
const NODES = {
  'cafeteria': {
    id: 'cafeteria',
    name: 'Cafeteria Hallway',
    description: 'The main campus dining hall hallway.',
    top: '27.84%',
    left: '79.26%',
    panorama: '/images/SmartVirtualTour/cafeteria_hallway_1.jpg',
    markers: [
      {
        id: 'to_church',
        position: { yaw: '317.2deg', pitch: '-4.7deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Administrative Hallway</div><div class="vt-nav-arrow" title="Walk to Administrative Hallway"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Administrative Hallway',
        style: { cursor: 'pointer' },
        data: { targetNode: 'church' }
      },
      {
        id: 'to_main_entrance',
        position: { yaw: '210deg', pitch: '-15deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Main Entrance</div><div class="vt-nav-arrow" title="Walk to Main Entrance"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Main Entrance',
        style: { cursor: 'pointer' },
        data: { targetNode: 'main_entrance' }
      },
      {
        id: 'to_court',
        position: { yaw: '310.5deg', pitch: '-10.5deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Campus Court</div><div class="vt-nav-arrow" title="Walk to Campus Court"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Campus Court',
        style: { cursor: 'pointer' },
        data: { targetNode: 'court' }
      }
    ]
  },
  'church': {
    id: 'church',
    name: 'Administrative Hallway',
    description: 'The corridor connecting the court and administrative offices.',
    top: '34.29%',
    left: '52.13%',
    panorama: '/images/SmartVirtualTour/church_x_hallway__1.jpg',
    markers: [
      {
        id: 'to_cafeteria',
        position: { yaw: '104.5deg', pitch: '-17.9deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Cafeteria Hallway</div><div class="vt-nav-arrow" title="Walk to Cafeteria Hallway"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Cafeteria Hallway',
        style: { cursor: 'pointer' },
        data: { targetNode: 'cafeteria' }
      },
      {
        id: 'to_court',
        position: { yaw: '85.9deg', pitch: '-17.2deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Campus Court</div><div class="vt-nav-arrow" title="Walk to Campus Court"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Campus Court',
        style: { cursor: 'pointer' },
        data: { targetNode: 'court' }
      }
    ]
  },
  'main_entrance': {
    id: 'main_entrance',
    name: 'Main Entrance',
    description: 'The main gateway to the SPUS campus.',
    top: '47.63%',
    left: '84.11%',
    panorama: '/images/SmartVirtualTour/Main_Entrance.jpg',
    markers: [
      {
        id: 'to_main_entrance_lobby',
        position: { yaw: '70deg', pitch: '-15deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Main Entrance Lobby</div><div class="vt-nav-arrow" title="Walk to Main Entrance Lobby"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Main Entrance Lobby',
        style: { cursor: 'pointer' },
        data: { targetNode: 'main_entrance_lobby' }
      },
      {
        id: 'to_cafeteria',
        position: { yaw: '240deg', pitch: '-15deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Cafeteria Hallway</div><div class="vt-nav-arrow" title="Walk to Cafeteria Hallway"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Cafeteria Hallway',
        style: { cursor: 'pointer' },
        data: { targetNode: 'cafeteria' }
      }
    ]
  },
  'main_entrance_lobby': {
    id: 'main_entrance_lobby',
    name: 'Main Entrance Lobby',
    description: 'The lobby area near the main entrance of the campus.',
    top: '41.70%',
    left: '83.63%',
    panorama: '/images/SmartVirtualTour/Main_Entrance_Lobby.jpg',
    markers: [
      {
        id: 'to_main_entrance',
        position: { yaw: '-70deg', pitch: '-15deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Main Entrance</div><div class="vt-nav-arrow" title="Walk to Main Entrance"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Main Entrance',
        style: { cursor: 'pointer' },
        data: { targetNode: 'main_entrance' }
      },
      {
        id: 'to_cafeteria',
        position: { yaw: '103.9deg', pitch: '-16.3deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Cafeteria Hallway</div><div class="vt-nav-arrow" title="Walk to Cafeteria Hallway"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Cafeteria Hallway',
        style: { cursor: 'pointer' },
        data: { targetNode: 'cafeteria' }
      }
    ]
  },
  'court': {
    id: 'court',
    name: 'Campus Court',
    description: 'The main sports and activity court.',
    top: '27.84%',
    left: '63.76%',
    panorama: '/images/SmartVirtualTour/COURT.jpg',
    markers: [
      {
        id: 'to_church',
        position: { yaw: '319.3deg', pitch: '-3.1deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Administrative Hallway</div><div class="vt-nav-arrow" title="Walk to Administrative Hallway"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Administrative Hallway',
        style: { cursor: 'pointer' },
        data: { targetNode: 'church' }
      },
      {
        id: 'to_cafeteria',
        position: { yaw: '117.3deg', pitch: '-7.6deg' },
        html: '<div class="vt-nav-container"><div class="vt-nav-label">Cafeteria Hallway</div><div class="vt-nav-arrow" title="Walk to Cafeteria Hallway"></div></div>',
        anchor: 'center center',
        tooltip: 'Walk to Cafeteria Hallway',
        style: { cursor: 'pointer' },
        data: { targetNode: 'cafeteria' }
      }
    ]
  }
};

export default function VirtualTour({ className = "" }) {
  const [viewMode, setViewMode] = useState('aerial'); // 'aerial' | '360'
  const [currentNodeId, setCurrentNodeId] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [tappedNode, setTappedNode] = useState(null);

  // Update viewer when the node changes
  const currentNode = NODES[currentNodeId] || NODES['cafeteria'];

  // Handle marker clicks to traverse nodes (PSV v5 API)
  const handleReady = (instance) => {
    const markersPlugin = instance.getPlugin(MarkersPlugin);

    if (markersPlugin) {
      markersPlugin.addEventListener('select-marker', ({ marker }) => {
        // PSV v5: try both data paths for compatibility
        const targetNode = marker?.data?.targetNode || marker?.config?.data?.targetNode;
        if (targetNode) {
          setCurrentNodeId(targetNode);
        }
      });
    }

    // --- YAW CALIBRATION HELPER ---
    // Click anywhere in the 360 view to log the exact yaw/pitch in the console.
    // Use this to fine-tune arrow positions if needed.
    instance.addEventListener('click', ({ data }) => {
      const yawDeg = (data.yaw * 180 / Math.PI).toFixed(1);
      const pitchDeg = (data.pitch * 180 / Math.PI).toFixed(1);
      console.log(
        `%c[VT Calibration] yaw: '${yawDeg}deg', pitch: '${pitchDeg}deg'`,
        'color: #D4AF37; font-weight: bold; font-size: 14px;'
      );
    });
  };

  const handleImageClickCoordLogger = (e) => {
    const rect = e.target.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const xPercent = ((x / rect.width) * 100).toFixed(2);
    const yPercent = ((y / rect.height) * 100).toFixed(2);

    console.log(`Node Coordinate -> top: '${yPercent}%', left: '${xPercent}%'`);
    alert(`Node Target Coordinates copied to console!\nTop: ${yPercent}%\nLeft: ${xPercent}%\n\nPaste these replacing the placeholder coordinates in VirtualTour.jsx NODES object.`);
  };

  // Handle node tap on mobile (toggle tooltip) or click to enter
  const handleNodeInteraction = (e, node) => {
    e.stopPropagation();
    // On mobile, first tap shows tooltip, second tap enters 360
    if ('ontouchstart' in window) {
      if (tappedNode === node.id) {
        // Second tap - enter 360 view
        setCurrentNodeId(node.id);
        setViewMode('360');
        setTappedNode(null);
      } else {
        // First tap - show tooltip
        setTappedNode(node.id);
        setHoveredNode(node.id);
      }
    } else {
      // Desktop - direct click enters 360
      setCurrentNodeId(node.id);
      setViewMode('360');
    }
  };

  // Clear tapped node when tapping elsewhere
  const handleContainerTap = (e) => {
    if (tappedNode) {
      setTappedNode(null);
      setHoveredNode(null);
    }
    // Calibration is a deliberate developer action, not a normal mobile tap.
    if (import.meta.env.DEV && e.altKey) handleImageClickCoordLogger(e);
  };

  if (viewMode === 'aerial') {
    return (
      <div className={`virtual-tour-container relative w-full h-full rounded-2xl overflow-hidden shadow-lg border border-gray-200 bg-[#E8EAE6] flex flex-col ${className}`}>
        {/* Header */}
        <div className="vt-header absolute top-3 left-3 z-10 bg-white/90 backdrop-blur px-3 py-1.5 rounded-xl shadow border border-gray-200 pointer-events-none">
          <span className="text-xs text-spus-green font-bold uppercase tracking-wider block">Smart Virtual Tour</span>
          <span className="vt-header-subtitle text-sm font-semibold text-gray-800">Select a Location</span>
        </div>

        {/* Aerial Image Container */}
        <div className="vt-aerial-area flex-1 w-full relative flex items-center justify-center p-2 sm:p-4">
          <div className="vt-aerial-wrapper relative inline-block max-w-full max-h-full">
            <img
              src="/images/SmartVirtualTour/SPUS_aerial_view.png"
              alt="SPUS Aerial View"
              className="vt-aerial-img max-h-[75vh] sm:max-h-[80vh] w-auto h-auto object-contain shadow-lg rounded-xl cursor-crosshair border border-gray-300 block"
              onClick={handleContainerTap}
            />

            {/* Render interactive nodes */}
            {Object.values(NODES).map(node => (
              <button type="button"
                key={node.id}
                className="vt-location-pin absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center group cursor-pointer z-10"
                style={{ top: node.top, left: node.left }}
                aria-label={`Preview ${node.name}`} aria-expanded={tappedNode === node.id}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => { if (tappedNode !== node.id) setHoveredNode(null); }}
                onClick={(e) => handleNodeInteraction(e, node)}
              >
                {/* Visual Pin */}
                <div className="relative">
                  <div className="absolute inset-0 bg-spus-gold rounded-full animate-ping opacity-75"></div>
                  <div className="vt-pin relative w-6 h-6 sm:w-7 sm:h-7 bg-spus-green border-2 sm:border-[3px] border-white rounded-full shadow-lg flex items-center justify-center text-white text-[10px] sm:text-xs font-bold ring-2 ring-spus-gold/50 hover:scale-110 transition-transform">
                    {node.id.charAt(0).toUpperCase()}
                  </div>
                </div>

                {/* Info Tooltip Hook into Hover */}
                <div className={`
                  vt-tooltip absolute top-8 sm:top-9 w-40 sm:w-48 bg-white/95 backdrop-blur shadow-xl rounded-xl p-2.5 sm:p-3 border border-gray-200/80
                  transition-all duration-200 ease-out origin-top pointer-events-none z-20
                  ${(hoveredNode === node.id || tappedNode === node.id) ? 'opacity-100 scale-100 translate-y-0' : 'opacity-0 scale-95 -translate-y-2'}
                `}>
                   <h4 className="font-bold text-spus-green mb-1 text-xs sm:text-sm">{node.name}</h4>
                   <p className="text-[10px] sm:text-xs text-gray-600 leading-tight border-b border-gray-100 pb-2 mb-2">{node.description}</p>
                   <div className="flex items-center gap-2 text-[9px] sm:text-[10px] font-bold text-spus-gold uppercase tracking-wider">
                     <MaterialIcon name="explore" size={14} color="var(--spus-gold)" /> {('ontouchstart' in window) ? 'Tap again to enter 360°' : 'Click to Enter 360°'}
                   </div>
                </div>
              </button>
            ))}
          </div>
        </div>
        <div className="vt-location-list" role="group" aria-label="Virtual tour locations">
          {Object.values(NODES).map(node => <button type="button" key={node.id}
            onClick={() => { setCurrentNodeId(node.id); setViewMode('360'); setTappedNode(null); }}>
            <MaterialIcon name="explore" size={18} />{node.name}
          </button>)}
        </div>
      </div>
    );
  }

  const plugins = [
    [MarkersPlugin, {
      markers: currentNode?.markers || []
    }]
  ];

  return (
    <div className={`virtual-tour-container vt-panorama-layout relative w-full h-full rounded-2xl overflow-hidden shadow-lg border border-gray-200 ${className}`}>
      <div className="vt-panorama-toolbar">
      {/* Overlay header */}
      <div className="vt-header absolute top-3 left-3 z-10 bg-white/90 backdrop-blur px-3 py-1.5 rounded-xl shadow border border-gray-200 flex flex-col pointer-events-none">
        <span className="text-xs text-spus-gold font-bold uppercase tracking-wider">Smart Virtual Tour</span>
        <span className="vt-header-subtitle text-sm font-semibold text-gray-800">{currentNode?.name}</span>
      </div>

      <button
        className="vt-back-btn absolute top-4 left-1/2 -translate-x-1/2 z-30 bg-white/90 backdrop-blur shadow-lg py-2 px-4 sm:px-6 rounded-2xl font-bold flex items-center gap-2 hover:bg-white hover:scale-105 border border-spus-gold/30 text-spus-green text-sm transition-all active:scale-95 group"
        onClick={() => setViewMode('aerial')}
      >
        <MaterialIcon name="arrow_back" size={18} color="var(--spus-green)" className="group-hover:-translate-x-0.5 transition-transform" /> 
        <span className="vt-back-label">Back to Aerial View</span>
      </button>
      </div>

      {/* key={currentNodeId} forces a clean remount when navigating between nodes */}
      <div className="vt-viewer"><ReactPhotoSphereViewer
        key={currentNodeId}
        src={currentNode?.panorama}
        height="100%"
        width="100%"
        plugins={plugins}
        onReady={handleReady}
        navbar={['zoom', 'fullscreen']}
        defaultZoomLvl={30}
      /></div>
    </div>
  );
}
