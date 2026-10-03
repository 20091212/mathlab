# -*- coding: utf-8 -*-
"""MathLab 图形界面 (tkinter): 计算器 / 绘图 / 方程 / 矩阵 / 统计 / 换换算

设计要点:
  * 全部中文界面, 单窗口, 无外部依赖
  * 右侧常驻历史面板(可折叠), 自动持久化
  * 全局快捷键: Ctrl+1..6 切页 / Ctrl+H 历史 / Ctrl+L 定位输入 / F5 重算 / F1 帮助
"""
from __future__ import annotations

import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import engine as E
from .history import History
from .plot import CURVE_COLORS, FunctionPlotter

# ---------------------------------------------------------------- 主题
C = {
    "bg": "#F7F6F3",
    "panel": "#FFFFFF",
    "border": "#E2DED4",
    "ink": "#23211E",
    "dim": "#8A8478",
    "accent": "#D97757",
    "accent_dk": "#BF5C3C",
    "sel": "#F3E6DE",
    "ok": "#3E7A52",
    "warn": "#B4552F",
}
UI = "Microsoft YaHei UI"
MONO = "Consolas"


def pick_fonts(root):
    global UI, MONO
    from tkinter import font as tkfont
    try:
        fams = set(tkfont.families(root))
    except Exception:
        return
    for f in ("Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", "Segoe UI", "TkDefaultFont"):
        if f in fams:
            UI = f
            break
    for f in ("Consolas", "Cascadia Mono", "Courier New", "TkFixedFont"):
        if f in fams:
            MONO = f
            break


# ---------------------------------------------------------------- 辅助控件
class ScrollFrame(ttk.Frame):
    """可滚动容器: 内容放在 .inner"""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=C["bg"])
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, ev):
        try:
            self.canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
        except Exception:
            pass


def card(parent, title, pad=10):
    f = ttk.LabelFrame(parent, text=" %s " % title, padding=pad)
    return f


def out_text(parent, height=6, width=40, size=10):
    t = tk.Text(parent, height=height, width=width, wrap="none",
                font=(MONO, size), bg=C["panel"], fg=C["ink"],
                relief="flat", highlightthickness=1,
                highlightbackground=C["border"], highlightcolor=C["accent"],
                padx=8, pady=6)
    return t


def set_out(text_widget, s):
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", s)
    text_widget.configure(state="disabled")


def entry(parent, textvariable=None, width=12, size=11, mono=True):
    return tk.Entry(parent, textvariable=textvariable, width=width,
                    font=((MONO if mono else UI), size), bg=C["panel"], fg=C["ink"],
                    relief="flat", highlightthickness=1,
                    highlightbackground=C["border"], highlightcolor=C["accent"],
                    insertbackground=C["ink"], justify="center" if mono else "left")


