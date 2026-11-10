import cv2
import numpy as np
import heapq
from scipy.spatial import cKDTree
import time

class CampusPathfinder:
    def __init__(self, pathway_img_path, base_map_path, scale=4, horizontal_alignment=None):
        """
        Initializes the pathfinder.
        scale: downsampling factor (4 means 4500px -> 1125px)
        """
        self.base_map_path = base_map_path
        self.scale = scale
        self.horizontal_alignment = horizontal_alignment
        
        # Step 1 & 2: Load mask and create Grid
        print(f"Initializing Routing Grid (Downsampled {scale}x)...")
        self.grid, self.dist_map = self._generate_walkable_grid(pathway_img_path)
        
        # Precompute KD-Tree for O(log n) point snapping
        walkable_y, walkable_x = np.nonzero(self.grid)
        if len(walkable_y) == 0:
            raise ValueError("No walkable paths found on the pathway map.")
        
        self.walkable_points = np.column_stack((walkable_y, walkable_x))
        self.kd_tree = cKDTree(self.walkable_points)
        print(f"Grid loaded! Cached {len(walkable_y)} navigable pixels at {scale}x scale.")

    def _generate_walkable_grid(self, img_path):
        """
        Extracts GREEN pathways, bridges gaps, downsamples, and calculates cost map.
        """
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Could not load image at: {img_path}")
        
        h_orig, w_orig = img.shape[:2]
        self.orig_size = (w_orig, h_orig)
            
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        mask = cv2.inRange(hsv, lower_green, upper_green)
        if self.horizontal_alignment is not None:
            # Align the existing pathways to the updated drawing's margins.
            # Keep the source pathway image and corridor layout unchanged.
            factor, offset_percent = self.horizontal_alignment
            matrix = np.float32([[factor, 0, w_orig * offset_percent / 100], [0, 1, 0]])
            mask = cv2.warpAffine(mask, matrix, (w_orig, h_orig), flags=cv2.INTER_NEAREST)
        
        # BRIDGE GAPS aggressively before downsampling
        gap_bridge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
        mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, gap_bridge_kernel)
        
        # DOWNSAMPLE for speed
        if self.scale > 1:
            new_w = w_orig // self.scale
            new_h = h_orig // self.scale
            mask_closed = cv2.resize(mask_closed, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
        
        # Binary grid: 1 for walkable
        grid = (mask_closed > 0).astype(np.uint8)
        
        # Calculate Distance Transform
        dist_map = cv2.distanceTransform(mask_closed, cv2.DIST_L2, 5)
        max_dist = np.max(dist_map)
        if max_dist > 0:
            dist_map = dist_map / max_dist
            
        return grid, dist_map

    def snap_coordinate(self, x, y):
        """
        Snaps original coordinates to the nearest walkable point on the DOWNSAMPLED grid.
        """
        # Scale input point to grid space
        gx, gy = x // self.scale, y // self.scale
        
        # Prevent out of bounds
        rows, cols = self.grid.shape
        gx = max(0, min(gx, cols - 1))
        gy = max(0, min(gy, rows - 1))

        if self.grid[gy, gx] == 1:
            return (gx, gy)
            
        # Query nearest point in scaled space
        distance, index = self.kd_tree.query([gy, gx])
        snapped_y, snapped_x = self.walkable_points[index]
        return int(snapped_x), int(snapped_y)

    def calculate_path(self, start_x, start_y, end_x, end_y):
        """
        A* Algorithm on the downsampled grid.
        Returns coordinates scaled back to original image size.
        """
        st_x, st_y = self.snap_coordinate(start_x, start_y)
        en_x, en_y = self.snap_coordinate(end_x, end_y)
        
        pq = [(0, 0, st_y, st_x, None)]
        came_from = {}
        g_score = { (st_y, st_x): 0 }
        
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        diagonals = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        rows, cols = self.grid.shape
        closed = set()
        # The smallest step cost is 0.2. Use an admissible octile heuristic
        # so a settled node never needs to be expanded again.
        min_cost = float(np.min(2.0 * (1.1 - self.dist_map[self.grid > 0])))
        
        def h(x1, y1, x2, y2):
            dx, dy = abs(x1 - x2), abs(y1 - y2)
            return min_cost * (max(dx, dy) + 0.414 * min(dx, dy))
            
        while pq:
            _, g, y, x, parent = heapq.heappop(pq)
            if (y, x) in closed or g > g_score[(y, x)]:
                continue
            closed.add((y, x))
            
            if (y, x) == (en_y, en_x):
                path = []
                curr = (y, x)
                while curr is not None:
                    # UPSCALE back to original coordinate space
                    path.append((int(curr[1] * self.scale), int(curr[0] * self.scale)))
                    curr = came_from.get(curr)
                return path[::-1]
                
            for dy, dx in directions + diagonals:
                ny, nx = y + dy, x + dx
                
                if 0 <= ny < rows and 0 <= nx < cols and self.grid[ny, nx] == 1 and (ny, nx) not in closed:
                    weight = 1.414 if (dy != 0 and dx != 0) else 1.0
                    cost_factor = 2.0 * (1.1 - self.dist_map[ny, nx]) 
                    
                    new_g = g + (weight * cost_factor)
                    if new_g < g_score.get((ny, nx), float('inf')):
                        came_from[(ny, nx)] = (y, x)
                        g_score[(ny, nx)] = new_g
                        f_score = new_g + h(nx, ny, en_x, en_y)
                        heapq.heappush(pq, (f_score, new_g, ny, nx, (y, x)))
                        
        return []

    def generate_visual_overlay(self, path, output_image_path):
        """
        Step 5: Visual Overlay
        Take the path array and draw a thick red line on the clean Base Map.
        """
        img = cv2.imread(self.base_map_path)
        if img is None or not path:
            return False
            
        # Routing pixels use the mask resolution; the drawing can be larger.
        orig_w, orig_h = self.orig_size
        image_h, image_w = img.shape[:2]
        pts = np.array([(x * image_w / orig_w, y * image_h / orig_h)
                        for x, y in path], np.int32)
        pts = pts.reshape((-1, 1, 2))
        
        cv2.polylines(img, [pts], isClosed=False, color=(0, 0, 255), thickness=10)
        cv2.imwrite(output_image_path, img)
        return True

if __name__ == "__main__":
    PATHWAY_MAP = r"C:\Dex\CAPSTONE\paulibot\images\2D_Mapping\ST.PAUL MAP_PATHWAY.png"
    BASE_MAP = r"C:\Dex\CAPSTONE\paulibot\images\2D_Mapping\ST.PAUL MAP (1).png"
    OUTPUT_MAP = r"C:\Dex\CAPSTONE\paulibot\images\2D_Mapping\ST.PAUL MAP_RESULT.png"
    
    pathfinder = CampusPathfinder(PATHWAY_MAP, BASE_MAP)
    
    # Randomly test routing across the map using (X, Y) layout from React
    print("Testing routing...")
    route = pathfinder.calculate_path(start_x=2754, start_y=620, end_x=2117, end_y=1782)
    
    if route:
        print(f"Path successfully drawn! Route length: {len(route)} pixels.")
        pathfinder.generate_visual_overlay(route, OUTPUT_MAP)
    else:
        print("Path blocked!")
