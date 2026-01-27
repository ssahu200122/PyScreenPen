from PySide6.QtGui import QColor

class MenuItem:
    def __init__(self, label: str, icon_filename: str, 
                 highlight_color: QColor = QColor("white"), 
                 action_key: str = None, submenu_id: str = None,
                 badge: str = None, slice_color: QColor = None, hide_label: bool = False):
        self.label = label; self.icon_filename = icon_filename 
        self.highlight_color = highlight_color; self.action_key = action_key
        self.submenu_id = submenu_id; self.badge = badge; self.hide_label = hide_label
        if slice_color: self.slice_color = slice_color
        else: self.slice_color = QColor("#2B2E36") 
        self.rim_color = QColor("#202227")   

class MenuPage:
    def __init__(self, items: list[MenuItem] = [], center_icon="logo.png", 
                 page_type="slices", dial_range=(1, 20), dial_step=1, current_value=5, action_prefix="set_val_"):
        self.items = items; self.center_icon = center_icon; self.page_type = page_type
        self.dial_range = dial_range; self.dial_step = dial_step; self.current_value = current_value; self.action_prefix = action_prefix

def create_menu_structure():
    pages = {}
    
    # --- ROOT ---
    root_items = [
        MenuItem("Select", "cursor.png", QColor("white"), action_key="tool_cursor", submenu_id="selection_menu", hide_label=True),
        MenuItem("More", "more.png", QColor("white"), submenu_id="more_menu", hide_label=True),
        MenuItem("Pen 1", "pen.png", QColor("#44ABFF"), action_key="tool_pen_1", submenu_id="pen_settings", hide_label=True), 
        MenuItem("Pen 2", "pen.png", QColor("#FF4444"), action_key="tool_pen_2", submenu_id="pen_settings", hide_label=True),
        MenuItem("Highlighter", "highlighter.png", QColor("#FFFF44"), action_key="tool_hl", submenu_id="hl_settings", hide_label=True), 
        MenuItem("Eraser", "eraser.png", QColor("white"), action_key="tool_eraser", submenu_id="eraser_settings", hide_label=True),
        MenuItem("Shapes", "shapes.png", QColor("white"), action_key="group_shapes", submenu_id="shapes_menu", hide_label=True),
        MenuItem("Text", "text.png", QColor("white"), action_key="tool_text", submenu_id="text_settings", hide_label=True),
    ]
    pages["root"] = MenuPage(root_items, center_icon="logo.png")

    # --- SELECTION CONTEXT ---
    selection_context_items = [
        MenuItem("Color", "color_wheel.png", QColor("white"), submenu_id="pen_settings", hide_label=True),
        MenuItem("Width", "thickness.png", QColor("white"), submenu_id="thickness_dial", badge="Edit", hide_label=True),
        MenuItem("Style", "boarderstyle.png", QColor("white"), submenu_id="style_options", badge="Edit", hide_label=True),
        MenuItem("Fill", "color_wheel.png", QColor("white"), action_key="toggle_tool_fill", submenu_id="fill_settings", badge="Fill", hide_label=True), 
        MenuItem("Delete", "trash.png", QColor("#FF4444"), action_key="action_delete", hide_label=True),
        MenuItem("Done", "check.png", QColor("#44FF44"), action_key="action_deselect", hide_label=True),
    ]
    pages["selection_context"] = MenuPage(selection_context_items, center_icon="select_rect.png")

    # --- SELECTION MENU ---
    selection_items = [
        MenuItem("Cursor", "cursor_arrow.png", QColor("white"), action_key="tool_cursor", hide_label=True),
        MenuItem("Rect", "select_rect.png", QColor("white"), action_key="tool_select_rect", hide_label=True),
        MenuItem("Lasso", "select_lasso.png", QColor("white"), action_key="tool_select_lasso", hide_label=True),
        MenuItem("Snip", "snip.png", QColor("#00FF00"), action_key="action_save", badge="SAVE", hide_label=True),
    ]
    pages["selection_menu"] = MenuPage(selection_items, center_icon="back.png")

    # --- BOARD SETTINGS ---
    board_items = [
        MenuItem("", None, submenu_id="board_white_shades", slice_color=QColor("#FFFFFF"), action_key="set_board_white", hide_label=True),
        MenuItem("", None, submenu_id="board_black_shades", slice_color=QColor("#000000"), action_key="set_board_black", hide_label=True),
        MenuItem("Opacity", "opacity.png", QColor("white"), submenu_id="board_opacity_dial", badge="BG", hide_label=True),
        MenuItem("Clear", "clear.png", QColor("#FF4444"), action_key="set_board_transparent", hide_label=True),
        MenuItem("", None, submenu_id="board_blue_shades", slice_color=QColor("#4444FF"), action_key="set_board_blue", hide_label=True),
        MenuItem("", None, submenu_id="board_green_shades", slice_color=QColor("#00CC00"), action_key="set_board_green", hide_label=True),
    ]
    pages["board_settings"] = MenuPage(board_items, center_icon="white_board.png")
    pages["board_opacity_dial"] = MenuPage(items=[], page_type="dial", dial_range=(0, 100), dial_step=10, current_value=100, action_prefix="set_board_opacity_", center_icon="back.png")

    # --- MORE MENU ---
    more_items = [
        MenuItem("Board", "white_board.png", QColor("white"), action_key="toggle_board", submenu_id="board_settings", hide_label=True),
        MenuItem("Laser", "laser.png", QColor("#FF0000"), action_key="tool_laser", submenu_id="laser_settings", hide_label=True),
        MenuItem("Lasso", "lasso.png", QColor("white"), action_key="tool_select_lasso", hide_label=True),
        MenuItem("Undo", "undo.png", QColor("white"), action_key="action_undo", hide_label=True),
        MenuItem("Redo", "redo.png", QColor("white"), action_key="action_redo", hide_label=True),
        MenuItem("Save", "save.png", QColor("white"), action_key="action_save", hide_label=True),
        MenuItem("Settings", "settings.png", QColor("white"), action_key="open_settings", hide_label=True),
    ]
    pages["more_menu"] = MenuPage(more_items, center_icon="back.png")

    # --- LASER SETTINGS ---
    laser_items = [
        MenuItem("", None, submenu_id="red_shades", slice_color=QColor("#FF4444"), action_key="set_red", hide_label=True),     
        MenuItem("Time", "clock.png", QColor("white"), submenu_id="laser_time_dial", badge="Time", hide_label=True),
        MenuItem("Size", "thickness.png", QColor("white"), submenu_id="thickness_dial", badge="Size", hide_label=True),
        MenuItem("", None, submenu_id="purple_shades", slice_color=QColor("#9F55FF"), action_key="set_purple", hide_label=True),  
        MenuItem("", None, submenu_id="blue_shades", slice_color=QColor("#4488FF"), action_key="set_blue", hide_label=True),    
        MenuItem("", None, submenu_id="green_shades", slice_color=QColor("#00CC66"), action_key="set_green", hide_label=True), 
    ]
    pages["laser_settings"] = MenuPage(laser_items, center_icon="laser.png")
    pages["laser_time_dial"] = MenuPage(items=[], page_type="dial", dial_range=(1, 30), dial_step=1, current_value=2, action_prefix="set_laser_time_", center_icon="back.png")

    # --- SHAPES ---
    shapes_items = [
        MenuItem("Line", "line.png", QColor("white"), action_key="tool_line", submenu_id="line_settings", hide_label=True),
        MenuItem("Arrow", "arrow.png", QColor("white"), action_key="tool_arrow", submenu_id="arrow_settings", hide_label=True),
        MenuItem("Rect", "rectangle.png", QColor("white"), action_key="tool_rect", submenu_id="rect_settings", hide_label=True),
        MenuItem("Circle", "circle.png", QColor("white"), action_key="tool_circle", submenu_id="circle_settings", hide_label=True),
        MenuItem("Poly", "polygon.png", QColor("white"), action_key="tool_polygon", submenu_id="polygon_settings", hide_label=True),
        MenuItem("Star", "star.png", QColor("white"), action_key="tool_star", submenu_id="star_settings", hide_label=True),
    ]
    pages["shapes_menu"] = MenuPage(shapes_items, center_icon="back.png")

    def create_shape_settings_items():
        return [
            MenuItem("", None, submenu_id="red_shades", slice_color=QColor("#FF4444"), action_key="set_red", hide_label=True),     
            MenuItem("", None, submenu_id="black_shades", slice_color=QColor("#111111"), action_key="set_black", hide_label=True),      
            MenuItem("Opacity", "opacity.png", QColor("white"), submenu_id="opacity_dial", badge="100", hide_label=True),
            # Fill now has 'toggle_tool_fill' key so main click toggles, arrow opens submenu
            MenuItem("Fill", "color_wheel.png", QColor("white"), action_key="toggle_tool_fill", submenu_id="fill_settings", badge="Fill", hide_label=True),
            MenuItem("Style", "boarderstyle.png", QColor("white"), submenu_id="style_options", badge="Solid", hide_label=True),
            MenuItem("Width", "thickness.png", QColor("white"), submenu_id="thickness_dial", badge="3", hide_label=True),
            MenuItem("", None, submenu_id="blue_shades", slice_color=QColor("#4488FF"), action_key="set_blue", hide_label=True),    
            MenuItem("", None, submenu_id="green_shades", slice_color=QColor("#00CC66"), action_key="set_green", hide_label=True), 
        ]

    # --- [CHANGE] Fill Settings Submenu: Removed Toggle Button ---
    fill_items = [
        MenuItem("Opacity", "opacity.png", QColor("white"), submenu_id="fill_opacity_dial", badge="100", hide_label=True),
        MenuItem("", None, submenu_id="fill_red_shades", slice_color=QColor("#FF4444"), action_key="set_fill_red", hide_label=True),
        MenuItem("", None, submenu_id="fill_blue_shades", slice_color=QColor("#4488FF"), action_key="set_fill_blue", hide_label=True),
        MenuItem("", None, submenu_id="fill_green_shades", slice_color=QColor("#00CC66"), action_key="set_fill_green", hide_label=True),
        MenuItem("", None, submenu_id="fill_orange_shades", slice_color=QColor("#FFA500"), action_key="set_fill_orange", hide_label=True),
        MenuItem("", None, submenu_id="fill_purple_shades", slice_color=QColor("#9F55FF"), action_key="set_fill_purple", hide_label=True),
        MenuItem("", None, submenu_id="fill_black_shades", slice_color=QColor("#333333"), action_key="set_fill_black", hide_label=True),
    ]
    pages["fill_settings"] = MenuPage(fill_items, center_icon="color_wheel.png")
    pages["fill_opacity_dial"] = MenuPage(items=[], page_type="dial", dial_range=(0, 100), dial_step=10, current_value=100, action_prefix="set_fill_opacity_", center_icon="back.png")

    pages["line_settings"] = MenuPage(create_shape_settings_items(), center_icon="line.png")
    pages["arrow_settings"] = MenuPage(create_shape_settings_items(), center_icon="arrow.png")
    pages["rect_settings"] = MenuPage(create_shape_settings_items(), center_icon="rectangle.png")
    pages["circle_settings"] = MenuPage(create_shape_settings_items(), center_icon="circle.png")
    pages["polygon_settings"] = MenuPage(create_shape_settings_items(), center_icon="polygon.png")
    pages["star_settings"] = MenuPage(create_shape_settings_items(), center_icon="star.png")
    pages["pen_settings"] = MenuPage(create_shape_settings_items(), center_icon="back.png")

    text_items = [
        MenuItem("", None, submenu_id="red_shades", slice_color=QColor("#FF4444"), action_key="set_red", hide_label=True),     
        MenuItem("", None, submenu_id="black_shades", slice_color=QColor("#111111"), action_key="set_black", hide_label=True),      
        MenuItem("Opacity", "opacity.png", QColor("white"), submenu_id="opacity_dial", badge="100", hide_label=True),
        MenuItem("Size", "thickness.png", QColor("white"), submenu_id="thickness_dial", badge="12", hide_label=True),
        MenuItem("Style", "text_style.png", QColor("white"), submenu_id="text_style_options", badge="Aa", hide_label=True),
        MenuItem("", None, submenu_id="purple_shades", slice_color=QColor("#9F55FF"), action_key="set_purple", hide_label=True),  
        MenuItem("", None, submenu_id="blue_shades", slice_color=QColor("#4488FF"), action_key="set_blue", hide_label=True),    
        MenuItem("", None, submenu_id="green_shades", slice_color=QColor("#00CC66"), action_key="set_green", hide_label=True),   
    ]
    pages["text_settings"] = MenuPage(text_items, center_icon="back.png")

    pages["text_style_options"] = MenuPage([
        MenuItem("Normal", "font_normal.png", QColor("white"), action_key="set_font_normal", hide_label=True),
        MenuItem("Bold", "font_bold.png", QColor("white"), action_key="set_font_bold", badge="B", hide_label=True),
        MenuItem("Italic", "font_italic.png", QColor("white"), action_key="set_font_italic", badge="I", hide_label=True),
        MenuItem("BoldItalic", "font_bi.png", QColor("white"), action_key="set_font_bolditalic", badge="BI", hide_label=True),
    ], center_icon="back.png")

    eraser_items = [
        MenuItem("Stroke", "strokeeraser.png", QColor("white"), action_key="set_eraser_stroke", hide_label=True),
        MenuItem("Pixel", "pixeleraser.png", QColor("white"), action_key="set_eraser_pixel", submenu_id="pixel_eraser_settings", hide_label=True),
        MenuItem("Clear", "clear.png", QColor("#FF4444"), action_key="clear_canvas", hide_label=True),
    ]
    pages["eraser_settings"] = MenuPage(eraser_items, center_icon="back.png")
    pages["pixel_eraser_settings"] = MenuPage(items=[], page_type="dial", dial_range=(5, 100), dial_step=5, current_value=30, action_prefix="set_eraser_size_", center_icon="back.png")

    hl_items = [
        MenuItem("", None, submenu_id="hl_pink_shades", slice_color=QColor("#FF66CC"), action_key="set_pink", hide_label=True),   
        MenuItem("", None, submenu_id="hl_yellow_shades", slice_color=QColor("#FFFF00"), action_key="set_gold", hide_label=True), 
        MenuItem("Opacity", "opacity.png", QColor("white"), submenu_id="opacity_dial", badge="50", hide_label=True),
        MenuItem("Thickness", "thickness.png", QColor("white"), submenu_id="thickness_dial", badge="20", hide_label=True),
        MenuItem("Style", "boarderstyle.png", QColor("white"), submenu_id="style_options", badge="Solid", hide_label=True),
        MenuItem("", None, submenu_id="hl_blue_shades", slice_color=QColor("#66CCFF"), action_key="set_cyan", hide_label=True),   
        MenuItem("", None, submenu_id="hl_green_shades", slice_color=QColor("#66FF66"), action_key="set_lime", hide_label=True),  
        MenuItem("", None, submenu_id="hl_orange_shades", slice_color=QColor("#FFCC66"), action_key="set_orange", hide_label=True), 
    ]
    pages["hl_settings"] = MenuPage(hl_items, center_icon="back.png")

    pages["thickness_dial"] = MenuPage(items=[], page_type="dial", dial_range=(1, 20), dial_step=1, current_value=5, action_prefix="set_thickness_", center_icon="back.png")
    pages["opacity_dial"] = MenuPage(items=[], page_type="dial", dial_range=(10, 100), dial_step=10, current_value=100, action_prefix="set_opacity_", center_icon="back.png")

    style_items = [
        MenuItem("Solid", "line_solid.png", QColor("white"), action_key="set_style_solid", hide_label=True),
        MenuItem("Dashed", "line_dashed.png", QColor("white"), action_key="set_style_dashed", hide_label=True),
        MenuItem("Dotted", "line_dotted.png", QColor("white"), action_key="set_style_dotted", hide_label=True),
        MenuItem("DashDot", "line_dashdot.png", QColor("white"), action_key="set_style_dashdot", hide_label=True),
    ]
    pages["style_options"] = MenuPage(style_items, center_icon="back.png")

    def create_color_page(color_list): return MenuPage(color_list, center_icon="back.png")

    green_shades = [MenuItem("", None, action_key="set_lime", slice_color=QColor("#00FF00"), hide_label=True), MenuItem("", None, action_key="set_pale_green", slice_color=QColor("#CCFFCC"), hide_label=True), MenuItem("", None, action_key="set_dark_green", slice_color=QColor("#004400"), hide_label=True), MenuItem("", None, action_key="set_olive", slice_color=QColor("#556B2F"), hide_label=True), MenuItem("", None, action_key="set_forest", slice_color=QColor("#228B22"), hide_label=True), MenuItem("", None, action_key="set_green", slice_color=QColor("#008000"), hide_label=True), MenuItem("", None, action_key="set_teal", slice_color=QColor("#008080"), hide_label=True), MenuItem("", None, action_key="set_neon", slice_color=QColor("#39FF14"), hide_label=True)]
    red_shades = [MenuItem("", None, action_key="set_pink", slice_color=QColor("#FFC0CB"), hide_label=True), MenuItem("", None, action_key="set_rose", slice_color=QColor("#FF007F"), hide_label=True), MenuItem("", None, action_key="set_maroon", slice_color=QColor("#800000"), hide_label=True), MenuItem("", None, action_key="set_brick", slice_color=QColor("#B22222"), hide_label=True), MenuItem("", None, action_key="set_crimson", slice_color=QColor("#DC143C"), hide_label=True), MenuItem("", None, action_key="set_red", slice_color=QColor("#FF0000"), hide_label=True), MenuItem("", None, action_key="set_salmon", slice_color=QColor("#FA8072"), hide_label=True), MenuItem("", None, action_key="set_coral", slice_color=QColor("#FF7F50"), hide_label=True)]
    blue_shades = [MenuItem("", None, action_key="set_cyan", slice_color=QColor("#00FFFF"), hide_label=True), MenuItem("", None, action_key="set_sky", slice_color=QColor("#87CEEB"), hide_label=True), MenuItem("", None, action_key="set_navy", slice_color=QColor("#000080"), hide_label=True), MenuItem("", None, action_key="set_royal", slice_color=QColor("#4169E1"), hide_label=True), MenuItem("", None, action_key="set_midnight", slice_color=QColor("#191970"), hide_label=True), MenuItem("", None, action_key="set_blue", slice_color=QColor("#0000FF"), hide_label=True), MenuItem("", None, action_key="set_cornflower", slice_color=QColor("#6495ED"), hide_label=True), MenuItem("", None, action_key="set_ice", slice_color=QColor("#F0F8FF"), hide_label=True)]
    purple_shades = [MenuItem("", None, action_key="set_lavender", slice_color=QColor("#E6E6FA"), hide_label=True), MenuItem("", None, action_key="set_plum", slice_color=QColor("#DDA0DD"), hide_label=True), MenuItem("", None, action_key="set_magenta", slice_color=QColor("#FF00FF"), hide_label=True), MenuItem("", None, action_key="set_dark_purple", slice_color=QColor("#301934"), hide_label=True), MenuItem("", None, action_key="set_indigo", slice_color=QColor("#4B0082"), hide_label=True), MenuItem("", None, action_key="set_purple", slice_color=QColor("#800080"), hide_label=True), MenuItem("", None, action_key="set_violet", slice_color=QColor("#EE82EE"), hide_label=True), MenuItem("", None, action_key="set_orchid", slice_color=QColor("#DA70D6"), hide_label=True)]
    orange_shades = [MenuItem("", None, action_key="set_gold", slice_color=QColor("#FFD700"), hide_label=True), MenuItem("", None, action_key="set_orange", slice_color=QColor("#FFA500"), hide_label=True), MenuItem("", None, action_key="set_dark_orange", slice_color=QColor("#FF8C00"), hide_label=True), MenuItem("", None, action_key="set_brown", slice_color=QColor("#A52A2A"), hide_label=True), MenuItem("", None, action_key="set_chocolate", slice_color=QColor("#D2691E"), hide_label=True), MenuItem("", None, action_key="set_sienna", slice_color=QColor("#A0522D"), hide_label=True), MenuItem("", None, action_key="set_peach", slice_color=QColor("#FFDAB9"), hide_label=True), MenuItem("", None, action_key="set_tan", slice_color=QColor("#D2B48C"), hide_label=True)]
    black_shades = [MenuItem("", None, action_key="set_black", slice_color=QColor("#000000"), hide_label=True), MenuItem("", None, action_key="set_dark_gray", slice_color=QColor("#333333"), hide_label=True), MenuItem("", None, action_key="set_dim_gray", slice_color=QColor("#555555"), hide_label=True), MenuItem("", None, action_key="set_gray", slice_color=QColor("#808080"), hide_label=True), MenuItem("", None, action_key="set_light_gray", slice_color=QColor("#AAAAAA"), hide_label=True), MenuItem("", None, action_key="set_silver", slice_color=QColor("#CCCCCC"), hide_label=True), MenuItem("", None, action_key="set_white", slice_color=QColor("#FFFFFF"), hide_label=True), MenuItem("", None, action_key="set_off_white", slice_color=QColor("#F5F5F5"), hide_label=True)]

    pages["green_shades"] = create_color_page(green_shades)
    pages["red_shades"] = create_color_page(red_shades)
    pages["blue_shades"] = create_color_page(blue_shades)
    pages["purple_shades"] = create_color_page(purple_shades)
    pages["orange_shades"] = create_color_page(orange_shades)
    pages["black_shades"] = create_color_page(black_shades)

    pages["hl_yellow_shades"] = create_color_page(orange_shades)
    pages["hl_pink_shades"] = create_color_page(red_shades)
    pages["hl_purple_shades"] = create_color_page(purple_shades)
    pages["hl_blue_shades"] = create_color_page(blue_shades)
    pages["hl_green_shades"] = create_color_page(green_shades)
    pages["hl_orange_shades"] = create_color_page(orange_shades)

    def create_board_color_page(base_items):
        new_items = []
        for item in base_items:
            new_action = item.action_key.replace("set_", "set_board_")
            new_items.append(MenuItem("", None, action_key=new_action, slice_color=item.slice_color, hide_label=True))
        return create_color_page(new_items)

    pages["board_white_shades"] = create_board_color_page(black_shades)
    pages["board_black_shades"] = create_board_color_page(black_shades)
    pages["board_blue_shades"] = create_board_color_page(blue_shades)
    pages["board_green_shades"] = create_board_color_page(green_shades)

    # --- Fill Color Pages ---
    def create_fill_color_page(base_items):
        new_items = []
        for item in base_items:
            new_action = item.action_key.replace("set_", "set_fill_")
            new_items.append(MenuItem("", None, action_key=new_action, slice_color=item.slice_color, hide_label=True))
        return create_color_page(new_items)

    pages["fill_red_shades"] = create_fill_color_page(red_shades)
    pages["fill_blue_shades"] = create_fill_color_page(blue_shades)
    pages["fill_green_shades"] = create_fill_color_page(green_shades)
    pages["fill_orange_shades"] = create_fill_color_page(orange_shades)
    pages["fill_purple_shades"] = create_fill_color_page(purple_shades)
    pages["fill_black_shades"] = create_fill_color_page(black_shades)

    return pages