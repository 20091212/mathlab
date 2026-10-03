# -*- coding: utf-8 -*-
"""MathLab 内核自测 (无 GUI, 可直接运行)"""
import math
import sys

sys.path.insert(0, ".")
from mathlab.engine import *          # noqa
from mathlab.engine import Evaluator, CalcError, Matrix

ok = fail = 0


def chk(name, got, want, tol=1e-9):
    global ok, fail
    good = False
    if isinstance(want, str):
        good = (got == want)
    elif isinstance(want, (int, float)):
        try:
            good = abs(float(got) - float(want)) <= tol * max(1.0, abs(float(want)))
        except Exception:
            good = False
    else:
        good = (got == want)
    if good:
        ok += 1
    else:
        fail += 1
        print("  ✗ %-34s got=%r want=%r" % (name, got, want))


def chkerr(name, expr):
    global ok, fail
    try:
        (expr() if callable(expr) else ev.evaluate(expr))
        fail += 1
        print("  ✗ %-34s 期望报错但没有" % name)
    except CalcError:
        ok += 1
    except Exception as e:
        fail += 1
        print("  ✗ %-34s 报错类型不对: %r" % (name, e))


ev = Evaluator()

print("[1] 基本运算与优先级")
chk("1+2*3", ev.evaluate("1+2*3"), 7)
chk("(1+2)*3", ev.evaluate("(1+2)*3"), 9)
chk("-2^2", ev.evaluate("-2^2"), -4)
chk("2^3^2", ev.evaluate("2^3^2"), 512)
chk("10/4", ev.evaluate("10/4"), 2.5)
chk("7//2", ev.evaluate("7//2"), 3)
chk("7%3", ev.evaluate("7%3"), 1)
chk("200*15%", ev.evaluate("200*15%"), 30)
chk("50%", ev.evaluate("50%"), 0.5)
chk("5!", ev.evaluate("5!"), 120)
chk("2.5! (gamma)", ev.evaluate("2.5!"), math.gamma(3.5), 1e-9)
chk("隐式乘法 2x", ev.evaluate("2pi"), 2 * math.pi)
chk("隐式 3(4+5)", ev.evaluate("3(4+5)"), 27)
chk("隐式 (1+1)(2+2)", ev.evaluate("(1+1)(2+2)"), 8)
chk("3sqrt(16)", ev.evaluate("3sqrt(16)"), 12)
chk("1.5e3", ev.evaluate("1.5e3"), 1500)
chk("|-7|", ev.evaluate("|-7|"), 7)
chk("1e-3*2", ev.evaluate("1e-3*2"), 0.002)

print("[2] 函数 / 常量 / 角度模式")
chk("sqrt(2)", ev.evaluate("sqrt(2)"), 2 ** 0.5)
chk("log(1000)", ev.evaluate("log(1000)"), 3)
chk("log(8,2)", ev.evaluate("log(8,2)"), 3)
chk("ln(e)", ev.evaluate("ln(e)"), 1)
chk("sin(pi/6) rad", ev.evaluate("sin(pi/6)"), 0.5, 1e-12)
chk("abs(-3)+floor(2.9)", ev.evaluate("abs(-3)+floor(2.9)"), 5)
chk("round(3.14159,3)", ev.evaluate("round(3.14159,3)"), 3.142, 1e-9)
chk("gcd(12,18)", ev.evaluate("gcd(12,18)"), 6)
chk("comb(5,2)", ev.evaluate("comb(5,2)"), 10)
chk("max(3,9,4)", ev.evaluate("max(3,9,4)"), 9)
chk("cbrt(-27)", ev.evaluate("cbrt(-27)"), -3)
chk("hypot(3,4)", ev.evaluate("hypot(3,4)"), 5)
ev_deg = Evaluator(angle_mode="deg")
chk("deg: sin(30)", ev_deg.evaluate("sin(30)"), 0.5, 1e-12)
chk("deg: asin(0.5)", ev_deg.evaluate("asin(0.5)"), 30, 1e-9)
chk("deg: atan2(1,1)", ev_deg.evaluate("atan2(1,1)"), 45, 1e-9)
chk("全角输入", Evaluator().evaluate("（1＋2）×3"), 9)
chk("π 全角", Evaluator().evaluate("2π"), 2 * math.pi)
chk("√9", Evaluator().evaluate("√9"), 3)
chk("ans 变量", Evaluator(ans=42).evaluate("ans/2"), 21)
chk("m 变量", Evaluator(memory=5).evaluate("m+1"), 6)
chk("变量 x 传入", Evaluator(variables={"x": 3}).evaluate("x^2+1"), 10)

