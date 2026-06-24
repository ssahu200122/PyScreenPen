import math
import os
import sys
import time
import cv2          
import numpy as np
import statistics
import keyboard
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QLineEdit, QFileDialog, QApplication, QPushButton
from PySide6.QtCore import Qt, QPoint, QRect, QPointF, QRectF, QTimer
from PySide6.QtGui import (
    QPainter, QColor, QPen, QPainterPath, QBrush, QPolygonF, QRegion, 
    QPixmap, QFont, QFontMetrics, QKeySequence, QCursor, QTransform, 
    QTabletEvent, QPainterPathStroker, QInputDevice
)

def get_asset_path(filename):
    try: base_path = sys._MEIPASS
    except AttributeError: base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets", filename)

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
        self.setAttribute(Qt.WA_TabletTracking)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.strokes = []       
        self.redo_stack = [] 
        self.clipboard = []              
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

        self.transform_mode = None  
        self.active_handle = None   
        self.selection_rect = QRectF() 
        self.original_selection_rect = QRectF() 
        self.original_selected_strokes = [] 
        self.rotation_angle = 0.0
        self.transform_center = QPointF()
        self.transform_start_angle = 0.0

        self.theme_border = QColor("#6c5ce7") 
        self.theme_fill = QColor(108, 92, 231, 30) 
        self.aesthetic_shape_color = QColor("#6c5ce7")

        self.vanish_timer = QTimer(self)
        self.vanish_timer.setInterval(100) 
        self.vanish_timer.timeout.connect(self.check_vanishing_strokes)
        self.vanish_timer.start()

        self.current_points = []  
        self.snapped_shape = None 
        self.is_scaling_shape = False 
        self.base_snapped_path = None 
        
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
        
        # Bind the canvas redraw to our new pattern settings
        state.pattern_changed.connect(self.update)

        QApplication.setOverrideCursor(Qt.ArrowCursor)
        self.set_tool(self.active_tool)

        self.global_hotkey_signal.connect(self.process_global_hotkey)
        self.setup_global_shortcuts()

    def setup_global_shortcuts(self):
        import keyboard 
        keyboard.unhook_all()
        def bind_dynamic_key(action_id):
            key_seq = state.get_shortcut(action_id)
            if not key_seq: return
            kb_seq = key_seq.lower().replace("meta", "windows").replace("control", "ctrl").replace("escape", "esc").replace("return", "enter").replace(" ", "")
            try: keyboard.add_hotkey(kb_seq, lambda a=action_id: self.global_hotkey_signal.emit(a), suppress=True, trigger_on_release=True)
            except Exception as e: print(f"Failed to bind hotkey {kb_seq}: {e}")

        action_ids = ["increase_size", "decrease_size", "toggle_eraser", "toggle_cursor", "toggle_board", "toggle_lasso", "clear_canvas", "toggle_laser","exit_app","toggle_visibility", "toggle_ghost"]
        for aid in action_ids: bind_dynamic_key(aid)

    def process_global_hotkey(self, action_id):
        current_tool = state.active_tool_id
        if action_id == "increase_size":
            new_size = min(100, self.active_size + 2)
            state.set_active_tool(f"set_eraser_size_{new_size}" if "eraser" in current_tool else f"set_thickness_{new_size}")
        elif action_id == "decrease_size":
            new_size = max(1, self.active_size - 2)
            state.set_active_tool(f"set_eraser_size_{new_size}" if "eraser" in current_tool else f"set_thickness_{new_size}")
        elif action_id == "toggle_eraser": state.set_active_tool(getattr(self, "last_pen_used", "tool_pen_1") if current_tool == "tool_eraser" else "tool_eraser")
        elif action_id == "toggle_cursor": state.set_active_tool(getattr(self, "last_pen_used", "tool_pen_1") if current_tool == "tool_cursor" else "tool_cursor")
        elif action_id == "toggle_board": state.set_active_tool("toggle_board")
        elif action_id == "toggle_lasso": state.set_active_tool("tool_pen_1" if current_tool == "tool_select_lasso" else "tool_select_lasso")
        elif action_id == "clear_canvas": self.handle_action("clear_canvas")
        elif action_id == "toggle_laser": state.set_active_tool("tool_hl" if current_tool == "tool_laser" else "tool_laser")
        elif action_id == "exit_app": QApplication.quit()
        elif action_id == "toggle_visibility":
            target_state = not self.isVisible()
            self.setVisible(target_state)
            if self.menu_ref: self.menu_ref.setVisible(target_state)
        elif action_id == "toggle_ghost":
            if self.menu_ref: self.menu_ref.setVisible(not self.menu_ref.isVisible())

    def load_cursors(self):
        def create_cursor(filename, hot_x, hot_y, fallback=Qt.ArrowCursor):
            path = get_asset_path(filename) 
            if os.path.exists(path):
                pix = QPixmap(path).scaled(32, 32, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
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
        QApplication.restoreOverrideCursor() 
        QApplication.setOverrideCursor(cursor)
        QApplication.processEvents() 

    def set_menu_ref(self, menu): self.menu_ref = menu

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
                if not self.strokes[i].get("locked", False):
                    self.strokes[i]["fill_color"] = color
            self.redraw_buffer(); self.update()

    def check_vanishing_strokes(self):
        if not self.strokes: return
        now = time.time()
        initial_count = len(self.strokes)
        self.strokes = [s for s in self.strokes if s.get("vanish_deadline", float('inf')) > now]
        if len(self.strokes) < initial_count:
            self.update_selection_rect(); self.redraw_buffer(); self.update()

    def update_selection_rect(self):
        if not self.selected_indices:
            self.selection_rect = QRectF(); self.selection_path = None; self.edit_btn_rect = None; return
        united_rect = QRectF()
        first = True
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
        btn_size = 28
        self.edit_btn_rect = QRectF(self.selection_rect.right() - btn_size/2, self.selection_rect.top() - btn_size/2, btn_size, btn_size)

    def import_image_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Image", "", "Images (*.png *.xpm *.jpg *.bmp *.jpeg)")
        if file_path: self.import_image_stroke(QPixmap(file_path))

    def import_image_stroke(self, pixmap):
        if pixmap.isNull(): return
        max_size = 800
        if pixmap.width() > max_size or pixmap.height() > max_size: pixmap = pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pos = QPointF(100, 100); base_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        path = QPainterPath(); path.addRect(base_rect); path.translate(pos)
        transform = QTransform(); transform.translate(pos.x(), pos.y())
        stroke = { "type": "image", "pixmap": pixmap, "base_rect": base_rect, "path": path, "transform": transform, "color": QColor("transparent"), "size": 1, "style": Qt.SolidLine, "locked": False }
        self.strokes.append(stroke)
        state.set_active_tool("tool_cursor")
        self.selected_indices = [len(self.strokes) - 1]
        self.update_selection_rect(); state.set_selection_active(True); self.redraw_buffer(); self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_B: state.set_active_tool("tool_pen_2" if state.active_tool_id == "tool_pen_1" else "tool_pen_1")
        elif key == Qt.Key_E: state.set_active_tool("tool_pen_1" if "eraser" in state.active_tool_id else "tool_eraser") 
        elif key == Qt.Key_H: state.set_active_tool("tool_hl")
        elif key == Qt.Key_L and event.modifiers() == Qt.NoModifier: state.set_active_tool("tool_select_lasso")
        elif key == Qt.Key_S: 
            if state.active_tool_id == "tool_rect": state.set_active_tool("tool_circle")
            elif state.active_tool_id == "tool_circle": state.set_active_tool("tool_arrow")
            else: state.set_active_tool("tool_rect")
        elif key == Qt.Key_Space: state.set_active_tool("tool_pen_1" if state.active_tool_id == "tool_pan" else "tool_pan")
        elif event.matches(QKeySequence.Undo): self.handle_action("action_undo"); event.accept()
        elif event.matches(QKeySequence.Redo): self.handle_action("action_redo"); event.accept()
        elif event.matches(QKeySequence.Save): self.save_canvas(); event.accept()
        elif event.matches(QKeySequence.Open) or (key == Qt.Key_I and event.modifiers() == Qt.ControlModifier): self.import_image_from_file(); event.accept()
        elif key == Qt.Key_L and event.modifiers() == Qt.ControlModifier:
            if self.selected_indices:
                for i in self.selected_indices: self.strokes[i]["locked"] = not self.strokes[i].get("locked", False)
                self.redraw_buffer(); self.update()
            event.accept()
        elif event.matches(QKeySequence.Copy):
            if self.selected_indices:
                self.clipboard = []
                for i in self.selected_indices:
                    stroke = self.strokes[i].copy(); stroke["locked"] = False
                    if stroke["type"] == "image": stroke["path"] = QPainterPath(self.strokes[i]["path"]); stroke["transform"] = QTransform(self.strokes[i]["transform"])
                    elif stroke["type"] != "text": stroke["path"] = QPainterPath(self.strokes[i]["path"])
                    if "points" in stroke and stroke["points"]: stroke["points"] = list(stroke["points"])
                    self.clipboard.append(stroke)
            event.accept()
        elif event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard(); mime_data = clipboard.mimeData()
            if mime_data.hasImage() and not clipboard.image().isNull():
                self.import_image_stroke(QPixmap.fromImage(clipboard.image())); event.accept(); return

            if hasattr(self, 'clipboard') and self.clipboard:
                new_indices = []; offset = QPointF(30, 30); self.selected_indices = []
                for stroke in self.clipboard:
                    new_stroke = stroke.copy(); new_stroke["locked"] = False
                    if new_stroke["type"] == "text": new_stroke["pos"] = new_stroke["pos"] + offset.toPoint()
                    elif new_stroke["type"] == "image":
                        new_path = QPainterPath(stroke["path"]); new_path.translate(offset); new_stroke["path"] = new_path
                        trans = QTransform(); trans.translate(offset.x(), offset.y()); new_stroke["transform"] = stroke["transform"] * trans
                    else:
                        new_path = QPainterPath(stroke["path"]); new_path.translate(offset); new_stroke["path"] = new_path
                        if "points" in new_stroke and new_stroke["points"]: new_stroke["points"] = [(p[0] + offset, p[1]) for p in stroke["points"]]
                    self.strokes.append(new_stroke); new_indices.append(len(self.strokes) - 1)
                
                self.clipboard = []
                for i in new_indices:
                    s = self.strokes[i].copy()
                    if s["type"] == "image": s["path"] = QPainterPath(self.strokes[i]["path"]); s["transform"] = QTransform(self.strokes[i]["transform"])
                    elif s["type"] != "text": s["path"] = QPainterPath(self.strokes[i]["path"])
                    if "points" in s and s["points"]: s["points"] = list(s["points"])
                    self.clipboard.append(s)
                
                self.selected_indices = new_indices
                self.update_selection_rect(); state.set_selection_active(True); self.redraw_buffer(); self.update()
            event.accept()

        elif key == Qt.Key_Escape:
            if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
            else: self.selected_indices = []; self.update_selection_rect(); self.active_handle = None; state.set_selection_active(False); state.set_active_tool("tool_cursor")
            self.update(); event.accept()
            
        elif key == Qt.Key_Delete:
            if self.selected_indices:
                indices_to_delete = [idx for idx in sorted(self.selected_indices, reverse=True) if not self.strokes[idx].get("locked", False)]
                for idx in indices_to_delete: self.strokes.pop(idx)
                self.selected_indices = []; self.update_selection_rect(); state.set_selection_active(False); self.redraw_buffer(); self.update()
            else: self.handle_action("clear_canvas")
            event.accept()
        else: super().keyPressEvent(event)

    def set_tool(self, tool_id):
        if "select" not in tool_id and "cursor" not in tool_id:
            self.selected_indices = []; self.update_selection_rect(); state.set_selection_active(False); self.update()

        if tool_id in ["tool_pen_1", "tool_pen_2"]: self.last_pen_used = tool_id

        self.active_tool = tool_id
        if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
        
        is_shape = any(k in tool_id for k in ["line", "arrow", "rect", "circle", "polygon", "star"])
        is_selection = "select" in tool_id or "cursor" in tool_id
        
        self.active_color = self.aesthetic_shape_color if (is_shape and not is_selection) else state.current_color
        self.active_size = state.eraser_size if "eraser" in tool_id else state.current_thickness
        self.active_opacity = state.current_opacity
        self.active_style = state.current_style
        self.active_font_style = state.current_font_style 
        
        self.apply_custom_cursor(tool_id)
        
        is_board_active = state.board_color.alpha() > 0 or state.pattern_type != "none"
        self.setAttribute(Qt.WA_TransparentForMouseEvents, not is_board_active if tool_id in ["tool_cursor", "tool_pan"] else False)
        self.update(); self.setFocus() 

    def set_color(self, color): 
        self.active_color = color
        if self.is_internal_sync: return 
        if self.selected_indices:
            for i in self.selected_indices: 
                if not self.strokes[i].get("locked", False): self.strokes[i]["color"] = color
            self.redraw_buffer(); self.update()

    def set_brush(self, size, opacity): 
        self.active_size = state.eraser_size if "eraser" in self.active_tool else size
        self.active_opacity = opacity
        self.active_color.setAlpha(opacity)
        if self.is_internal_sync: return 
        if self.selected_indices:
            for i in self.selected_indices:
                stroke = self.strokes[i]
                if stroke.get("locked", False): continue
                stroke["size"] = size
                c = stroke["color"]; c.setAlpha(opacity); stroke["color"] = c
                if "points" in stroke and stroke["points"]: stroke["path"] = self.generate_variable_width_path(stroke["points"], size)
            self.update_selection_rect(); self.redraw_buffer(); self.update()
        
    def set_style(self, style_val):
        if isinstance(style_val, str) and style_val in ["Normal", "Bold", "Italic", "BoldItalic"]:
            self.active_font_style = style_val; target_key = "font_style"; target_val = style_val
        else:
            target_key = "style"
            if isinstance(style_val, str): target_val = { "solid": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine, "dashdot": Qt.DashDotLine }.get(style_val, Qt.SolidLine)
            else: target_val = style_val
            self.active_style = target_val

        if self.is_internal_sync: return 
        if self.selected_indices:
            for i in self.selected_indices:
                stroke = self.strokes[i]
                if stroke.get("locked", False): continue
                if stroke["type"] == "text" and target_key == "font_style": stroke["font_style"] = target_val
                elif stroke["type"] != "text" and target_key == "style": stroke["style"] = target_val
            self.redraw_buffer(); self.update()

    def handle_action(self, action):
        if action == "clear_canvas": 
            self.strokes = [s for s in self.strokes if s.get("locked", False)]
            self.redo_stack = []; self.update_selection_rect(); self.redraw_buffer(); self.update()
        elif action == "action_undo": 
            if self.strokes: 
                self.redo_stack.append(self.strokes.pop())
                if len(self.redo_stack) > 50: self.redo_stack.pop(0) 
                self.update_selection_rect(); self.redraw_buffer(); self.update()
        elif action == "action_redo":
             if self.redo_stack:
                stroke = self.redo_stack.pop(); self.strokes.append(stroke)
                painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
                self.draw_stroke_entity(painter, stroke); painter.end(); self.update()
        elif action == "action_save": self.save_canvas()
        elif action == "action_lock":
             if self.selected_indices:
                 for i in self.selected_indices: self.strokes[i]["locked"] = not self.strokes[i].get("locked", False)
                 self.redraw_buffer(); self.update()
        elif action == "delete_selection":
            if self.selected_indices:
                indices_to_delete = [idx for idx in sorted(self.selected_indices, reverse=True) if not self.strokes[idx].get("locked", False)]
                for idx in indices_to_delete: self.strokes.pop(idx)
                self.selected_indices = []; self.update_selection_rect(); state.set_selection_active(False); self.redraw_buffer(); self.update()
        elif action == "clear_selection":
            self.selected_indices = []; self.update_selection_rect(); state.set_selection_active(False); self.update()
        elif action == "open_settings":
            if not self.settings_win: self.settings_win = SettingsWindow(self)
            self.settings_win.show()

    def save_canvas(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Drawing", "", "PNG Image (*.png);;JPEG Image (*.jpg)")
        if file_path:
            if self.selection_path and self.active_tool in ["tool_select_rect", "tool_select_lasso"]:
                rect = self.selection_path.boundingRect().toRect().intersected(self.rect())
                if not rect.isEmpty(): self.grab(rect).save(file_path); return
            if state.board_color.alpha() > 0 or state.pattern_type != "none":
                final_pix = QPixmap(self.size())
                final_pix.fill(state.board_color if state.board_color.alpha() > 0 else Qt.white)
                painter = QPainter(final_pix)
                self.draw_background_pattern(painter) # Draw the grid/lines onto the save file
                painter.drawPixmap(0, 0, self.buffer_pixmap); painter.end()
                final_pix.save(file_path)
            else: self.buffer_pixmap.save(file_path)

    def find_selected_strokes(self):
        self.selected_indices = []
        if not self.selection_path: return
        for i, stroke in enumerate(self.strokes):
            if stroke["type"] == "eraser": continue
            if stroke["type"] == "text":
                txt_w = stroke.get("text_width", 100); txt_h = stroke.get("text_height", stroke["size"] + 5)
                if self.selection_path.contains(QRectF(stroke["pos"].x(), stroke["pos"].y() - stroke["size"], txt_w, txt_h)): self.selected_indices.append(i)
                continue

            if stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen", "image"]:
                if self.selection_path.contains(stroke["path"]): self.selected_indices.append(i)
            else:
                stroker = QPainterPathStroker(); stroker.setWidth(stroke["size"]) 
                if self.selection_path.contains(stroker.createStroke(stroke["path"])): self.selected_indices.append(i)

    def move_selection(self, delta):
        for i in self.selected_indices:
            stroke = self.strokes[i]
            if stroke.get("locked", False): continue
            if stroke["type"] == "text": stroke["pos"] += delta
            elif stroke["type"] == "image":
                stroke["path"].translate(delta)
                trans = QTransform(); trans.translate(delta.x(), delta.y()); stroke["transform"] = stroke["transform"] * trans
            else:
                stroke["path"].translate(delta)
                if "points" in stroke and stroke["points"]: stroke["points"] = [(p[0] + delta, p[1]) for p in stroke["points"]]
        self.update_selection_rect()

    def get_handles(self):
        r = self.selection_rect; h_size = 10 
        tl = QRectF(r.left()-h_size, r.top()-h_size, h_size, h_size); tr = QRectF(r.right(), r.top()-h_size, h_size, h_size)
        bl = QRectF(r.left()-h_size, r.bottom(), h_size, h_size); br = QRectF(r.right(), r.bottom(), h_size, h_size)
        tm = QRectF(r.center().x()-h_size/2, r.top()-h_size, h_size, h_size); bm = QRectF(r.center().x()-h_size/2, r.bottom(), h_size, h_size)
        lm = QRectF(r.left()-h_size, r.center().y()-h_size/2, h_size, h_size); rm = QRectF(r.right(), r.center().y()-h_size/2, h_size, h_size)
        rot_pt = QPointF(r.center().x(), r.top() - 30); rot = QRectF(rot_pt.x()-6, rot_pt.y()-6, 12, 12)
        return {"tl": tl, "tr": tr, "bl": bl, "br": br, "tm": tm, "bm": bm, "lm": lm, "rm": rm, "rot": rot}

    def get_anchor_point(self, handle):
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
            text_stroke = { "type": "text", "text": text, "pos": pos, "color": QColor(self.active_color), "size": font_size, "font_style": self.active_font_style, "path": QPainterPath(), "text_width": w, "text_height": h, "locked": False }
            self.strokes.append(text_stroke)
            painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
            self.draw_stroke_entity(painter, text_stroke); painter.end(); self.update()
        self.active_text_widget.deleteLater(); self.active_text_widget = None

    def snap_to_shape(self):
        if not self.current_points or len(self.current_points) < 10: return
        
        points_array = np.array([[p.x(), p.y()] for p in self.current_points], dtype=np.int32)
        start = self.current_points[0]; end = self.current_points[-1]
        perimeter = cv2.arcLength(points_array, False) 
        if perimeter == 0: return
        linearity = math.hypot(end.x() - start.x(), end.y() - start.y()) / perimeter
        
        detected_path = QPainterPath(); shape_type = None
        
        if linearity > 0.95:
            shape_type = "line"; detected_path.moveTo(start); detected_path.lineTo(end)
        else:
            approx_curve = cv2.approxPolyDP(points_array, 0.02 * perimeter, True) 
            vertex_count = len(approx_curve)
            poly_qpoints = [QPointF(float(p[0][0]), float(p[0][1])) for p in approx_curve]
            
            if vertex_count == 3:
                shape_type = "triangle"; detected_path.addPolygon(QPolygonF(poly_qpoints)); detected_path.closeSubpath() 
            elif vertex_count == 4 or vertex_count == 5:
                shape_type = "rect"; rect_data = cv2.minAreaRect(points_array); (center, (w, h), angle) = rect_data
                aspect_ratio = min(w, h) / max(w, h) if max(w, h) > 0 else 0
                if aspect_ratio > 0.90: side = (w + h) / 2; rect_data = (center, (side, side), angle)
                box = cv2.boxPoints(rect_data); perfect_poly = [QPointF(float(p[0]), float(p[1])) for p in box]
                detected_path.addPolygon(QPolygonF(perfect_poly)); detected_path.closeSubpath() 
            elif vertex_count > 5:
                shape_type = "circle"; detected_path.addEllipse(QPolygonF(self.current_points).boundingRect())

        if shape_type:
            self.snapped_shape = {
                "type": shape_type, "color": self.active_color, "size": self.active_size,
                "opacity": self.active_opacity, "style": self.active_style,
                "fill_enabled": state.current_fill_enabled, "fill_color": state.current_fill_color,
                "path": detected_path, "is_preview": True, "shape_type": shape_type, "locked": False
            }
            self.is_scaling_shape = True; self.base_snapped_path = detected_path 
            self.shape_center = start if shape_type == "line" else detected_path.boundingRect().center()
            
            curr_pos = self.current_points[-1]
            self.scale_start_dist = max(1.0, math.hypot(curr_pos.x() - self.shape_center.x(), curr_pos.y() - self.shape_center.y()))
            start_vec = curr_pos - self.shape_center
            self.snap_start_angle = math.atan2(start_vec.y(), start_vec.x())
            self.update()

    def generate_variable_width_path(self, points, base_size):
        if not points or len(points) < 2:
            path = QPainterPath()
            if points: path.addEllipse(points[0][0], max(1.0, (base_size * points[0][1]) / 2), max(1.0, (base_size * points[0][1]) / 2))
            return path

        left_pts = []; right_pts = []
        for i in range(len(points) - 1):
            p1, press1 = points[i]; p2, press2 = points[i+1]
            dx = p2.x() - p1.x(); dy = p2.y() - p1.y()
            length = math.hypot(dx, dy)
            if length == 0: continue
            
            nx = -dy / length; ny = dx / length
            w1 = max(1.0, base_size * press1)
            offset_x = nx * w1 * 0.5; offset_y = ny * w1 * 0.5
            
            left_pts.append(QPointF(p1.x() + offset_x, p1.y() + offset_y))
            right_pts.append(QPointF(p1.x() - offset_x, p1.y() - offset_y))
            
            if i == len(points) - 2:
                w2 = max(1.0, base_size * press2)
                off2_x = nx * w2 * 0.5; off2_y = ny * w2 * 0.5
                left_pts.append(QPointF(p2.x() + off2_x, p2.y() + off2_y))
                right_pts.append(QPointF(p2.x() - off2_x, p2.y() - off2_y))

        path = QPainterPath()
        if left_pts:
            path.moveTo(left_pts[0])
            for p in left_pts[1:]: path.lineTo(p)
            for p in reversed(right_pts): path.lineTo(p)
            path.closeSubpath()
        path.setFillRule(Qt.WindingFill)
        return path

    def tabletEvent(self, event: QTabletEvent):
        try:
            if HAS_POINTING_DEVICE:
                pt = event.pointerType(); current_tool = state.active_tool_id
                if pt == QPointingDevice.PointerType.Eraser and current_tool != "tool_eraser": state.set_active_tool("tool_eraser")
                elif pt == QPointingDevice.PointerType.Pen and current_tool == "tool_eraser": state.set_active_tool(getattr(self, "last_pen_used", "tool_pen_1"))
        except Exception: pass 

        pos = event.position(); pressure = event.pressure(); btns = event.buttons()
        if pressure == 0.0: pressure = 1.0 
        
        if event.type() == QTabletEvent.TabletPress: self._handle_input(pos, pressure, "press", Qt.LeftButton if btns == Qt.NoButton else btns); event.accept()
        elif event.type() == QTabletEvent.TabletMove: self._handle_input(pos, pressure, "move", btns); event.accept()
        elif event.type() == QTabletEvent.TabletRelease: self._handle_input(pos, pressure, "release", btns); event.accept()

    def mousePressEvent(self, event): self._handle_input(event.position(), 1.0, "press", event.button())
    def mouseMoveEvent(self, event): self._handle_input(event.position(), 1.0, "move", event.buttons())
    def mouseReleaseEvent(self, event): self._handle_input(event.position(), 1.0, "release", event.button())

    def _handle_input(self, posF, pressure, event_type, buttons):
        pos = posF; pressure = math.pow(pressure, 1.4) 

        if event_type == "press":
            if buttons == Qt.LeftButton or buttons == Qt.NoButton:
                if self.selected_indices and ("select" in self.active_tool or "cursor" in self.active_tool):
                    for key, rect in self.get_handles().items():
                        if rect.contains(pos):
                            self.transform_mode = "rotate" if key == "rot" else "scale"
                            self.active_handle = key; self.move_start_pos = pos
                            self.original_selection_rect = QRectF(self.selection_rect)
                            self.transform_center = self.selection_rect.center()
                            mouse_vec = pos - self.transform_center
                            self.transform_start_angle = math.atan2(mouse_vec.y(), mouse_vec.x())
                            self.original_selected_strokes = [self.strokes[i].copy() for i in self.selected_indices]
                            for k, stroke in enumerate(self.original_selected_strokes):
                                if stroke["type"] == "image":
                                    stroke["path"] = QPainterPath(self.strokes[self.selected_indices[k]]["path"])
                                    stroke["transform"] = QTransform(self.strokes[self.selected_indices[k]]["transform"])
                                elif stroke["type"] != "text": stroke["path"] = QPainterPath(self.strokes[self.selected_indices[k]]["path"])
                            return

                if self.edit_btn_rect and self.edit_btn_rect.contains(pos): state.request_menu_context.emit("selection_context"); return
                if self.menu_ref and self.menu_ref.geometry().contains(pos.toPoint()): return 
                
                if self.active_tool == "tool_text":
                    if self.active_text_widget: self.active_text_widget.deleteLater(); self.active_text_widget = None
                    else: self.spawn_text_input(pos.toPoint())
                    return
                
                self.is_drawing = True; self.last_pos = pos; self.current_pos = pos; self.start_pos = pos.toPoint()
                self.redo_stack = []; self.current_points = [pos] 
                self.snapped_shape = None; self.is_scaling_shape = False; self.shape_hold_timer.stop()

                if "select" in self.active_tool or "cursor" in self.active_tool:
                    if self.selected_indices and self.selection_rect.contains(pos): self.is_moving_selection = True; self.move_start_pos = pos; return
                    self.selected_indices = []; self.update_selection_rect(); state.set_selection_active(False)
                    if self.active_tool == "tool_select_lasso": self.selection_path = QPainterPath(); self.selection_path.moveTo(pos)
                    elif self.active_tool == "tool_select_rect": self.selection_path = QPainterPath() 
                    self.update(); return 

                if "eraser" in self.active_tool and state.eraser_type == "stroke":
                    if self.delete_stroke_at(pos.toPoint()): self.redraw_buffer(); self.update()
                    return

                self.current_stroke = {
                    "type": self.get_stroke_type(), "color": QColor(self.active_color),
                    "size": self.active_size, "style": self.active_style,
                    "fill_enabled": state.current_fill_enabled, "fill_color": QColor(state.current_fill_color),
                    "path": QPainterPath(), "start": self.start_pos, "end": self.start_pos, "points": [], "locked": False
                }
                
                if self.current_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]:
                    self.current_stroke["points"].append((pos, pressure))
                    rad = max(1.0, (self.active_size * pressure) / 2)
                    self.current_stroke["path"].addEllipse(pos, rad, rad)
                else: self.current_stroke["path"].moveTo(pos)

        elif event_type == "move":
            if self.transform_mode:
                transform = QTransform()
                if self.transform_mode == "scale":
                    anchor = self.get_anchor_point(self.active_handle)
                    orig_vector = self.move_start_pos - anchor; curr_vector = pos - anchor
                    sx = curr_vector.x() / orig_vector.x() if abs(orig_vector.x()) > 1 else 1.0
                    sy = curr_vector.y() / orig_vector.y() if abs(orig_vector.y()) > 1 else 1.0
                    if self.active_handle in ["tm", "bm"]: sx = 1.0
                    if self.active_handle in ["lm", "rm"]: sy = 1.0
                    transform.translate(anchor.x(), anchor.y()); transform.scale(sx, sy); transform.translate(-anchor.x(), -anchor.y())
                elif self.transform_mode == "rotate":
                    center = self.transform_center; mouse_vec = pos - center
                    delta_angle_deg = math.degrees(math.atan2(mouse_vec.y(), mouse_vec.x()) - self.transform_start_angle)
                    transform.translate(center.x(), center.y()); transform.rotate(delta_angle_deg); transform.translate(-center.x(), -center.y())

                for idx, orig_stroke in enumerate(self.original_selected_strokes):
                    real_idx = self.selected_indices[idx]
                    if self.strokes[real_idx].get("locked", False): continue
                    
                    if orig_stroke["type"] == "text":
                        self.strokes[real_idx]["pos"] = transform.map(orig_stroke["pos"])
                        if self.transform_mode == "scale": self.strokes[real_idx]["size"] = max(5, int(orig_stroke["size"] * ((abs(sx) + abs(sy)) / 2)))
                    elif orig_stroke["type"] == "image":
                        self.strokes[real_idx]["path"] = transform.map(orig_stroke["path"])
                        self.strokes[real_idx]["transform"] = orig_stroke["transform"] * transform
                    else:
                        self.strokes[real_idx]["path"] = transform.map(orig_stroke["path"])
                        if "points" in orig_stroke and orig_stroke["points"]: self.strokes[real_idx]["points"] = [(transform.map(pt), press) for pt, press in orig_stroke["points"]]

                self.update_selection_rect(); self.redraw_buffer(); self.update(); return

            if self.is_scaling_shape and self.snapped_shape:
                if self.snapped_shape["shape_type"] == "line":
                    path = QPainterPath(); path.moveTo(self.current_points[0]); path.lineTo(pos); self.snapped_shape["path"] = path
                else:
                    current_dist = math.hypot(pos.x() - self.shape_center.x(), pos.y() - self.shape_center.y())
                    scale_factor = current_dist / self.scale_start_dist
                    curr_vec = pos - self.shape_center
                    delta_angle_deg = math.degrees(math.atan2(curr_vec.y(), curr_vec.x()) - self.snap_start_angle)
                    transform = QTransform(); transform.translate(self.shape_center.x(), self.shape_center.y())
                    transform.rotate(delta_angle_deg); transform.scale(scale_factor, scale_factor); transform.translate(-self.shape_center.x(), -self.shape_center.y())
                    self.snapped_shape["path"] = transform.map(self.base_snapped_path)
                self.update(); return 

            if self.selected_indices and not self.is_drawing and ("select" in self.active_tool or "cursor" in self.active_tool):
                handles = self.get_handles(); h_cursor = Qt.ArrowCursor
                if handles["tl"].contains(pos) or handles["br"].contains(pos): h_cursor = Qt.SizeFDiagCursor
                elif handles["tr"].contains(pos) or handles["bl"].contains(pos): h_cursor = Qt.SizeBDiagCursor
                elif handles["tm"].contains(pos) or handles["bm"].contains(pos): h_cursor = Qt.SizeVerCursor
                elif handles["lm"].contains(pos) or handles["rm"].contains(pos): h_cursor = Qt.SizeHorCursor
                elif handles["rot"].contains(pos): h_cursor = Qt.PointingHandCursor
                
                if QApplication.overrideCursor() is not None:
                    if QApplication.overrideCursor().shape() != h_cursor: QApplication.changeOverrideCursor(h_cursor)
                else: self.setCursor(h_cursor)

            if self.is_drawing:
                if "pen" in self.active_tool:
                    dist = (pos - self.last_pos).manhattanLength()
                    if dist > 2.0:
                        self.shape_hold_timer.start(); self.current_points.append(pos)
                        if self.snapped_shape and dist > 10: self.snapped_shape = None; self.is_scaling_shape = False; self.update()

                if (pos - self.last_pos).manhattanLength() < 2.0: return
                
                if "select" in self.active_tool or "cursor" in self.active_tool:
                    if self.is_moving_selection: self.move_selection(pos - self.move_start_pos); self.move_start_pos = pos; self.redraw_buffer()
                    else:
                        if self.active_tool == "tool_select_rect" and self.selection_path is not None: 
                            self.selection_path = QPainterPath(); self.selection_path.addRect(QRectF(self.start_pos, pos).normalized())
                        elif self.active_tool == "tool_select_lasso" and self.selection_path is not None: self.selection_path.lineTo(pos)
                    self.update(); return
                
                if "eraser" in self.active_tool and state.eraser_type == "stroke":
                    if self.delete_stroke_at(pos.toPoint()): self.redraw_buffer(); self.update()
                    return
                
                if self.current_stroke:
                    if self.current_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]:
                        self.current_stroke["points"].append((pos, pressure))
                        self.current_stroke["path"] = self.generate_variable_width_path(self.current_stroke["points"], self.active_size)
                        self.last_pos = pos
                    else: self.current_stroke["end"] = pos.toPoint()
                    self.update()

        elif event_type == "release":
            self.shape_hold_timer.stop(); self.is_scaling_shape = False; self.transform_mode = None; self.active_handle = None
            
            if self.is_drawing:
                self.is_drawing = False
                if "select" in self.active_tool or "cursor" in self.active_tool:
                    if self.is_moving_selection:
                        self.is_moving_selection = False
                        if self.active_tool == "tool_select_lasso" and self.selection_path is not None: self.selection_path.closeSubpath()
                    else:
                        if self.active_tool == "tool_select_lasso" and self.selection_path is not None: self.selection_path.closeSubpath()
                        if self.selection_path is not None: self.find_selected_strokes()
                            
                        if not self.selected_indices: self.update_selection_rect(); state.set_selection_active(False)
                        else:
                            self.is_internal_sync = True; state.set_selection_active(True)
                            ls = self.strokes[self.selected_indices[-1]]
                            state.sync_tool_properties(color=ls.get("color", QColor("black")), thickness=ls.get("size", 2), style=ls.get("style", Qt.SolidLine), is_filled=ls.get("fill_enabled", False), fill_color=ls.get("fill_color", state.current_fill_color))
                            self.is_internal_sync = False; self.update_selection_rect()
                    self.update(); return

                if self.current_stroke:
                    final_stroke = self.current_stroke
                    if self.snapped_shape: final_stroke = self.snapped_shape; self.snapped_shape = None 
                    else:
                        if final_stroke["type"] in ["pen", "highlighter", "eraser", "laser_pen"]: final_stroke["path"] = self.generate_variable_width_path(final_stroke["points"], self.active_size)
                        else:
                            path = QPainterPath(); self.generate_shape_path(path, final_stroke["type"], final_stroke["start"], final_stroke["end"]); final_stroke["path"] = path
                    
                    if final_stroke["type"] == "laser_pen": final_stroke["vanish_deadline"] = time.time() + state.laser_duration
                    self.strokes.append(final_stroke)
                    painter = QPainter(self.buffer_pixmap); painter.setRenderHint(QPainter.Antialiasing)
                    self.draw_stroke_entity(painter, final_stroke); painter.end()
                    self.current_stroke = None; self.update()

    def draw_selection_overlay(self, painter):
        if not self.selected_indices: return
        border_color = QColor("#FF4444") if any(self.strokes[i].get("locked", False) for i in self.selected_indices) else self.theme_border
        
        painter.setPen(QPen(border_color, 2, Qt.DashLine if "select" in self.active_tool else Qt.SolidLine))
        painter.setBrush(self.theme_fill); painter.drawRect(self.selection_rect)
        
        painter.setPen(QPen(border_color, 1)); painter.setBrush(Qt.white)
        for key, rect in self.get_handles().items():
            if key == "rot":
                painter.drawLine(rect.center(), QPointF(rect.center().x(), self.selection_rect.top())); painter.drawEllipse(rect)
            else: painter.drawRect(rect)

        if self.edit_btn_rect:
            painter.setBrush(border_color); painter.setPen(QPen(Qt.white, 2)); painter.drawEllipse(self.edit_btn_rect)
            icon_path = get_asset_path("edit.png")
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(QRectF(self.edit_btn_rect.center().x()-8, self.edit_btn_rect.center().y()-8, 16, 16).toRect(), pix)

    def draw_stroke_entity(self, painter, stroke):
        st_type = stroke["type"]
        is_live = (painter.device() == self) 
        
        if st_type == "text":
            painter.setPen(stroke["color"])
            font_style = stroke.get("font_style", "Normal")
            weight = QFont.Bold if "Bold" in font_style else QFont.Normal
            italic = "Italic" in font_style
            font = QFont("Arial", stroke["size"]); font.setWeight(weight); font.setItalic(italic)
            painter.setFont(font)
            painter.drawText(stroke["pos"] + QPoint(4, stroke["size"] + 5), stroke["text"])
            return

        if st_type == "image":
            painter.save()
            painter.setTransform(stroke["transform"], True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(stroke["base_rect"], stroke["pixmap"], QRectF(stroke["pixmap"].rect()))
            painter.restore()
            return
        
        path = stroke["path"]
        if st_type == "laser_pen":
            glow_color = QColor(stroke["color"]); glow_color.setAlpha(120) 
            painter.setPen(Qt.NoPen); painter.setBrush(glow_color); painter.setCompositionMode(QPainter.CompositionMode_SourceOver); painter.drawPath(path)
            if "points" in stroke and stroke["points"]:
                core_size = max(1.0, stroke["size"] * 0.3)
                core_path = self.generate_variable_width_path(stroke["points"], core_size)
                painter.setBrush(Qt.white); painter.drawPath(core_path)
            return

        if st_type in ["pen", "highlighter", "eraser"] and stroke.get("style", Qt.SolidLine) == Qt.SolidLine:
            if stroke.get("fill_enabled", False):
                 if "points" in stroke and stroke["points"]:
                     fill_path = QPainterPath(); pts = stroke["points"]
                     if pts:
                         fill_path.moveTo(pts[0][0])
                         for i in range(1, len(pts)): fill_path.lineTo(pts[i][0])
                         fill_path.closeSubpath()
                     painter.setPen(Qt.NoPen); painter.setBrush(stroke.get("fill_color", QColor(255, 200, 0, 100))); painter.drawPath(fill_path)

            if st_type == "highlighter":
                 c = QColor(stroke["color"].red(), stroke["color"].green(), stroke["color"].blue(), 80)
                 painter.setBrush(c); painter.setPen(Qt.NoPen)
                 painter.setCompositionMode(QPainter.CompositionMode_SourceOver if is_live else QPainter.CompositionMode_Multiply) 
            elif st_type == "eraser":
                 painter.setCompositionMode(QPainter.CompositionMode_Clear); painter.setBrush(Qt.black); painter.setPen(Qt.NoPen)
            else:
                 painter.setBrush(stroke["color"]); painter.setPen(Qt.NoPen); painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawPath(path)
        else:
            pen = QPen(stroke["color"], stroke["size"], stroke.get("style", Qt.SolidLine), Qt.RoundCap, Qt.RoundJoin)
            if st_type == "highlighter":
                pen.setColor(QColor(stroke["color"].red(), stroke["color"].green(), stroke["color"].blue(), 80))
                pen.setWidth(stroke["size"] + 10)
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver if is_live else QPainter.CompositionMode_Multiply)
            elif st_type == "eraser":
                painter.setCompositionMode(QPainter.CompositionMode_Clear); pen.setColor(Qt.transparent); pen.setWidth(stroke["size"])
            else: painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                
            painter.setPen(pen)
            painter.setBrush(stroke.get("fill_color", QColor(255, 200, 0, 100)) if stroke.get("fill_enabled", False) else Qt.NoBrush)
            
            if "points" in stroke and stroke["points"]:
                simple_path = QPainterPath(); pts = stroke["points"]
                if pts:
                    simple_path.moveTo(pts[0][0])
                    for i in range(1, len(pts)): simple_path.lineTo(pts[i][0])
                painter.drawPath(simple_path)
            else: painter.drawPath(path)

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
            if stroke.get("locked", False): continue
            
            if stroke["type"] == "text":
                if (stroke["pos"] - pos).manhattanLength() < 30: self.strokes.pop(i); return True
            elif stroke["path"].intersects(eraser_area): self.strokes.pop(i); return True
        return False

    # --- NEW: FAST PATTERN DRAWING ALGORITHM ---
    def draw_background_pattern(self, painter):
        p_type = state.pattern_type
        if p_type == "none": return

        settings = state.pattern_settings.get(p_type, {})
        spacing = max(5, settings.get("spacing", 40)) # Prevent division by zero or negative size
        opacity = settings.get("opacity", 100)
        thickness = settings.get("thickness", 1)
        
        color = QColor(settings.get("color", "#808080"))
        color.setAlpha(opacity)

        # 1. We create a tiny invisible square "Tile"
        tile = QPixmap(spacing, spacing)
        tile.fill(Qt.transparent)
        
        tile_painter = QPainter(tile)
        tile_painter.setRenderHint(QPainter.Antialiasing)
        tile_painter.setPen(QPen(color, thickness))

        # 2. Draw the specific pattern on that single tile
        if p_type in ["grid", "coordinate"]:
            tile_painter.drawLine(0, 0, spacing, 0)
            tile_painter.drawLine(0, 0, 0, spacing)
        elif p_type == "lines":
            tile_painter.drawLine(0, 0, spacing, 0)
        elif p_type == "dots":
            tile_painter.setBrush(color)
            tile_painter.setPen(Qt.NoPen)
            rad = thickness / 2.0
            # Draw dot exactly in the center of the tile
            tile_painter.drawEllipse(QPointF(spacing/2, spacing/2), rad, rad)
            
        tile_painter.end()

        # 3. Tell Qt's graphics engine to mathematically repeat the tile across the whole screen!
        painter.fillRect(self.rect(), QBrush(tile))

        # 4. If it's a coordinate system, manually paint the two big bold center axis lines
        if p_type == "coordinate":
            axis_color = QColor(settings.get("axis_color", "#FF4444"))
            axis_color.setAlpha(opacity)
            painter.setPen(QPen(axis_color, settings.get("axis_thickness", 2)))

            w = self.width()
            h = self.height()
            
            # Snap axis to the nearest grid line exactly in the middle of screen
            mid_x = (w // (2 * spacing)) * spacing
            mid_y = (h // (2 * spacing)) * spacing
            
            painter.drawLine(mid_x, 0, mid_x, h)
            painter.drawLine(0, mid_y, w, mid_y)


    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 1. Base Background Color
        if state.board_color.alpha() > 0: painter.fillRect(self.rect(), state.board_color)
        elif self.active_tool not in ["tool_cursor", "tool_pan"]: painter.fillRect(self.rect(), QColor(255, 255, 255, 1))
            
        # 2. Draw the new Grids/Patterns OVER the background but UNDER the ink
        self.draw_background_pattern(painter)
            
        # 3. Draw the Ink Buffer
        if self.buffer_pixmap:
            target_rect = QRect(0, 0, self.width(), self.height())
            painter.drawPixmap(target_rect, self.buffer_pixmap, self.buffer_pixmap.rect())
        
        # 4. Draw Live Previews (snapping shape, current stroke, selection box)
        if self.snapped_shape:
            painter.setRenderHint(QPainter.Antialiasing)
            self.draw_stroke_entity(painter, self.snapped_shape)
        elif self.current_stroke:
            painter.setRenderHint(QPainter.Antialiasing)
            st_type = self.current_stroke["type"]
            
            if st_type in ["pen", "highlighter", "eraser", "laser_pen", "image"]:
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
        elif self.selection_path and ("select" in self.active_tool or "cursor" in self.active_tool):
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(self.theme_border, 2, Qt.DashLine))
            painter.setBrush(self.theme_fill)
            painter.drawPath(self.selection_path)
