"""The simulated rig: page of open squares, plotter landing model, camera and rendering."""
from freehand.sim.camera import A_AREA, A_GAP_MM, A_SIZES, CAM_H, CAM_W, make_camera, project, render_raw
from freehand.sim.geometry import CENTRE, CROP_PX_PER_MM, LETTER_H, LETTER_W, PX, REGION, TOL_MM
from freehand.sim.page import Square, far_apart_order, make_page, renumber
from freehand.sim.plotter import FunctionMapper, Landing, PlotterMap, closure, densify, land, poly_len
from freehand.sim.render import crop_view, png_bytes, render_rect, render_view, render_view_warp, warp_rect

__all__ = [
    "A_AREA", "A_GAP_MM", "A_SIZES", "CAM_H", "CAM_W", "CENTRE", "CROP_PX_PER_MM", "LETTER_H", "LETTER_W", "PX",
    "REGION", "TOL_MM", "FunctionMapper", "Landing", "PlotterMap", "Square", "closure", "crop_view", "densify",
    "far_apart_order", "land", "make_camera", "make_page", "png_bytes", "poly_len", "project", "render_raw",
    "render_rect", "render_view", "render_view_warp", "renumber", "warp_rect",
]