# ================================================================ 计算器
KEYS = [
    [("7", "7"), ("8", "8"), ("9", "9"), ("÷", "/"), ("(", "("), (")", ")")],
    [("4", "4"), ("5", "5"), ("6", "6"), ("×", "*"), ("^", "^"), ("√", "sqrt(")],
    [("1", "1"), ("2", "2"), ("3", "3"), ("−", "-"), ("%", "%"), ("π", "pi")],
    [("0", "0"), (".", "."), ("e", "e"), ("+", "+"), ("x!", "!"), ("1/x", "^-1")],
    [("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("ln", "ln("), ("log", "log("), ("x²", "^2")],
    [("←", "@BS"), ("C", "@C"), ("ANS", "ans"), ("M+", "@M+"), ("MR", "m"), ("MC", "@MC")],
]


class CalcTab:
    name = "计算器"

    def __init__(self, parent, app):
        self.app = app
        f = ttk.Frame(parent, padding=12)
        self.frame = f
        f.columnconfigure(0, weight=1)

        # 输入
        top = ttk.Frame(f)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        box = tk.Frame(top, bg=C["border"])
        box.grid(row=0, column=0, sticky="ew")
        self.entry = tk.Entry(box, font=(MONO, 17), bg=C["panel"], fg=C["ink"],
                              relief="flat", insertbackground=C["accent"],
                              highlightthickness=0)
        self.entry.pack(fill="x", padx=1, pady=1, ipady=7, ipadx=6)
        self.entry.bind("<Return>", lambda e: self.calculate())
        self.entry.bind("<Escape>", lambda e: self.entry.delete(0, "end"))
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Up>", lambda e: self._recall(1))
        self.entry.bind("<Down>", lambda e: self._recall(-1))
        ttk.Button(top, text="计算  ⏎", style="Accent.TButton",
                   command=self.calculate).grid(row=0, column=1, padx=(8, 0), sticky="ns")
        self.entry.focus_set()

        self.preview = ttk.Label(f, text="", foreground=C["dim"])
        self.preview.grid(row=1, column=0, sticky="w", pady=(6, 8))

        # 键盘
        kb = ttk.Frame(f)
        kb.grid(row=2, column=0, sticky="ew")
        for r, row in enumerate(KEYS):
            kb.rowconfigure(r, weight=1)
            for c, (label, ins) in enumerate(row):
                kb.columnconfigure(c, weight=1)
                st = "Key.TButton" if not label[0].isdigit() and label not in (
                    "(", ")", ".", "e", "%") else "Num.TButton"
                ttk.Button(kb, text=label, style=st,
                           command=lambda i=ins: self._key(i)).grid(
                    row=r, column=c, sticky="nsew", padx=2, pady=2, ipady=2)

        # 结果
        res = card(f, "结果")
        res.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        res.columnconfigure(0, weight=1)
        self.result = tk.Label(res, text="0", font=(MONO, 30), bg=C["panel"],
                               fg=C["ink"], anchor="e")
        self.result.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 0))
        self.hint = tk.Label(res, text="", font=(UI, 10), bg=C["panel"],
                             fg=C["dim"], anchor="e")
        self.hint.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        bar = ttk.Frame(res)
        bar.grid(row=2, column=0, sticky="e", pady=(2, 2))
        ttk.Button(bar, text="复制结果", command=self.copy_result).pack(side="left", padx=3)
        ttk.Button(bar, text="清空输入", command=self.clear_all).pack(side="left", padx=3)
        self._after = None
        self._last_result = "0"

    # ---------- 交互 ----------
    def _key(self, ins):
        w = self.entry
        if ins == "@BS":
            cur = w.index("insert")
            if cur > 0:
                w.delete(cur - 1)
        elif ins == "@C":
            w.delete(0, "end")
            self.preview.configure(text="")
        elif ins == "@M+":
            try:
                cur = self.app.evaluator().evaluate(w.get() or "0")
                self.app.memory += cur
                self.app.notify("记忆值 M = %s" % E.format_number(self.app.memory))
            except E.CalcError as ex:
                self.app.notify("⚠ " + str(ex))
        elif ins == "@MC":
            self.app.memory = 0.0
            self.app.notify("记忆值已清零")
        elif ins == "=":
            self.calculate()
        else:
            w.insert("insert", ins)
        w.focus_set()
        self._on_key(None)

    def _on_key(self, _ev):
        if self._after:
            try:
                self.app.root.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.app.root.after(200, self._preview)

    def _preview(self):
        self._after = None
        s = self.entry.get().strip()
        if not s:
            self.preview.configure(text="")
            return
        try:
            v = self.app.evaluator().evaluate(s)
            self.preview.configure(text="= %s" % E.format_number(v), foreground=C["dim"])
        except E.CalcError as ex:
            self.preview.configure(text="… %s" % ex, foreground=C["warn"])
        except Exception:
            self.preview.configure(text="")

    def _recall(self, direction):
        items = [it for it in self.app.history.items if it.get("kind") == self.name]
        if not items:
            return
        if not hasattr(self, "_rp"):
            self._rp = 0
        self._rp = max(0, min(len(items) - 1, self._rp + direction))
        self.entry.delete(0, "end")
        self.entry.insert(0, items[self._rp].get("expr", ""))
        self._on_key(None)

    def calculate(self):
        s = self.entry.get().strip()
        if not s:
            return
        try:
            v = self.app.evaluator().evaluate(s)
        except E.CalcError as ex:
            self.result.configure(text="—")
            self.hint.configure(text="⚠ %s" % ex, fg=C["warn"])
            self.app.notify("⚠ " + str(ex))
            return
        self.app.ans = v
        self.app.last_value = v
        txt = E.format_number(v)
        self._last_result = txt
        self.result.configure(text=txt, fg=C["ink"])
        bits = []
        fr = E.fraction_hint(v)
        if fr:
            bits.append("≈ " + fr)
        bases = E.int_bases(v)
        if bases:
            bits.append(bases)
        bits.append("ANS = %s" % E.format_number(self.app.ans, 8))
        bits.append("模式：%s" % ("角度" if self.app.angle.get() == "deg" else "弧度"))
        self.hint.configure(text="    ".join(bits), fg=C["dim"])
        self.app.push_history(self.name, s, txt)
        self.preview.configure(text="")

    def copy_result(self):
        self.app.copy(self._last_result)

    def clear_all(self):
        self.entry.delete(0, "end")
        self.result.configure(text="0")
        self.hint.configure(text="")
        self.preview.configure(text="")

    def focus_input(self):
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def recompute(self):
        self.calculate()


# ================================================================ 绘图
class PlotTab:
    name = "函数绘图"

    def __init__(self, parent, app):
        self.app = app
        f = ttk.Frame(parent, padding=10)
        self.frame = f
        f.columnconfigure(0, weight=0)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)

        left = ttk.Frame(f)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.rows = []
        box = card(left, "曲线")
        box.pack(fill="x")
        for i in range(3):
            row = ttk.Frame(box)
            row.pack(fill="x", pady=3)
            var_vis = tk.BooleanVar(value=(i == 0))
            ttk.Checkbutton(row, variable=var_vis,
                            command=self.redraw).pack(side="left")
            sw = tk.Canvas(row, width=12, height=12, highlightthickness=0, bg=C["bg"])
            sw.create_rectangle(1, 1, 11, 11, fill=CURVE_COLORS[i], outline="")
            sw.pack(side="left", padx=(0, 4))
            ent = entry(row, width=18, size=11, mono=True)
            ent.insert(0, ["sin(x)", "cos(x)", "x^2/4"][i] if i == 0 else "")
            ent.pack(side="left", fill="x", expand=True)
            ent.bind("<Return>", lambda e: self.redraw())
            ent.bind("<KeyRelease>", lambda e: self._debounce())
            self.rows.append({"vis": var_vis, "entry": ent})

        rng = card(left, "X 轴范围")
        rng.pack(fill="x", pady=(8, 0))
        r = ttk.Frame(rng)
        r.pack(fill="x")
        self.xmin = entry(r, width=7, size=10)
        self.xmin.insert(0, "-10")
        self.xmin.pack(side="left")
        ttk.Label(r, text=" ~ ").pack(side="left")
        self.xmax = entry(r, width=7, size=10)
        self.xmax.insert(0, "10")
        self.xmax.pack(side="left")
        ttk.Button(r, text="应用", width=6, command=self.apply_range).pack(side="left", padx=5)
        self.auto_y = tk.BooleanVar(value=True)
        ttk.Checkbutton(rng, text="自动 Y 轴", variable=self.auto_y,
                        command=lambda: self.plotter.set_auto_y(self.auto_y.get())
                        ).pack(anchor="w", pady=(4, 0))
        ops = card(left, "操作")
        ops.pack(fill="x", pady=(8, 0))
        for txt, cmd in [("重绘", self.redraw), ("重置视图", self.reset),
                         ("放大", lambda: self.plotter.zoom(0.8)),
                         ("缩小", lambda: self.plotter.zoom(1.25)),
                         ("求零点", self.find_zeros),
                         ("保存 PNG", self.save_png)]:
            ttk.Button(ops, text=txt, command=cmd).pack(fill="x", pady=2)
        tip = ttk.Label(left, text="滚轮缩放 · 拖动平移\n双击复位",
                        foreground=C["dim"], justify="left")
        tip.pack(anchor="w", pady=(8, 0))

        right = ttk.Frame(f)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.plotter = FunctionPlotter(right, on_status=lambda s: self.app.notify(s))
        self.plotter.grid(row=0, column=0, sticky="nsew")
        self.err = ttk.Label(right, text="", foreground=C["warn"])
        self.err.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._after = None

    def _debounce(self):
        if self._after:
            try:
                self.app.root.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.app.root.after(350, self.redraw)

    def apply_range(self):
        try:
            a, b = float(self.xmin.get()), float(self.xmax.get())
            if b <= a:
                raise ValueError
            self.plotter.xmin, self.plotter.xmax = a, b
            self.plotter.redraw()
        except ValueError:
            self.app.notify("⚠ X 轴范围不合法")

    def redraw(self):
        self.plotter.angle_mode = self.app.angle.get()
        items = [(r["entry"].get(), CURVE_COLORS[i], r["vis"].get())
                 for i, r in enumerate(self.rows)]
        errs = self.plotter.set_functions(items)
        bad = [e for e in errs if e]
        self.err.configure(text=("⚠ " + bad[0]) if bad else "")
        try:
            self.plotter.xmin = float(self.xmin.get())
            self.plotter.xmax = float(self.xmax.get())
        except ValueError:
            pass
        self.plotter.redraw()

    def reset(self):
        self.plotter.reset_view()

    def find_zeros(self):
        found = []
        for r in self.rows:
            s = r["entry"].get().strip()
            if not s or not r["vis"].get():
                continue
            try:
                from .engine import Evaluator
                fn = Evaluator(angle_mode=self.app.angle.get()).scalar_function(s)
                roots = E.find_roots(fn, self.plotter.xmin, self.plotter.xmax)
            except E.CalcError as ex:
                self.app.notify("⚠ " + str(ex))
                return
            if roots:
                found.append("%s: %s" % (s, "、".join(E.format_number(v, 8) for v in roots)))
        msg = "\n".join(found) if found else "当前范围内未找到零点"
        messagebox.showinfo("零点 (x 轴交点)", msg, parent=self.app.root)
        if found:
            self.app.push_history(self.name, "零点 " + " | ".join(
                r["entry"].get() for r in self.rows if r["entry"].get()),
                "\n".join(found))
        self.app.notify("已求零点")

    def save_png(self):
        path = filedialog.asksaveasfilename(
            parent=self.app.root, defaultextension=".png",
            initialfile="mathlab-plot.png",
            filetypes=[("PNG 图片", "*.png")])
        if not path:
            return
        try:
            self.plotter.export_png(path)
            self.app.notify("已保存: " + os.path.basename(path))
            self.app.push_history(self.name, "导出图像", path)
        except Exception as ex:
            messagebox.showerror("导出失败", str(ex), parent=self.app.root)

    def focus_input(self):
        self.rows[0]["entry"].focus_set()

    def recompute(self):
        self.redraw()


# ================================================================ 方程
class EquationTab:
    name = "方程求解"

    def __init__(self, parent, app):
        self.app = app
        sf = ScrollFrame(parent)
        self.frame = sf
        f = sf.inner
        f.columnconfigure(0, weight=1)

        # --- 多项式 ---
        b1 = card(f, "一元二次 / 三次方程   ax² + bx + c = 0   (a 为 0 时自动降次)")
        b1.grid(row=0, column=0, sticky="ew")
        row = ttk.Frame(b1)
        row.pack(fill="x")
        self.co = {}
        for nm, dv in (("a", "1"), ("b", "-3"), ("c", "2"), ("d", "")):
            ttk.Label(row, text=nm + " =").pack(side="left", padx=(6, 2))
            e = entry(row, width=8, size=11)
            e.insert(0, dv)
            e.pack(side="left")
            self.co[nm] = e
        ttk.Label(row, text="  (d 不填则解一元二次)", foreground=C["dim"]).pack(side="left")
        ttk.Button(b1, text="求解", style="Accent.TButton",
                   command=self.solve_poly).pack(anchor="w", pady=(8, 2))
        self.poly_out = out_text(b1, height=7)
        self.poly_out.pack(fill="x", pady=(4, 0))

        # --- 通用 ---
        b2 = card(f, "通用方程 f(x) = 0  (支持 sin/cos/ln/exp 等)")
        b2.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        r2 = ttk.Frame(b2)
        r2.pack(fill="x")
        ttk.Label(r2, text="方程").pack(side="left", padx=(6, 4))
        self.gen_expr = entry(r2, width=30, size=11)
        self.gen_expr.insert(0, "x^3 - 2x + 1 = 0")
        self.gen_expr.pack(side="left")
        ttk.Label(r2, text="区间").pack(side="left", padx=(10, 4))
        self.g_lo = entry(r2, width=7, size=10)
        self.g_lo.insert(0, "-20")
        self.g_lo.pack(side="left")
        ttk.Label(r2, text="~").pack(side="left", padx=2)
        self.g_hi = entry(r2, width=7, size=10)
        self.g_hi.insert(0, "20")
        self.g_hi.pack(side="left")
        ttk.Button(r2, text="求根", style="Accent.TButton",
                   command=self.solve_general).pack(side="left", padx=8)
        ttk.Button(r2, text="画出来", command=self.plot_it).pack(side="left")
        self.gen_out = out_text(b2, height=6)
        self.gen_out.pack(fill="x", pady=(6, 0))

        # --- 线性方程组 ---
        b3 = card(f, "线性方程组  (每行一个等式, 如  2x + y - z = 8)")
        b3.grid(row=2, column=0, sticky="ew", pady=(10, 6))
        self.lin_in = out_text(b3, height=5)
        self.lin_in.pack(fill="x")
        self.lin_in.configure(state="normal")
        self.lin_in.insert("1.0", "2x + y - z = 8\n-3x - y + 2z = -11\n-2x + y + 2z = -3")
        r3 = ttk.Frame(b3)
        r3.pack(fill="x", pady=(6, 0))
        ttk.Button(r3, text="求解", style="Accent.TButton",
                   command=self.solve_linear).pack(side="left", padx=3)
        ttk.Button(r3, text="清空", command=lambda: self.lin_in.delete("1.0", "end")
                   ).pack(side="left", padx=3)
        ttk.Button(r3, text="二元示例", command=lambda: self._demo(2)).pack(side="left", padx=3)
        ttk.Button(r3, text="三元示例", command=lambda: self._demo(3)).pack(side="left", padx=3)
        self.lin_out = out_text(b3, height=7)
        self.lin_out.pack(fill="x", pady=(6, 0))

    def _demo(self, n):
        self.lin_in.delete("1.0", "end")
        if n == 2:
            self.lin_in.insert("1.0", "2x + y = 5\nx - y = 1")
        else:
            self.lin_in.insert("1.0", "2x + y - z = 8\n-3x - y + 2z = -11\n-2x + y + 2z = -3")

    def solve_poly(self):
        try:
            a = float(self.co["a"].get() or 0)
            b = float(self.co["b"].get() or 0)
            c = float(self.co["c"].get() or 0)
            d = self.co["d"].get().strip()
        except ValueError:
            set_out(self.poly_out, "系数必须是数字")
            return
        lines = []
        try:
            if d:
                dd = float(d)
                roots, kind = E.solve_cubic(a, b, c, dd)
                lines.append("方程：%gx³ + %gx² + %gx + %g = 0" % (a, b, c, dd))
                lines.append("判别类型：%s" % kind)
                for i, (z, _m) in enumerate(roots, 1):
                    lines.append("  x%d = %s" % (i, E.format_complex(z)))
                ssum = sum(z for z, _ in roots)
                prod = 1
                for z, _ in roots:
                    prod *= z
                lines.append("根之和 = %s    根之积 = %s" % (
                    E.format_complex(ssum), E.format_complex(prod)))
            else:
                roots, kind = E.solve_quadratic(a, b, c)
                lines.append("方程：%gx² + %gx + %g = 0" % (a, b, c))
                lines.append("判别类型：%s    判别式 Δ = %s" % (kind, E.format_number(b * b - 4 * a * c)))
                for i, (z, _m) in enumerate(roots, 1):
                    lines.append("  x%d = %s" % (i, E.format_complex(z)))
                if a != 0:
                    h, k = -b / (2 * a), (4 * a * c - b * b) / (4 * a)
                    lines.append("顶点 = (%s, %s)   对称轴 x = %s" % (
                        E.format_number(h), E.format_number(k), E.format_number(h)))
                    lines.append("根之和 = %s   根之积 = %s" % (
                        E.format_number(-b / a), E.format_number(c / a)))
            txt = "\n".join(lines)
            set_out(self.poly_out, txt)
            self.app.push_history(self.name, lines[0].replace("方程：", ""),
                                  "；".join(l.strip() for l in lines[2:]))
        except E.CalcError as ex:
            set_out(self.poly_out, "⚠ %s" % ex)

    def solve_general(self):
        s = self.gen_expr.get().strip()
        if not s:
            return
        if "=" in s:
            parts = s.split("=")
            if len(parts) != 2:
                set_out(self.gen_out, "⚠ 等号只能出现一次")
                return
            s = "(%s)-(%s)" % (parts[0], parts[1])
        try:
            lo, hi = float(self.g_lo.get()), float(self.g_hi.get())
        except ValueError:
            set_out(self.gen_out, "⚠ 区间必须是数字")
            return
        try:
            fn = E.Evaluator(angle_mode=self.app.angle.get()).scalar_function(s)
            roots = E.find_roots(fn, lo, hi)
        except E.CalcError as ex:
            set_out(self.gen_out, "⚠ %s" % ex)
            return
        if not roots:
            set_out(self.gen_out, "在 [%g, %g] 内未找到实根" % (lo, hi))
            return
        txt = "在 [%g, %g] 内找到 %d 个实根：\n" % (lo, hi, len(roots))
        txt += "\n".join("  x%d = %s" % (i, E.format_number(v, 10)) for i, v in enumerate(roots, 1))
        txt += "\n\n校验 f(x)：\n"
        txt += "\n".join("  f(%s) = %s" % (E.format_number(v, 8), E.format_number(fn(v), 6))
                         for v in roots[:6])
        set_out(self.gen_out, txt)
        self.app.push_history(self.name, self.gen_expr.get().strip(),
                              "、".join(E.format_number(v, 8) for v in roots))

    def plot_it(self):
        s = self.gen_expr.get().strip()
        if not s:
            return
        if "=" in s:
            parts = s.split("=")
            s = "(%s)-(%s)" % (parts[0], parts[1])
        self.app.goto_tab(1)
        self.app.plot_tab.rows[0]["vis"].set(True)
        e0 = self.app.plot_tab.rows[0]["entry"]
        e0.delete(0, "end")
        e0.insert(0, s)
        try:
            lo, hi = float(self.g_lo.get()), float(self.g_hi.get())
            self.app.plot_tab.xmin.delete(0, "end")
            self.app.plot_tab.xmin.insert(0, "%g" % lo)
            self.app.plot_tab.xmax.delete(0, "end")
            self.app.plot_tab.xmax.insert(0, "%g" % hi)
        except ValueError:
            pass
        self.app.plot_tab.redraw()
        self.app.notify("已在「函数绘图」中显示")

    def solve_linear(self):
        txt = self.lin_in.get("1.0", "end")
        try:
            A, b, vars_ = E.parse_linear_equations(txt)
        except E.CalcError as ex:
            set_out(self.lin_out, "⚠ %s" % ex)
            return
        kind, sol = E.solve_linear_system(A, b)
        head = "未知数：%s      方程数：%d\n" % ("、".join(vars_), len(A))
        if kind == "none":
            body = "方程组无解（存在矛盾方程）"
        elif kind == "infinite":
            M, piv = sol
            free = [v for i, v in enumerate(vars_) if i not in piv]
            body = "方程组有无穷多解（自由未知数：%s）\n\n行简化阶梯形：\n%s" % (
                "、".join(free), E.Matrix([r[:len(vars_) + 1] for r in M]))
        else:
            body = "唯一解：\n" + "\n".join(
                "  %s = %s" % (v, E.format_number(x, 10)) for v, x in zip(vars_, sol))
        set_out(self.lin_out, head + body)
        note = body.split("\n")[0]
        self.app.push_history(self.name, "解方程组: " + txt.strip().replace("\n", " ; "), note)

    def focus_input(self):
        self.gen_expr.focus_set()

    def recompute(self):
        self.solve_general()


# ================================================================ 矩阵
class MatrixTab:
    name = "矩阵运算"

    def __init__(self, parent, app):
        self.app = app
        f = ttk.Frame(parent, padding=12)
        self.frame = f
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        top = ttk.Frame(f)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        ba = card(top, "矩阵 A   (行用换行或 ; 分隔, 元素用空格或逗号)")
        ba.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.A = out_text(ba, height=5, size=11)
        self.A.pack(fill="both", expand=True)
        self.A.configure(state="normal")
        self.A.insert("1.0", "1 2 3\n4 5 6\n7 8 10")

        bb = card(top, "矩阵 B  /  标量 k")
        bb.grid(row=0, column=1, sticky="nsew")
        self.B = out_text(bb, height=5, size=11)
        self.B.pack(fill="both", expand=True)
        self.B.configure(state="normal")
        self.B.insert("1.0", "1 0 0\n0 1 0\n0 0 1")
        rk = ttk.Frame(bb)
        rk.pack(fill="x", pady=(6, 0))
        ttk.Label(rk, text="k =").pack(side="left", padx=(4, 3))
        self.k = entry(rk, width=8, size=11)
        self.k.insert(0, "2")
        self.k.pack(side="left")
        ttk.Button(rk, text="填充 A 为随机", command=self.rand_a).pack(side="left", padx=6)
        ttk.Button(rk, text="B 设为单位阵", command=self.iden_b).pack(side="left")

        ops = card(f, "运算")
        ops.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        names = [("A + B", self.op_add), ("A − B", self.op_sub), ("A × B", self.op_mul),
                 ("k · A", self.op_scale), ("Aᵀ", self.op_trans),
                 ("det(A)", self.op_det), ("A⁻¹", self.op_inv),
                 ("秩 r(A)", self.op_rank), ("RREF(A)", self.op_rref),
                 ("迹 tr(A)", self.op_trace), ("特征值", self.op_eig)]
        grid = ttk.Frame(ops)
        grid.pack(fill="x")
        per_row = 4
        for i, (txt, cmd) in enumerate(names):
            grid.columnconfigure(i % per_row, weight=1)
            ttk.Button(grid, text=txt, width=13, command=cmd).grid(
                row=i // per_row, column=i % per_row, padx=3, pady=3, sticky="ew")

        bo = card(f, "结果")
        bo.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        f.rowconfigure(2, weight=2)
        self.out = out_text(bo, height=12, size=11)
        self.out.pack(fill="both", expand=True)
        bar = ttk.Frame(bo)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="复制结果", command=lambda: self.app.copy(self.out.get("1.0", "end").strip())
                   ).pack(side="left", padx=3)
        ttk.Button(bar, text="清空", command=lambda: set_out(self.out, "")
                   ).pack(side="left", padx=3)

    # ---------- 工具 ----------
    def _A(self):
        return E.Matrix.parse(self.A.get("1.0", "end"))

    def _B(self):
        return E.Matrix.parse(self.B.get("1.0", "end"))

    def _k(self):
        try:
            return float(self.k.get())
        except ValueError:
            raise E.CalcError("标量 k 必须是数字")

    def _show(self, title, obj):
        body = str(obj) if not isinstance(obj, str) else obj
        set_out(self.out, "%s\n%s\n%s" % (title, "─" * 34, body))
        self.app.push_history(self.name, title, body.replace("\n", " ; ")[:160])
        self.app.notify(title + " 完成")

    def _err(self, ex):
        set_out(self.out, "⚠ %s" % ex)
        self.app.notify("⚠ " + str(ex))

    # ---------- 运算 ----------
    def op_add(self):
        try:
            self._show("A + B", self._A().add(self._B()))
        except E.CalcError as ex:
            self._err(ex)

    def op_sub(self):
        try:
            self._show("A − B", self._A().sub(self._B()))
        except E.CalcError as ex:
            self._err(ex)

    def op_mul(self):
        try:
            self._show("A × B", self._A().mul(self._B()))
        except E.CalcError as ex:
            self._err(ex)

    def op_scale(self):
        try:
            self._show("k · A  (k=%s)" % self._k(), self._A().scale(self._k()))
        except E.CalcError as ex:
            self._err(ex)

    def op_trans(self):
        try:
            self._show("Aᵀ", self._A().transpose())
        except E.CalcError as ex:
            self._err(ex)

    def op_det(self):
        try:
            self._show("det(A)", E.format_number(self._A().det()))
        except E.CalcError as ex:
            self._err(ex)

    def op_inv(self):
        try:
            self._show("A⁻¹", self._A().inv())
        except E.CalcError as ex:
            self._err(ex)

    def op_rank(self):
        try:
            self._show("秩 r(A)", str(self._A().rank()))
        except E.CalcError as ex:
            self._err(ex)

    def op_rref(self):
        try:
            M, piv = self._A().rref()
            self._show("RREF(A)  主元列: %s" % ([p + 1 for p in piv],), M)
        except E.CalcError as ex:
            self._err(ex)

    def op_trace(self):
        try:
            self._show("迹 tr(A)", E.format_number(self._A().trace()))
        except E.CalcError as ex:
            self._err(ex)

    def op_eig(self):
        try:
            vals = self._A().eigen()
            body = "\n".join("  λ%d = %s" % (i, E.format_complex(v)) for i, v in enumerate(vals, 1))
            self._show("特征值", body)
        except E.CalcError as ex:
            self._err(ex)

    def rand_a(self):
        import random
        n = random.choice([2, 3])
        rows = [" ".join("%d" % random.randint(-6, 9) for _ in range(n)) for _ in range(n)]
        self.A.delete("1.0", "end")
        self.A.insert("1.0", "\n".join(rows))

    def iden_b(self):
        n = len(self.A.get("1.0", "end").strip().split("\n"))
        n = max(2, min(6, n))
        self.B.delete("1.0", "end")
        self.B.insert("1.0", "\n".join(
            " ".join("1" if i == j else "0" for j in range(n)) for i in range(n)))

    def focus_input(self):
        self.A.focus_set()

    def recompute(self):
        self.op_det()


# ================================================================ 统计
class StatsTab:
    name = "统计"

    def __init__(self, parent, app):
        self.app = app
        sf = ScrollFrame(parent)
        self.frame = sf
        f = sf.inner
        f.columnconfigure(0, weight=1)

        b1 = card(f, "数据 (用逗号、空格或换行分隔)")
        b1.grid(row=0, column=0, sticky="ew")
        self.data = out_text(b1, height=5)
        self.data.pack(fill="x")
        self.data.configure(state="normal")
        self.data.insert("1.0", "2, 4, 4, 4, 5, 5, 7, 9")
        r = ttk.Frame(b1)
        r.pack(fill="x", pady=(6, 0))
        ttk.Button(r, text="计算统计量", style="Accent.TButton",
                   command=self.compute).pack(side="left", padx=3)
        ttk.Button(r, text="清空", command=lambda: self.data.delete("1.0", "end")
                   ).pack(side="left", padx=3)
        ttk.Button(r, text="示例数据", command=lambda: self._demo("2 4 4 4 5 5 7 9")
                   ).pack(side="left", padx=3)

        b2 = card(f, "统计结果")
        b2.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.gridf = ttk.Frame(b2)
        self.gridf.pack(fill="x")
        self.cells = {}
        for i, key in enumerate(["个数", "求和", "平均值", "中位数", "众数", "最小值",
                                 "最大值", "极差", "总体方差", "样本方差",
                                 "总体标准差", "样本标准差", "下四分位 Q1",
                                 "上四分位 Q3", "四分位距", "平方和"]):
            r0, c0 = divmod(i, 4)
            cell = ttk.Frame(self.gridf)
            cell.grid(row=r0, column=c0, sticky="ew", padx=6, pady=4)
            ttk.Label(cell, text=key, foreground=C["dim"], font=(UI, 9)).pack(anchor="w")
            lb = tk.Label(cell, text="—", font=(MONO, 12), bg=C["panel"], fg=C["ink"])
            lb.pack(anchor="w")
            self.cells[key] = lb
        for c0 in range(4):
            self.gridf.columnconfigure(c0, weight=1)

        b3 = card(f, "线性回归   y = a + b·x")
        b3.grid(row=2, column=0, sticky="ew", pady=(10, 6))
        r3 = ttk.Frame(b3)
        r3.pack(fill="x")
        ttk.Label(r3, text="X 数据").pack(side="left", padx=(4, 3))
        self.rx = entry(r3, width=26, size=10)
        self.rx.insert(0, "1 2 3 4 5")
        self.rx.pack(side="left")
        ttk.Label(r3, text="Y 数据").pack(side="left", padx=(10, 3))
        self.ry = entry(r3, width=26, size=10)
        self.ry.insert(0, "2.1 3.9 6.2 8.1 10.2")
        self.ry.pack(side="left")
        ttk.Button(r3, text="拟合", style="Accent.TButton",
                   command=self.regress).pack(side="left", padx=8)
        ttk.Button(r3, text="画出直线", command=self.plot_line).pack(side="left")
        self.reg_out = out_text(b3, height=4)
        self.reg_out.pack(fill="x", pady=(6, 0))

    def _demo(self, s):
        self.data.delete("1.0", "end")
        self.data.insert("1.0", s)

    def compute(self):
        txt = self.data.get("1.0", "end")
        try:
            vals = E.parse_numbers(txt)
            res = E.stats_summary(vals)
        except E.CalcError as ex:
            self.app.notify("⚠ " + str(ex))
            return
        for k, v in res:
            if k in self.cells:
                self.cells[k].configure(text=v)
        set_out(self.data, "")
        self.data.configure(state="normal")
        self.data.delete("1.0", "end")
        self.data.insert("1.0", ", ".join(E.format_number(v, 8) for v in vals))
        ones = sum(1 for v in vals if v == 1)
        self.app.push_history(self.name, "统计 %d 个数据 (1 出现 %d 次)" % (len(vals), ones),
                              "  ".join("%s=%s" % (k, v) for k, v in res[:6]))
        self.app.notify("统计完成：共 %d 个数据" % len(vals))

    def regress(self):
        try:
            xs = E.parse_numbers(self.rx.get())
            ys = E.parse_numbers(self.ry.get())
            r = E.linear_regression(xs, ys)
        except E.CalcError as ex:
            set_out(self.reg_out, "⚠ %s" % ex)
            return
        sign = "+" if r["intercept"] >= 0 else "−"
        txt = ("拟合直线：  y = %s %s %s·x\n"
               "斜率 b = %s     截距 a = %s\n"
               "相关系数 r = %s     R² = %s     样本点 n = %d") % (
            E.format_number(abs(r["slope"]), 8), sign,
            E.format_number(abs(r["intercept"]), 8),
            E.format_number(r["slope"], 8), E.format_number(r["intercept"], 8),
            E.format_number(r["r"], 8), E.format_number(r["r2"], 8), r["n"])
        set_out(self.reg_out, txt)
        self._last_fit = (r["intercept"], r["slope"])
        self.app.push_history(self.name, "线性回归 y = a + b x",
                              "b=%s a=%s r²=%s" % (E.format_number(r["slope"], 6),
                                                   E.format_number(r["intercept"], 6),
                                                   E.format_number(r["r2"], 6)))
        self.app.notify("拟合完成")

    def plot_line(self):
        if not hasattr(self, "_last_fit"):
            self.regress()
        if not hasattr(self, "_last_fit"):
            return
        a, b = self._last_fit
        self.app.goto_tab(1)
        t = self.app.plot_tab
        for i, (expr, vis) in enumerate([("(%s) + (%s)*x" % (E.format_number(a, 8),
                                                            E.format_number(b, 8)), True)]):
            e = t.rows[i]["entry"]
            e.delete(0, "end")
            e.insert(0, expr)
            t.rows[i]["vis"].set(vis)
        t.redraw()
        self.app.notify("拟合直线已画到「函数绘图」")

    def focus_input(self):
        self.data.focus_set()

    def recompute(self):
        self.compute()


# ================================================================ 单位换算
class UnitTab:
    name = "单位换算"

    def __init__(self, parent, app):
        self.app = app
        f = ttk.Frame(parent, padding=12)
        self.frame = f
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)

        b1 = card(f, "换算")
        b1.grid(row=0, column=0, sticky="ew")
        r = ttk.Frame(b1)
        r.pack(fill="x")
        ttk.Label(r, text="类别").pack(side="left", padx=(2, 4))
        self.kind = ttk.Combobox(r, values=list(E.UNITS.keys()) + ["温度"],
                                 state="readonly", width=8)
        self.kind.set("长度")
        self.kind.pack(side="left")
        self.kind.bind("<<ComboboxSelected>>", lambda e: self.sync_units())
        ttk.Label(r, text="数值").pack(side="left", padx=(12, 4))
        self.val = entry(r, width=16, size=12)
        self.val.insert(0, "1")
        self.val.pack(side="left")
        self.val.bind("<KeyRelease>", lambda e: self.convert())
        ttk.Label(r, text="从").pack(side="left", padx=(12, 4))
        self.frm = ttk.Combobox(r, state="readonly", width=16)
        self.frm.pack(side="left")
        self.frm.bind("<<ComboboxSelected>>", lambda e: self.convert())
        ttk.Button(r, text="⇄", width=3, command=self.swap).pack(side="left", padx=6)
        ttk.Label(r, text="到").pack(side="left", padx=(0, 4))
        self.to = ttk.Combobox(r, state="readonly", width=16)
        self.to.pack(side="left")
        self.to.bind("<<ComboboxSelected>>", lambda e: self.convert())

        b2 = card(f, "结果")
        b2.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.result = tk.Label(b2, text="", font=(MONO, 22), bg=C["panel"], fg=C["ink"],
                               anchor="w")
        self.result.pack(fill="x", padx=6)
        self.sub = tk.Label(b2, text="", font=(UI, 10), bg=C["panel"], fg=C["dim"],
                            anchor="w", justify="left")
        self.sub.pack(fill="x", padx=6, pady=(0, 4))

        b3 = card(f, "该数值在同类单位中的全部换算")
        b3.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.tree = ttk.Treeview(b3, columns=("u", "v"), show="headings", height=10)
        self.tree.heading("u", text="单位")
        self.tree.heading("v", text="数值")
        self.tree.column("u", width=220, anchor="w")
        self.tree.column("v", width=260, anchor="e")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._pick)
        ttk.Label(b3, text="双击某一行可把它设为「到」的目标单位",
                  foreground=C["dim"]).pack(anchor="w", pady=(4, 0))
        self.sync_units()

    def sync_units(self):
        units = E.unit_list(self.kind.get())
        self.frm.configure(values=units)
        self.to.configure(values=units)
        self.frm.set(units[0])
        self.to.set(units[1] if len(units) > 1 else units[0])
        self.convert()

    def swap(self):
        a, b = self.frm.get(), self.to.get()
        self.frm.set(b)
        self.to.set(a)
        self.convert()

    def convert(self):
        try:
            v = float(self.val.get())
        except ValueError:
            self.result.configure(text="—")
            self.sub.configure(text="请输入数字")
            return
        kind = self.kind.get()
        try:
            out = E.convert_unit(v, kind, self.frm.get(), self.to.get())
        except E.CalcError as ex:
            self.result.configure(text="—")
            self.sub.configure(text=str(ex))
            return
        self.result.configure(text="%s %s  =  %s %s" % (
            E.format_number(v, 10), self.frm.get().split()[-1],
            E.format_number(out, 10), self.to.get().split()[-1]))
        self.sub.configure(text="1 %s = %s %s" % (
            self.frm.get(),
            E.format_number(E.convert_unit(1, kind, self.frm.get(), self.to.get()), 10),
            self.to.get()))
        self.tree.delete(*self.tree.get_children())
        for u in E.unit_list(kind):
            try:
                cv = E.convert_unit(v, kind, self.frm.get(), u)
            except E.CalcError:
                continue
            mark = "  ◀" if u == self.to.get() else ""
            self.tree.insert("", "end", values=(u + mark, E.format_number(cv, 10)))
        self.app.last_unit = (v, kind, self.frm.get(), self.to.get(), out)

    def _pick(self, _ev):
        sel = self.tree.selection()
        if not sel:
            return
        u = self.tree.item(sel[0], "values")[0].replace("  ◀", "")
        self.to.set(u)
        self.convert()

    def focus_input(self):
        self.val.focus_set()

    def recompute(self):
        self.convert()


