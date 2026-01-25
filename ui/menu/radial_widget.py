import math
import os
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QRectF, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QBrush, QFont, QPixmap, QRadialGradient

from ui.menu.menu_models import create_menu_structure
from core.state import state 

class DrawboardMenu(QWidget):
    action_triggered = Signal(str)
    geometry_changed = Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFixedSize(340, 340) 
        self.center = QPoint(170, 170)
        self.base_inner_radius = 30    
        self.base_rim_radius = 90      
        self.base_outer_radius = 120   
        self.pages = create_menu_structure()
        self.current_page_id = "root"
        self.history_stack = []
        self.hovered_index = -1
        self.hovered_val = None 
        self.hovered_zone = None 
        self.dragging_window = False 
        self.dragging_dial = False   
        self.drag_start_pos = QPoint()
        self.has_moved = False
        self.icon_cache = {} 
        self.pending_page_id = None
        self.is_navigating = False
        self.animation_style = "spin" 
        self._expansion = 1.0
        self.anim = QPropertyAnimation(self, b"expansion")
        self.anim.finished.connect(self.on_animation_finished)
        state.tool_changed.connect(self.update)
        state.style_changed.connect(self.update)
        state.color_changed.connect(self.update)
        state.brush_changed.connect(self.update)
        state.request_menu_context.connect(self.open_with_context)
        state.selection_changed.connect(self.on_selection_changed)

    def on_selection_changed(self, active):
        if active:
            if self.current_page_id == "root":
                self.current_page_id = "selection_context"
                self.history_stack = []
                self.update()
        else:
            if self.current_page_id == "selection_context":
                self.current_page_id = "root"
                self.history_stack = []
                self.update()

    def open_with_context(self, context_id):
        if context_id == "selection_context" and not state.has_selection:
            context_id = "root"
        
        if self.current_page_id != context_id and "settings" not in self.current_page_id:
            self.current_page_id = context_id
            self.history_stack = []
        
        if self._expansion < 0.5: self.toggle_collapse()
        else: self.update()

    def get_expansion(self): return self._expansion
    def set_expansion(self, val):
        self._expansion = val; self.update()
    expansion = Property(float, get_expansion, set_expansion)

    def get_icon(self, filename):
        if not filename: return None
        if filename not in self.icon_cache:
            path = os.path.join("assets", filename)
            if os.path.exists(path): self.icon_cache[filename] = QPixmap(path)
            else: self.icon_cache[filename] = None
        return self.icon_cache[filename]

    def get_current_page(self): return self.pages[self.current_page_id]

    def toggle_collapse(self):
        self.animation_style = "spin"
        if self._expansion > 0.5:
            self.anim.setDuration(250); self.anim.setStartValue(1.0); self.anim.setEndValue(0.0); self.anim.setEasingCurve(QEasingCurve.InQuad)
        else:
            if state.has_selection:
                self.current_page_id = "selection_context"
                self.history_stack = []
            else:
                if self.current_page_id == "selection_context":
                    self.current_page_id = "root"
            
            self.anim.setDuration(300); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0); self.anim.setEasingCurve(QEasingCurve.OutQuad)
        self.anim.start()

    def navigate_to(self, page_id):
        if page_id == "go_back": self.navigate_back(); return
        if page_id in self.pages:
            self.pending_page_id = page_id
            self.is_navigating = True
            self.animation_style = "bump"
            self.anim.setDuration(150); self.anim.setStartValue(self._expansion); self.anim.setEndValue(0.0); self.anim.setEasingCurve(QEasingCurve.InBack)
            self.anim.start()

    def navigate_back(self):
        if self.history_stack:
            self.pending_page_id = "BACK_ACTION" 
            self.is_navigating = True
            self.animation_style = "bump"
            self.anim.setDuration(150); self.anim.setStartValue(self._expansion); self.anim.setEndValue(0.0); self.anim.setEasingCurve(QEasingCurve.InBack)
            self.anim.start()

    def on_animation_finished(self):
        if self.is_navigating and self._expansion == 0.0:
            if self.pending_page_id == "BACK_ACTION":
                if self.history_stack: self.current_page_id = self.history_stack.pop()
            elif self.pending_page_id:
                self.history_stack.append(self.current_page_id)
                self.current_page_id = self.pending_page_id
            self.pending_page_id = None; self.is_navigating = False; self.hovered_index = -1; self.animation_style = "bump"
            self.anim.setDuration(400); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0); self.anim.setEasingCurve(QEasingCurve.OutBack); self.anim.start()

    def get_slice_path(self, start_angle, sweep, r_in, r_out):
        path = QPainterPath(); rad_start = math.radians(start_angle); rad_end = math.radians(start_angle + sweep)
        path.moveTo(self.center + QPoint(math.cos(rad_start) * r_in, -math.sin(rad_start) * r_in))
        path.lineTo(self.center + QPoint(math.cos(rad_start) * r_out, -math.sin(rad_start) * r_out))
        path.arcTo(QRectF(self.center.x()-r_out, self.center.y()-r_out, r_out*2, r_out*2), start_angle, sweep)
        path.lineTo(self.center + QPoint(math.cos(rad_end) * r_in, -math.sin(rad_end) * r_in))
        path.arcTo(QRectF(self.center.x()-r_in, self.center.y()-r_in, r_in*2, r_in*2), start_angle + sweep, -sweep)
        path.closeSubpath(); return path

    def paint_icon_colored(self, painter, rect, pixmap, color):
        if not pixmap or pixmap.isNull(): return
        tinted = QPixmap(pixmap.size()); tinted.fill(Qt.transparent)
        p = QPainter(tinted); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(0, 0, pixmap); p.setCompositionMode(QPainter.CompositionMode_SourceIn); p.fillRect(tinted.rect(), color); p.end()
        painter.drawPixmap(rect.toRect(), tinted)

    def paint_dial_page(self, painter, page, cur_rim, cur_out):
        painter.setBrush(QColor("#15171A")); painter.setPen(Qt.NoPen); painter.drawEllipse(self.center, cur_rim, cur_rim)
        rim_path = QPainterPath(); rim_path.addEllipse(self.center, cur_out, cur_out)
        inner_cut = QPainterPath(); inner_cut.addEllipse(self.center, cur_rim, cur_rim)
        rim_path = rim_path.subtracted(inner_cut)
        painter.setBrush(QColor("#202227")); painter.setPen(QPen(QColor("#0F1115"), 1)); painter.drawPath(rim_path)
        start_val, end_val = page.dial_range; step = page.dial_step
        count = int((end_val - start_val) / step) + 1; angle_step = 360 / count; text_radius = (cur_rim + cur_out) / 2
        current_val = page.current_value; preview_val = self.hovered_val if self.hovered_val is not None else current_val
        bubble_radius = 16; needle_stop_radius = text_radius - bubble_radius - 2 

        if preview_val is not None and preview_val != current_val:
            p_idx = (preview_val - start_val) / step; p_angle = (p_idx * angle_step) - 90; p_rad = math.radians(p_angle)
            p_start = self.center + QPoint(math.cos(p_rad)*(self.base_inner_radius+5), math.sin(p_rad)*(self.base_inner_radius+5))
            p_end = self.center + QPoint(math.cos(p_rad)*needle_stop_radius, math.sin(p_rad)*needle_stop_radius)
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.SolidLine)); painter.drawLine(p_start, p_end)
            bubble_center = self.center + QPoint(math.cos(p_rad)*text_radius, math.sin(p_rad)*text_radius)
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1)); painter.setBrush(Qt.NoBrush); painter.drawEllipse(bubble_center, bubble_radius, bubble_radius)

        if current_val is not None:
            c_idx = (current_val - start_val) / step; c_angle = (c_idx * angle_step) - 90; c_rad = math.radians(c_angle)
            painter.setPen(QPen(QColor("#66FF66"), 4)); painter.setBrush(Qt.NoBrush); painter.drawEllipse(self.center, self.base_inner_radius + 4, self.base_inner_radius + 4)
            c_start = self.center + QPoint(math.cos(c_rad)*(self.base_inner_radius+8), math.sin(c_rad)*(self.base_inner_radius+8))
            c_end = self.center + QPoint(math.cos(c_rad)*needle_stop_radius, math.sin(c_rad)*needle_stop_radius)
            painter.setPen(QPen(QColor("#66FF66"), 4, Qt.SolidLine, Qt.RoundCap)); painter.drawLine(c_start, c_end)
            bubble_center = self.center + QPoint(math.cos(c_rad)*text_radius, math.sin(c_rad)*text_radius)
            painter.setBrush(QColor("#66FF66")); painter.setPen(Qt.NoPen); painter.drawEllipse(bubble_center, bubble_radius, bubble_radius)

        for i in range(count):
            val = start_val + (i * step); angle_deg = (i * angle_step) - 90; rad = math.radians(angle_deg)
            tx = self.center.x() + math.cos(rad) * text_radius; ty = self.center.y() + math.sin(rad) * text_radius
            is_preview = (val == preview_val); is_current = (val == current_val)
            rect = QRectF(tx-15, ty-15, 30, 30)
            if is_current: painter.setPen(QColor("black")); painter.setFont(QFont("Arial", 11, QFont.Bold))
            elif is_preview: painter.setPen(QColor("white")); painter.setFont(QFont("Arial", 11, QFont.Bold))
            else: painter.setPen(QColor("#666666")); painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, str(val))

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.animation_style == "spin" and self._expansion < 1.0:
            painter.translate(self.center); painter.rotate((1.0 - self._expansion) * 90); painter.translate(-self.center)

        cur_rim = self.base_inner_radius + (self.base_rim_radius - self.base_inner_radius) * self._expansion
        cur_out = self.base_inner_radius + (self.base_outer_radius - self.base_inner_radius) * self._expansion
        
        if self._expansion > 0.05:
            shadow_rad = cur_out + 18; shadow_grad = QRadialGradient(self.center, shadow_rad)
            shadow_grad.setColorAt(0.6, QColor(0, 0, 0, 60)); shadow_grad.setColorAt(1.0, Qt.transparent)
            painter.setBrush(QBrush(shadow_grad)); painter.setPen(Qt.NoPen); painter.drawEllipse(self.center, shadow_rad, shadow_rad)

        page = self.get_current_page()
        if getattr(page, "page_type", "slices") == "dial" and self._expansion > 0.1: self.paint_dial_page(painter, page, cur_rim, cur_out)
        else:
            items = page.items
            count = len(items)
            if count > 0 and self._expansion > 0.01:
                angle_span = 360 / count
                
                for i, item in enumerate(items):
                    start_angle = (i * angle_span) + 90
                    is_active = state.is_key_active(item.action_key)
                    is_hovered = (i == self.hovered_index)
                    
                    body_path = self.get_slice_path(start_angle, angle_span, self.base_inner_radius, cur_rim)
                    base_col = item.slice_color 
                    if is_hovered and self.hovered_zone == "main": base_col = base_col.lighter(115)
                    if is_active: base_col = base_col.lighter(110)
                    grad = QRadialGradient(self.center, cur_rim); grad.setColorAt(0.0, base_col.lighter(110)); grad.setColorAt(1.0, base_col)
                    painter.setBrush(QBrush(grad)); painter.setPen(QPen(QColor("#0F1115"), 1)); painter.drawPath(body_path)

                    rim_path = self.get_slice_path(start_angle, angle_span, cur_rim, cur_out)
                    rim_base = QColor("#1A1C21") 
                    if is_hovered: rim_base = rim_base.lighter(140)
                    rim_grad = QRadialGradient(self.center, cur_out); rim_grad.setColorAt(cur_rim/cur_out, rim_base.lighter(110)); rim_grad.setColorAt(1.0, rim_base.darker(110))
                    painter.setBrush(QBrush(rim_grad)); painter.setPen(QPen(QColor("#0F1115"), 1)); painter.drawPath(rim_path)

                    if item.submenu_id and self._expansion > 0.8:
                        mid = start_angle + angle_span/2; ar_r = (cur_rim + cur_out)/2
                        ax, ay = self.center.x() + math.cos(math.radians(mid))*ar_r, self.center.y() - math.sin(math.radians(mid))*ar_r
                        painter.save(); painter.translate(ax, ay); painter.rotate(-mid); painter.setPen(QPen(QColor("#777777"), 2))
                        painter.drawLine(0, -4, 4, 0); painter.drawLine(4, 0, 0, 4); painter.restore()

                    if is_active and self._expansion > 0.9:
                        painter.setPen(QPen(QColor("white"), 5)); painter.setBrush(Qt.NoBrush)
                        rect_active = QRectF(self.center.x()-cur_rim+3, self.center.y()-cur_rim+3, cur_rim*2-6, cur_rim*2-6)
                        painter.drawArc(rect_active, int(start_angle*16), int(angle_span*16))

                    if self._expansion > 0.6:
                        label_r = (self.base_inner_radius + cur_rim) / 2
                        mid = start_angle + angle_span/2
                        lx, ly = self.center.x() + math.cos(math.radians(mid))*label_r, self.center.y() - math.sin(math.radians(mid))*label_r
                        pixmap = self.get_icon(item.icon_filename)
                        if pixmap:
                            icon_size = 20; rect = QRectF(lx - icon_size/2, ly - icon_size/2, icon_size, icon_size)
                            icon_color = Qt.white
                            if is_active: icon_color = item.highlight_color
                            elif not is_active: icon_color = QColor("#999999") 
                            self.paint_icon_colored(painter, rect, pixmap, icon_color)
                        elif not item.hide_label:
                            painter.setPen(Qt.white if is_active else QColor("#AAAAAA")); painter.setFont(QFont("Arial", 9, QFont.Bold))
                            painter.drawText(QRectF(lx-30, ly-15, 60, 30), Qt.AlignCenter, item.label[:3])
                    
                    if item.badge and self._expansion > 0.8:
                        b_angle = start_angle + angle_span * 0.75; b_rad = cur_out - 10
                        bx, by = self.center.x() + math.cos(math.radians(b_angle))*b_rad, self.center.y() - math.sin(math.radians(b_angle))*b_rad
                        painter.setBrush(QColor("#15171A")); painter.setPen(Qt.NoPen); painter.drawEllipse(QPoint(bx, by), 9, 9)
                        painter.setPen(Qt.white); painter.setFont(QFont("Arial", 7, QFont.Bold))
                        painter.drawText(QRectF(bx-9, by-9, 18, 18), Qt.AlignCenter, item.badge)

        if self.animation_style == "spin" and self._expansion < 1.0: painter.resetTransform()
        c_base = QColor("#1A1C21"); c_grad = QRadialGradient(self.center, self.base_inner_radius)
        c_grad.setColorAt(0.0, c_base.lighter(130)); c_grad.setColorAt(1.0, c_base)
        painter.setBrush(QBrush(c_grad)); painter.setPen(QPen(QColor("#444444"), 5))
        painter.drawEllipse(self.center, self.base_inner_radius, self.base_inner_radius)
        center_pix = self.get_icon(page.center_icon)
        if center_pix:
            sz = 26; rect = QRectF(self.center.x()-sz/2, self.center.y()-sz/2, sz, sz)
            self.paint_icon_colored(painter, rect, center_pix, QColor("#EEEEEE"))
        painter.end()

    def get_hit_data(self, pos):
        dx, dy = pos.x() - self.center.x(), pos.y() - self.center.y()
        dist = math.hypot(dx, dy)
        if dist < self.base_inner_radius: return (-99, "center")
        if self._expansion < 0.5 or dist > (self.base_outer_radius + 40): return (-1, None)
        page = self.get_current_page()
        if getattr(page, "page_type", "slices") == "dial":
            start_val, end_val = page.dial_range; step = page.dial_step
            count = int((end_val - start_val) / step) + 1
            angle = (math.degrees(math.atan2(dy, dx)) + 90) % 360
            angle_span = 360 / count
            index = round(angle / angle_span) % count
            val = start_val + (index * step)
            return (val, "dial")
        else:
            if dist > self.base_outer_radius: return (-1, None)
            zone = "rim" if dist > self.base_rim_radius else "main"
            angle = (math.degrees(math.atan2(-dy, dx)) - 90) % 360
            count = len(page.items)
            if count == 0: return (-1, None)
            index = int(angle / (360 / count))
            return (index, zone)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton: return
        self.drag_start_pos = event.globalPosition().toPoint()
        self.has_moved = False
        result = self.get_hit_data(event.position().toPoint())
        
        # Center Click (Drag or Toggle)
        if result == (-99, "center"): self.dragging_window = True; return
        
        page = self.get_current_page()
        
        # Dial Handling
        if getattr(page, "page_type", "slices") == "dial":
            val, zone = result
            if zone == "dial": self.dragging_dial = True; self.hovered_val = val; self.update(); return
        
        # Slice Handling
        index, zone = result
        if index >= 0 and index < len(page.items):
            item = page.items[index]
            
            # 1. Clicked Outer Rim -> Always open submenu if present
            if zone == "rim" and item.submenu_id:
                self.navigate_to(item.submenu_id)
            
            # 2. Clicked Inner Body
            elif zone == "main":
                if item.action_key:
                    state.set_active_tool(item.action_key)
                    self.action_triggered.emit(item.action_key)
                elif item.submenu_id:
                    # If button has no action but has a submenu (like "More"), open it
                    self.navigate_to(item.submenu_id)

    def mouseMoveEvent(self, event):
        cur_pos = event.position().toPoint()
        if self.dragging_window:
            global_pos = event.globalPosition().toPoint()
            if (global_pos - self.drag_start_pos).manhattanLength() > 5:
                self.has_moved = True
                self.move(self.pos() + global_pos - self.drag_start_pos)
                self.drag_start_pos = global_pos
                self.geometry_changed.emit() 
            return
        if self.dragging_dial:
            val, zone = self.get_hit_data(cur_pos)
            if zone == "dial" and val != self.hovered_val: self.hovered_val = val; self.update()
            return
        result = self.get_hit_data(cur_pos)
        page = self.get_current_page()
        if getattr(page, "page_type", "slices") == "dial":
            val, zone = result
            if self.hovered_val != val: self.hovered_val = val; self.update()
        else:
            index, zone = result
            if index != self.hovered_index or zone != self.hovered_zone: self.hovered_index = index; self.hovered_zone = zone; self.update() 

    def mouseReleaseEvent(self, event):
        if self.dragging_dial:
            page = self.get_current_page()
            if self.hovered_val is not None:
                page.current_value = self.hovered_val
                action_name = f"{page.action_prefix}{self.hovered_val}"
                state.set_active_tool(action_name) 
                self.action_triggered.emit(action_name)
            self.dragging_dial = False; self.update(); return
        if self.dragging_window:
            if not self.has_moved:
                if self.current_page_id in ["root", "selection_context"]: 
                    self.toggle_collapse()
                else: 
                    self.navigate_back()
            self.dragging_window = False