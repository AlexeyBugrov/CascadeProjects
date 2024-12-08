import cv2
import numpy as np
from pathlib import Path
import json
import signal
import sys
import time

class RegionSelector:
    def __init__(self, image_path):
        self.image_path = Path(image_path)
        self.image = cv2.imdecode(
            np.fromfile(str(self.image_path), dtype=np.uint8),
            cv2.IMREAD_COLOR
        )
        if self.image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        self.original_image = self.image.copy()
        self.window_w = 1024
        self.window_h = 768
        
        # Initialize regions first
        self.regions = {
            'dark': [],    # Dark regions (red)
            'light': [],   # Light regions (green)
            'work': []     # Work area (yellow)
        }
        self.current_region = 'dark'
        
        # Colors (BGR)
        self.colors = {
            'dark': (0, 0, 255),     # Red
            'light': (0, 255, 0),    # Green
            'work': (0, 255, 255)    # Yellow
        }
        
        # Scroll positions
        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_dragging_x = False
        self.scroll_dragging_y = False
        self.scroll_start_x = None
        self.scroll_start_y = None
        
        # Drawing state
        self.drawing = False
        self.start_point = None
        self.current_point = None
        
        # Region editing
        self.selected_corner = None
        self.selected_region = None
        self.selected_region_type = None
        self.editing = False
        
        # History for undo
        self.history = []
        self.save_state()
        
        # Create window
        cv2.namedWindow('Region Selector', cv2.WINDOW_NORMAL)
        cv2.setMouseCallback('Region Selector', self.mouse_callback)
        cv2.resizeWindow('Region Selector', 1024, 768)
        
        # Handle Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C signal"""
        print("\nExiting...")
        cv2.destroyAllWindows()
        sys.exit(0)
    
    def save_state(self):
        """Save current state for undo"""
        state = {region_type: [rect.copy() for rect in rects] 
                for region_type, rects in self.regions.items()}
        self.history.append(state)
        # Keep last 50 states
        if len(self.history) > 50:
            self.history.pop(0)

    def undo(self):
        """Undo last action"""
        if len(self.history) > 1:
            self.history.pop()  # Remove current state
            last_state = self.history[-1]
            self.regions = {region_type: [rect.copy() for rect in rects] 
                          for region_type, rects in last_state.items()}
            self.update_display()

    def find_nearest_corner(self, x, y, max_dist=10):
        """Find nearest corner of any region"""
        nearest_dist = max_dist
        nearest_corner = None
        nearest_region = None
        nearest_region_type = None
        
        for region_type, regions in self.regions.items():
            for i, rect in enumerate(regions):
                for j, point in enumerate(rect):
                    dx = point[0] - x
                    dy = point[1] - y
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest_corner = j
                        nearest_region = i
                        nearest_region_type = region_type
        
        return nearest_corner, nearest_region, nearest_region_type

    def maintain_rectangle(self, rect, corner_idx, new_pos):
        """Maintain rectangular shape when moving corners"""
        new_rect = rect.copy()
        new_rect[corner_idx] = new_pos
        
        # Corner pairs that should move together (opposite corners stay fixed)
        if corner_idx == 0:  # Top-left
            new_rect[3][0] = new_pos[0]  # Bottom-left x
            new_rect[1][1] = new_pos[1]  # Top-right y
        elif corner_idx == 1:  # Top-right
            new_rect[2][0] = new_pos[0]  # Bottom-right x
            new_rect[0][1] = new_pos[1]  # Top-left y
        elif corner_idx == 2:  # Bottom-right
            new_rect[1][0] = new_pos[0]  # Top-right x
            new_rect[3][1] = new_pos[1]  # Bottom-left y
        else:  # Bottom-left
            new_rect[0][0] = new_pos[0]  # Top-left x
            new_rect[2][1] = new_pos[1]  # Bottom-right y
            
        return new_rect

    def mouse_callback(self, event, x, y, flags, param):
        """Mouse event handler"""
        
        # Handle vertical scrollbar
        scrollbar_y_x = self.window_w - 20
        if x >= scrollbar_y_x and y <= self.window_h - 20:
            if event == cv2.EVENT_LBUTTONDOWN:
                self.scroll_dragging_y = True
                self.scroll_start_y = y
            elif event == cv2.EVENT_LBUTTONUP:
                self.scroll_dragging_y = False
            elif event == cv2.EVENT_MOUSEMOVE and self.scroll_dragging_y:
                if self.scroll_start_y is not None:
                    delta = y - self.scroll_start_y
                    self.scroll_y = max(0, min(
                        self.scroll_y + delta,
                        max(0, self.image.shape[0] - self.window_h)
                    ))
                    self.scroll_start_y = y
                    self.update_display()
            return
            
        # Handle horizontal scrollbar
        scrollbar_x_y = self.window_h - 20
        if y >= scrollbar_x_y and x <= self.window_w - 20:
            if event == cv2.EVENT_LBUTTONDOWN:
                self.scroll_dragging_x = True
                self.scroll_start_x = x
            elif event == cv2.EVENT_LBUTTONUP:
                self.scroll_dragging_x = False
            elif event == cv2.EVENT_MOUSEMOVE and self.scroll_dragging_x:
                if self.scroll_start_x is not None:
                    delta = x - self.scroll_start_x
                    self.scroll_x = max(0, min(
                        self.scroll_x + delta,
                        max(0, self.image.shape[1] - self.window_w)
                    ))
                    self.scroll_start_x = x
                    self.update_display()
            return
            
        # Handle mouse wheel
        if event == cv2.EVENT_MOUSEWHEEL:
            if flags > 0:
                self.scroll_y = max(0, self.scroll_y - 30)
            else:
                self.scroll_y = min(
                    max(0, self.image.shape[0] - self.window_h),
                    self.scroll_y + 30
                )
            self.update_display()
            return
            
        # Handle Shift + mouse wheel
        if flags & cv2.EVENT_FLAG_SHIFTKEY and event == cv2.EVENT_MOUSEWHEEL:
            if flags > 0:
                self.scroll_x = max(0, self.scroll_x - 30)
            else:
                self.scroll_x = min(
                    max(0, self.image.shape[1] - self.window_w),
                    self.scroll_x + 30
                )
            self.update_display()
            return

        # Adjust coordinates for scroll
        x = x + self.scroll_x
        y = y + self.scroll_y
        
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if clicking near a corner
            corner, region, region_type = self.find_nearest_corner(x, y)
            if corner is not None:
                self.editing = True
                self.selected_corner = corner
                self.selected_region = region
                self.selected_region_type = region_type
            else:
                self.drawing = True
                self.start_point = (x, y)
                self.current_point = (x, y)
            
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.editing and self.selected_corner is not None:
                # Update corner position maintaining rectangle shape
                rect = self.regions[self.selected_region_type][self.selected_region]
                new_rect = self.maintain_rectangle(rect, self.selected_corner, [x, y])
                self.regions[self.selected_region_type][self.selected_region] = new_rect
                self.update_display()
            elif self.drawing:
                self.current_point = (x, y)
                self.update_display()
            
        elif event == cv2.EVENT_LBUTTONUP:
            if self.editing:
                self.editing = False
                self.selected_corner = None
                self.selected_region = None
                self.selected_region_type = None
                self.save_state()
            elif self.drawing and self.start_point and self.current_point:
                if abs(self.start_point[0] - self.current_point[0]) > 5 and \
                   abs(self.start_point[1] - self.current_point[1]) > 5:
                    rect = self.get_rect_points(self.start_point, self.current_point)
                    self.regions[self.current_region].append(rect)
                    self.save_state()
            
            self.drawing = False
            self.start_point = None
            self.current_point = None
            self.update_display()

    def get_rect_points(self, start, end):
        """Get 4 points of rectangle"""
        return np.array([
            [min(start[0], end[0]), min(start[1], end[1])],  # Top left
            [max(start[0], end[0]), min(start[1], end[1])],  # Top right
            [max(start[0], end[0]), max(start[1], end[1])],  # Bottom right
            [min(start[0], end[0]), max(start[1], end[1])]   # Bottom left
        ], dtype=np.int32)

    def update_display(self):
        """Update display"""
        # Create display canvas
        display = np.zeros((self.window_h, self.window_w, 3), dtype=np.uint8)
        display[:, :] = (30, 30, 30)  # Dark background
        
        # Draw mode indicator at the top
        mode_color = self.colors[self.current_region]
        cv2.rectangle(display,
                     (0, 0),
                     (self.window_w, 5),
                     mode_color, -1)
        
        # Calculate visible region
        y1 = self.scroll_y
        y2 = min(y1 + self.window_h - 20, self.image.shape[0])
        x1 = self.scroll_x
        x2 = min(x1 + self.window_w - 20, self.image.shape[1])
        
        # Draw visible part of the image
        visible_image = self.original_image[y1:y2, x1:x2]
        if visible_image.shape[0] > 0 and visible_image.shape[1] > 0:
            display[5:visible_image.shape[0]+5, :visible_image.shape[1]] = visible_image
        
        # Draw regions
        for region_type, regions in self.regions.items():
            color = self.colors[region_type]
            for i, rect in enumerate(regions):
                # Adjust coordinates for scroll
                adjusted_rect = rect.copy()
                adjusted_rect[:, 0] -= self.scroll_x
                adjusted_rect[:, 1] -= self.scroll_y
                
                # Only draw if region is visible
                if np.any((adjusted_rect[:, 1] >= 0) & (adjusted_rect[:, 1] < self.window_h) &
                         (adjusted_rect[:, 0] >= 0) & (adjusted_rect[:, 0] < self.window_w)):
                    cv2.polylines(display, [adjusted_rect], True, color, 2)
                    for j, point in enumerate(adjusted_rect):
                        if 0 <= point[1] < self.window_h and 0 <= point[0] < self.window_w:
                            # Highlight selected corner
                            if (self.selected_region == i and 
                                self.selected_region_type == region_type and 
                                self.selected_corner == j):
                                cv2.circle(display, tuple(point), 6, (255, 255, 255), -1)
                            cv2.circle(display, tuple(point), 4, color, -1)
        
        # Draw current rectangle
        if self.drawing and self.start_point and self.current_point:
            color = self.colors[self.current_region]
            start = (self.start_point[0] - self.scroll_x, self.start_point[1] - self.scroll_y)
            current = (self.current_point[0] - self.scroll_x, self.current_point[1] - self.scroll_y)
            rect = self.get_rect_points(start, current)
            cv2.polylines(display, [rect], True, color, 2)
            for point in rect:
                if 0 <= point[1] < self.window_h and 0 <= point[0] < self.window_w:
                    cv2.circle(display, tuple(point), 4, color, -1)
        
        # Draw scrollbars if needed
        # Vertical scrollbar
        if self.image.shape[0] > self.window_h:
            # Background
            cv2.rectangle(display, 
                         (self.window_w - 20, 0),
                         (self.window_w, self.window_h - 20),
                         (60, 60, 60), -1)
            
            # Thumb
            total_height = self.image.shape[0]
            thumb_height = max(40, int((self.window_h - 20) * (self.window_h - 20) / total_height))
            thumb_pos = int(self.scroll_y * (self.window_h - 20 - thumb_height) / (total_height - self.window_h))
            cv2.rectangle(display,
                         (self.window_w - 18, thumb_pos),
                         (self.window_w - 2, thumb_pos + thumb_height),
                         (120, 120, 120), -1)
        
        # Horizontal scrollbar
        if self.image.shape[1] > self.window_w:
            # Background
            cv2.rectangle(display, 
                         (0, self.window_h - 20),
                         (self.window_w - 20, self.window_h),
                         (60, 60, 60), -1)
            
            # Thumb
            total_width = self.image.shape[1]
            thumb_width = max(40, int((self.window_w - 20) * (self.window_w - 20) / total_width))
            thumb_pos = int(self.scroll_x * (self.window_w - 20 - thumb_width) / (total_width - self.window_w))
            cv2.rectangle(display,
                         (thumb_pos, self.window_h - 18),
                         (thumb_pos + thumb_width, self.window_h - 2),
                         (120, 120, 120), -1)
        
        cv2.imshow('Region Selector', display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # q or ESC
            cv2.destroyAllWindows()
            sys.exit(0)
        elif key == ord('1'):
            self.current_region = 'dark'
        elif key == ord('2'):
            self.current_region = 'light'
        elif key == ord('3'):
            self.current_region = 'work'
        elif key == ord('s'):
            self.save_regions()
        elif key == ord('c'):
            self.clear_regions()
            self.save_state()
        elif key == ord('r'):
            self.undo()

    def save_image(self, image, path):
        """Save image with error handling"""
        try:
            # Convert path to string if it's a Path object
            path_str = str(path)
            # Use imencode/imwrite for reliable saving
            is_success, im_buf_arr = cv2.imencode(".png", image)
            if is_success:
                im_buf_arr.tofile(path_str)
                return True
            else:
                print(f"Error encoding image: {path}")
                return False
        except Exception as e:
            print(f"Error saving image: {path}")
            print(f"Error details: {str(e)}")
            return False

    def save_regions(self):
        """Save selected regions to separate files"""
        try:
            # Get the directory where the original image is located
            base_save_dir = self.image_path.parent / 'selected_regions'
            base_save_dir.mkdir(exist_ok=True)
            
            # Get timestamp for unique directory name
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_dir = base_save_dir / timestamp
            save_dir.mkdir(exist_ok=True)
            
            print(f"\nOriginal image path: {self.image_path}")
            print(f"Save directory: {save_dir}")
            
            # Save a copy of the original image
            original_copy_path = save_dir / f"original_{self.image_path.name}"
            if self.save_image(self.original_image, original_copy_path):
                print(f"Saved copy of original image: {original_copy_path}")
            
            all_regions_info = {}
            
            for region_type, regions in self.regions.items():
                if not regions:  # Skip if no regions of this type
                    continue
                
                # Create type-specific directory
                type_dir = save_dir / region_type
                type_dir.mkdir(exist_ok=True)
                print(f"\nProcessing {region_type} regions:")
                
                regions_info = []
                for i, rect in enumerate(regions, 1):
                    # Get region bounds
                    x_coords = rect[:, 0]
                    y_coords = rect[:, 1]
                    x1, x2 = min(x_coords), max(x_coords)
                    y1, y2 = min(y_coords), max(y_coords)
                    
                    # Extract and save region
                    region = self.original_image[y1:y2, x1:x2]
                    if region.size > 0:  # Check if region is valid
                        # Save region image
                        region_filename = f"{region_type}_{i}.png"
                        region_path = type_dir / region_filename
                        
                        if self.save_image(region, region_path):
                            print(f"  Saved region {i}: {region_filename} ({region.shape[1]}x{region.shape[0]} px)")
                            
                            # Store region info
                            regions_info.append({
                                'id': i,
                                'filename': region_filename,
                                'type': region_type,
                                'coordinates': rect.tolist(),
                                'bounds': {
                                    'x1': int(x1),
                                    'y1': int(y1),
                                    'x2': int(x2),
                                    'y2': int(y2),
                                    'width': int(x2 - x1),
                                    'height': int(y2 - y1)
                                }
                            })
                
                all_regions_info[region_type] = regions_info
                print(f"  Total {region_type} regions: {len(regions_info)}")
            
            # Save all coordinates and metadata to a single JSON
            if all_regions_info:
                metadata = {
                    'timestamp': timestamp,
                    'original_image': self.image_path.name,
                    'image_size': {
                        'width': self.original_image.shape[1],
                        'height': self.original_image.shape[0]
                    },
                    'regions': all_regions_info
                }
                
                json_path = save_dir / 'regions_info.json'
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                print(f"\nSaved regions metadata to: {json_path}")
        
        except Exception as e:
            print(f"Error during saving process: {str(e)}")

    def clear_regions(self):
        """Clear all regions"""
        self.regions = {k: [] for k in self.regions}
        self.update_display()

    def run(self):
        print("Instructions:")
        print("1: Select dark region (red)")
        print("2: Select light region (green)")
        print("3: Select work area (yellow)")
        print("LMB: Draw rectangle (click and drag)")
        print("Mouse wheel: Vertical scroll")
        print("Shift + wheel: Horizontal scroll")
        print("S: Save regions")
        print("C: Clear all regions")
        print("Q/ESC: Exit")
        print("R: Undo")
        
        while True:
            try:
                self.update_display()
            except KeyboardInterrupt:
                print("\nExiting...")
                cv2.destroyAllWindows()
                sys.exit(0)

if __name__ == "__main__":
    try:
        from config import FILE_SETTINGS
        image_path = FILE_SETTINGS['IMAGE_PATH']
        selector = RegionSelector(image_path)
        selector.run()
    except Exception as e:
        print(f"Error: {str(e)}")
