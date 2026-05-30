import math
import os
import time
import cv2          
import numpy as np
import statistics
import keyboard
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QLineEdit, QFileDialog, QApplication
from PySide6.QtCore import Qt, QPoint, QRect, QPointF, QRectF, QTimer
from PySide6.QtGui import (
    QPainter, QColor, QPen, QPainterPath, QBrush, QPolygonF, QRegion, 
    QPixmap, QFont, QFontMetrics, QKeySequence, QCursor, QTransform, 
    QTabletEvent, QPainterPathStroker, QInputDevice
)

# Safe Import for QPointingDevice (Qt6)
try:
    from PySide6.QtGui import QPointingDevice
    HAS_POINTING_DEVICE = True
except ImportError:
    HAS_POINTING_DEVICE = False

from core.state import state
from ui.settings_window import SettingsWindow

class FloatingTextInput(QLineEdit):
    def __init__(self, parent, pos, color, font_size, font_style_str):
        super().__init__(parent)
        self.move(pos)
        self.setPlaceholderText("Type here...")
        weight = QFont.Bold if "Bold" in font_style_str else QFont.Normal
        italic = "Italic" in font_style_str
        font = QFont("Arial", font_size); font.setWeight(weight); font.setItalic(italic)
        self.setFont(font)
        text_color = color.name()
        self.setStyleSheet(f"QLineEdit {{ background: rgba(255, 255, 255, 200); border: 1px dashed {text_color}; border-radius: 4px; color: {text_color}; padding: 2px; }}")
        self.textChanged.connect(self.adjust_size)
        self.adjust_size("Type here...")
        self.show(); self.setFocus()
    def adjust_size(self, text):
        fm = QFontMetrics(self.font())
        width = max(100, fm.horizontalAdvance(text) + 30)
        self.setFixedSize(width, fm.height() + 10)

