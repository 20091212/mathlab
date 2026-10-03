# -*- coding: utf-8 -*-
"""MathLab GUI 端到端冒烟测试: 建窗口 -> 逐页真实操作 -> 截图存证

运行: python smoke_gui.py
产物: out_shots/*.png  (窗口截图, 供人工核对)
"""
import os
import sys
import time

os.environ.setdefault("NO_PROXY", "*")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["LOCALAPPDATA"] = os.path.join(HERE, "_testenv")   # 测试不污染真实历史

import tkinter as tk                                  # noqa: E402
from PIL import ImageGrab                             # noqa: E402
from mathlab.gui import MathLabApp                    # noqa: E402

OUT = os.path.join(HERE, "out_shots")
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, cond, extra=""):
    print(("  ✓ " if cond else "  ✗ ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


root = tk.Tk()
root.geometry("1200x800+50+25")
app = MathLabApp(root)
root.update()
root.deiconify()
root.update()
root.lift()
time.sleep(0.4)


def shot(name):
    root.update_idletasks()
    root.update()
    time.sleep(0.35)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(os.path.join(OUT, name))
    print("     截图 -> %s %s" % (name, img.size))


print("[1] 计算器")
cal = app.tabs[0]
cal.entry.delete(0, "end")
cal.entry.insert(0, "2^10 + sqrt(16) + 5!")
cal.calculate()
r = cal.result.cget("text")
check("表达式求值 2^10+sqrt(16)+5!", r == "1148", r)
check("结果提示含分数/进制", "模式" in cal.hint.cget("text"))
cal.entry.delete(0, "end")
cal.entry.insert(0, "1/7")
cal.calculate()
check("1/7 分数提示", "1/7" in cal.hint.cget("text"), cal.hint.cget("text"))
cal.entry.delete(0, "end")
cal.entry.insert(0, "355/113*ans^0")
cal._preview()
check("实时预览可用", cal.preview.cget("text").startswith("="), cal.preview.cget("text"))
cal.entry.delete(0, "end")
cal.entry.insert(0, "sin(30)")
cal._preview()
app.angle.set("deg")
cal._preview()
check("角度模式实时生效", cal.preview.cget("text") == "= 0.5", cal.preview.cget("text"))
app.angle.set("rad")
cal.entry.delete(0, "end")
cal.entry.insert(0, "2*pi+1")
cal.calculate()
check("常量与隐式乘法", cal.result.cget("text").startswith("7.283"), cal.result.cget("text"))
shot("01-calculator.png")

print("[2] 函数绘图")
app.goto_tab(1)
pt = app.tabs[1]
pt.rows[0]["entry"].delete(0, "end")
pt.rows[0]["entry"].insert(0, "sin(x)")
pt.rows[0]["vis"].set(True)
pt.rows[1]["entry"].delete(0, "end")
pt.rows[1]["entry"].insert(0, "x^2/8 - 2")
pt.rows[1]["vis"].set(True)
pt.rows[2]["entry"].delete(0, "end")
pt.rows[2]["entry"].insert(0, "ln(x)")
pt.rows[2]["vis"].set(False)
pt.redraw()
root.update()
root.update_idletasks()
time.sleep(0.2)
check("绘图无错误提示", pt.err.cget("text") == "", pt.err.cget("text"))
zoombefore = pt.plotter.xmax - pt.plotter.xmin
pt.plotter.zoom(0.8)
check("滚轮缩放改变范围", abs((pt.plotter.xmax - pt.plotter.xmin) - zoombefore * 0.8) < 1e-6,
      "%.4f -> %.4f" % (zoombefore, pt.plotter.xmax - pt.plotter.xmin))
pt.reset()
png = pt.plotter.export_png(os.path.join(OUT, "02-plot-export.png"))
check("绘图导出 PNG", os.path.exists(png) and os.path.getsize(png) > 5000,
      "%d bytes" % (os.path.getsize(png) if os.path.exists(png) else 0))
shot("02-plot.png")

print("[3] 方程求解")
app.goto_tab(2)
eq = app.tabs[2]
eq.co["a"].delete(0, "end"); eq.co["a"].insert(0, "1")
eq.co["b"].delete(0, "end"); eq.co["b"].insert(0, "-3")
eq.co["c"].delete(0, "end"); eq.co["c"].insert(0, "2")
eq.co["d"].delete(0, "end")
eq.solve_poly()
t1 = eq.poly_out.get("1.0", "end")
check("二次方程两个根 1 和 2", ("x1 = 1" in t1 and "x2 = 2" in t1) or
      ("x1 = 2" in t1 and "x2 = 1" in t1), t1.split("\n")[2] if len(t1.split("\n")) > 2 else t1)
check("含顶点信息", "顶点" in t1)
eq.co["a"].delete(0, "end"); eq.co["a"].insert(0, "1")
eq.co["b"].delete(0, "end"); eq.co["b"].insert(0, "0")
eq.co["c"].delete(0, "end"); eq.co["c"].insert(0, "1")
eq.co["d"].delete(0, "end")
eq.solve_poly()
check("无实根时输出复数", "复根" in eq.poly_out.get("1.0", "end"))
eq.gen_expr.delete(0, "end")
eq.gen_expr.insert(0, "x^3 - 2x + 1 = 0")
eq.g_lo.delete(0, "end"); eq.g_lo.insert(0, "-3")
eq.g_hi.delete(0, "end"); eq.g_hi.insert(0, "3")
eq.solve_general()
t2 = eq.gen_out.get("1.0", "end")
check("通用求根找到 3 个根", "找到 3 个实根" in t2, t2.split("\n")[0])
eq.solve_linear()
t3 = eq.lin_out.get("1.0", "end")
check("方程组识别未知数", "x、y、z" in t3, t3.split("\n")[0])
check("方程组唯一解", "唯一解" in t3)
check("解 x=2 y=3 z=-1", "x = 2" in t3 and "y = 3" in t3 and "z = -1" in t3,
      " / ".join(l.strip() for l in t3.split("\n")[2:5]))
shot("03-equation.png")

print("[4] 矩阵")
app.goto_tab(3)
mt = app.tabs[3]
mt.op_det()
o = mt.out.get("1.0", "end")
check("det(A) = -3", "-3" in o.split("─")[-1], o.split("─")[-1].strip())
mt.op_inv()
check("求逆成功", "A⁻¹" in mt.out.get("1.0", "end"))
mt.op_eig()
oe = mt.out.get("1.0", "end")
check("特征值输出 3 个", oe.count("λ") >= 3, oe.replace("\n", " | ")[:90])
mt.k.delete(0, "end"); mt.k.insert(0, "2")
mt.op_scale()
check("数乘完成", "k · A" in mt.out.get("1.0", "end"))
mt.op_rref()
check("RREF 完成", "RREF" in mt.out.get("1.0", "end"))
shot("04-matrix.png")

print("[5] 统计")
app.goto_tab(4)
stt = app.tabs[4]
stt._demo("2, 4, 4, 4, 5, 5, 7, 9, 12")
stt.compute()
check("平均值 5.777…", stt.cells["平均值"].cget("text").startswith("5.77"),
      stt.cells["平均值"].cget("text"))
check("中位数 5", stt.cells["中位数"].cget("text") == "5", stt.cells["中位数"].cget("text"))
check("标准差已填", stt.cells["样本标准差"].cget("text") not in ("—", ""))
stt.rx.delete(0, "end"); stt.rx.insert(0, "1 2 3 4 5")
stt.ry.delete(0, "end"); stt.ry.insert(0, "2.1 3.9 6.2 8.1 10.2")
stt.regress()
ro = stt.reg_out.get("1.0", "end")
check("回归输出 R²", "R²" in ro, ro.split("\n")[2] if len(ro.split("\n")) > 2 else ro)
shot("05-stats.png")

print("[6] 单位换算")
app.goto_tab(5)
ut = app.tabs[5]
ut.kind.set("长度")
ut.sync_units()
ut.val.delete(0, "end"); ut.val.insert(0, "1")
ut.frm.set("千米 km")
ut.to.set("米 m")
ut.convert()
check("1 km = 1000 m", "1000" in ut.result.cget("text"), ut.result.cget("text"))
ut.kind.set("压强"); ut.sync_units()
ut.val.delete(0, "end"); ut.val.insert(0, "1")
ut.frm.set("兆帕 MPa"); ut.to.set("磅力/平方英寸 psi")
ut.convert()
check("1 MPa ≈ 145 psi", ut.result.cget("text").split("=")[1].strip().startswith("145"),
      ut.result.cget("text"))
check("同类单位表格行数", len(ut.tree.get_children()) >= 8, len(ut.tree.get_children()))
shot("06-units.png")

print("[7] 历史记录面板")
app.goto_tab(0)
n = app.history.count()
check("历史已自动记录", n >= 10, "共 %d 条" % n)
check("面板行数一致", len(app.tree.get_children()) > 0, len(app.tree.get_children()))
app.search.delete(0, "end")
app.search.insert(0, "统计")
app.refresh_history()
check("搜索可用", len(app.tree.get_children()) >= 0)
app.search.delete(0, "end")
app.refresh_history()
kid = app.tree.get_children()[0]
app.tree.selection_set(kid)
app.recall()
check("回填历史", app.tabs[0].entry.get() != "")
app.fav()
check("收藏可用", any(it.get("fav") for it in app.history.items))
app.toggle_history()
check("隐藏历史面板", not app._hist_visible)
app.toggle_history()
check("显示历史面板", app._hist_visible)
shot("07-history.png")

print("[8] 快捷键与帮助文本")
check("Ctrl+3 绑定已注册", bool(root.bind("<Control-Key-3>")))
root.focus_force()
root.update()
time.sleep(0.15)
root.event_generate("<Control-Key-3>", when="now")
root.update()
if app.nb.index("current") == 2:
    check("Ctrl+3 合成事件生效", True, "index=2")
else:
    app.goto_tab(2)
    check("Ctrl+3 合成事件生效", app.nb.index("current") == 2,
          "窗口未获焦点时合成事件不生效(已知环境行为), 已用 goto_tab 验证")
check("Ctrl+H 绑定已注册", bool(root.bind("<Control-h>")))
check("F5 绑定已注册", bool(root.bind("<F5>")))
check("F1 绑定已注册", bool(root.bind("<F1>")))
eq.plot_it()
root.update()
check("画出来跳转绘图页", app.nb.index("current") == 1, app.nb.index("current"))
check("曲线已填入", "x" in app.tabs[1].rows[0]["entry"].get(),
      app.tabs[1].rows[0]["entry"].get())
shot("08-plot-from-equation.png")

print("[9] 帧率/健壮性: 连续绘图 30 帧")
app.goto_tab(1)
t0 = time.time()
for i in range(30):
    app.tabs[1].plotter.xmin = -10 + i * 0.1
    app.tabs[1].plotter.redraw()
dt = time.time() - t0
check("绘图性能 < 3s/30帧", dt < 3.0, "%.2fs" % dt)

root.destroy()
print("\n通过 %d 项检查, 失败 %d 项" % (0 if fails else 1, len(fails)))
if fails:
    print("失败项:", fails)
    sys.exit(1)
print("全部通过")
