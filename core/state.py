from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, Qt

import os
import json
from PySide6.QtCore import QObject, Signal, QPointF
from PySide6.QtGui import QColor, QPainterPath

# The file where your settings will be saved permanently
CONFIG_FILE = "settings.json"

class StateManager(QObject):
    # --- SIGNALS ---
    tool_changed = Signal(str)          
    color_changed = Signal(QColor)      
    brush_changed = Signal(int, int)    
    style_changed = Signal(str)         
    action_triggered = Signal(str)      
    mode_changed = Signal(bool) 
    
    request_menu_context = Signal(str) 
    selection_changed = Signal(bool) 
    background_changed = Signal(QColor)
    board_state_changed = Signal(bool)

    # --- Fill Signals ---
    fill_toggled = Signal(bool)
    fill_color_changed = Signal(QColor)  # <--- Add this missing line!
    opacity_changed = Signal(int)
    font_changed = Signal(dict)
    text_style_changed = Signal(str)

    def __init__(self):
        super().__init__()
        
        # --- DYNAMIC SHORTCUTS MEMORY BANK ---
        self._shortcuts = {
            "increase_size": "F5",
            "decrease_size": "F6",
            "toggle_eraser": "F8",
            "toggle_cursor": "F9",
            "toggle_board": "F2",
            "toggle_lasso": "F3",
            "clear_canvas": "F4",
            "toggle_laser": "F7"
        }
        
        # Load any saved shortcuts from the JSON file
        self.load_settings()
        # -------------------------------------

        self.active_tool_id = "tool_pen_1"
        self.is_whiteboard_mode = False
        self.has_selection = False 
        
        # Changed to black and updated the transparent base to match
        self.board_color = QColor(0, 0, 0, 0) 
        self.last_board_color = QColor("black")
        
        # Default yellow-ish tint
        self.current_fill_color = QColor(255, 200, 0, 100) 
        self.laser_duration = 2.0 
        
        self.shape_tools = ["tool_line", "tool_arrow", "tool_rect", "tool_circle", "tool_polygon", "tool_star"]
        self.last_active_shape = "tool_line"

        default_mem = {"color": QColor("#6c5ce7"), "thickness": 3, "opacity": 255, "style": Qt.SolidLine, "fill_enabled": False}

        self.tool_states = {
            "tool_pen_1": { "color": QColor("#44ABFF"), "thickness": 3, "opacity": 255, "style": Qt.SolidLine, "fill_enabled": False },
            "tool_pen_2": { "color": QColor("#FF4444"), "thickness": 5, "opacity": 255, "style": Qt.SolidLine, "fill_enabled": False },
            "tool_hl":    { "color": QColor("#FFFF44"), "thickness": 20, "opacity": 100, "style": Qt.SolidLine, "fill_enabled": False },
            "tool_text":  { "color": QColor("#000000"), "thickness": 12, "opacity": 255, "style": Qt.SolidLine, "font_style": "Normal" },
            "tool_eraser": { "color": QColor("white"), "thickness": 30, "opacity": 255, "style": Qt.SolidLine },
            
            "tool_laser": { "color": QColor("#FF0000"), "thickness": 6, "opacity": 255, "style": Qt.SolidLine },

            "tool_line":    default_mem.copy(),
            "tool_arrow":   default_mem.copy(),
            "tool_rect":    default_mem.copy(),
            "tool_circle":  default_mem.copy(),
            "tool_polygon": default_mem.copy(),
            "tool_star":    default_mem.copy(),
            "tool_cursor":  default_mem.copy(),
            "tool_select_rect": {}, "tool_select_lasso": {}, "tool_pan": {},
            "default": { "color": QColor("black"), "thickness": 2, "opacity": 255, "style": Qt.SolidLine, "fill_enabled": False }
        }
        
        self.eraser_size = 30 
        self.eraser_type = "stroke" 

        self.color_map = {
            "set_black": "#000000", "set_dark_gray": "#333333", "set_dim_gray": "#555555",
            "set_gray": "#808080", "set_light_gray": "#AAAAAA", "set_silver": "#CCCCCC",
            "set_white": "#FFFFFF", "set_off_white": "#F5F5F5",
            "set_pink": "#FFC0CB", "set_rose": "#FF007F", "set_maroon": "#800000",
            "set_brick": "#B22222", "set_crimson": "#DC143C", "set_red": "#FF0000",
            "set_salmon": "#FA8072", "set_coral": "#FF7F50",
            "set_cyan": "#00FFFF", "set_sky": "#87CEEB", "set_navy": "#000080",
            "set_royal": "#4169E1", "set_midnight": "#191970", "set_blue": "#0000FF",
            "set_cornflower": "#6495ED", "set_ice": "#F0F8FF",
            "set_lime": "#00FF00", "set_pale_green": "#CCFFCC", "set_dark_green": "#004400",
            "set_olive": "#556B2F", "set_forest": "#228B22", "set_green": "#008000",
            "set_teal": "#008080", "set_neon": "#39FF14",
            "set_lavender": "#E6E6FA", "set_plum": "#DDA0DD", "set_magenta": "#FF00FF", "set_dark_purple": "#301934",
            "set_indigo": "#4B0082", "set_purple": "#800080", "set_violet": "#EE82EE", "set_orchid": "#DA70D6",
            "set_gold": "#FFD700", "set_orange": "#FFA500", "set_dark_orange": "#FF8C00", "set_brown": "#A52A2A",
            "set_chocolate": "#D2691E", "set_sienna": "#A0522D", "set_peach": "#FFDAB9", "set_tan": "#D2B48C"
        }


    def load_settings(self):
        """Loads the shortcuts from the JSON file when the app starts."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved_shortcuts = json.load(f)
                    # Merge the saved keys over the defaults
                    self._shortcuts.update(saved_shortcuts)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        """Writes the current shortcuts to the JSON file."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._shortcuts, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get_shortcut(self, action_name):
        return self._shortcuts.get(action_name, "")

    def set_shortcut(self, action_name, key_sequence_str):
        self._shortcuts[action_name] = key_sequence_str
        # Instantly save the file to the hard drive every time a key is changed!
        self.save_settings()

    @property
    def current_settings(self): return self.tool_states.get(self.active_tool_id, self.tool_states["default"])
    @property
    def current_color(self): return self.current_settings.get("color", QColor("black"))
    @property
    def current_thickness(self): return self.current_settings.get("thickness", 2)
    @property
    def current_opacity(self): return self.current_settings.get("opacity", 255)
    @property
    def current_style(self): return self.current_settings.get("style", Qt.SolidLine)
    @property
    def current_font_style(self): return self.current_settings.get("font_style", "Normal")
    @property
    def current_fill_enabled(self): return self.current_settings.get("fill_enabled", False)

    def set_selection_active(self, active: bool):
        if self.has_selection != active:
            self.has_selection = active
            self.selection_changed.emit(active)

    def sync_tool_properties(self, color=None, thickness=None, style=None, fill_color=None, is_filled=None):
        s = self.tool_states["tool_cursor"]
        if color: 
            s["color"] = QColor(color); self.color_changed.emit(s["color"])
        if thickness: 
            s["thickness"] = thickness; self.brush_changed.emit(thickness, s.get("opacity", 255))
        if style is not None: 
            s["style"] = style; self.style_changed.emit("sync")
        if fill_color:
            self.current_fill_color = QColor(fill_color); self.fill_color_changed.emit(self.current_fill_color)
        if is_filled is not None:
            s["fill_enabled"] = is_filled; self.fill_toggled.emit(is_filled)

    def is_key_active(self, key):
        if not key: return False
        if key == "toggle_board": return self.board_color.alpha() > 0
        if key == "toggle_tool_fill": return self.current_fill_enabled

        if key.startswith("set_board_"):
            if key == "set_board_transparent": return self.board_color.alpha() == 0
            if "opacity" in key: return False 
            map_key = key.replace("set_board_", "set_")
            if map_key in self.color_map:
                c1 = QColor(self.color_map[map_key]); c1.setAlpha(255)
                c2 = QColor(self.board_color); c2.setAlpha(255)
                return c1.name() == c2.name() and self.board_color.alpha() > 0
            return False

        if self.has_selection: source_settings = self.tool_states["tool_cursor"]
        else: source_settings = self.current_settings

        if key == self.active_tool_id: return True
        if key == "group_shapes" and self.active_tool_id in self.shape_tools: return True
        if key == "set_eraser_stroke" and self.eraser_type == "stroke" and "eraser" in self.active_tool_id: return True
        if key == "set_eraser_pixel" and self.eraser_type == "pixel" and "eraser" in self.active_tool_id: return True
        
        if key in self.color_map:
            t = QColor(self.color_map[key]); t.setAlpha(255)
            c = source_settings.get("color", QColor("black")); c.setAlpha(255)
            return t.name().upper() == c.name().upper()

        # [FIX] Fill Color Active Check - Ignore Alpha
        if key.startswith("set_fill_"):
            map_key = key.replace("set_fill_", "set_")
            if map_key in self.color_map:
                t = QColor(self.color_map[map_key])
                c = self.current_fill_color
                # Compare RGB only (HexRgb avoids the alpha component)
                return t.name(QColor.HexRgb).upper() == c.name(QColor.HexRgb).upper()

        if key.startswith("set_font_"): return key.replace("set_font_", "").lower() == source_settings.get("font_style", "Normal").lower()
        if key.startswith("set_style_"):
            style_str = key.replace("set_style_", "")
            mapping = { "solid": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine, "dashdot": Qt.DashDotLine }
            return mapping.get(style_str) == source_settings.get("style", Qt.SolidLine)

        return False

    def set_active_tool(self, action_key):
        if action_key == "group_shapes": action_key = self.last_active_shape
        if action_key in self.shape_tools: self.last_active_shape = action_key

        if action_key.startswith("set_laser_time_"):
            try:
                val = int(action_key.split("_")[-1]); self.laser_duration = float(val) 
            except ValueError: pass
            return

        if action_key == "toggle_tool_fill":
            new_state = not self.current_fill_enabled
            if self.has_selection:
                self.tool_states["tool_cursor"]["fill_enabled"] = new_state
            else:
                self.current_settings["fill_enabled"] = new_state
            self.fill_toggled.emit(new_state)
            return

        if action_key.startswith("set_fill_opacity_"):
            try:
                val = int(action_key.split("_")[-1])
                alpha = int((val / 100.0) * 255)
                new_col = QColor(self.current_fill_color)
                new_col.setAlpha(alpha)
                self.current_fill_color = new_col
                self.fill_color_changed.emit(new_col)
            except ValueError: pass
            return

        if action_key.startswith("set_fill_"):
            map_key = action_key.replace("set_fill_", "set_")
            if map_key in self.color_map:
                base_color = QColor(self.color_map[map_key])
                current_alpha = self.current_fill_color.alpha()
                base_color.setAlpha(current_alpha)
                self.current_fill_color = base_color
                self.fill_color_changed.emit(base_color)
            return

        if action_key == "toggle_board":
            if self.board_color.alpha() > 0:
                self.last_board_color = QColor(self.board_color); self.board_color.setAlpha(0)
            else:
                self.board_color = QColor(self.last_board_color)
                if self.board_color.alpha() == 0: self.board_color = QColor("black") # Updated fallback
            self.background_changed.emit(self.board_color); return

        elif action_key == "set_board_transparent":
            self.board_color.setAlpha(0); self.background_changed.emit(self.board_color); return
        
        elif action_key.startswith("set_board_opacity_"):
            try:
                val = int(action_key.split("_")[-1]); alpha = int((val / 100.0) * 255)
                if alpha == 0: alpha = 1 
                self.board_color.setAlpha(alpha); self.background_changed.emit(self.board_color)
            except ValueError: pass
            return

        elif action_key.startswith("set_board_"):
            map_key = action_key.replace("set_board_", "set_")
            if map_key in self.color_map:
                new_col = QColor(self.color_map[map_key])
                current_alpha = self.board_color.alpha()
                if current_alpha == 0: current_alpha = 255
                new_col.setAlpha(current_alpha); self.board_color = new_col; self.background_changed.emit(self.board_color)
            return

        if action_key.startswith("tool_"):
            self.active_tool_id = action_key; s = self.current_settings; self.tool_changed.emit(action_key)
            if "color" in s: self.color_changed.emit(s["color"])
            if "eraser" in action_key: self.brush_changed.emit(self.eraser_size, 255)
            elif "thickness" in s: self.brush_changed.emit(s["thickness"], s.get("opacity", 255))
            if "fill_enabled" in s: self.fill_toggled.emit(s["fill_enabled"])
        
        elif action_key.startswith("set_text_"):
            suffix = action_key.replace("set_text_", ""); size_map = {"small": 12, "medium": 24, "large": 48}
            if suffix in size_map:
                self.tool_states["tool_text"]["thickness"] = size_map[suffix]
                self.active_tool_id = "tool_text"; s = self.current_settings
                self.tool_changed.emit("tool_text"); self.brush_changed.emit(s["thickness"], s["opacity"])

        elif action_key in self.color_map:
            new_col = QColor(self.color_map[action_key]); new_col.setAlpha(self.current_opacity)
            if self.has_selection: self.tool_states["tool_cursor"]["color"] = new_col
            elif "color" in self.current_settings: self.current_settings["color"] = new_col
            self.color_changed.emit(new_col)
        
        elif action_key.startswith("set_thickness_"):
            try:
                val = int(action_key.split("_")[-1])
                if self.has_selection:
                    self.tool_states["tool_cursor"]["thickness"] = val
                    current_op = self.tool_states["tool_cursor"].get("opacity", 255)
                    self.brush_changed.emit(val, current_op)
                elif "thickness" in self.current_settings:
                    self.current_settings["thickness"] = val
                    self.brush_changed.emit(val, self.current_opacity)
            except ValueError: pass
        
        elif action_key.startswith("set_opacity_"):
            try:
                val = int(action_key.split("_")[-1]); alpha = int((val / 100.0) * 255)
                if self.has_selection:
                    c = self.tool_states["tool_cursor"]["color"]; c.setAlpha(alpha)
                    self.tool_states["tool_cursor"]["color"] = c; self.tool_states["tool_cursor"]["opacity"] = alpha
                    current_th = self.tool_states["tool_cursor"].get("thickness", 2)
                    self.brush_changed.emit(current_th, alpha); self.color_changed.emit(c)
                elif "opacity" in self.current_settings:
                    self.current_settings["opacity"] = alpha
                    c = self.current_settings["color"]; c.setAlpha(alpha); self.current_settings["color"] = c
                    self.brush_changed.emit(self.current_thickness, alpha); self.color_changed.emit(self.current_color)
            except ValueError: pass
        
        elif action_key.startswith("set_style_"):
            style_str = action_key.replace("set_style_", "")
            qt_style = { "solid": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine, "dashdot": Qt.DashDotLine }.get(style_str, Qt.SolidLine)
            if self.has_selection: self.tool_states["tool_cursor"]["style"] = qt_style
            elif "style" in self.current_settings: self.current_settings["style"] = qt_style
            self.style_changed.emit(style_str)
        
        elif action_key.startswith("set_font_"):
            style_str = action_key.replace("set_font_", ""); fmt = "Normal"
            if "bolditalic" in style_str: fmt = "BoldItalic"
            elif "bold" in style_str: fmt = "Bold"
            elif "italic" in style_str: fmt = "Italic"
            if self.has_selection: self.tool_states["tool_cursor"]["font_style"] = fmt
            elif "font_style" in self.current_settings: self.current_settings["font_style"] = fmt
            self.style_changed.emit(fmt)
        
        elif action_key.startswith("set_eraser_size_"):
            try:
                val = int(action_key.split("_")[-1]); self.eraser_size = val
                self.tool_states["tool_eraser"]["thickness"] = val
                if "eraser" in self.active_tool_id: self.brush_changed.emit(val, 255)
            except ValueError: pass

        elif action_key == "set_eraser_stroke":
            self.eraser_type = "stroke"; self.active_tool_id = "tool_eraser"; self.tool_changed.emit("tool_eraser")
        elif action_key == "set_eraser_pixel":
            self.eraser_type = "pixel"; self.active_tool_id = "tool_eraser"; self.tool_changed.emit("tool_eraser")
        
        elif action_key == "action_delete": self.action_triggered.emit("delete_selection")
        elif action_key == "action_deselect":
            self.action_triggered.emit("clear_selection"); self.set_selection_active(False)
            self.active_tool_id = "tool_cursor"; self.tool_changed.emit("tool_cursor")

        elif action_key.startswith("action_") or action_key == "clear_canvas" or action_key == "open_settings":
            self.action_triggered.emit(action_key)

state = StateManager()