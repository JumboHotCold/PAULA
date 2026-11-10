/**
 * Campus Graph Data — Saint Paul University Surigao
 * ==================================================
 * Defines all navigable locations (nodes) and walkable paths (edges)
 * for Dijkstra's shortest-path campus navigation.
 *
 * COORDINATES: x/y are percentage-based (0-100) relative to the 2D map image.
 *   - x = left percentage (0% = left edge, 100% = right edge)
 *   - y = top percentage  (0% = top edge, 100% = bottom edge)
 *
 * NODE TYPES:
 *   - 'office', 'building', 'facility', 'landmark', 'college' = Real locations
 *   - 'waypoint' = Invisible corridor bend points (NOT shown in UI)
 *
 * CORRIDOR SYSTEM (based on ST.PAUL MAP_PATHWAY.png green highlights):
 *   1. Left vertical walkway        — Main Entrance → Cafeteria → Visitors Lodge → bottom
 *   2. Court area walkway            — broad area around left + bottom of open court
 *   3. Cathedral east path           — wrapping around right side of cathedral
 *   4. Center-south corridor         — from court/SP Building south to bottom hallway
 *   5. Bottom horizontal corridor    — the long office hallway (left → right)
 *   6. Right vertical corridor       — SAO/Student Lounge area down to Finance Office
 *   7. Upper-left zone               — connecting Main Entrance, Guidance, San Nicolas, CFO
 */

// =============================================================================
// CAMPUS NODES — Real Locations
// =============================================================================

