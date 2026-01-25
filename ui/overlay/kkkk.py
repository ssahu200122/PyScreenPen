import math
import os
import time
import cv2          
import numpy as np
import statistics
from PySide6.QtWidgets import QWidget, QLineEdit, QFileDialog
from PySide6.QtCore import Qt, QPoint, QRect, QPointF, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QBrush, QPolygonF, QRegion, QPixmap, QFont, QFontMetrics, QKeySequence, QCursor, QTransform

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
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.strokes = []       
        self.redo_stack = [] 
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
        self.theme_border = QColor("#8E24AA") 
        self.theme_fill = QColor(142, 36, 170, 25) 

        # --- LASER / VANISHING INK ---
        self.laser_points = [] 
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

        self.set_tool(self.active_tool)

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
        if tool_id == "tool_cursor": self.setCursor(Qt.ArrowCursor)
        elif tool_id == "tool_laser": self.setCursor(self.cursors["laser"]) 
        elif "pen" in tool_id: self.setCursor(self.cursors["pen"])
        elif "eraser" in tool_id: self.setCursor(self.cursors["eraser"])
        elif "hl" in tool_id: self.setCursor(self.cursors["hl"])
        elif "text" in tool_id: self.setCursor(self.cursors["text"])
        elif "tool_select" in tool_id: self.setCursor(self.cursors["select"])
        elif "tool_" in tool_id: self.setCursor(self.cursors["shape"])
        else: self.setCursor(Qt.ArrowCursor)

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

    def check_vanishing_strokes(self):
        if not self.strokes: return
        now = time.time()
        initial_count = len(self.strokes)
        self.strokes = [s for s in self.strokes if s.get("vanish_deadline", float('inf')) > now]
        if len(self.strokes) < initial_count:
            self.redraw_buffer(); self.update()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Undo): self.handle_action("action_undo"); event.accept()
        elif event.matches(QKeySequence.Redo): self.handle_action("action_redo"); event.accept()
        elif event.matches(QKeySequence.Save): self.save_canvas(); event.accept()
        elif event.key() == Qt.Key_Escape:
            if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
            else: 
                self.selected_indices = []
                self.selection_path = None
                self.edit_btn_rect = None 
                self.active_handle = None
                state.set_selection_active(False)
                state.set_active_tool("tool_cursor")
            self.update()
            event.accept()
        elif event.key() == Qt.Key_Delete:
            if self.selected_indices:
                for idx in sorted(self.selected_indices, reverse=True): self.strokes.pop(idx)
                self.selected_indices = []
                self.selection_path = None
                self.edit_btn_rect = None 
                state.set_selection_active(False)
                self.redraw_buffer()
                self.update()
            else: self.handle_action("clear_canvas")
            event.accept()
        else: super().keyPressEvent(event)

    def set_tool(self, tool_id):
        self.active_tool = tool_id
        if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
        self.active_color = state.current_color
        if "eraser" in tool_id:
            self.active_size = state.eraser_size
        else:
            self.active_size = state.current_thickness
        self.active_opacity = state.current_opacity
        self.active_style = state.current_style
        self.active_font_style = state.current_font_style 
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
                self.strokes[i]["size"] = size
                c = self.strokes[i]["color"]; c.setAlpha(opacity); self.strokes[i]["color"] = c
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
            if self.strokes: self.strokes.pop(); self.redo_stack.append(self.strokes); self.redraw_buffer(); self.update()
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
                txt_w = stroke.get("text_width", 100); txt_h = stroke.get("text_height", stroke["size"] + 5)
                item_rect = QRectF(stroke["pos"].x(), stroke["pos"].y() - stroke["size"], txt_w, txt_h)
            else: item_rect = stroke["path"].boundingRect()
            if self.selection_path.contains(item_rect): self.selected_indices.append(i)

    def move_selection(self, delta):
        self.selection_rect.translate(delta)
        if self.selection_path: self.selection_path.translate(delta)
        if self.edit_btn_rect: self.edit_btn_rect.translate(delta)
        for i in self.selected_indices:
            stroke = self.strokes[i]
            if stroke["type"] == "text": stroke["pos"] += delta
            else: stroke["path"].translate(delta)

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
            self.snapped_shape = {
                "type": "pen", "color": self.active_color, "size": self.active_size,
                "opacity": self.active_opacity, "style": self.active_style,
                "path": detected_path, "is_preview": True, "shape_type": shape_type
            }
            self.is_scaling_shape = True
            self.base_snapped_path = detected_path 
            self.shape_center = detected_path.boundingRect().center()
            if shape_type == "line": self.shape_center = start 
            
            curr_pos = self.current_points[-1]
            # Calculate Initial Radius
            self.scale_start_dist = math.hypot(curr_pos.x() - self.shape_center.x(), curr_pos.y() - self.shape_center.y())
            if self.scale_start_dist < 1: self.scale_start_dist = 1
            
            # Calculate Initial Angle (for rotation check)
            start_vec = curr_pos - self.shape_center
            self.snap_start_angle = math.atan2(start_vec.y(), start_vec.x())
            
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            context = "selection_context" if self.selected_indices else "root"
            state.request_menu_context.emit(context)
            return

        if event.button() == Qt.LeftButton:
            # Check Handles First
            if self.selected_indices:
                handles = self.get_handles()
                for key, rect in handles.items():
                    if rect.contains(event.position()):
                        self.transform_mode = "rotate" if key == "rot" else "scale"
                        self.active_handle = key
                        self.move_start_pos = event.position()
                        self.original_selection_rect = QRectF(self.selection_rect)
                        # Prepare math data for rotation
                        self.transform_center = self.selection_rect.center()
                        mouse_vec = event.position() - self.transform_center
                        self.transform_start_angle = math.atan2(mouse_vec.y(), mouse_vec.x())
                        
                        # Deep copy for non-destructive
                        self.original_selected_strokes = [self.strokes[i].copy() for i in self.selected_indices]
                        for k, stroke in enumerate(self.original_selected_strokes):
                            if stroke["type"] != "text": stroke["path"] = QPainterPath(self.strokes[self.selected_indices[k]]["path"])
                        return

            if self.edit_btn_rect and self.edit_btn_rect.contains(event.position()):
                state.request_menu_context.emit("selection_context"); return

            if self.menu_ref and self.menu_ref.geometry().contains(event.globalPosition().toPoint()): return 
            if self.active_tool == "tool_text":
                if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
                else: self.spawn_text_input(event.position().toPoint())
                return
            
            self.is_drawing = True
            self.last_pos = event.position()
            self.current_pos = self.last_pos
            self.start_pos = self.last_pos.toPoint()
            self.redo_stack = []
            
            self.current_points = [self.last_pos]
            self.snapped_shape = None
            self.is_scaling_shape = False
            self.shape_hold_timer.stop()

            if "select" in self.active_tool:
                # Check move
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
                "path": QPainterPath(), "start": self.start_pos, "end": self.start_pos
            }
            if self.current_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]: self.current_stroke["path"].moveTo(self.last_pos)

    def mouseMoveEvent(self, event):
        pos = event.position()
        
        # 1. Transform Handles (Scale/Rotate)
        if self.transform_mode:
            if self.transform_mode == "scale":
                # Get Anchor and Distances
                anchor = self.get_anchor_point(self.active_handle)
                orig_vector = self.move_start_pos - anchor
                curr_vector = pos - anchor
                
                # Avoid division by zero
                sx = 1.0; sy = 1.0
                if abs(orig_vector.x()) > 1: sx = curr_vector.x() / orig_vector.x()
                if abs(orig_vector.y()) > 1: sy = curr_vector.y() / orig_vector.y()
                
                # Apply Transform
                transform = QTransform()
                transform.translate(anchor.x(), anchor.y())
                transform.scale(sx, sy)
                transform.translate(-anchor.x(), -anchor.y())
                
                # Update Strokes
                united_rect = QRectF()
                first = True
                
                for idx, orig_stroke in enumerate(self.original_selected_strokes):
                    real_idx = self.selected_indices[idx]
                    if orig_stroke["type"] == "text":
                        new_pos = transform.map(orig_stroke["pos"])
                        self.strokes[real_idx]["pos"] = new_pos
                        # Approximate rect for text
                        item_rect = QRectF(new_pos.x(), new_pos.y() - orig_stroke["size"], orig_stroke.get("text_width", 10), orig_stroke.get("text_height", 10))
                    else:
                        self.strokes[real_idx]["path"] = transform.map(orig_stroke["path"])
                        item_rect = self.strokes[real_idx]["path"].boundingRect()
                    
                    if first: united_rect = item_rect; first = False
                    else: united_rect = united_rect.united(item_rect)
                
                self.selection_rect = united_rect.adjusted(-10, -10, 10, 10)
                self.selection_path = QPainterPath()
                self.selection_path.addRect(self.selection_rect)
                self.redraw_buffer(); self.update()
                
            elif self.transform_mode == "rotate":
                center = self.transform_center
                mouse_vec = pos - center
                curr_angle = math.atan2(mouse_vec.y(), mouse_vec.x())
                delta_angle_rad = curr_angle - self.transform_start_angle
                delta_angle_deg = math.degrees(delta_angle_rad)
                
                transform = QTransform()
                transform.translate(center.x(), center.y())
                transform.rotate(delta_angle_deg)
                transform.translate(-center.x(), -center.y())
                
                united_rect = QRectF(); first = True
                
                for idx, orig_stroke in enumerate(self.original_selected_strokes):
                    real_idx = self.selected_indices[idx]
                    if orig_stroke["type"] == "text":
                        new_pos = transform.map(orig_stroke["pos"])
                        self.strokes[real_idx]["pos"] = new_pos
                        item_rect = QRectF(new_pos.x(), new_pos.y() - orig_stroke["size"], orig_stroke.get("text_width", 10), orig_stroke.get("text_height", 10))
                    else:
                        self.strokes[real_idx]["path"] = transform.map(orig_stroke["path"])
                        item_rect = self.strokes[real_idx]["path"].boundingRect()
                        
                    if first: united_rect = item_rect; first = False
                    else: united_rect = united_rect.united(item_rect)
                
                self.selection_rect = united_rect.adjusted(-10, -10, 10, 10)
                self.selection_path = QPainterPath()
                self.selection_path.addRect(self.selection_rect)
                self.redraw_buffer(); self.update()
                
            return

        # 2. Scaling & Rotating Shape (Magic Shape Hold)
        if self.is_scaling_shape and self.snapped_shape:
            if self.snapped_shape["shape_type"] == "line":
                path = QPainterPath(); path.moveTo(self.current_points[0]); path.lineTo(pos); self.snapped_shape["path"] = path
            else:
                # Calculate Scale (Distance)
                current_dist = math.hypot(pos.x() - self.shape_center.x(), pos.y() - self.shape_center.y())
                scale_factor = current_dist / self.scale_start_dist
                
                # Calculate Rotation (Angle difference)
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

        # 3. Update Laser Tail (if active)
        if self.active_tool == "tool_laser":
            self.laser_points.append(pos); self.update()
            # Falls through to drawing logic below so we also get the stroke recorded

        # 4. Handle Cursors for Selection
        if self.selected_indices and not self.is_drawing:
            handles = self.get_handles()
            h_cursor = Qt.ArrowCursor
            if handles["tl"].contains(pos) or handles["br"].contains(pos): h_cursor = Qt.SizeFDiagCursor
            elif handles["tr"].contains(pos) or handles["bl"].contains(pos): h_cursor = Qt.SizeBDiagCursor
            elif handles["tm"].contains(pos) or handles["bm"].contains(pos): h_cursor = Qt.SizeVerCursor
            elif handles["lm"].contains(pos) or handles["rm"].contains(pos): h_cursor = Qt.SizeHorCursor
            elif handles["rot"].contains(pos): h_cursor = Qt.PointingHandCursor
            if self.cursor().shape() != h_cursor: self.setCursor(h_cursor)

        # 5. Main Drawing Logic
        if self.is_drawing:
            # Check Magic Shape Timer (only if Pen)
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
                    mid_x = (self.last_pos.x() + pos.x()) / 2; mid_y = (self.last_pos.y() + pos.y()) / 2
                    self.current_stroke["path"].quadTo(self.last_pos, QPointF(mid_x, mid_y)); self.last_pos = pos
                else: self.current_stroke["end"] = pos.toPoint()
                self.update()

    def mouseReleaseEvent(self, event):
        self.shape_hold_timer.stop()
        self.is_scaling_shape = False 
        self.transform_mode = None
        self.active_handle = None
        
        if event.button() == Qt.LeftButton and self.is_drawing:
            self.is_drawing = False
            if "select" in self.active_tool:
                if self.is_moving_selection:
                    self.is_moving_selection = False
                    if self.active_tool == "tool_select_lasso": self.selection_path.closeSubpath()
                else:
                    if self.active_tool == "tool_select_lasso": self.selection_path.closeSubpath()
                    self.find_selected_strokes()
                    if not self.selected_indices:
                        self.selection_path = None
                        self.edit_btn_rect = None
                        self.selection_rect = QRectF()
                        state.set_selection_active(False)
                    else:
                        self.is_internal_sync = True
                        state.set_selection_active(True)
                        last_stroke = self.strokes[self.selected_indices[-1]]
                        s_col = last_stroke.get("color", QColor("black"))
                        s_size = last_stroke.get("size", 2)
                        s_style = last_stroke.get("style", Qt.SolidLine)
                        state.sync_tool_properties(color=s_col, thickness=s_size, style=s_style)
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
                        self.selection_path = QPainterPath()
                        self.selection_path.addRect(self.selection_rect)
                        
                        rect = self.selection_rect
                        btn_size = 28
                        self.edit_btn_rect = QRectF(rect.right() - btn_size/2, rect.top() - btn_size/2, btn_size, btn_size)
                self.update(); return

            if self.current_stroke:
                final_stroke = self.current_stroke
                if self.snapped_shape:
                    final_stroke = self.snapped_shape; self.snapped_shape = None 
                else:
                    if self.current_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]: self.current_stroke["path"].lineTo(self.last_pos)
                    else:
                        path = QPainterPath()
                        self.generate_shape_path(path, self.current_stroke["type"], self.current_stroke["start"], self.current_stroke["end"])
                        self.current_stroke["path"] = path
                
                if final_stroke["type"] == "laser_pen": final_stroke["vanish_deadline"] = time.time() + state.laser_duration
                self.strokes.append(final_stroke)
                painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
                self.draw_stroke_entity(painter, final_stroke); painter.end()
                self.current_stroke = None; self.update()

    def draw_selection_overlay(self, painter):
        if not self.selected_indices: return
        # AESTHETIC CHANGE: Modern Violet
        pen = QPen(self.theme_border, 2, Qt.SolidLine)
        painter.setPen(pen); painter.setBrush(self.theme_fill)
        painter.drawRect(self.selection_rect)
        
        handles = self.get_handles()
        # Handle Border Color matches Theme
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
            glow_pen = QPen(glow_color, stroke["size"] + 8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(glow_pen)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            core_pen = QPen(Qt.white, max(1, stroke["size"] - 2), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(core_pen)
            painter.drawPath(path)
            return

        pen = QPen(stroke["color"], stroke["size"], stroke["style"], Qt.RoundCap, Qt.RoundJoin)
        if st_type == "highlighter":
            pen.setColor(QColor(stroke["color"].red(), stroke["color"].green(), stroke["color"].blue(), 80))
            pen.setWidth(stroke["size"] + 10); painter.setCompositionMode(QPainter.CompositionMode_Multiply) 
        elif st_type == "eraser":
            painter.setCompositionMode(QPainter.CompositionMode_Clear); pen.setColor(Qt.transparent); pen.setWidth(stroke["size"])
        else: painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawPath(path)

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
        eraser_area = QPainterPath(); eraser_area.addEllipse(pos, 10, 10) 
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
            if self.current_stroke["type"] != "text":
                if self.current_stroke["type"] not in ["pen", "highlighter", "eraser", "laser_pen"]:
                    temp_path = QPainterPath()
                    self.generate_shape_path(temp_path, self.current_stroke["type"], self.current_stroke["start"], self.current_stroke["end"])
                    temp_stroke = self.current_stroke.copy(); temp_stroke["path"] = temp_path
                    self.draw_stroke_entity(painter, temp_stroke)
                else: self.draw_stroke_entity(painter, self.current_stroke)
        
        if self.laser_points:
            painter.setRenderHint(QPainter.Antialiasing)
            points_len = len(self.laser_points)
            if points_len > 1:
                base_color = state.current_color 
                for i in range(points_len - 1):
                    opacity_factor = (i + 1) / points_len 
                    opacity = int((opacity_factor ** 2) * 255)
                    segment_color = QColor(base_color)
                    segment_color.setAlpha(opacity)
                    pen = QPen(segment_color, 6 * opacity_factor, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.drawLine(self.laser_points[i], self.laser_points[i+1])
            head_pos = self.laser_points[-1]
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(state.current_color))
            painter.drawEllipse(head_pos, 4, 4)
            glow_color = QColor(state.current_color); glow_color.setAlpha(80)
            painter.setBrush(glow_color); painter.drawEllipse(head_pos, 8, 8)

        if self.selected_indices:
            painter.setRenderHint(QPainter.Antialiasing)
            self.draw_selection_overlay(painter)
        elif self.selection_path and "select" in self.active_tool:
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(self.theme_border, 2, Qt.DashLine); painter.setPen(pen)
            painter.setBrush(self.theme_fill)
            painter.drawPath(self.selection_path)