print("[3] 错误处理")
chkerr("除零", "1/0")
chkerr("未知函数", "foo(3)")
chkerr("未知变量", "y+1")
chkerr("括号不匹配", "(1+2")
chkerr("多余内容", "1+2 3 4 5 +")
chkerr("非法字符", "1+@")
chkerr("空表达式", "   ")
chkerr("三角定义域", "asin(5)")
chkerr("负log", "ln(-1)")

print("[4] 数字格式化")
chk("整数", format_number(6.0), "6")
chk("循环小数", format_number(1 / 3), "0.333333333333")
chk("大数科学计数", format_number(1.234e20), "1.234×10^20")
chk("√2 分数提示", fraction_hint(2 ** 0.5), "√2")
chk("1/3 分数提示", fraction_hint(1 / 3), "1/3")
chk("π/2", fraction_hint(math.pi / 2), "π/2")
chk("整数等价无提示", fraction_hint(4.0), "")
chk("复数格式化", format_complex(complex(0, 1)), "i")

print("[5] 一元二次 / 三次 / 多项式")
r, kind = solve_quadratic(1, -3, 2)
chk("x²-3x+2 根数", len(r), 2)
chk("x²-3x+2 根1", min(x[0] for x in r), 1.0)
chk("x²-3x+2 根2", max(x[0] for x in r), 2.0)
r, kind = solve_quadratic(1, 2, 5)
chk("复根个数", len(r), 2)
chk("复根实部", r[0][0].real, -1.0)
chk("复根虚部", abs(r[0][0].imag), 2.0)
r, kind = solve_quadratic(0, 2, -6)
chk("退化为一元一次", r[0][0], 3.0)
r3 = poly_roots([1, 0, -1, 0])       # x³ - x = 0 -> -1, 0, 1
chk("x³-x 根数", len(r3), 3)
chk("x³-x 根和", sum(z.real for z in r3), 0.0, 1e-7)
r3b = poly_roots([1, -6, 11, -6])    # (x-1)(x-2)(x-3)
chk("三次根乘积", abs(r3b[0].real * r3b[1].real * r3b[2].real), 6.0, 1e-6)

print("[6] 通用数值求根")
f = Evaluator().scalar_function("x^3-2x+1")
roots = find_roots(f, -3, 3)
chk("x³-2x+1 根数", len(roots), 3)
chk("根含 1", min(abs(r - 1) for r in roots) < 1e-6, True)
chk("根含 0.618", min(abs(r - 0.6180339887) for r in roots) < 1e-6, True)
g = Evaluator().scalar_function("sin(x)-0.5")
rs = find_roots(g, 0, 3.15)
chk("sin(x)=0.5 首根", round(rs[0], 6) if rs else None, round(math.pi / 6, 6))

print("[7] 线性方程组")
kind, sol = solve_linear_system([[2, 1], [1, -1]], [5, 1])
chk("唯一解", kind, "unique")
chk("x=2", sol[0], 2.0)
chk("y=1", sol[1], 1.0)
kind, _ = solve_linear_system([[1, 1], [2, 2]], [3, 7])
chk("无解", kind, "none")
kind2, _ = solve_linear_system([[1, 1], [2, 2]], [3, 6])
chk("无穷多解", kind2, "infinite")
kind3, _ = solve_linear_system([[1, 1], [1, 1]], [3, 3])
chk("重复方程", kind3, "infinite")
kind, sol = solve_linear_system([[2, 1, -1], [-3, -1, 2], [-2, 1, 2]], [8, -11, -3])
chk("三元唯一", kind, "unique")
chk("三元 x", sol[0], 2.0, 1e-9)
chk("三元 y", sol[1], 3.0, 1e-9)
chk("三元 z", sol[2], -1.0, 1e-9)

