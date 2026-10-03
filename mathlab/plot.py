# -*- coding: utf-8 -*-
"""函数绘图部件: 自带坐标轴/网格/刻度/多曲线/缩放/平移/游标追踪/导出 PNG

渲染代码只依赖一个极薄的 Surface 抽象, 因此同一份绘制逻辑既可画在
tk.Canvas 上, 也可直接渲染成 PNG (无需 Ghostscript)。
"""
from __future__ import annotations

import math
import tkinter as tk

from .engine import Evaluator, CalcError, format_number


# ----------------------------------------------------------------------
# 绘制面抽象
# ----------------------------------------------------------------------
class TkSurface:
    def __init__(self, canvas: tk.Canvas):
        self.c = canvas

    def size(self):
        return self.c.winfo_width(), self.c.winfo_height()

    def line(self, x1, y1, x2, y2, fill="#000", width=1, dash=None):
        self.c.create_line(x1, y1, x2, y2, fill=fill, width=width,
                           dash=dash, capstyle="round")

    def rect(self, x1, y1, x2, y2, fill=None, outline=None, width=1):
        self.c.create_rectangle(x1, y1, x2, y2, fill=fill or "",
                                outline=outline or "", width=width)

    def oval(self, x1, y1, x2, y2, fill=None, outline=None, width=1):
        self.c.create_oval(x1, y1, x2, y2, fill=fill or "",
                           outline=outline or "", width=width)

    def text(self, x, y, s, fill="#000", anchor="center", size=9, bold=False, mono=False):
        fam = "Consolas" if mono else "Microsoft YaHei UI"
        self.c.create_text(x, y, text=s, fill=fill, anchor=anchor,
                           font=(fam, size, "bold" if bold else "normal"))


class PILSurface:
    """把同样的绘制指令画到 PIL 图上, 用于导出 PNG"""

    def __init__(self, w, h, bg="#FFFFFF", scale=2):
        from PIL import Image, ImageDraw, ImageFont
        self.scale = scale
        self.img = Image.new("RGB", (int(w * scale), int(h * scale)), bg)
        self.d = ImageDraw.Draw(self.img)
        self._if = ImageFont
        self._w, self._h = w, h
        self._cache = {}

    def size(self):
        return self._w, self._h

    def _f(self, size, bold, mono):
        key = (size, bold, mono)
        f = self._cache.get(key)
        if f is None:
            # 注意: 微软雅黑是 msyh.ttc(字体集合), 必须带 index; 早期用 msyh.ttf 会静默回退成极小字体
            cands = [("msyhbd.ttc", 0), ("msyh.ttc", 0), ("segoeuib.ttf", 0), ("arialbd.ttf", 0)] \
                if (bold and not mono) else \
                ([("msyh.ttc", 0), ("segoeui.ttf", 0), ("arial.ttf", 0)] if not mono else
                 [("consolab.ttf", 0), ("consola.ttf", 0), ("arialbd.ttf", 0)] if bold else
                 [("consola.ttf", 0), ("arial.ttf", 0)])
            f = None
            for name, idx in cands:
                try:
                    f = self._if.truetype("C:/Windows/Fonts/" + name,
                                          int(size * self.scale * 1.34), index=idx)
                    break
                except Exception:
                    continue
            if f is None:
                f = self._if.load_default()
            self._cache[key] = f
        return f

    def line(self, x1, y1, x2, y2, fill="#000", width=1, dash=None):
        w = max(1, int(round(width * self.scale)))
        if dash:
            # 手动画虚线
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy)
            if L < 1:
                return
            ux, uy = dx / L, dy / L
            on, off = 5 * self.scale, 4 * self.scale
            t = 0.0
            while t < L:
                t2 = min(t + on, L)
                self.d.line([(x1 + ux * t) * self.scale, (y1 + uy * t) * self.scale,
                             (x1 + ux * t2) * self.scale, (y1 + uy * t2) * self.scale],
                            fill=fill, width=w)
                t = t2 + off
            return
        self.d.line([x1 * self.scale, y1 * self.scale, x2 * self.scale, y2 * self.scale],
                    fill=fill, width=w)

    def rect(self, x1, y1, x2, y2, fill=None, outline=None, width=1):
        self.d.rectangle([x1 * self.scale, y1 * self.scale, x2 * self.scale, y2 * self.scale],
                         fill=fill, outline=outline,
                         width=max(1, int(round(width * self.scale))))

    def oval(self, x1, y1, x2, y2, fill=None, outline=None, width=1):
        self.d.ellipse([x1 * self.scale, y1 * self.scale, x2 * self.scale, y2 * self.scale],
                       fill=fill, outline=outline,
                       width=max(1, int(round(width * self.scale))))

    def text(self, x, y, s, fill="#000", anchor="center", size=9, bold=False, mono=False):
        amap = {"center": "mm", "w": "lm", "e": "rm", "n": "ma", "s": "ms",
                "nw": "la", "ne": "ra", "sw": "ld", "se": "rd"}
        self.d.text((x * self.scale, y * self.scale), s, fill=fill,
                    anchor=amap.get(anchor, "mm"), font=self._f(size, bold, mono))

    def save(self, path):
        self.img.save(path)


