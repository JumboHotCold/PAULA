// Picker visibility affects location choices only; pins and pathways stay intact.
const HIDDEN_CHOICES = new Set(['restroom_left', 'cathedral', 'open_court', 'san_nicolas_bldg']);

export function sortCampusLocations(nodes) {
  return Object.values(nodes).filter(node => node.type !== 'waypoint')
    .sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base', numeric: true }));
}

export function campusLocationChoices(nodes, query = '') {
  const search = query.trim().toLowerCase();
  return sortCampusLocations(nodes).filter(node => !HIDDEN_CHOICES.has(node.id) && (
    node.name.toLowerCase().includes(search) || node.aliases.some(alias => alias.toLowerCase().includes(search))
  ));
}