print("[8] 矩阵")
A = Matrix.parse("1 2; 3 4")
B = Matrix.parse("5 6; 7 8")
chk("A+B 行列", (A.add(B)).rows[0][0], 6)
chk("A*B", A.mul(B).rows[0][1], 22)
chk("det A", A.det(), -2.0)
chk("trace", A.trace(), 5.0)
chk("transpose", A.transpose().rows[0][1], 3)
chk("inv A", A.inv().rows[0][0], -2.0, 1e-9)
chk("A*A⁻¹=单位阵", A.mul(A.inv()).rows[0][0], 1.0, 1e-9)
chk("rank", Matrix.parse("1 2; 2 4").rank(), 1)
chk("rref", Matrix.parse("1 2; 3 4").rref()[0].rows[1][0], 0.0, 1e-12)
ev2 = Matrix.parse("2 1; 1 2").eigen()
chk("2x2 特征值", sorted(round(z.real, 6) for z in ev2), [1.0, 3.0])
ev3 = Matrix.parse("2 0 0; 0 3 0; 0 0 4").eigen()
chk("3x3 特征值", sorted(round(z.real, 6) for z in ev3), [2.0, 3.0, 4.0])
chkerr("非方阵行列式", lambda: Matrix.parse("1 2 3; 4 5 6").det())
chkerr("不可逆", lambda: Matrix.parse("1 2; 2 4").inv())
chkerr("维度不匹配乘法", lambda: Matrix.parse("1 2 3").mul(Matrix.parse("1 2 3")))

print("[9] 统计与回归")
vals = parse_numbers("2, 4, 4, 4, 5, 5, 7, 9")
d = dict(stats_summary(vals))
chk("均值", float(d["平均值"]), 5.0)
chk("中位数", float(d["中位数"]), 4.5)
chk("众数", d["众数"], "4")
chk("总体标准差", float(d["总体标准差"]), 2.0)
chk("样本标准差", float(d["样本标准差"]), 2.1380899353, 1e-8)
chk("Q1", float(d["下四分位 Q1"]), 4.0)
chk("四分位距", float(d["四分位距"]), 1.5)
reg = linear_regression([1, 2, 3, 4], [2, 4, 6, 8])
chk("斜率", reg["slope"], 2.0)
chk("截距", reg["intercept"], 0.0)
chk("r²", reg["r2"], 1.0)
reg2 = linear_regression([1, 2, 3], [2, 2.5, 3.2])
chk("r 介于0-1", 0 < reg2["r"] <= 1, True)
chkerr("长度不等", lambda: linear_regression([1, 2], [1]))

print("[10] 单位换算")
chk("1km=1000m", convert_unit(1, "长度", "千米 km", "米 m"), 1000)
chk("1in=2.54cm", convert_unit(1, "长度", "英寸 in", "厘米 cm"), 2.54)
chk("1公顷=15亩", convert_unit(1, "面积", "公顷 ha", "亩"), 15.0, 1e-6)
chk("1吨=1000kg", convert_unit(1, "质量", "吨 t", "千克 kg"), 1000)
chk("100km/h->m/s", convert_unit(100, "速度", "千米/小时 km/h", "米/秒 m/s"), 27.7777778, 1e-6)
chk("1MPa=1000kPa", convert_unit(1, "压强", "兆帕 MPa", "千帕 kPa"), 1000)
chk("14.5psi->MPa", convert_unit(14.5, "压强", "磅力/平方英寸 psi", "兆帕 MPa"), 0.09997, 1e-4)
chk("0°C=32°F", convert_unit(0, "温度", "摄氏度 °C", "华氏度 °F"), 32)
chk("100°C=212°F", convert_unit(100, "温度", "摄氏度 °C", "华氏度 °F"), 212)
chk("0°C=273.15K", convert_unit(0, "温度", "摄氏度 °C", "开尔文 K"), 273.15)
chk("98.6°F=37°C", convert_unit(98.6, "温度", "华氏度 °F", "摄氏度 °C"), 37, 1e-6)
chk("180°=π rad", convert_unit(180, "角度", "度 °", "弧度 rad"), math.pi, 1e-9)
chk("类目分组", len(unit_list("长度")) > 5, True)

print("\n通过 %d 项, 失败 %d 项" % (ok, fail))
sys.exit(1 if fail else 0)
