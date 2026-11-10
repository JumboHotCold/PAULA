import os
from django.conf import settings
from .pathfinding_engine import CampusPathfinder

# Singleton instance of the pathfinder to ensure heavy processing (grids/distances)
# only happens once during the server lifecycle.
_pathfinder_instance = None

def get_pathfinder():
    global _pathfinder_instance
    if _pathfinder_instance is None:
        # Load the paths dynamically based on the Django BASE_DIR
        base_dir = settings.BASE_DIR
        pathway_img_path = os.path.join(base_dir, 'images', '2D_Mapping', 'ST.PAUL MAP_PATHWAY.png')
        base_map_path = os.path.join(base_dir, 'images', '2D_Mapping', 'ST.PAUL-2D MAP.jpg')
        
        _pathfinder_instance = CampusPathfinder(
            pathway_img_path, base_map_path, scale=4,
            horizontal_alignment=(0.9375, 3.1),
        )
        
    return _pathfinder_instance