# ================================================================ 主程序
TABS = [CalcTab, PlotTab, EquationTab, MatrixTab, StatsTab, UnitTab]


class MathLabApp:
    def __init__(self, root):
        self.root = root
        self.history = History()
        self.angle = tk.StringVar(value="rad")
        self.ans = 0.0
        self.memory = 0.0
        self.last_value = 0.0
        self.status = tk.StringVar(value="就绪")
        self._hist_visible = True
        pick_fonts(root)
        self._theme()
        self._layout()
        self._keys()
        self.refresh_history()
        self.notify("就绪 · 按 F1 查看帮助与全部函数")

    # ---------- 主题 ----------
    def _theme(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=C["bg"], foreground=C["ink"], font=(UI, 10))
        st.configure("TFrame", background=C["bg"])
        st.configure("TLabel", background=C["bg"], foreground=C["ink"], font=(UI, 10))
        st.configure("TLabelframe", background=C["bg"], bordercolor=C["border"],
                     relief="solid", borderwidth=1)
        st.configure("TLabelframe.Label", background=C["bg"], foreground=C["accent_dk"],
                     font=(UI, 10, "bold"))
        st.configure("TButton", background=C["panel"], foreground=C["ink"],
                     borderwidth=1, relief="solid", padding=(9, 5), font=(UI, 10))
        st.map("TButton",
               background=[("active", C["sel"]), ("pressed", C["sel"])],
               bordercolor=[("hover", C["accent"])])
        st.configure("Accent.TButton", background=C["accent"], foreground="#FFFFFF",
                     borderwidth=0, padding=(12, 6), font=(UI, 10, "bold"))
        st.map("Accent.TButton", background=[("active", C["accent_dk"]),
                                             ("pressed", C["accent_dk"])])
        st.configure("Num.TButton", padding=(9, 5), font=(MONO, 12))
        st.configure("Key.TButton", padding=(9, 5), font=(UI, 10))
        st.configure("TCheckbutton", background=C["bg"], foreground=C["ink"], font=(UI, 10))
        st.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(6, 6, 0, 0))
        st.configure("TNotebook.Tab", padding=(16, 8), font=(UI, 10),
                     background="#EFEDE7", foreground=C["dim"], borderwidth=0)
        st.map("TNotebook.Tab",
               background=[("selected", C["panel"])],
               foreground=[("selected", C["accent_dk"])],
               font=[("selected", (UI, 10, "bold"))])
        st.configure("Treeview", background=C["panel"], fieldbackground=C["panel"],
                     foreground=C["ink"], rowheight=26, borderwidth=0, font=(UI, 10))
        st.configure("Treeview.Heading", background="#EFEDE7", foreground=C["dim"],
                     font=(UI, 9), relief="flat")
        st.map("Treeview", background=[("selected", C["sel"])],
               foreground=[("selected", C["ink"])])
        st.configure("TCombobox", padding=4, font=(UI, 10))
        st.configure("Vertical.TScrollbar", background="#E6E2D9", troughcolor=C["bg"],
                     borderwidth=0, arrowsize=12)

    # ---------- 布局 ----------
    def _layout(self):
        self.root.title("MathLab 数学计算器")
        self.root.configure(bg=C["bg"])

        bar = ttk.Frame(self.root, padding=(14, 10, 14, 6))
        bar.pack(fill="x")
        tk.Label(bar, text="MathLab", font=(UI, 16, "bold"), bg=C["bg"],
                 fg=C["accent_dk"]).pack(side="left")
        tk.Label(bar, text="数学计算 · 绘图 · 方程 · 矩阵 · 统计 · 换算",
                 font=(UI, 9), bg=C["bg"], fg=C["dim"]).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="帮助 F1", command=self.show_help).pack(side="right", padx=3)
        self.hist_btn = ttk.Button(bar, text="历史 Ctrl+H", command=self.toggle_history)
        self.hist_btn.pack(side="right", padx=3)
        ang = ttk.Frame(bar)
        ang.pack(side="right", padx=(0, 14))
        ttk.Label(ang, text="角度模式").pack(side="left", padx=(0, 6))
        ttk.Radiobutton(ang, text="弧度", value="rad", variable=self.angle,
                        command=self._angle_changed).pack(side="left")
        ttk.Radiobutton(ang, text="角度", value="deg", variable=self.angle,
                        command=self._angle_changed).pack(side="left")

        body = ttk.PanedWindow(self.root, orient="horizontal")

        sb = ttk.Frame(self.root, padding=(14, 4, 14, 8))
        sb.pack(side="bottom", fill="x")
        ttk.Label(sb, textvariable=self.status, foreground=C["dim"]).pack(side="left")
        ttk.Label(sb, text="Ctrl+1~6 切页 · Ctrl+L 输入框 · F5 重算 · Enter 计算",
                  foreground="#B4AEA1", font=(UI, 9)).pack(side="right")

        body.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.nb = ttk.Notebook(body)
        self.tabs = []
        for cls in TABS:
            t = cls(self.nb, self)
            self.nb.add(t.frame, text="  %s  " % t.name)
            self.tabs.append(t)
        # 便捷别名 (供各页互相调用)
        self.calc_tab, self.plot_tab, self.eq_tab = self.tabs[0], self.tabs[1], self.tabs[2]
        self.matrix_tab, self.stats_tab, self.unit_tab = self.tabs[3], self.tabs[4], self.tabs[5]
        body.add(self.nb, weight=5)

        self.hpanel = ttk.Frame(body, padding=8)
        self._build_history_panel()
        body.add(self.hpanel, weight=1)
        self.body = body

        self.root.update_idletasks()
        w, h = 1200, 800
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(w, sw - 80), min(h, sh - 100)
        self.root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(20, (sh - h) // 2 - 20)))
        self.root.minsize(1000, 660)

    def _build_history_panel(self):
        h = self.hpanel
        top = ttk.Frame(h)
        top.pack(fill="x")
        tk.Label(top, text="历史记录", font=(UI, 11, "bold"), bg=C["bg"],
                 fg=C["accent_dk"]).pack(side="left")
        self.hcount = tk.Label(top, text="0", bg=C["bg"], fg=C["dim"])
        self.hcount.pack(side="left", padx=6)
        self.search = entry(h, width=14, size=10, mono=False)
        self.search.pack(fill="x", pady=(6, 6))
        self.search.bind("<KeyRelease>", lambda e: self.refresh_history())
        self.tree = ttk.Treeview(h, columns=("t", "c"), show="headings")
        self.tree.heading("t", text="时间")
        self.tree.heading("c", text="内容")
        self.tree.column("t", width=88, anchor="w", stretch=False)
        self.tree.column("c", width=210, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.recall())
        self.tree.bind("<Button-3>", lambda e: self._ctx_menu(e))
        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="回填到当前页", command=self.recall)
        self.ctx.add_command(label="复制结果", command=lambda: self.copy(self._sel_value(1)))
        self.ctx.add_command(label="收藏 / 取消收藏", command=self.fav)
        self.ctx.add_separator()
        self.ctx.add_command(label="删除", command=self.del_item)

        btns = ttk.Frame(h)
        btns.pack(fill="x", pady=(6, 0))
        row1 = ttk.Frame(btns)
        row1.pack(fill="x")
        ttk.Button(row1, text="回填", command=self.recall).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(row1, text="复制", command=lambda: self.copy(self._sel_value(1))
                   ).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(row1, text="★", width=3, command=self.fav).pack(side="left", padx=1)
        row2 = ttk.Frame(btns)
        row2.pack(fill="x", pady=(3, 0))
        ttk.Button(row2, text="删除", command=self.del_item).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(row2, text="清空", command=self.clear_hist).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(row2, text="导出", command=self.export_hist).pack(side="left", expand=True, fill="x", padx=1)

    # ---------- 快捷键 ----------
    def _keys(self):
        r = self.root
        r.protocol("WM_DELETE_WINDOW", self.quit)
        for i in range(len(TABS)):
            r.bind("<Control-Key-%d>" % (i + 1), lambda e, i=i: self.goto_tab(i))
        r.bind("<Control-h>", lambda e: self.toggle_history())
        r.bind("<Control-l>", lambda e: self.tabs[self.nb.index("current")].focus_input())
        r.bind("<Control-d>", lambda e: self.tabs[self.nb.index("current")].clear_all()
               if hasattr(self.tabs[self.nb.index("current")], "clear_all") else None)
        r.bind("<F1>", lambda e: self.show_help())
        r.bind("<F5>", lambda e: self.tabs[self.nb.index("current")].recompute())
        r.bind("<Control-q>", lambda e: self.quit())

    # ---------- 通用 ----------
    def evaluator(self):
        return E.Evaluator(angle_mode=self.angle.get(), ans=self.ans, memory=self.memory)

    def notify(self, msg):
        self.status.set(msg)

    def copy(self, s):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(s or "")
            self.notify("已复制到剪贴板")
        except Exception:
            pass

    def goto_tab(self, i):
        i = max(0, min(len(self.tabs) - 1, i))
        self.nb.select(i)
        self.notify("已切换到「%s」" % self.tabs[i].name)

    def _angle_changed(self):
        self.notify("角度模式：%s" % ("角度(deg)" if self.angle.get() == "deg" else "弧度(rad)"))
        try:
            self.tabs[1].plotter.angle_mode = self.angle.get()
            self.tabs[1].redraw()
        except Exception:
            pass

    def toggle_history(self):
        if self._hist_visible:
            self.body.forget(self.hpanel)
            self._hist_visible = False
            self.notify("已隐藏历史面板")
        else:
            self.body.add(self.hpanel, weight=1)
            self._hist_visible = True
            self.notify("已显示历史面板")

    def quit(self):
        try:
            self.history.save()
        except Exception:
            pass
        self.root.destroy()

    # ---------- 历史 ----------
    def push_history(self, kind, expr, result, note=""):
        self.history.add(kind, expr, result, note)
        self.refresh_history()

    def refresh_history(self):
        q = self.search.get() if hasattr(self, "search") else ""
        items = self.history.search(q)
        self.tree.delete(*self.tree.get_children())
        for it in items[:400]:
            star = "★ " if it.get("fav") else ""
            ts = it.get("ts", "")[5:16]
            expr = (it.get("expr") or "").replace("\n", " ")
            res = (it.get("result") or "").replace("\n", " ")
            if len(expr) > 30:
                expr = expr[:29] + "…"
            if len(res) > 30:
                res = res[:29] + "…"
            self.tree.insert("", "end", iid=it["id"],
                             values=(ts, "%s[%s] %s = %s" % (star, it.get("kind", ""), expr, res)))
        self.hcount.configure(text=str(len(items)))

    def _sel(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _sel_value(self, idx):
        iid = self._sel()
        if not iid:
            return ""
        vals = self.tree.item(iid, "values")
        return vals[idx] if idx < len(vals) else ""

    def recall(self):
        iid = self._sel()
        it = self.history.get(iid) if iid else None
        if not it:
            self.notify("请先在历史中选择一条记录")
            return
        cur = self.tabs[self.nb.index("current")]
        if isinstance(cur, CalcTab):
            cur.entry.delete(0, "end")
            cur.entry.insert(0, it.get("expr", ""))
            cur.focus_input()
            cur._on_key(None)
            self.notify("已回填输入表达式")
        elif isinstance(cur, EquationTab):
            cur.gen_expr.delete(0, "end")
            cur.gen_expr.insert(0, it.get("expr", ""))
            cur.focus_input()
            self.notify("已回填到方程输入框")
        else:
            self.copy(it.get("result", ""))
            self.notify("当前页无输入框, 已复制该条结果")

    def fav(self):
        iid = self._sel()
        if not iid:
            return
        on = self.history.toggle_fav(iid)
        self.refresh_history()
        self.notify("已收藏" if on else "已取消收藏")

    def del_item(self):
        iid = self._sel()
        if not iid:
            return
        if self.history.delete(iid):
            self.refresh_history()
            self.notify("已删除该条历史")

    def clear_hist(self):
        if not messagebox.askyesno("清空历史", "确定清空全部历史记录吗？（收藏项会保留）",
                                   parent=self.root):
            return
        self.history.clear(keep_fav=True)
        self.refresh_history()
        self.notify("历史已清空（收藏保留）")

    def export_hist(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".csv",
            initialfile="mathlab-history.csv",
            filetypes=[("CSV 表格", "*.csv"), ("文本文件", "*.txt")])
        if not path:
            return
        if path.lower().endswith(".txt"):
            self.history.export_txt(path)
        else:
            self.history.export_csv(path)
        self.notify("已导出: " + os.path.basename(path))
        messagebox.showinfo("导出完成", "已导出到:\n" + path, parent=self.root)

    def _ctx_menu(self, ev):
        iid = self.tree.identify_row(ev.y)
        if iid:
            self.tree.selection_set(iid)
            try:
                self.ctx.tk_popup(ev.x_root, ev.y_root)
            finally:
                self.ctx.grab_release()

    # ---------- 帮助 ----------
    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title("MathLab 帮助")
        win.configure(bg=C["bg"])
        win.geometry("760x640")
        win.transient(self.root)
        t = tk.Text(win, wrap="word", font=(UI, 10), bg=C["panel"], fg=C["ink"],
                    relief="flat", padx=16, pady=14)
        t.pack(fill="both", expand=True, padx=12, pady=12)
        t.insert("1.0", HELP_TEXT)
        t.configure(state="disabled")
        ttk.Button(win, text="知道了", command=win.destroy).pack(pady=(0, 12))


HELP_TEXT = """MathLab 使用说明
════════════════════════════════════════════

【快捷键】
  Enter           计算当前表达式
  ↑ / ↓           在计算器里翻上/下一条历史表达式
  Esc             清空输入框
  Ctrl + 1 ~ 6    切换功能页（计算器 / 绘图 / 方程 / 矩阵 / 统计 / 换算）
  Ctrl + H        显示或隐藏右侧历史面板
  Ctrl + L        光标跳到当前页的输入框
  F5              重新计算当前页
  F1              本帮助
  绘图区：鼠标滚轮缩放、按住左键拖动平移、双击复位

【输入写法】
  · 四则运算      1+2*3   (1+2)*3   10/4   7//2(整除)   7%3(取模)
  · 乘方与根号    2^10   2**10    sqrt(16)    cbrt(-27)    √9
  · 阶乘与百分号  5!     2.5!      200*15%  (即 30)      50%  (即 0.5)
  · 隐式乘法      2pi    3(4+5)    (1+1)(2+2)    2x
  · 常量          pi  π   e   tau   phi   inf
  · 三角函数      sin cos tan + asin acos atan / sinh cosh tanh
                  （右上角可切换「角度 / 弧度」）
  · 对数指数      ln(x)  log(x)即log10  log(8,2)   exp(x)
  · 其他函数      abs sign floor ceil trunc round frac hypot gcd lcm
                  max min sum comb(n,r) perm(n,r) gamma(n) mod(a,b)
  · 绝对值        |x-3|
  · 变量          ans(上次结果)  m(记忆值, 用 M+ 累加 / MC 清零)

【各功能区】
  计算器  ......... 边输入边预览结果；结果显示分数提示与二/八/十六进制
  函数绘图  ....... 最多 3 条曲线叠加，自动 Y 轴或手动范围，可求零点、导出 PNG
  方程求解  ....... ①一元二次/三次(含复数根、顶点、判别式)
                    ②通用方程 f(x)=0 数值求根(支持 sin/ln 等)
                    ③线性方程组：按 2x + y - z = 8 的自然写法逐行输入
  矩阵运算  ....... A±B、A×B、k·A、转置、行列式、逆、秩、RREF、迹、特征值
                    （支持 2×2 / 3×3 / 4×4 特征值）
  统计      ....... 个数/求和/均值/中位数/众数/方差/标准差/四分位，
                    以及一元线性回归 y = a + b·x（含 r 与 R²）
  单位换算  ....... 长度/面积/体积/质量/时间/速度/压强/能量/功率/角度/数据/温度，
                    双击结果表任一行即可设为兑换目标单位

【历史记录】
  所有计算结果自动保存到：
    %LOCALAPPDATA%\\MathLab\\history.json
  支持搜索、★★ 收藏（清空时保留）、右键菜单、导出 CSV / TXT。

【小技巧】
  · 想连算：直接引用 ans，例如  2*ans+1
  · 记忆功能：M+ 把当前输入值累加到 m；输入 m 即可调用
  · 画图前把方程页的「画出来」按一下，会自动跳到绘图页并设好范围
"""


def run():
    root = tk.Tk()
    app = MathLabApp(root)
    root.mainloop()
    return app


if __name__ == "__main__":
    run()