# ----------------------------------------------------------------------
# 颜色 / 主题
# ----------------------------------------------------------------------
PLOT_BG = "#FFFFFF"
GRID = "#EDEAE3"
GRID_MAJOR = "#DCD7CB"
AXIS = "#8C8577"
CURVE_COLORS = ["#D97757", "#2F6FB2", "#3E9E6A", "#8B5CC4"]

FONT = "Microsoft YaHei UI"
MONO = "Consolas"


class FunctionPlotter(tk.Canvas):
    """函数绘图控件"""

    def __init__(self, master, on_status=None, **kw):
        super().__init__(master, bg=PLOT_BG, highlightthickness=1,
                         highlightbackground="#DCD7CB", **kw)
        self.funcs = []                 # [(expr, color, visible, compiled)]
        self.angle_mode = "rad"
        self.xmin, self.xmax = -10.0, 10.0
        self.ymin, self.ymax = -6.0, 6.0
        self.auto_y = True
        self.on_status = on_status
        self._drag = None
        self._trace = None
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))
        self.bind("<Double-Button-1>", lambda e: (self.reset_view(), None))
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: (setattr(self, "_trace", None), self.redraw()))

    # ---------------- 外部接口 ----------------
    def set_functions(self, items):
        """items: [(expr|None, color, visible)]"""
        self.funcs = []
        for expr, color, visible in items:
            compiled = None
            err = None
            if expr and expr.strip():
                try:
                    ev = Evaluator(angle_mode=self.angle_mode)
                    compiled = ev.scalar_function(expr.strip(), "x")
                except CalcError as ex:
                    err = str(ex)
            self.funcs.append({"expr": expr, "color": color,
                               "visible": visible, "f": compiled, "err": err})
        self.redraw()
        return [f["err"] for f in self.funcs]

    def reset_view(self):
        self.xmin, self.xmax = -10.0, 10.0
        self.ymin, self.ymax = -6.0, 6.0
        self.auto_y = True
        self.redraw()

    def set_auto_y(self, flag):
        self.auto_y = bool(flag)
        self.redraw()

    def zoom(self, factor, cx=None, cy=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:                 # 尚未完成布局时用默认视口
            w, h = 800, 560
        cx = w / 2 if cx is None else cx
        cy = h / 2 if cy is None else cy
        x0 = self._px2x(cx)
        y0 = self._px2y(cy)
        self.xmin = x0 + (self.xmin - x0) * factor
        self.xmax = x0 + (self.xmax - x0) * factor
        self.ymin = y0 + (self.ymin - y0) * factor
        self.ymax = y0 + (self.ymax - y0) * factor
        self.redraw()

    # ---------------- 坐标换算 ----------------
    def _size(self):
        """当前绘制面尺寸: 渲染中取绘制面尺寸(导出时为导出画布), 否则取控件尺寸"""
        cur = getattr(self, "_cur_size", None)
        if cur:
            return cur
        return self.winfo_width(), self.winfo_height()

    def _margin(self):
        return 70, 42, 30, 48          # left, top, right, bottom

    def _plot_box(self):
        w, h = self._size()
        l, t, r, b = self._margin()
        return l, t, max(l + 10, w - r), max(t + 10, h - b)

    def _x2px(self, x, box=None):
        l, t, r, b = box or self._plot_box()
        return l + (x - self.xmin) / (self.xmax - self.xmin) * (r - l)

    def _y2px(self, y, box=None):
        l, t, r, b = box or self._plot_box()
        return b - (y - self.ymin) / (self.ymax - self.ymin) * (b - t)

    def _px2x(self, px, box=None):
        l, t, r, b = box or self._plot_box()
        return self.xmin + (px - l) / max(1, (r - l)) * (self.xmax - self.xmin)

    def _px2y(self, py, box=None):
        l, t, r, b = box or self._plot_box()
        return self.ymin + (b - py) / max(1, (b - t)) * (self.ymax - self.ymin)

    # ---------------- 刻度 ----------------
    @staticmethod
    def _nice_step(span, target=8):
        if span <= 0 or not math.isfinite(span):
            return 1.0
        raw = span / max(3, target)
        mag = 10 ** math.floor(math.log10(raw))
        for m in (1, 2, 2.5, 5, 10):
            if raw <= m * mag:
                return m * mag
        return 10 * mag

    @staticmethod
    def _fmt_tick(v, step):
        if abs(v) < 1e-12:
            return "0"
        dec = max(0, min(6, -int(math.floor(math.log10(abs(step)))))) if step > 0 else 2
        s = ("%.*f" % (dec, v)).rstrip("0").rstrip(".")
        if abs(v) >= 1e6 or (abs(v) < 1e-4 and v != 0):
            s = "%.3g" % v
        return s

    # ---------------- 自动 y 范围 ----------------
    def _compute_auto_y(self):
        vals = []
        box = self._plot_box()
        n = max(60, box[2] - box[0])
        for fn in self.funcs:
            f = fn.get("f")
            if not f or not fn["visible"]:
                continue
            prev = None
            for i in range(0, n + 1, 2):
                x = self.xmin + (self.xmax - self.xmin) * i / n
                try:
                    y = f(x)
                except Exception:
                    continue
                if not math.isfinite(y):
                    continue
                if prev is not None and abs(y - prev) > 4 * (self.ymax - self.ymin):
                    prev = y
                    continue
                if abs(y) < 1e7:
                    vals.append(y)
                prev = y
        if not vals:
            return None
        vals.sort()
        lo = vals[int(len(vals) * 0.02)]
        hi = vals[int(len(vals) * 0.98)] if len(vals) > 5 else vals[-1]
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.12
        return lo - pad, hi + pad

    # ---------------- 绘制 ----------------
    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        self.delete("all")
        self._render(TkSurface(self))

    def _render(self, s):
        w, h = s.size()
        self._cur_size = (w, h)          # 关键: 让坐标换算与当前绘制面一致
        try:
            self._render_inner(s, w, h)
        finally:
            self._cur_size = None

    def _render_inner(self, s, w, h):
        if self.auto_y:
            got = self._compute_auto_y()
            if got:
                self.ymin, self.ymax = got
        # 背景
        s.rect(0, 0, w, h, fill=PLOT_BG)
        box = self._plot_box()
        l, t, r, b = box
        stepx = self._nice_step(self.xmax - self.xmin, max(4, (r - l) // 90))
        stepy = self._nice_step(self.ymax - self.ymin, max(3, (b - t) // 60))
        major = 5.0
        # 网格
        x0 = math.floor(self.xmin / stepx) * stepx
        mx = 0
        while x0 <= self.xmax + stepx * 0.5 and mx < 400:
            px = self._x2px(x0, box)
            if l - 1 <= px <= r + 1:
                is_major = abs((x0 / stepx) % major) < 1e-6
                s.line(px, t, px, b, fill=GRID_MAJOR if is_major else GRID, width=1)
                # 贴边的刻度标签会被画布裁掉, 直接不画
                if (x0 != 0 or not (self.ymin <= 0 <= self.ymax)) and l + 10 <= px <= r - 10:
                    s.text(px, b + 6, self._fmt_tick(x0, stepx), fill=AXIS,
                           anchor="n", size=9)
            x0 += stepx
            mx += 1
        y0 = math.floor(self.ymin / stepy) * stepy
        my = 0
        while y0 <= self.ymax + stepy * 0.5 and my < 400:
            py = self._y2px(y0, box)
            if t - 1 <= py <= b + 1:
                is_major = abs((y0 / stepy) % major) < 1e-6
                s.line(l, py, r, py, fill=GRID_MAJOR if is_major else GRID, width=1)
                if (y0 != 0 or not (self.xmin <= 0 <= self.xmax)) and t + 4 <= py <= b - 4:
                    s.text(l - 6, py, self._fmt_tick(y0, stepy), fill=AXIS,
                           anchor="e", size=9)
            y0 += stepy
            my += 1
        # 坐标轴
        if self.ymin <= 0 <= self.ymax:
            py = self._y2px(0, box)
            s.line(l, py, r, py, fill=AXIS, width=2)
        if self.xmin <= 0 <= self.xmax:
            px = self._x2px(0, box)
            s.line(px, t, px, b, fill=AXIS, width=2)
        # 曲线
        n = max(80, (r - l) * 2)
        for fn in self.funcs:
            f = fn.get("f")
            if not f or not fn["visible"]:
                continue
            pts = []
            prev_y = None
            for i in range(n + 1):
                x = self.xmin + (self.xmax - self.xmin) * i / n
                try:
                    y = f(x)
                except Exception:
                    y = float("nan")
                if not math.isfinite(y):
                    self._flush_curve(s, pts)
                    pts = []
                    prev_y = None
                    continue
                py = self._y2px(y, box)
                if py < -5000 or py > 5000:
                    self._flush_curve(s, pts)
                    pts = []
                    prev_y = None
                    continue
                if prev_y is not None and abs(py - prev_y) > (b - t) * 1.6:
                    self._flush_curve(s, pts)
                    pts = []
                pts.append((self._x2px(x, box), py, fn["color"]))
                prev_y = py
            self._flush_curve(s, pts)
        # 游标标线
        if self._trace:
            tx, ty, txt, color = self._trace
            s.line(tx, t, tx, b, fill="#B9B2A5", width=1, dash=(4, 4))
            s.oval(tx - 4, ty - 4, tx + 4, ty + 4, fill=color, outline="#FFFFFF", width=2)
            tw = max(90, len(txt) * 8)
            px = min(max(tx + 10, l + 2), r - tw)
            py = min(max(ty - 34, t + 2), b - 26)
            s.rect(px, py, px + tw, py + 22, fill="#2B2823", outline="#2B2823")
            s.text(px + 8, py + 11, txt, fill="#F7F5F0", anchor="w", size=9, mono=True)
        # 图例
        ly = t + 10
        for fn in self.funcs:
            if not fn["expr"] or not fn["expr"].strip():
                continue
            col = fn["color"] if fn["visible"] else "#C9C4B8"
            s.line(l + 12, ly, l + 34, ly, fill=col, width=3)
            label = fn["expr"] if len(fn["expr"]) <= 26 else fn["expr"][:25] + "…"
            s.text(l + 40, ly, label, fill=col if fn["visible"] else "#B5AFA2",
                   anchor="w", size=9)
            ly += 20

    @staticmethod
    def _flush_curve(s, pts):
        if len(pts) < 2:
            return
        col = pts[0][2] if len(pts[0]) > 2 else "#D97757"
        for i in range(len(pts) - 1):
            s.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                   fill=col, width=2)

    # ---------------- 交互 ----------------
    def _on_wheel(self, ev):
        self.zoom(0.85 if ev.delta > 0 else 1.18, ev.x, ev.y)

    def _on_press(self, ev):
        self._drag = (ev.x, ev.y, self.xmin, self.xmax, self.ymin, self.ymax)

    def _on_drag(self, ev):
        if not self._drag:
            return
        x0, y0, xmin, xmax, ymin, ymax = self._drag
        box = self._plot_box()
        dx = (ev.x - x0) / max(1, box[2] - box[0]) * (xmax - xmin)
        dy = (ev.y - y0) / max(1, box[3] - box[1]) * (ymax - ymin)
        self.xmin, self.xmax = xmin - dx, xmax - dx
        self.ymin, self.ymax = ymin + dy, ymax + dy
        self.auto_y = False
        self.redraw()

    def _on_motion(self, ev):
        box = self._plot_box()
        if not (box[0] <= ev.x <= box[2] and box[1] <= ev.y <= box[3]):
            if self._trace:
                self._trace = None
                self.redraw()
            return
        x = self._px2x(ev.x, box)
        best = None
        for fn in self.funcs:
            f = fn.get("f")
            if not f or not fn["visible"]:
                continue
            try:
                y = f(x)
            except Exception:
                continue
            if not math.isfinite(y):
                continue
            py = self._y2px(y, box)
            if not (box[1] - 40 <= py <= box[3] + 40):
                continue
            d = abs(py - ev.y)
            if best is None or d < best[0]:
                best = (d, self._x2px(x, box), py, y, fn["color"])
        if best is None:
            msg = "x = %s" % format_number(x, 6)
            self._trace = (ev.x, ev.y, msg, "#8C8577")
        else:
            d, px, py, y, col = best
            msg = "x=%s   y=%s" % (format_number(x, 6), format_number(y, 6))
            self._trace = (px, py, msg, col)
        if self.on_status:
            self.on_status(self._trace[2])
        self.redraw()

    # ---------------- 导出 ----------------
    def export_png(self, path, w=1280, h=800):
        """用与屏幕完全相同的绘制逻辑渲染成 PNG (2× 超采样, 保持屏幕当前视图)"""
        saved = self.auto_y
        self.auto_y = False          # 保持屏幕上的范围, 所见即所得
        try:
            s = PILSurface(w, h, PLOT_BG, scale=2)
            self._render(s)
            s.save(path)
        finally:
            self.auto_y = saved
        return path