export const CAMPUS_NODES = {

  // Locations added in the updated campus drawing.
  cbma: {
    id: 'cbma',
    name: 'College of Business Management and Accountancy',
    x: 7.2, y: 64.6,
    aliases: ['cbma', 'college of business management and accountancy', 'business management', 'accountancy'],
    type: 'college',
  },
  chs: {
    id: 'chs',
    name: 'College of Health Sciences',
    x: 87.6, y: 47.4,
    aliases: ['chs', 'college of health sciences', 'health sciences', 'nursing'],
    type: 'college',
  },
  maclab: {
    id: 'maclab',
    name: 'MacLab',
    x: 87, y: 60.3,
    aliases: ['maclab', 'mac lab', 'mac laboratory'],
    type: 'facility',
  },



  // ── ZONE A: Top-Left Wing ──
  main_entrance: {
    id: 'main_entrance',
    name: 'Main Entrance',
    x: 10.1, y: 23.8,
    aliases: ['main entrance', 'entrance', 'gate', 'main gate', 'front gate', 'pasukan'],
    type: 'landmark',
  },
  guidance_office: {
    id: 'guidance_office',
    name: 'Guidance Office',
    x: 20.7, y: 22.6,
    aliases: ['guidance office', 'guidance', 'counselor', 'counseling'],
    type: 'office',
  },
  restroom_left: {
    id: 'restroom_left',
    name: 'Restroom (Left Wing)',
    x: 5.1, y: 25,
    aliases: ['restroom', 'bathroom', 'cr', 'comfort room', 'toilet'],
    type: 'facility',
  },
  san_nicolas_bldg: {
    id: 'san_nicolas_bldg',
    name: 'San Nicolas Building',
    x: 11.4, y: 26.1,
    aliases: ['san nicolas', 'san nicolas building', 'sn building'],
    type: 'building',
  },
  cfo: {
    id: 'cfo',
    name: 'PRISM (CFO)',
    x: 16.7, y: 32,
    aliases: ['prism', 'prism (cfo)', 'prism cfo', 'cfo', 'campus front office', 'front office'],
    type: 'office',
  },
  restroom_lower: {
    id: 'restroom_lower',
    name: 'Restroom (Lower)',
    x: 10.3, y: 33.9,
    aliases: ['restroom lower', 'lower restroom', 'lower cr'],
    type: 'facility',
  },
  clinic: {
    id: 'clinic',
    name: 'Clinic',
    x: 20.1, y: 37.4,
    aliases: ['clinic', 'health center', 'infirmary', 'nurse', 'medical'],
    type: 'facility',
  },

  // ── ZONE B: Center Area ──
  cafeteria: {
    id: 'cafeteria',
    name: 'Cafeteria',
    x: 7.8, y: 43.5,
    aliases: ['cafeteria', 'canteen', 'kainan', 'food', 'dining'],
    type: 'facility',
  },
  visitors_lodge: {
    id: 'visitors_lodge',
    name: "Visitor's Lodge",
    x: 13, y: 50.5,
    aliases: ['visitors lodge', "visitor's lodge", 'visitor', 'lodge'],
    type: 'facility',
  },
  open_court: {
    id: 'open_court',
    name: 'Open Court',
    x: 25.9, y: 58.4,
    aliases: ['open court', 'court', 'basketball court', 'covered court', 'gym'],
    type: 'landmark',
  },
  cathedral: {
    id: 'cathedral',
    name: 'Cathedral',
    x: 45.1, y: 43.2,
    aliases: ['cathedral', 'church', 'chapel', 'simbahan'],
    type: 'landmark',
  },
  sp_building: {
    id: 'sp_building',
    name: 'St. Paul Building (2nd-4th Floor)',
    x: 37.4, y: 56,
    aliases: ['sp building', 'st paul building', 'saint paul building', 'sp bldg'],
    type: 'building',
  },

  // ── ZONE C: Bottom Hallway ──
  college_education: {
    id: 'college_education',
    name: 'College of Education, Arts & Science',
    x: 3.1, y: 64.6,
    aliases: ['college of education', 'education', 'arts and science', 'ceas'],
    type: 'college',
  },
  hr_office: {
    id: 'hr_office',
    name: 'Human Resource Management Office',
    x: 11.3, y: 64.6,
    aliases: ['hr', 'human resource', 'hrmo', 'human resources'],
    type: 'office',
  },
  dean_graduate: {
    id: 'dean_graduate',
    name: 'Dean Graduate School',
    x: 15.4, y: 64.6,
    aliases: ['dean', 'graduate school', 'dean graduate', 'graduate'],
    type: 'office',
  },
  presidents_office: {
    id: 'presidents_office',
    name: 'Office of the President',
    x: 19.4, y: 64.6,
    aliases: ['president', "president's office", 'office of the president', 'op'],
    type: 'office',
  },
  presidents_boardroom: {
    id: 'presidents_boardroom',
    name: "President's Boardroom",
    x: 23.5, y: 64.6,
    aliases: ['boardroom', "president's boardroom", 'meeting room'],
    type: 'office',
  },
  inspire: {
    id: 'inspire',
    name: 'INS PIRE',
    x: 27.4, y: 64.6,
    aliases: ['inspire', 'ins pire', 'international networking', 'scholarship office', 'partnership'],
    type: 'office',
  },
  community_dev: {
    id: 'community_dev',
    name: 'Community Development Services',
    x: 31.5, y: 64.6,
    aliases: ['community development', 'community services', 'cds'],
    type: 'office',
  },
  ccje: {
    id: 'ccje',
    name: 'College of Criminal Justice Education (CCJE)',
    x: 35.4, y: 64.6,
    aliases: ['ccje', 'criminal justice', 'criminology'],
    type: 'college',
  },
  ceit: {
    id: 'ceit',
    name: 'College of Engineering and Information Technology',
    x: 39.4, y: 64.6,
    aliases: ['ceit', 'engineering', 'information technology', 'it', 'computer science', 'coeit'],
    type: 'college',
  },
  snb_building: {
    id: 'snb_building',
    name: 'SNB Building',
    x: 46.7, y: 64.6,
    aliases: ['snb', 'snb building'],
    type: 'building',
  },
  registrar_office: {
    id: 'registrar_office',
    name: 'Registrar Office',
    x: 55.8, y: 59.7,
    aliases: ['registrar', "registrar's office", 'registrar office', 'registration', 'enrollment office'],
    type: 'office',
  },

  // ── ZONE D: Right Wing ──
  science_building: {
    id: 'science_building',
    name: 'Science Building',
    x: 63, y: 21.9,
    aliases: ['science building', 'science', 'laboratory', 'lab', 'science lab'],
    type: 'building',
  },
  sao: {
    id: 'sao',
    name: 'Student Affairs Office (SAO)',
    x: 82.3, y: 51.3,
    aliases: ['sao', 'student affairs', 'student affairs office'],
    type: 'office',
  },
  student_lounge_upper: {
    id: 'student_lounge_upper',
    name: 'Student Lounge (Upper)',
    x: 78.5, y: 51.3,
    aliases: ['student lounge', 'lounge', 'upper lounge', 'tambayan'],
    type: 'facility',
  },
  finance_office: {
    id: 'finance_office',
    name: 'Finance Office',
    x: 70.1, y: 60.3,
    aliases: ['finance', 'finance office', 'cashier', 'accounting', 'payment'],
    type: 'office',
  },
  student_lounge_lower: {
    id: 'student_lounge_lower',
    name: 'Student Lounge (Lower)',
    x: 77.4, y: 60.3,
    aliases: ['student lounge lower', 'lower lounge'],
    type: 'facility',
  },
  ict_office: {
    id: 'ict_office',
    name: 'ICT Office',
    x: 83, y: 60.3,
    aliases: ['ict', 'ict office', 'computer room', 'internet'],
    type: 'office',
  },
  music_room: {
    id: 'music_room',
    name: 'Music Room',
    x: 91.8, y: 60.3,
    aliases: ['music room', 'music', 'band room'],
    type: 'facility',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CORRIDOR WAYPOINTS
  // Based on green highlighted pathways in ST.PAUL MAP_PATHWAY.png
  // ═══════════════════════════════════════════════════════════════════════════

  // ── 1. Upper-Left Zone (green area around Main Entrance / San Nicolas) ──
  // The green shows a walkable zone around the Main Entrance, connecting
  // down to restrooms and across to guidance/san nicolas.
  wp_entrance_south: {
    id: 'wp_entrance_south', name: 'Entrance South',
    x: 7.5, y: 28, aliases: [], type: 'waypoint',
  },
  wp_upper_hall: {
    id: 'wp_upper_hall', name: 'Upper Hall Junction',
    x: 13, y: 28, aliases: [], type: 'waypoint',
  },

  // ── 2. Left Vertical Walkway ──
  // Green path going down the left edge from restroom area past cafeteria
  // to visitors lodge and continuing to bottom corridor.
  wp_left_mid: {
    id: 'wp_left_mid', name: 'Left Walk Mid',
    x: 3.5, y: 36, aliases: [], type: 'waypoint',
  },
  wp_left_lower: {
    id: 'wp_left_lower', name: 'Left Walk Lower',
    x: 3.5, y: 52, aliases: [], type: 'waypoint',
  },
  wp_left_bottom: {
    id: 'wp_left_bottom', name: 'Left Walk Bottom',
    x: 3.5, y: 60, aliases: [], type: 'waypoint',
  },

  // ── 3. Court Area Walkway ──
  // Court boundaries: left x≈14, right x≈35, top y≈37, bottom y≈51
  // ALL waypoints placed with 3% safety buffer OUTSIDE the court.
  // This guarantees no line segment can visually cross through the court.
  wp_court_left_upper: {
    id: 'wp_court_left_upper', name: 'Court Left Upper',
    x: 11, y: 36, aliases: [], type: 'waypoint',
  },
  wp_court_left_mid: {
    id: 'wp_court_left_mid', name: 'Court Left Mid',
    x: 11, y: 44, aliases: [], type: 'waypoint',
  },
  wp_court_left_lower: {
    id: 'wp_court_left_lower', name: 'Court Left Lower',
    x: 11, y: 54, aliases: [], type: 'waypoint',
  },
  wp_court_bottom_left: {
    id: 'wp_court_bottom_left', name: 'Court Bottom Left',
    x: 14, y: 54, aliases: [], type: 'waypoint',
  },
  wp_court_bottom_mid: {
    id: 'wp_court_bottom_mid', name: 'Court Bottom Mid',
    x: 24, y: 54, aliases: [], type: 'waypoint',
  },
  wp_court_bottom_right: {
    id: 'wp_court_bottom_right', name: 'Court Bottom Right',
    x: 36, y: 54, aliases: [], type: 'waypoint',
  },

  // ── 4. Cathedral East Path ──
  // Green wraps around the RIGHT side of the cathedral, connecting
  // the top area down to the court-bottom / SP building zone.
  wp_cathedral_ne: {
    id: 'wp_cathedral_ne', name: 'Cathedral NE',
    x: 53, y: 20, aliases: [], type: 'waypoint',
  },
  wp_cathedral_east: {
    id: 'wp_cathedral_east', name: 'Cathedral East',
    x: 55, y: 33, aliases: [], type: 'waypoint',
  },
  wp_cathedral_se: {
    id: 'wp_cathedral_se', name: 'Cathedral SE',
    x: 50, y: 44, aliases: [], type: 'waypoint',
  },

  // ── 5. Center-South Corridor ──
  // Green going from the court/SP building area south to the bottom hallway.
  wp_center_south: {
    id: 'wp_center_south', name: 'Center South',
    x: 37, y: 60, aliases: [], type: 'waypoint',
  },
  wp_center_bottom: {
    id: 'wp_center_bottom', name: 'Center Bottom Junction',
    x: 42, y: 63, aliases: [], type: 'waypoint',
  },

  // ── 6. Right Vertical Corridor ──
  // Green going from the SAO/Student Lounge area straight down
  // to the Finance Office on the bottom corridor.
  wp_right_mid: {
    id: 'wp_right_mid', name: 'Right Walk Mid',
    x: 78, y: 52, aliases: [], type: 'waypoint',
  },
  wp_right_bottom: {
    id: 'wp_right_bottom', name: 'Right Walk Bottom',
    x: 74, y: 58, aliases: [], type: 'waypoint',
  },

  // ── 7. Bottom Corridor Connector (between CEIT and Registrar) ──
  // The bottom hallway has a gap/turn near SNB building.
  wp_bottom_mid: {
    id: 'wp_bottom_mid', name: 'Bottom Mid Junction',
    x: 50, y: 63, aliases: [], type: 'waypoint',
  },
};

// =============================================================================
// CAMPUS EDGES
// =============================================================================
// ALL paths follow the green highlighted corridors from ST.PAUL MAP_PATHWAY.png.
// No edge ever cuts through a building.

export const CAMPUS_EDGES = [
  { from: 'college_education', to: 'cbma' },
  { from: 'cbma', to: 'hr_office' },
  { from: 'sao', to: 'chs' },
  { from: 'ict_office', to: 'maclab' },
  { from: 'maclab', to: 'music_room' },

  // ═══════════════════════════════════════════════
  // 1. UPPER-LEFT ZONE (Main Entrance area)
  // ═══════════════════════════════════════════════
  // Green area connects: Main Entrance, Guidance, San Nicolas, CFO, Restrooms
  { from: 'main_entrance', to: 'guidance_office' },      // Across the top of the zone
  { from: 'main_entrance', to: 'wp_entrance_south' },    // Down from entrance
  { from: 'guidance_office', to: 'wp_upper_hall' },       // Guidance to the hall junction
  { from: 'wp_entrance_south', to: 'wp_upper_hall' },    // Horizontal connector
  { from: 'wp_entrance_south', to: 'restroom_left' },    // Down to restroom
  { from: 'wp_upper_hall', to: 'san_nicolas_bldg' },     // To san nicolas
  { from: 'wp_upper_hall', to: 'cfo' },                  // Down to CFO
  { from: 'cfo', to: 'restroom_lower' },                 // CFO to lower restroom
  { from: 'cfo', to: 'wp_court_left_upper' },            // CFO to court entry
  { from: 'restroom_lower', to: 'wp_left_mid' },         // Restroom to left corridor

  // ═══════════════════════════════════════════════
  // 2. LEFT VERTICAL WALKWAY
  // ═══════════════════════════════════════════════
  // Green path down the left edge: Restroom → Cafeteria → Visitors Lodge → Bottom
  { from: 'restroom_left', to: 'wp_left_mid' },          // Restroom to left corridor
  { from: 'wp_left_mid', to: 'cafeteria' },              // Down to cafeteria
  { from: 'cafeteria', to: 'wp_left_lower' },            // Past cafeteria going south
  { from: 'wp_left_lower', to: 'visitors_lodge' },       // To visitors lodge
  { from: 'wp_left_lower', to: 'wp_left_bottom' },       // Continue south
  { from: 'visitors_lodge', to: 'wp_left_bottom' },      // Alt path from visitors lodge
  { from: 'wp_left_bottom', to: 'college_education' },   // Join bottom corridor

  // ═══════════════════════════════════════════════
  // 3. COURT AREA WALKWAY
  // ═══════════════════════════════════════════════
  // Path hugs the OUTSIDE of the court with a 3% safety buffer.
  // Court boundary: x=14..35, y=37..51
  // Left-side waypoints: x=11 (3% left of court)
  // Bottom waypoints: y=54 (3% below court)
  //
  // LEFT SIDE (vertical, x=11, outside the court's left edge):
  { from: 'clinic', to: 'wp_court_left_upper' },              // Clinic to court walkway
  { from: 'wp_court_left_upper', to: 'wp_court_left_mid' },   // Down left side (x=11)
  { from: 'wp_court_left_mid', to: 'wp_court_left_lower' },   // Continue down (x=11)
  //
  // CORNER TURN (left side → bottom):
  { from: 'wp_court_left_lower', to: 'wp_court_bottom_left' },// Turn corner (11,54)→(14,54)
  //
  // BOTTOM (horizontal, y=54, below the court's bottom edge):
  { from: 'wp_court_bottom_left', to: 'wp_court_bottom_mid' },// Along bottom (y=54)
  { from: 'wp_court_bottom_mid', to: 'wp_court_bottom_right' },// Continue right (y=54)
  //
  // CONNECTIONS from left corridor to court perimeter:
  { from: 'cafeteria', to: 'wp_court_left_mid' },             // Cafeteria to court left
  { from: 'wp_court_left_lower', to: 'visitors_lodge' },      // Court bottom-left to lodge
  //
  // Open Court is a SPUR only — NOT a through-path:
  { from: 'open_court', to: 'wp_court_bottom_mid' },          // Court center to perimeter

  // ═══════════════════════════════════════════════
  // 4. CATHEDRAL EAST PATH
  // ═══════════════════════════════════════════════
  // Green wraps around the right side of the cathedral
  { from: 'cathedral', to: 'wp_cathedral_ne' },          // Cathedral to NE path
  { from: 'wp_cathedral_ne', to: 'science_building' },   // NE path to Science Building
  { from: 'wp_cathedral_ne', to: 'wp_cathedral_east' },  // Down the east side
  { from: 'wp_cathedral_east', to: 'wp_cathedral_se' },  // Continue south-east
  { from: 'wp_cathedral_se', to: 'wp_court_bottom_right' }, // Join court bottom area

  // ═══════════════════════════════════════════════
  // 5. CENTER-SOUTH CORRIDOR
  // ═══════════════════════════════════════════════
  // Green from court/SP Building area south to bottom hallway
  { from: 'wp_court_bottom_right', to: 'sp_building' },  // Court bottom → SP building
  { from: 'sp_building', to: 'wp_center_south' },        // SP building → going south
  { from: 'wp_center_south', to: 'wp_center_bottom' },   // Continue south
  { from: 'wp_center_bottom', to: 'ceit' },              // Join bottom corridor at CEIT

  // ═══════════════════════════════════════════════
  // 6. BOTTOM HORIZONTAL CORRIDOR
  // ═══════════════════════════════════════════════
  // The main office hallway — clearly green all the way across
  { from: 'college_education', to: 'hr_office' },
  { from: 'hr_office', to: 'dean_graduate' },
  { from: 'dean_graduate', to: 'presidents_office' },
  { from: 'presidents_office', to: 'presidents_boardroom' },
  { from: 'presidents_boardroom', to: 'inspire' },
  { from: 'inspire', to: 'community_dev' },
  { from: 'community_dev', to: 'ccje' },
  { from: 'ccje', to: 'ceit' },
  // Gap between CEIT and Registrar — routed through SNB area
  { from: 'wp_center_bottom', to: 'wp_bottom_mid' },     // Center junction east
  { from: 'wp_bottom_mid', to: 'snb_building' },         // To SNB building
  { from: 'snb_building', to: 'registrar_office' },      // SNB to Registrar
  { from: 'wp_bottom_mid', to: 'registrar_office' },     // Direct path option
  // Continue east on bottom corridor
  { from: 'registrar_office', to: 'finance_office' },
  { from: 'finance_office', to: 'student_lounge_lower' },
  { from: 'student_lounge_lower', to: 'ict_office' },
  { from: 'ict_office', to: 'music_room' },

  // ═══════════════════════════════════════════════
  // 7. RIGHT VERTICAL CORRIDOR
  // ═══════════════════════════════════════════════
  // Green going from SAO/Student Lounge down to Finance Office
  { from: 'sao', to: 'student_lounge_upper' },           // SAO to Student Lounge
  { from: 'student_lounge_upper', to: 'wp_right_mid' },  // Down from Student Lounge
  { from: 'wp_right_mid', to: 'wp_right_bottom' },       // Continue south
  { from: 'wp_right_bottom', to: 'finance_office' },     // Join bottom corridor
];

// =============================================================================
// KEYWORD → NODE ID LOOKUP (excludes waypoints)
// =============================================================================

export const KEYWORD_TO_NODE = {};
Object.values(CAMPUS_NODES).forEach(node => {
  if (node.type === 'waypoint') return;
  node.aliases.forEach(alias => {
    KEYWORD_TO_NODE[alias.toLowerCase()] = node.id;
  });
});

/**
 * Resolve a user's free-text input to a campus node ID.
 */
export function resolveLocationFromText(input) {
  if (!input) return null;
  const lowerInput = input.toLowerCase().trim();

  if (KEYWORD_TO_NODE[lowerInput]) {
    return KEYWORD_TO_NODE[lowerInput];
  }

  for (const [alias, nodeId] of Object.entries(KEYWORD_TO_NODE)) {
    if (lowerInput.includes(alias) || alias.includes(lowerInput)) {
      return nodeId;
    }
  }

  return null;
}

/**
 * Calculate Euclidean distance between two nodes (for edge weights).
 */
export function calculateEdgeWeight(nodeA, nodeB) {
  const dx = nodeA.x - nodeB.x;
  const dy = nodeA.y - nodeB.y;
  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * Build adjacency list with auto-calculated weights from coordinates.
 */
export function buildAdjacencyList() {
  const adj = {};

  Object.keys(CAMPUS_NODES).forEach(id => {
    adj[id] = [];
  });

  CAMPUS_EDGES.forEach(({ from, to }) => {
    const nodeA = CAMPUS_NODES[from];
    const nodeB = CAMPUS_NODES[to];

    if (!nodeA || !nodeB) {
      console.warn(`Edge references unknown node: ${from} → ${to}`);
      return;
    }

    const weight = calculateEdgeWeight(nodeA, nodeB);

    adj[from].push({ node: to, weight });
    adj[to].push({ node: from, weight });
  });

  return adj;
}