class Canvas(QWidget):
    global_hotkey_signal = Signal(str)
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.strokes = []       
        self.redo_stack = [] 
        self.clipboard = []              # ADD THIS LINE
        # self.is_keyboard_rotating = False # ADD THIS LINE
        self.current_stroke = None 
        
        self.active_tool = "tool_pen_1"
        self.active_color = state.current_color
        self.active_size = state.current_thickness
        self.active_opacity = state.current_opacity
        self.active_style = state.current_style
        self.active_font_style = state.current_font_style 
        
        self.last_pos = QPointF() 
        self.current_pos = QPointF()
        self.start_pos = QPoint()
        self.is_drawing = False

        self.selection_path = None
        self.selected_indices = []
        self.is_moving_selection = False
        self.move_start_pos = QPointF()
        
        self.edit_btn_rect = None
        self.active_text_widget = None
        self.buffer_pixmap = None
        self.menu_ref = None 
        self.settings_win = None

        self.is_internal_sync = False 
        self.previous_tool_before_eraser = None 

        # --- SELECTION TRANSFORMATION ---
        self.transform_mode = None  
        self.active_handle = None   
        self.selection_rect = QRectF() 
        self.original_selection_rect = QRectF() 
        self.original_selected_strokes = [] 
        self.rotation_angle = 0.0
        self.transform_center = QPointF()
        self.transform_start_angle = 0.0

        # --- AESTHETIC CONFIG ---
        self.theme_border = QColor("#6c5ce7") 
        self.theme_fill = QColor(108, 92, 231, 30) 
        self.aesthetic_shape_color = QColor("#6c5ce7")

        # --- VANISHING INK TIMER ---
        self.vanish_timer = QTimer(self)
        self.vanish_timer.setInterval(100) 
        self.vanish_timer.timeout.connect(self.check_vanishing_strokes)
        self.vanish_timer.start()

        # --- MAGIC SHAPE & SCALING ---
        self.current_points = []  
        self.snapped_shape = None 
        self.is_scaling_shape = False 
        self.base_snapped_path = None 
        
        # New: Tracking for Snap-Hold-Rotate
        self.scale_start_dist = 0.0   
        self.snap_start_angle = 0.0
        self.shape_center = QPointF() 
        
        self.shape_hold_timer = QTimer(self)
        self.shape_hold_timer.setInterval(600) 
        self.shape_hold_timer.setSingleShot(True)
        self.shape_hold_timer.timeout.connect(self.snap_to_shape)

        self.cursors = {}
        self.load_cursors()

        state.tool_changed.connect(self.set_tool)
        state.color_changed.connect(self.set_color)
        state.brush_changed.connect(self.set_brush)
        state.style_changed.connect(self.set_style) 
        state.action_triggered.connect(self.handle_action)
        state.background_changed.connect(self.update_background)
        state.fill_toggled.connect(self.update)
        state.fill_color_changed.connect(self.update_fill_color_selection)

        # Initialize Cursor
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        self.set_tool(self.active_tool)

        self.global_hotkey_signal.connect(self.process_global_hotkey)
        self.setup_global_shortcuts()

    def setup_global_shortcuts(self):
        # These listen globally, even when clicking other apps!
        keyboard.on_press_key("F2", lambda e: self.global_hotkey_signal.emit("F2"))
        keyboard.on_press_key("F3", lambda e: self.global_hotkey_signal.emit("F3"))
        keyboard.on_press_key("F4", lambda e: self.global_hotkey_signal.emit("F4"))
        keyboard.on_press_key("F5", lambda e: self.global_hotkey_signal.emit("F5"))
        keyboard.on_press_key("F6", lambda e: self.global_hotkey_signal.emit("F6"))
        keyboard.on_press_key("F7", lambda e: self.global_hotkey_signal.emit("F7"))
        keyboard.on_press_key("F8", lambda e: self.global_hotkey_signal.emit("F8"))
        keyboard.on_press_key("F9", lambda e: self.global_hotkey_signal.emit("F9"))

    def process_global_hotkey(self, key_str):
        current_tool = state.active_tool_id

        # Lower Button: Eraser Toggle
        if key_str == "F8": 
            if current_tool != "tool_eraser":
                if current_tool not in ["tool_eraser", "tool_cursor", "tool_pan", "tool_select_lasso"]:
                    self.last_drawing_tool = current_tool
                state.set_active_tool("tool_eraser")
            else:
                target = getattr(self, "last_drawing_tool", "tool_pen_1")
                state.set_active_tool(target)

        # Upper Button: Pointer Toggle
        elif key_str == "F9": 
            if current_tool != "tool_cursor":
                if current_tool not in ["tool_eraser", "tool_cursor", "tool_pan", "tool_select_lasso"]:
                    self.last_drawing_tool = current_tool
                state.set_active_tool("tool_cursor")
            else:
                target = getattr(self, "last_drawing_tool", "tool_pen_1")
                state.set_active_tool(target)

        # Express Keys
        elif key_str == "F2":
            state.set_active_tool("toggle_board")
        elif key_str == "F3":
            if current_tool == "tool_select_lasso":
                state.set_active_tool("tool_pen_1")
            else:
                state.set_active_tool("tool_select_lasso")
        elif key_str == "F4":
            self.handle_action("clear_canvas")
        elif key_str == "F5":
            # Key 5 now INCREASES brush size
            new_size = min(100, self.active_size + 2)
            state.sync_tool_properties(thickness=new_size)
            self.active_size = new_size
            
        elif key_str == "F6":
            # Key 6 now DECREASES brush size
            new_size = max(1, self.active_size - 2)
            state.sync_tool_properties(thickness=new_size)
            self.active_size = new_size
        elif key_str == "F7":
            if current_tool == "tool_laser":
                state.set_active_tool("tool_hl")
            else:
                state.set_active_tool("tool_laser")

    def load_cursors(self):
        def create_cursor(filename, hot_x, hot_y, fallback=Qt.ArrowCursor):
            path = os.path.join("assets", filename)
            if os.path.exists(path):
                pix = QPixmap(path)
                pix = pix.scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                return QCursor(pix, hot_x, hot_y)
            return QCursor(fallback)

        self.cursors["pen"] = create_cursor("cursor_pen.png", 0, 31, Qt.CrossCursor)
        self.cursors["hl"] = create_cursor("cursor_hl.png", 0, 31, Qt.SplitVCursor)
        self.cursors["eraser"] = create_cursor("cursor_eraser.png", 6, 26, Qt.ForbiddenCursor)
        self.cursors["text"] = create_cursor("cursor_text.png", 16, 16, Qt.IBeamCursor)
        self.cursors["shape"] = create_cursor("cursor_cross.png", 16, 16, Qt.CrossCursor)
        self.cursors["select"] = Qt.PointingHandCursor
        self.cursors["laser"] = create_cursor("cursor_pen.png", 0, 31, Qt.CrossCursor)

    def apply_custom_cursor(self, tool_id):
        cursor = Qt.ArrowCursor
        if tool_id == "tool_laser": cursor = self.cursors["laser"] 
        elif "pen" in tool_id: cursor = self.cursors["pen"]
        elif "eraser" in tool_id: cursor = self.cursors["eraser"]
        elif "hl" in tool_id: cursor = self.cursors["hl"]
        elif "text" in tool_id: cursor = self.cursors["text"]
        elif "tool_select" in tool_id: cursor = self.cursors["select"]
        elif "tool_" in tool_id: cursor = self.cursors["shape"]
        
        # Use changeOverrideCursor for immediate, prioritized updates
        QApplication.restoreOverrideCursor() 
        QApplication.setOverrideCursor(cursor)
        QApplication.processEvents() # Force UI refresh immediately

    def set_menu_ref(self, menu): self.menu_ref = menu

    # --- HELPERS ---
    def get_stroke_type(self):
        if "pen" in self.active_tool: return "pen"
        if "laser" in self.active_tool: return "laser_pen"
        if "hl" in self.active_tool: return "highlighter"
        if "eraser" in self.active_tool: return "eraser"
        if "line" in self.active_tool: return "line"
        if "arrow" in self.active_tool: return "arrow"
        if "rect" in self.active_tool: return "rect"
        if "circle" in self.active_tool: return "circle"
        if "polygon" in self.active_tool: return "polygon"
        if "star" in self.active_tool: return "star"
        return "pen"

    def redraw_buffer(self):
        self.buffer_pixmap.fill(Qt.transparent)
        painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
        for stroke in self.strokes: self.draw_stroke_entity(painter, stroke)
        painter.end()

    def resizeEvent(self, event):
        dpr = self.devicePixelRatio()
        new_pixmap = QPixmap(self.size() * dpr)
        new_pixmap.setDevicePixelRatio(dpr)
        new_pixmap.fill(Qt.transparent)
        if self.buffer_pixmap:
            painter = QPainter(new_pixmap); painter.drawPixmap(0, 0, self.buffer_pixmap); painter.end()
        self.buffer_pixmap = new_pixmap
        self.redraw_buffer()

    def update_background(self, color): self.update()
    
    def update_fill_color_selection(self, color):
        if self.selected_indices:
            for i in self.selected_indices:
                self.strokes[i]["fill_color"] = color
            self.redraw_buffer()
            self.update()

    def check_vanishing_strokes(self):
        if not self.strokes: return
        now = time.time()
        initial_count = len(self.strokes)
        self.strokes = [s for s in self.strokes if s.get("vanish_deadline", float('inf')) > now]
        if len(self.strokes) < initial_count:
            self.redraw_buffer(); self.update()

    # --- KEYBOARD SHORTCUTS ---
    def keyPressEvent(self, event):
        key = event.key()
        
        # --- STANDARD KEYBOARD SHORTCUTS ---
        
        if key == Qt.Key_B: 
            if state.active_tool_id == "tool_pen_1": state.set_active_tool("tool_pen_2")
            else: state.set_active_tool("tool_pen_1")
            
        elif key == Qt.Key_E:
            if "eraser" not in state.active_tool_id: state.set_active_tool("tool_eraser")
            else: state.set_active_tool("tool_pen_1") 
            
        elif key == Qt.Key_H: 
            state.set_active_tool("tool_hl")
            
        elif key == Qt.Key_L: 
            state.set_active_tool("tool_select_lasso")
            
        elif key == Qt.Key_S: 
            if state.active_tool_id == "tool_rect": state.set_active_tool("tool_circle")
            elif state.active_tool_id == "tool_circle": state.set_active_tool("tool_arrow")
            else: state.set_active_tool("tool_rect")
            
        elif key == Qt.Key_Space:
            if state.active_tool_id == "tool_pan": state.set_active_tool("tool_pen_1")
            else: state.set_active_tool("tool_pan")
        
        # --- ESSENTIAL SYSTEM ACTIONS ---
        
        elif event.matches(QKeySequence.Undo): 
            self.handle_action("action_undo")
            event.accept()
            
        elif event.matches(QKeySequence.Redo): 
            self.handle_action("action_redo")
            event.accept()
            
        elif event.matches(QKeySequence.Save): 
            self.save_canvas()
            event.accept()

        # --- COPY AND PASTE ---
        elif event.matches(QKeySequence.Copy):
            if self.selected_indices:
                self.clipboard = []
                for i in self.selected_indices:
                    stroke = self.strokes[i].copy()
                    # We must create deep copies of paths and points so they don't link to the original
                    if stroke["type"] != "text":
                        stroke["path"] = QPainterPath(self.strokes[i]["path"])
                    if "points" in stroke and stroke["points"]:
                        stroke["points"] = list(stroke["points"])
                    self.clipboard.append(stroke)
            event.accept()

        elif event.matches(QKeySequence.Paste):
            if hasattr(self, 'clipboard') and self.clipboard:
                new_indices = []
                offset = QPointF(30, 30) # Offset so it doesn't paste perfectly on top
                
                self.selected_indices = []
                
                for stroke in self.clipboard:
                    new_stroke = stroke.copy()
                    if new_stroke["type"] == "text":
                        new_stroke["pos"] = new_stroke["pos"] + offset.toPoint()
                    else:
                        new_path = QPainterPath(stroke["path"])
                        new_path.translate(offset)
                        new_stroke["path"] = new_path
                        if "points" in new_stroke and new_stroke["points"]:
                            new_stroke["points"] = [(p[0] + offset, p[1]) for p in stroke["points"]]
                    
                    self.strokes.append(new_stroke)
                    new_indices.append(len(self.strokes) - 1)
                
                # Shift the clipboard offset so pasting again moves it further down
                self.clipboard = []
                for i in new_indices:
                    s = self.strokes[i].copy()
                    if s["type"] != "text": s["path"] = QPainterPath(self.strokes[i]["path"])
                    if "points" in s and s["points"]: s["points"] = list(s["points"])
                    self.clipboard.append(s)
                
                self.selected_indices = new_indices
                
                # Rebuild the selection highlight box around the new pasted items
                united_rect = QRectF()
                first = True
                for i in self.selected_indices:
                    stroke = self.strokes[i]
                    if stroke["type"] == "text":
                        txt_w = stroke.get("text_width", 100)
                        txt_h = stroke.get("text_height", stroke["size"] + 5)
                        item_rect = QRectF(stroke["pos"].x(), stroke["pos"].y() - stroke["size"], txt_w, txt_h)
                    else:
                        item_rect = stroke["path"].boundingRect()
                    if first: united_rect = item_rect; first = False
                    else: united_rect = united_rect.united(item_rect)
                
                self.selection_rect = united_rect.adjusted(-10, -10, 10, 10)
                self.selection_path = QPainterPath()
                self.selection_path.addRect(self.selection_rect)
                btn_size = 28
                self.edit_btn_rect = QRectF(self.selection_rect.right() - btn_size/2, self.selection_rect.top() - btn_size/2, btn_size, btn_size)
                
                state.set_selection_active(True)
                self.redraw_buffer()
                self.update()
            event.accept()

            
        elif key == Qt.Key_Escape:
            if self.active_text_widget: 
                self.active_text_widget.deleteLater()
                self.active_text_widget = None
            else: 
                self.selected_indices = []
                self.selection_path = None
                self.edit_btn_rect = None 
                self.active_handle = None
                state.set_selection_active(False)
                state.set_active_tool("tool_cursor")
            self.update()
            event.accept()
            
        elif key == Qt.Key_Delete:
            if self.selected_indices:
                for idx in sorted(self.selected_indices, reverse=True): 
                    self.strokes.pop(idx)
                self.selected_indices = []
                self.selection_path = None
                self.edit_btn_rect = None 
                state.set_selection_active(False)
                self.redraw_buffer()
                self.update()
            else: 
                self.handle_action("clear_canvas")
            event.accept()
            
        else: 
            super().keyPressEvent(event)

    def set_tool(self, tool_id):
        if "select" not in tool_id and "cursor" not in tool_id:
            self.selected_indices = []
            self.selection_path = None
            self.edit_btn_rect = None
            state.set_selection_active(False)
            self.update()

        self.active_tool = tool_id
        if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
        
        shape_keywords = ["line", "arrow", "rect", "circle", "polygon", "star"]
        is_shape = any(k in tool_id for k in shape_keywords)
        is_selection = "select" in tool_id or "cursor" in tool_id
        
        if is_shape and not is_selection:
            self.active_color = self.aesthetic_shape_color
        else:
            self.active_color = state.current_color

        if "eraser" in tool_id:
            self.active_size = state.eraser_size
        else:
            self.active_size = state.current_thickness
        self.active_opacity = state.current_opacity
        self.active_style = state.current_style
        self.active_font_style = state.current_font_style 
        
        # Cursor Update
        self.apply_custom_cursor(tool_id)
        
        is_board_active = state.board_color.alpha() > 0
        if tool_id in ["tool_cursor", "tool_pan"]:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, not is_board_active)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            
        self.update(); self.setFocus() 

    def set_color(self, color): 
        self.active_color = color
        if self.is_internal_sync: return 
        if self.selected_indices:
            for i in self.selected_indices: self.strokes[i]["color"] = color
            self.redraw_buffer(); self.update()

    def set_brush(self, size, opacity): 
        if "eraser" in self.active_tool: self.active_size = state.eraser_size
        else: self.active_size = size
        self.active_opacity = opacity
        self.active_color.setAlpha(opacity)
        if self.is_internal_sync: return 
        if self.selected_indices:
            for i in self.selected_indices:
                stroke = self.strokes[i]
                stroke["size"] = size
                c = stroke["color"]; c.setAlpha(opacity); stroke["color"] = c
                if "points" in stroke and stroke["points"]:
                    stroke["path"] = self.generate_variable_width_path(stroke["points"], size)
            self.redraw_buffer(); self.update()
        
    def set_style(self, style_val):
        if isinstance(style_val, str) and style_val in ["Normal", "Bold", "Italic", "BoldItalic"]:
            self.active_font_style = style_val; target_key = "font_style"; target_val = style_val
        else:
            target_key = "style"
            if isinstance(style_val, str):
                mapping = { "solid": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine, "dashdot": Qt.DashDotLine }
                target_val = mapping.get(style_val, Qt.SolidLine)
            else:
                target_val = style_val
            self.active_style = target_val

        if self.is_internal_sync: return 
        if self.selected_indices:
            for i in self.selected_indices:
                stroke = self.strokes[i]
                if stroke["type"] == "text" and target_key == "font_style": stroke["font_style"] = target_val
                elif stroke["type"] != "text" and target_key == "style": stroke["style"] = target_val
            self.redraw_buffer(); self.update()

    def handle_action(self, action):
        if action == "clear_canvas": self.strokes = []; self.redo_stack = []; self.redraw_buffer(); self.update()
        elif action == "action_undo": 
            if self.strokes: 
                stroke = self.strokes.pop()
                self.redo_stack.append(stroke)
                if len(self.redo_stack) > 50: self.redo_stack.pop(0) 
                self.redraw_buffer(); self.update()
        elif action == "action_redo":
             if self.redo_stack:
                stroke = self.redo_stack.pop(); self.strokes.append(stroke)
                painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
                self.draw_stroke_entity(painter, stroke); painter.end(); self.update()
        elif action == "action_save": self.save_canvas()
        elif action == "delete_selection":
            if self.selected_indices:
                for idx in sorted(self.selected_indices, reverse=True): self.strokes.pop(idx)
                self.selected_indices = []; self.selection_path = None; self.edit_btn_rect = None
                state.set_selection_active(False)
                self.redraw_buffer(); self.update()
        elif action == "clear_selection":
            self.selected_indices = []; self.selection_path = None; self.edit_btn_rect = None
            state.set_selection_active(False)
            self.update()
        elif action == "open_settings":
            if not self.settings_win: self.settings_win = SettingsWindow(self)
            self.settings_win.show()

    def save_canvas(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Drawing", "", "PNG Image (*.png);;JPEG Image (*.jpg)")
        if file_path:
            if self.selection_path and self.active_tool in ["tool_select_rect", "tool_select_lasso"]:
                rect = self.selection_path.boundingRect().toRect()
                rect = rect.intersected(self.rect())
                if not rect.isEmpty(): crop = self.grab(rect); crop.save(file_path); return
            if state.board_color.alpha() > 0:
                final_pix = QPixmap(self.size()); final_pix.fill(state.board_color)
                painter = QPainter(final_pix); painter.drawPixmap(0, 0, self.buffer_pixmap); painter.end()
                final_pix.save(file_path)
            else: self.buffer_pixmap.save(file_path)

    # --- SELECTION & GEOMETRY HELPERS ---
    def find_selected_strokes(self):
        self.selected_indices = []
        if not self.selection_path: return
        
        for i, stroke in enumerate(self.strokes):
            if stroke["type"] == "eraser": continue
            
            if stroke["type"] == "text":
                txt_w = stroke.get("text_width", 100)
                txt_h = stroke.get("text_height", stroke["size"] + 5)
                item_rect = QRectF(stroke["pos"].x(), stroke["pos"].y() - stroke["size"], txt_w, txt_h)
                if self.selection_path.contains(item_rect):
                    self.selected_indices.append(i)
                continue

            path_to_check = stroke["path"]
            
            st_type = stroke["type"]
            is_filled_poly = st_type in ["pen", "highlighter", "eraser", "laser_pen"]
            
            if is_filled_poly:
                if self.selection_path.contains(path_to_check):
                    self.selected_indices.append(i)
            else:
                stroker = QPainterPathStroker()
                stroker.setWidth(stroke["size"]) 
                hit_area = stroker.createStroke(path_to_check)
                
                if self.selection_path.contains(hit_area):
                    self.selected_indices.append(i)

    def move_selection(self, delta):
        self.selection_rect.translate(delta)
        if self.selection_path: self.selection_path.translate(delta)
        if self.edit_btn_rect: self.edit_btn_rect.translate(delta)
        for i in self.selected_indices:
            stroke = self.strokes[i]
            if stroke["type"] == "text": stroke["pos"] += delta
            else:
                stroke["path"].translate(delta)
                if "points" in stroke and stroke["points"]:
                    stroke["points"] = [(p[0] + delta, p[1]) for p in stroke["points"]]

    def get_handles(self):
        r = self.selection_rect
        h_size = 10 
        
        # Corners
        tl = QRectF(r.left()-h_size, r.top()-h_size, h_size, h_size)
        tr = QRectF(r.right(), r.top()-h_size, h_size, h_size)
        bl = QRectF(r.left()-h_size, r.bottom(), h_size, h_size)
        br = QRectF(r.right(), r.bottom(), h_size, h_size)
        
        # Sides
        tm = QRectF(r.center().x()-h_size/2, r.top()-h_size, h_size, h_size)
        bm = QRectF(r.center().x()-h_size/2, r.bottom(), h_size, h_size)
        lm = QRectF(r.left()-h_size, r.center().y()-h_size/2, h_size, h_size)
        rm = QRectF(r.right(), r.center().y()-h_size/2, h_size, h_size)
        
        # Rotate
        rot_pt = QPointF(r.center().x(), r.top() - 30)
        rot = QRectF(rot_pt.x()-6, rot_pt.y()-6, 12, 12)
        
        return {
            "tl": tl, "tr": tr, "bl": bl, "br": br,
            "tm": tm, "bm": bm, "lm": lm, "rm": rm,
            "rot": rot
        }

    def get_anchor_point(self, handle):
        # Returns the stationary opposite point for the given handle
        r = self.original_selection_rect
        if handle == "tl": return r.bottomRight()
        if handle == "tr": return r.bottomLeft()
        if handle == "bl": return r.topRight()
        if handle == "br": return r.topLeft()
        if handle == "tm": return QPointF(r.center().x(), r.bottom())
        if handle == "bm": return QPointF(r.center().x(), r.top())
        if handle == "lm": return QPointF(r.right(), r.center().y())
        if handle == "rm": return QPointF(r.left(), r.center().y())
        return r.center()

    def spawn_text_input(self, pos):
        font_size = 10 + (self.active_size * 2)
        self.active_text_widget = FloatingTextInput(self, pos, self.active_color, font_size, self.active_font_style)
        self.active_text_widget.returnPressed.connect(lambda: self.commit_text(pos, font_size))
        self.active_text_widget.show()

    def commit_text(self, pos, font_size):
        if not self.active_text_widget: return
        text = self.active_text_widget.text()
        if text.strip():
            fm = QFontMetrics(self.active_text_widget.font()); w = fm.horizontalAdvance(text); h = fm.height()
            text_stroke = { "type": "text", "text": text, "pos": pos, "color": QColor(self.active_color), "size": font_size, "font_style": self.active_font_style, "path": QPainterPath(), "text_width": w, "text_height": h }
            self.strokes.append(text_stroke)
            painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
            self.draw_stroke_entity(painter, text_stroke); painter.end(); self.update()
        self.active_text_widget.deleteLater(); self.active_text_widget = None

    def snap_to_shape(self):
        if not self.current_points or len(self.current_points) < 10: return
        
        points_array = np.array([[p.x(), p.y()] for p in self.current_points], dtype=np.int32)
        start = self.current_points[0]; end = self.current_points[-1]
        dist_start_end = math.hypot(end.x() - start.x(), end.y() - start.y())
        perimeter = cv2.arcLength(points_array, False) 
        if perimeter == 0: return
        linearity = dist_start_end / perimeter
        
        detected_path = QPainterPath(); shape_type = None
        
        if linearity > 0.95:
            shape_type = "line"; detected_path.moveTo(start); detected_path.lineTo(end)
        else:
            epsilon = 0.02 * perimeter
            approx_curve = cv2.approxPolyDP(points_array, epsilon, True) 
            vertex_count = len(approx_curve)
            poly_qpoints = [QPointF(float(p[0][0]), float(p[0][1])) for p in approx_curve]
            
            if vertex_count == 3:
                shape_type = "triangle"; detected_path.addPolygon(QPolygonF(poly_qpoints)); detected_path.closeSubpath() 
            elif vertex_count == 4 or vertex_count == 5:
                shape_type = "rect"; rect_data = cv2.minAreaRect(points_array); (center, (w, h), angle) = rect_data
                aspect_ratio = min(w, h) / max(w, h) if max(w, h) > 0 else 0
                if aspect_ratio > 0.90: side = (w + h) / 2; rect_data = (center, (side, side), angle)
                box = cv2.boxPoints(rect_data)
                perfect_poly = [QPointF(float(p[0]), float(p[1])) for p in box]
                detected_path.addPolygon(QPolygonF(perfect_poly)); detected_path.closeSubpath() 
            elif vertex_count > 5:
                shape_type = "circle"; bbox = QPolygonF(self.current_points).boundingRect(); detected_path.addEllipse(bbox)

        if shape_type:
            # FIX: Use specific shape type and inherit fill settings
            self.snapped_shape = {
                "type": shape_type, 
                "color": self.active_color, 
                "size": self.active_size,
                "opacity": self.active_opacity, 
                "style": self.active_style,
                "fill_enabled": state.current_fill_enabled,
                "fill_color": state.current_fill_color,
                "path": detected_path, 
                "is_preview": True, 
                "shape_type": shape_type
            }
            self.is_scaling_shape = True
            self.base_snapped_path = detected_path 
            self.shape_center = detected_path.boundingRect().center()
            if shape_type == "line": self.shape_center = start 
            
            curr_pos = self.current_points[-1]
            self.scale_start_dist = math.hypot(curr_pos.x() - self.shape_center.x(), curr_pos.y() - self.shape_center.y())
            if self.scale_start_dist < 1: self.scale_start_dist = 1
            
            start_vec = curr_pos - self.shape_center
            self.snap_start_angle = math.atan2(start_vec.y(), start_vec.x())
            
            self.update()

    # --- VARIABLE WIDTH GENERATOR ---
    def generate_variable_width_path(self, points, base_size):
        if not points or len(points) < 2:
            path = QPainterPath()
            if points:
                pt, press = points[0]
                rad = max(1.0, (base_size * press) / 2)
                path.addEllipse(pt, rad, rad)
            return path

        left_pts = []
        right_pts = []

        for i in range(len(points) - 1):
            p1, press1 = points[i]
            p2, press2 = points[i+1]
            
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.hypot(dx, dy)
            if length == 0: continue
            
            nx = -dy / length
            ny = dx / length
            
            w1 = max(1.0, base_size * press1)
            offset_x = nx * w1 * 0.5
            offset_y = ny * w1 * 0.5
            
            left_pts.append(QPointF(p1.x() + offset_x, p1.y() + offset_y))
            right_pts.append(QPointF(p1.x() - offset_x, p1.y() - offset_y))
            
            if i == len(points) - 2:
                w2 = max(1.0, base_size * press2)
                off2_x = nx * w2 * 0.5
                off2_y = ny * w2 * 0.5
                left_pts.append(QPointF(p2.x() + off2_x, p2.y() + off2_y))
                right_pts.append(QPointF(p2.x() - off2_x, p2.y() - off2_y))

        path = QPainterPath()
        if left_pts:
            path.moveTo(left_pts[0])
            for p in left_pts[1:]:
                path.lineTo(p)
            for p in reversed(right_pts):
                path.lineTo(p)
            path.closeSubpath()
        
        path.setFillRule(Qt.WindingFill)
        
        return path

    def tabletEvent(self, event: QTabletEvent):
        # [FIX] Safer logic to prevent crashes if QPointingDevice is missing/different
        try:
            if HAS_POINTING_DEVICE:
                pt = event.pointerType()
                if pt == QPointingDevice.PointerType.Eraser:
                    if "eraser" not in self.active_tool:
                        self.previous_tool_before_eraser = self.active_tool
                        state.set_active_tool("tool_eraser")
                elif pt == QPointingDevice.PointerType.Pen:
                    if self.previous_tool_before_eraser:
                        state.set_active_tool(self.previous_tool_before_eraser)
                        self.previous_tool_before_eraser = None
        except Exception:
            pass # Gracefully ignore tablet feature failures

        # [FIX] Simplified extraction and force-start drawing
        pos = event.position()
        pressure = event.pressure()
        if pressure == 0.0: pressure = 1.0 # Fallback for some drivers

        # If a tablet button is pressed (or tip is down), treat as click
        btns = event.buttons()
        
        if event.type() == QTabletEvent.TabletPress:
            # Force Left Button if the driver sends NoButton on press
            if btns == Qt.NoButton: btns = Qt.LeftButton
            self._handle_input(pos, pressure, "press", btns)
            event.accept()
        elif event.type() == QTabletEvent.TabletMove:
            self._handle_input(pos, pressure, "move", btns)
            event.accept()
        elif event.type() == QTabletEvent.TabletRelease:
            self._handle_input(pos, pressure, "release", btns)
            event.accept()

    def mousePressEvent(self, event):
        self._handle_input(event.position(), 1.0, "press", event.button())

    def mouseMoveEvent(self, event):
        self._handle_input(event.position(), 1.0, "move", event.buttons())

    def mouseReleaseEvent(self, event):
        self._handle_input(event.position(), 1.0, "release", event.button())

    def _handle_input(self, posF, pressure, event_type, buttons):
        pos = posF
        
        # Pressure Curve
        pressure = math.pow(pressure, 1.4) 

        if event_type == "press":

        
            # --- REQUIREMENT 1 & 2: Stylus Button Toggles ---
            if buttons == Qt.RightButton: # Lower Pen Button
                if "eraser" not in state.active_tool_id:
                    self.previous_tool_before_eraser = state.active_tool_id
                    state.set_active_tool("tool_eraser")
                else:
                    if hasattr(self, 'previous_tool_before_eraser') and self.previous_tool_before_eraser:
                        state.set_active_tool(self.previous_tool_before_eraser)
                return

            if buttons == Qt.MiddleButton: # Upper Pen Button
                if "cursor" not in state.active_tool_id:
                    self.previous_tool_before_cursor = state.active_tool_id
                    state.set_active_tool("tool_cursor")
                else:
                    if hasattr(self, 'previous_tool_before_cursor') and self.previous_tool_before_cursor:
                        state.set_active_tool(self.previous_tool_before_cursor)
                return

            # [FIX] Robust Left Click check (some tablets send NoButton on tip press)
            if buttons == Qt.LeftButton or buttons == Qt.NoButton:
                if self.selected_indices and ("select" in self.active_tool or "cursor" in self.active_tool):
                    handles = self.get_handles()
                    for key, rect in handles.items():
                        if rect.contains(pos):
                            self.transform_mode = "rotate" if key == "rot" else "scale"
                            self.active_handle = key
                            self.move_start_pos = pos
                            self.original_selection_rect = QRectF(self.selection_rect)
                            self.transform_center = self.selection_rect.center()
                            mouse_vec = pos - self.transform_center
                            self.transform_start_angle = math.atan2(mouse_vec.y(), mouse_vec.x())
                            self.original_selected_strokes = [self.strokes[i].copy() for i in self.selected_indices]
                            for k, stroke in enumerate(self.original_selected_strokes):
                                if stroke["type"] != "text": stroke["path"] = QPainterPath(self.strokes[self.selected_indices[k]]["path"])
                            return

                if self.edit_btn_rect and self.edit_btn_rect.contains(pos):
                    state.request_menu_context.emit("selection_context"); return

                if self.menu_ref and self.menu_ref.geometry().contains(pos.toPoint()): return 
                if self.active_tool == "tool_text":
                    if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
                    else: self.spawn_text_input(pos.toPoint())
                    return
                
                self.is_drawing = True
                self.last_pos = pos
                self.current_pos = self.last_pos
                self.start_pos = self.last_pos.toPoint()
                self.redo_stack = []
                self.current_points = [self.last_pos] 
                self.snapped_shape = None
                self.is_scaling_shape = False
                self.shape_hold_timer.stop()

                if "select" in self.active_tool:
                    if self.selected_indices and self.selection_rect.contains(self.last_pos):
                        self.is_moving_selection = True; self.move_start_pos = self.last_pos; return
                    self.selected_indices = []; self.selection_path = None; self.edit_btn_rect = None 
                    state.set_selection_active(False)
                    if self.active_tool == "tool_select_lasso": self.selection_path = QPainterPath(); self.selection_path.moveTo(self.last_pos)
                    else: self.selection_path = QPainterPath() 
                    self.update(); return

                if "eraser" in self.active_tool and state.eraser_type == "stroke":
                    if self.delete_stroke_at(self.current_pos.toPoint()): self.redraw_buffer(); self.update()
                    return

                self.current_stroke = {
                    "type": self.get_stroke_type(), "color": QColor(self.active_color),
                    "size": self.active_size, "style": self.active_style,
                    "fill_enabled": state.current_fill_enabled,
                    "fill_color": QColor(state.current_fill_color),
                    "path": QPainterPath(), "start": self.start_pos, "end": self.start_pos,
                    "points": [] 
                }
                
                if self.current_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]:
                    self.current_stroke["points"].append((pos, pressure))
                    rad = max(1.0, (self.active_size * pressure) / 2)
                    self.current_stroke["path"].addEllipse(pos, rad, rad)
                else:
                    self.current_stroke["path"].moveTo(self.last_pos)

        elif event_type == "move":
            if self.transform_mode:
                transform = QTransform()
                
                if self.transform_mode == "scale":
                    anchor = self.get_anchor_point(self.active_handle)
                    orig_vector = self.move_start_pos - anchor
                    curr_vector = pos - anchor
                    sx = 1.0; sy = 1.0
                    if abs(orig_vector.x()) > 1: sx = curr_vector.x() / orig_vector.x()
                    if abs(orig_vector.y()) > 1: sy = curr_vector.y() / orig_vector.y()
                    
                    if self.active_handle in ["tm", "bm"]: sx = 1.0
                    if self.active_handle in ["lm", "rm"]: sy = 1.0
                    
                    transform.translate(anchor.x(), anchor.y())
                    transform.scale(sx, sy)
                    transform.translate(-anchor.x(), -anchor.y())
                elif self.transform_mode == "rotate":
                    center = self.transform_center
                    mouse_vec = pos - center
                    curr_angle = math.atan2(mouse_vec.y(), mouse_vec.x())
                    delta_angle_rad = curr_angle - self.transform_start_angle
                    delta_angle_deg = math.degrees(delta_angle_rad)
                    transform.translate(center.x(), center.y())
                    transform.rotate(delta_angle_deg)
                    transform.translate(-center.x(), -center.y())

                united_rect = QRectF(); first = True
                for idx, orig_stroke in enumerate(self.original_selected_strokes):
                    real_idx = self.selected_indices[idx]
                    
                    if orig_stroke["type"] == "text":
                        new_pos = transform.map(orig_stroke["pos"])
                        self.strokes[real_idx]["pos"] = new_pos
                        if self.transform_mode == "scale":
                            scale_avg = (abs(sx) + abs(sy)) / 2
                            new_size = max(5, int(orig_stroke["size"] * scale_avg))
                            self.strokes[real_idx]["size"] = new_size
                        
                        item_rect = QRectF(new_pos.x(), new_pos.y() - self.strokes[real_idx]["size"], 
                                         orig_stroke.get("text_width", 10), orig_stroke.get("text_height", 10))
                    else:
                        self.strokes[real_idx]["path"] = transform.map(orig_stroke["path"])
                        if "points" in orig_stroke and orig_stroke["points"]:
                            new_points = []
                            for pt, press in orig_stroke["points"]:
                                new_points.append((transform.map(pt), press))
                            self.strokes[real_idx]["points"] = new_points
                        
                        item_rect = self.strokes[real_idx]["path"].boundingRect()
                        
                    if first: united_rect = item_rect; first = False
                    else: united_rect = united_rect.united(item_rect)
                
                self.selection_rect = united_rect.adjusted(-10, -10, 10, 10)
                self.selection_path = QPainterPath(); self.selection_path.addRect(self.selection_rect)
                self.redraw_buffer(); self.update()
                return

            if self.is_scaling_shape and self.snapped_shape:
                if self.snapped_shape["shape_type"] == "line":
                    path = QPainterPath(); path.moveTo(self.current_points[0]); path.lineTo(pos); self.snapped_shape["path"] = path
                else:
                    current_dist = math.hypot(pos.x() - self.shape_center.x(), pos.y() - self.shape_center.y())
                    scale_factor = current_dist / self.scale_start_dist
                    curr_vec = pos - self.shape_center
                    curr_angle = math.atan2(curr_vec.y(), curr_vec.x())
                    delta_angle_deg = math.degrees(curr_angle - self.snap_start_angle)
                    transform = QTransform()
                    transform.translate(self.shape_center.x(), self.shape_center.y())
                    transform.rotate(delta_angle_deg)
                    transform.scale(scale_factor, scale_factor)
                    transform.translate(-self.shape_center.x(), -self.shape_center.y())
                    self.snapped_shape["path"] = transform.map(self.base_snapped_path)
                self.update(); return 

            if self.selected_indices and not self.is_drawing and ("select" in self.active_tool or "cursor" in self.active_tool):
                handles = self.get_handles()
                h_cursor = Qt.ArrowCursor
                if handles["tl"].contains(pos) or handles["br"].contains(pos): h_cursor = Qt.SizeFDiagCursor
                elif handles["tr"].contains(pos) or handles["bl"].contains(pos): h_cursor = Qt.SizeBDiagCursor
                elif handles["tm"].contains(pos) or handles["bm"].contains(pos): h_cursor = Qt.SizeVerCursor
                elif handles["lm"].contains(pos) or handles["rm"].contains(pos): h_cursor = Qt.SizeHorCursor
                elif handles["rot"].contains(pos): h_cursor = Qt.PointingHandCursor
                
                if QApplication.overrideCursor() is not None:
                    if QApplication.overrideCursor().shape() != h_cursor:
                        QApplication.changeOverrideCursor(h_cursor)
                else:
                    self.setCursor(h_cursor)

            if self.is_drawing:
                if "pen" in self.active_tool:
                    dist = (pos - self.last_pos).manhattanLength()
                    if dist > 2.0:
                        self.shape_hold_timer.start(); self.current_points.append(pos)
                        if self.snapped_shape and dist > 10: self.snapped_shape = None; self.is_scaling_shape = False; self.update()

                if (pos - self.last_pos).manhattanLength() < 2.0: return
                
                if "select" in self.active_tool:
                    if self.is_moving_selection:
                        delta = pos - self.move_start_pos; self.move_selection(delta); self.move_start_pos = pos; self.redraw_buffer()
                    else:
                        if self.active_tool == "tool_select_rect": 
                            self.selection_path = QPainterPath(); self.selection_path.addRect(QRectF(self.start_pos, pos).normalized())
                        elif self.active_tool == "tool_select_lasso": self.selection_path.lineTo(pos)
                    self.update(); return
                
                if "eraser" in self.active_tool and state.eraser_type == "stroke":
                    if self.delete_stroke_at(pos.toPoint()): self.redraw_buffer(); self.update()
                    return
                
                if self.current_stroke:
                    st_type = self.current_stroke["type"]
                    if st_type in ["pen", "highlighter", "eraser", "laser_pen"]:
                        self.current_stroke["points"].append((pos, pressure))
                        self.current_stroke["path"] = self.generate_variable_width_path(self.current_stroke["points"], self.active_size)
                        self.last_pos = pos
                    else: 
                        self.current_stroke["end"] = pos.toPoint()
                    self.update()

        elif event_type == "release":
            self.shape_hold_timer.stop()
            self.is_scaling_shape = False 
            self.transform_mode = None
            self.active_handle = None
            
            if self.is_drawing:
                self.is_drawing = False
                if "select" in self.active_tool:
                    if self.is_moving_selection:
                        self.is_moving_selection = False
                        if self.active_tool == "tool_select_lasso": self.selection_path.closeSubpath()
                    else:
                        if self.active_tool == "tool_select_lasso": self.selection_path.closeSubpath()
                        self.find_selected_strokes()
                        if not self.selected_indices:
                            self.selection_path = None; self.edit_btn_rect = None; self.selection_rect = QRectF(); state.set_selection_active(False)
                        else:
                            self.is_internal_sync = True; state.set_selection_active(True)
                            last_stroke = self.strokes[self.selected_indices[-1]]
                            s_col = last_stroke.get("color", QColor("black"))
                            s_size = last_stroke.get("size", 2)
                            s_style = last_stroke.get("style", Qt.SolidLine)
                            s_fill = last_stroke.get("fill_enabled", False)
                            s_fill_col = last_stroke.get("fill_color", state.current_fill_color)
                            state.sync_tool_properties(color=s_col, thickness=s_size, style=s_style, is_filled=s_fill, fill_color=s_fill_col)
                            self.is_internal_sync = False
                            united_rect = QRectF(); first = True
                            for i in self.selected_indices:
                                stroke = self.strokes[i]
                                if stroke["type"] == "text":
                                    txt_w = stroke.get("text_width", 100); txt_h = stroke.get("text_height", stroke["size"] + 5)
                                    item_rect = QRectF(stroke["pos"].x(), stroke["pos"].y() - stroke["size"], txt_w, txt_h)
                                else: item_rect = stroke["path"].boundingRect()
                                if first: united_rect = item_rect; first = False
                                else: united_rect = united_rect.united(item_rect)
                            self.selection_rect = united_rect.adjusted(-10, -10, 10, 10)
                            self.selection_path = QPainterPath(); self.selection_path.addRect(self.selection_rect)
                            rect = self.selection_rect
                            btn_size = 28
                            self.edit_btn_rect = QRectF(rect.right() - btn_size/2, rect.top() - btn_size/2, btn_size, btn_size)
                    self.update(); return

                if self.current_stroke:
                    final_stroke = self.current_stroke
                    if self.snapped_shape:
                        final_stroke = self.snapped_shape; self.snapped_shape = None 
                    else:
                        if final_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]:
                            final_stroke["path"] = self.generate_variable_width_path(final_stroke["points"], self.active_size)
                        else:
                            path = QPainterPath()
                            self.generate_shape_path(path, final_stroke["type"], final_stroke["start"], final_stroke["end"])
                            final_stroke["path"] = path
                    
                    if final_stroke["type"] == "laser_pen": 
                        final_stroke["vanish_deadline"] = time.time() + state.laser_duration

                    self.strokes.append(final_stroke)
                    painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
                    self.draw_stroke_entity(painter, final_stroke); painter.end()
                    self.current_stroke = None; self.update()

    def draw_selection_overlay(self, painter):
        if not self.selected_indices: return
        pen = QPen(self.theme_border, 2, Qt.SolidLine)
        painter.setPen(pen); painter.setBrush(self.theme_fill)
        painter.drawRect(self.selection_rect)
        
        handles = self.get_handles()
        painter.setPen(QPen(self.theme_border, 1)); painter.setBrush(Qt.white)
        for key, rect in handles.items():
            if key == "rot":
                painter.drawLine(rect.center(), QPointF(rect.center().x(), self.selection_rect.top()))
                painter.drawEllipse(rect)
            else: painter.drawRect(rect)

        if self.edit_btn_rect:
            painter.setBrush(self.theme_border); painter.setPen(QPen(Qt.white, 2))
            painter.drawEllipse(self.edit_btn_rect)
            icon_path = os.path.join("assets", "edit.png")
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_rect = QRectF(self.edit_btn_rect.center().x()-8, self.edit_btn_rect.center().y()-8, 16, 16)
                painter.drawPixmap(icon_rect.toRect(), pix)

    def draw_stroke_entity(self, painter, stroke):
        st_type = stroke["type"]
        if st_type == "text":
            painter.setPen(stroke["color"])
            font_style = stroke.get("font_style", "Normal")
            weight = QFont.Bold if "Bold" in font_style else QFont.Normal
            italic = "Italic" in font_style
            font = QFont("Arial", stroke["size"]); font.setWeight(weight); font.setItalic(italic)
            painter.setFont(font)
            painter.drawText(stroke["pos"] + QPoint(4, stroke["size"] + 5), stroke["text"])
            return
        
        path = stroke["path"]
        
        if st_type == "laser_pen":
            glow_color = QColor(stroke["color"])
            glow_color.setAlpha(120) 
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow_color)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawPath(path)
            
            if "points" in stroke and stroke["points"]:
                core_size = max(1.0, stroke["size"] * 0.3)
                core_path = self.generate_variable_width_path(stroke["points"], core_size)
                painter.setBrush(Qt.white)
                painter.drawPath(core_path)
            return

        if st_type in ["pen", "highlighter", "eraser"] and stroke.get("style", Qt.SolidLine) == Qt.SolidLine:
            if stroke.get("fill_enabled", False):
                 if "points" in stroke and stroke["points"]:
                     fill_path = QPainterPath()
                     pts = stroke["points"]
                     if pts:
                         fill_path.moveTo(pts[0][0])
                         for i in range(1, len(pts)): fill_path.lineTo(pts[i][0])
                         fill_path.closeSubpath()
                     painter.setPen(Qt.NoPen)
                     painter.setBrush(stroke.get("fill_color", QColor(255, 200, 0, 100))) 
                     painter.drawPath(fill_path)

            if st_type == "highlighter":
                 c = QColor(stroke["color"].red(), stroke["color"].green(), stroke["color"].blue(), 80)
                 painter.setBrush(c); painter.setPen(Qt.NoPen)
                 painter.setCompositionMode(QPainter.CompositionMode_Multiply) 
            elif st_type == "eraser":
                 painter.setCompositionMode(QPainter.CompositionMode_Clear)
                 painter.setBrush(Qt.black); painter.setPen(Qt.NoPen)
            else:
                 painter.setBrush(stroke["color"]); painter.setPen(Qt.NoPen)
                 painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawPath(path)
        else:
            pen = QPen(stroke["color"], stroke["size"], stroke.get("style", Qt.SolidLine), Qt.RoundCap, Qt.RoundJoin)
            
            if st_type == "highlighter":
                pen.setColor(QColor(stroke["color"].red(), stroke["color"].green(), stroke["color"].blue(), 80))
                pen.setWidth(stroke["size"] + 10); painter.setCompositionMode(QPainter.CompositionMode_Multiply)
            elif st_type == "eraser":
                painter.setCompositionMode(QPainter.CompositionMode_Clear); pen.setColor(Qt.transparent); pen.setWidth(stroke["size"])
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                
            painter.setPen(pen)
            
            if stroke.get("fill_enabled", False):
                painter.setBrush(stroke.get("fill_color", QColor(255, 200, 0, 100)))
            else:
                painter.setBrush(Qt.NoBrush)
            
            if "points" in stroke and stroke["points"]:
                simple_path = QPainterPath()
                pts = stroke["points"]
                if pts:
                    simple_path.moveTo(pts[0][0])
                    for i in range(1, len(pts)): simple_path.lineTo(pts[i][0])
                painter.drawPath(simple_path)
            else:
                painter.drawPath(path)

    def generate_shape_path(self, path, shape_type, start, end):
        rect = QRect(start, end).normalized()
        if shape_type == "rect": path.addRect(rect)
        elif shape_type == "circle": path.addEllipse(rect)
        elif shape_type == "line": path.moveTo(start); path.lineTo(end)
        elif shape_type == "arrow":
            path.moveTo(start); path.lineTo(end)
            dx, dy = end.x() - start.x(), end.y() - start.y(); angle = math.atan2(dy, dx); arrow_size = 20
            p1 = QPointF(end.x() - arrow_size * math.cos(angle - math.pi / 6), end.y() - arrow_size * math.sin(angle - math.pi / 6))
            p2 = QPointF(end.x() - arrow_size * math.cos(angle + math.pi / 6), end.y() - arrow_size * math.sin(angle + math.pi / 6))
            path.moveTo(end); path.lineTo(p1); path.moveTo(end); path.lineTo(p2)
        elif shape_type == "polygon":
            center = rect.center(); radius = min(rect.width(), rect.height()) / 2; poly = QPolygonF()
            for i in range(6): theta = 2.0 * math.pi * i / 6; poly.append(QPointF(center.x() + radius * math.cos(theta), center.y() + radius * math.sin(theta)))
            poly.append(poly[0]); path.addPolygon(poly)
        elif shape_type == "star":
            center = rect.center(); r_out = min(rect.width(), rect.height())/2; r_in = r_out/2.5; poly = QPolygonF()
            for i in range(5):
                th_o = (2.0*math.pi*i/5)-(math.pi/2); poly.append(QPointF(center.x()+r_out*math.cos(th_o), center.y()+r_out*math.sin(th_o)))
                th_i = (2.0*math.pi*(i+0.5)/5)-(math.pi/2); poly.append(QPointF(center.x()+r_in*math.cos(th_i), center.y()+r_in*math.sin(th_i)))
            poly.append(poly[0]); path.addPolygon(poly)

    def delete_stroke_at(self, pos):
        r = self.active_size / 2
        eraser_area = QPainterPath(); eraser_area.addEllipse(pos, r, r) 
        for i in range(len(self.strokes) - 1, -1, -1):
            stroke = self.strokes[i]
            if stroke["type"] == "text":
                if (stroke["pos"] - pos).manhattanLength() < 30: self.strokes.pop(i); return True
            elif stroke["path"].intersects(eraser_area): self.strokes.pop(i); return True
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        if state.board_color.alpha() > 0: painter.fillRect(self.rect(), state.board_color)
        elif self.active_tool not in ["tool_cursor", "tool_pan"]: painter.fillRect(self.rect(), QColor(255, 255, 255, 1))
            
        if self.buffer_pixmap:
            target_rect = QRect(0, 0, self.width(), self.height())
            painter.drawPixmap(target_rect, self.buffer_pixmap, self.buffer_pixmap.rect())
        
        if self.snapped_shape:
            painter.setRenderHint(QPainter.Antialiasing)
            self.draw_stroke_entity(painter, self.snapped_shape)
        elif self.current_stroke:
            painter.setRenderHint(QPainter.Antialiasing)
            st_type = self.current_stroke["type"]
            
            if st_type in ["pen", "highlighter", "eraser", "laser_pen"]:
                self.draw_stroke_entity(painter, self.current_stroke)
            else:
                temp_path = QPainterPath()
                self.generate_shape_path(temp_path, st_type, self.current_stroke["start"], self.current_stroke["end"])
                
                temp_stroke = self.current_stroke.copy()
                temp_stroke["path"] = temp_path
                self.draw_stroke_entity(painter, temp_stroke)
        
        if self.selected_indices:
            painter.setRenderHint(QPainter.Antialiasing)
            self.draw_selection_overlay(painter)
        elif self.selection_path and "select" in self.active_tool:
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(self.theme_border, 2, Qt.DashLine); painter.setPen(pen)
            painter.setBrush(self.theme_fill)
            painter.drawPath(self.selection_path)