/**
 * Dijkstra's Shortest Path Algorithm
 * ====================================
 * Finds the shortest path between two campus nodes.
 * Pure frontend implementation — no backend needed for the small campus graph.
 */

import { CAMPUS_NODES, buildAdjacencyList } from '../data/campusGraph';

/**
 * Find the shortest path between two nodes using Dijkstra's algorithm.
 * 
 * @param {string} startId - Starting node ID
 * @param {string} endId   - Destination node ID
 * @returns {{ path: string[], distance: number, steps: Array<{from: string, to: string, instruction: string}> } | null}
 */
export function findShortestPath(startId, endId) {
  if (!CAMPUS_NODES[startId] || !CAMPUS_NODES[endId]) {
    console.warn(`Invalid node ID: ${startId} or ${endId}`);
    return null;
  }

  if (startId === endId) {
    return { path: [startId], distance: 0, steps: [] };
  }

  const adj = buildAdjacencyList();

  // Dijkstra init
  const dist = {};
  const prev = {};
  const visited = new Set();

  Object.keys(CAMPUS_NODES).forEach(id => {
    dist[id] = Infinity;
    prev[id] = null;
  });
  dist[startId] = 0;

  // Simple priority queue via unvisited set (fine for ~30 nodes)
  while (true) {
    // Find unvisited node with smallest distance
    let current = null;
    let currentDist = Infinity;

    for (const id of Object.keys(CAMPUS_NODES)) {
      if (!visited.has(id) && dist[id] < currentDist) {
        current = id;
        currentDist = dist[id];
      }
    }

    if (current === null || current === endId) break;

    visited.add(current);

    // Relax neighbors
    for (const { node: neighbor, weight } of (adj[current] || [])) {
      if (visited.has(neighbor)) continue;

      const newDist = dist[current] + weight;
      if (newDist < dist[neighbor]) {
        dist[neighbor] = newDist;
        prev[neighbor] = current;
      }
    }
  }

  // Reconstruct path
  if (dist[endId] === Infinity) {
    console.warn(`No path found from ${startId} to ${endId}`);
    return null;
  }

  const path = [];
  let node = endId;
  while (node !== null) {
    path.unshift(node);
    node = prev[node];
  }

  // Generate human-readable step-by-step directions
  const steps = generateDirections(path);

  return {
    path,
    distance: dist[endId],
    steps,
  };
}

/**
 * Generate human-readable walking directions from a path.
 */
function generateDirections(path) {
  if (path.length < 2) return [];

  const steps = [];

  steps.push({
    from: null,
    to: path[0],
    nodeId: path[0],
    instruction: `Start at ${CAMPUS_NODES[path[0]].name}`,
    icon: 'near_me',
  });

  for (let i = 1; i < path.length - 1; i++) {
    steps.push({
      from: path[i - 1],
      to: path[i],
      nodeId: path[i],
      instruction: `Walk to ${CAMPUS_NODES[path[i]].name}`,
      icon: 'chevron_right',
    });
  }

  steps.push({
    from: path[path.length - 2],
    to: path[path.length - 1],
    nodeId: path[path.length - 1],
    instruction: `Arrive at ${CAMPUS_NODES[path[path.length - 1]].name}`,
    icon: 'flag',
  });

  return steps;
}

/**
 * Estimate walking time in minutes from path distance.
 * Assumes ~5% of map width per ~20 seconds of walking.
 */
export function estimateWalkingTime(distance) {
  // distance is in percentage units; rough conversion:
  // 10 percentage units ≈ 1 minute of walking
  const minutes = Math.ceil(distance / 10);
  return Math.max(1, minutes);
}
