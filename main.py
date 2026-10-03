# -*- coding: utf-8 -*-
"""MathLab 启动入口

直接运行:  python main.py
打包运行:  MathLab.exe (见 build_exe.bat)
"""
import os
import sys
import ctypes


def _enable_dpi_awareness():
    """高分屏下文字不糊"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _fix_path():
    """源码运行时保证能 import mathlab 包"""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    # 打包后 (PyInstaller) 以 _MEIPASS 为准
    base = getattr(sys, "_MEIPASS", None)
    if base and base not in sys.path:
        sys.path.insert(0, base)


def _selftest(outpath):
    """自检 (打包后也能验证): python main.py --selftest out.json"""
    import json
    import tempfile
    import traceback

    res = {"ok": False, "checks": [], "exe": sys.executable,
           "meipass": bool(getattr(sys, "_MEIPASS", None))}
    try:
        import tkinter as tk
        from mathlab import engine as E
        from mathlab.gui import MathLabApp

        root = tk.Tk()
        root.withdraw()
        app = MathLabApp(root)
        root.update()
        checks = []
        checks.append(("engine_calc",
                       E.Evaluator().evaluate("2^10 + sqrt(16) + 5!") == 1148.0))
        r, _ = E.solve_quadratic(1, -3, 2)
        checks.append(("engine_quadratic", sorted(x[0] for x in r) == [1.0, 2.0]))
        A, b, vars_ = E.parse_linear_equations("2x + y = 5\nx - y = 1")
        kind, sol = E.solve_linear_system(A, b)
        checks.append(("engine_linear", kind == "unique" and abs(sol[0] - 2) < 1e-9))
        checks.append(("engine_matrix", abs(E.Matrix.parse("1 2; 3 4").det() + 2) < 1e-12))
        checks.append(("engine_units",
                       abs(E.convert_unit(1, "长度", "千米 km", "米 m") - 1000) < 1e-9))
        cal = app.tabs[0]
        cal.entry.delete(0, "end")
        cal.entry.insert(0, "1/3")
        cal.calculate()
        checks.append(("gui_calc", cal.result.cget("text") == "0.333333333333"))
        app.tabs[1].redraw()
        png = os.path.join(tempfile.gettempdir(), "mathlab_selftest.png")
        app.tabs[1].plotter.export_png(png, 480, 320)
        checks.append(("gui_plot_export", os.path.exists(png) and os.path.getsize(png) > 3000))
        app.tabs[5].convert()
        checks.append(("gui_units_tab", app.tabs[5].result.cget("text") != ""))
        app.history.add("自检", "1+1", "2")
        checks.append(("history_io", app.history.count() >= 1))
        root.destroy()
        res["checks"] = checks
        res["ok"] = all(c[1] for c in checks)
    except Exception:
        res["error"] = traceback.format_exc()
    try:
        with open(outpath, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return 0 if res.get("ok") else 1


def main():
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) else "mathlab_selftest.json"
        _enable_dpi_awareness()
        _fix_path()
        sys.exit(_selftest(out))

    _enable_dpi_awareness()
    _fix_path()
    import tkinter as tk
    from mathlab.gui import MathLabApp

    root = tk.Tk()
    try:
        dpi = root.winfo_fpixels("1i")
        root.tk.call("tk", "scaling", max(1.0, dpi / 72.0))
    except Exception:
        pass
    MathLabApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
