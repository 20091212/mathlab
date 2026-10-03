# -*- coding: utf-8 -*-
"""MathLab 数学计算内核

模块内容:
  * 表达式解析求值 (自写分词 + 递归下降, 不使用 eval)
  * 角度/弧度、百分号、阶乘、隐式乘法、ANS/M 变量
  * 方程求解 (二次/三次解析解, 通用数值求根, 线性方程组)
  * 矩阵运算 (加减乘、行列式、逆、转置、秩、RREF、特征值)
  * 统计 (均值/中位数/方差/标准差/回归)
  * 单位换算
"""
from __future__ import annotations

import math
from fractions import Fraction

__all__ = ["CalcError", "Evaluator", "format_number", "format_complex", "fraction_hint",
           "int_bases", "solve_quadratic", "solve_cubic", "find_roots", "poly_roots",
           "solve_linear_system", "parse_linear_equations", "Matrix", "stats_summary",
           "linear_regression",
           "parse_numbers", "UNITS", "unit_list", "convert_unit"]


class CalcError(Exception):
    """计算错误 (用户可读的中文提示)"""


# ==========================================================================
# 输入规范化
# ==========================================================================
_FULLWIDTH = {
    "（": "(", "）": ")", "，": ",", "＋": "+", "－": "-", "−": "-",
    "×": "*", "＊": "*", "÷": "/", "／": "/", "％": "%", "！": "!",
    "＝": "=", "＾": "^", "。": ".", "　": " ", "；": ";", "：": ":",
    "，": ",", "【": "[", "】": "]",
}
_SUPERS = {"²": "^2", "³": "^3", "⁴": "^4", "⁻": "^-"}


def normalize(text: str) -> str:
    out = []
    for ch in text:
        if ch in _FULLWIDTH:
            out.append(_FULLWIDTH[ch])
        elif ch in _SUPERS:
            out.append(_SUPERS[ch])
        else:
            out.append(ch)
    s = "".join(out)
    s = s.replace("√", "sqrt")          # √9 -> sqrt9 -> sqrt(9) 由隐式乘法兜不住, 见下
    s = s.replace("π", " pi ").replace("∞", " inf ")
    s = s.replace("√", "sqrt")
    return s


def _fix_bare_sqrt(s: str) -> str:
    """把 sqrt9 / sqrt 9 之类补成 sqrt(9) —— 仅处理紧跟数字的裸 sqrt"""
    res = []
    i = 0
    n = len(s)
    while i < n:
        if s.startswith("sqrt", i):
            j = i + 4
            k = j
            while k < n and s[k] == " ":
                k += 1
            if k < n and (s[k].isdigit() or s[k] == "."):
                m = k
                while m < n and (s[m].isdigit() or s[m] == "."):
                    m += 1
                res.append("sqrt(" + s[k:m] + ")")
                i = m
                continue
        res.append(s[i])
        i += 1
    return "".join(res)


# ==========================================================================
# 分词
# ==========================================================================
_OPS = set("+-*/^%!(),;=|<>")


def tokenize(s: str):
    s = _fix_bare_sqrt(normalize(s))
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            seen_dot = False
            seen_exp = False
            while j < n:
                d = s[j]
                if d.isdigit():
                    j += 1
                elif d == "." and not seen_dot and not seen_exp:
                    seen_dot = True
                    j += 1
                elif d in "eE" and not seen_exp and j + 1 < n and (
                        s[j + 1].isdigit() or (s[j + 1] in "+-" and j + 2 < n and s[j + 2].isdigit())):
                    seen_exp = True
                    j += 2 if s[j + 1] in "+-" else 1
                else:
                    break
            txt = s[i:j]
            try:
                val = float(txt)
            except ValueError:
                raise CalcError("数字格式错误: %s" % txt)
            toks.append(("num", val))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("id", s[i:j].lower()))
            i = j
            continue
        if c in _OPS:
            # 双字符运算符
            if c in "/*" and i + 1 < n and s[i + 1] == c:
                toks.append(("op", c + c))
                i += 2
                continue
            toks.append(("op", c))
            i += 1
            continue
        raise CalcError("无法识别的字符: %s" % c)
    if not toks:
        raise CalcError("表达式为空")
    return toks


# ==========================================================================
# 函数库 / 常量
# ==========================================================================
def _fact(x):
    if x < 0 or abs(x - round(x)) > 1e-9:
        return math.gamma(x + 1)          # 非整数走 gamma
    return float(math.factorial(int(round(x))))


def _comb(n, r):
    n, r = int(round(n)), int(round(r))
    if r < 0 or n < 0 or r > n:
        raise CalcError("组合数参数不合法")
    return float(math.comb(n, r))


def _perm(n, r):
    n, r = int(round(n)), int(round(r))
    if r < 0 or n < 0 or r > n:
        raise CalcError("排列数参数不合法")
    return float(math.perm(n, r))


def _safe_div(a, b):
    if b == 0:
        raise CalcError("除以零")
    return a / b


class Evaluator:
    """表达式求值器. angle_mode: 'rad' | 'deg'"""

    def __init__(self, angle_mode="rad", ans=0.0, memory=0.0, variables=None):
        self.angle_mode = angle_mode
        self.variables = {"ans": ans, "m": memory}
        if variables:
            self.variables.update(variables)
        self.funcs = self._build_funcs()

    # ---- 三角函数 (按角度模式包装) ----
    def _build_funcs(self):
        def to_rad(x):
            return math.radians(x) if self.angle_mode == "deg" else x

        def from_rad(x):
            return math.degrees(x) if self.angle_mode == "deg" else x

        def wrap(f):
            return lambda *a: f(*[to_rad(v) for v in a])
        return {
            "sin": wrap(math.sin), "cos": wrap(math.cos), "tan": wrap(math.tan),
            "sec": wrap(lambda x: 1 / math.cos(x)), "csc": wrap(lambda x: 1 / math.sin(x)),
            "cot": wrap(lambda x: 1 / math.tan(x)),
            "asin": lambda x: from_rad(math.asin(x)),
            "acos": lambda x: from_rad(math.acos(x)),
            "atan": lambda x: from_rad(math.atan(x)),
            "atan2": lambda y, x: from_rad(math.atan2(y, x)),
            "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
            "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
            "ln": math.log, "log": lambda x, b=10.0: math.log(x, b),
            "lg": math.log10, "log10": math.log10, "log2": math.log2,
            "exp": math.exp, "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
            "root": lambda n, x: math.copysign(abs(x) ** (1.0 / n), x) if n % 2 else abs(x) ** (1.0 / n),
            "abs": abs, "sign": lambda x: (x > 0) - (x < 0), "floor": math.floor,
            "ceil": math.ceil, "trunc": math.trunc, "frac": lambda x: x - math.trunc(x),
            "round": lambda x, n=0: round(x, int(round(n))),
            "fact": _fact, "gamma": math.gamma, "lgamma": math.lgamma,
            "hypot": math.hypot, "atanh2": math.atanh,
            "pow": lambda a, b: a ** b, "mod": lambda a, b: math.fmod(a, b),
            "gcd": lambda a, b: float(math.gcd(int(round(a)), int(round(b)))),
            "lcm": lambda a, b: float(math.lcm(int(round(a)), int(round(b)))),
            "perm": _perm, "comb": _comb, "ncr": _comb, "npr": _perm,
            "min": min, "max": max, "sum": lambda *a: float(sum(a)),
            "deg": math.degrees, "rad": math.radians,
        }

    consts = {"pi": math.pi, "e": math.e, "tau": math.tau, "phi": (1 + 5 ** 0.5) / 2,
              "inf": math.inf, "nan": math.nan}

    # ---- 解析 ----
    def parse(self, expr: str):
        self.toks = tokenize(expr)
        self.pos = 0
        node = self._expr()
        if self.pos < len(self.toks):
            t = self.toks[self.pos]
            raise CalcError("表达式有多余内容: %s" % (t[1],))
        return node

    def _peek(self, k=0):
        i = self.pos + k
        return self.toks[i] if i < len(self.toks) else (None, None)

    def _is_op(self, ch, k=0):
        t = self._peek(k)
        return t[0] == "op" and t[1] == ch

    def _eat(self, ch):
        if self._is_op(ch):
            self.pos += 1
            return True
        return False

    def _expr(self):
        node = self._term()
        while True:
            if self._eat("+"):
                node = ("add", node, self._term())
            elif self._eat("-"):
                node = ("sub", node, self._term())
            else:
                return node

    def _starts_primary(self, k=0):
        t = self._peek(k)
        if t[0] == "num":
            return True
        if t[0] == "id":
            return True
        if t[0] == "op" and t[1] in "(":
            return True
        return False

    def _term(self):
        node = self._unary()
        while True:
            if self._eat("*"):
                node = ("mul", node, self._unary())
            elif self._eat("/"):
                node = ("div", node, self._unary())
            elif self._is_op("//"):
                self.pos += 1
                node = ("floordiv", node, self._unary())
            elif self._is_op("%"):
                # a % b -> 取模 (后面还有操作数); a% 结尾 -> 百分号
                if self._starts_primary(1):
                    self.pos += 1
                    node = ("mod", node, self._unary())
                else:
                    self.pos += 1
                    node = ("div", node, ("num", 100.0))
            elif self._starts_primary():        # 隐式乘法: 2x, 3(4+5), 2pi
                node = ("mul", node, self._unary())
            else:
                return node

    def _unary(self):
        if self._eat("-"):
            return ("neg", self._unary())
        if self._eat("+"):
            return self._unary()
        return self._power()

    def _power(self):
        base = self._postfix()
        if self._eat("^"):
            return ("pow", base, self._unary())     # 右结合, -2^2 = -4
        if self._eat("**"):
            return ("pow", base, self._unary())
        return base

    def _postfix(self):
        node = self._primary()
        while self._is_op("!"):
            self.pos += 1
            node = ("fact", node)
        return node

    def _primary(self):
        t = self._peek()
        kind, val = t
        if kind == "num":
            self.pos += 1
            return ("num", val)
        if kind == "op" and val == "(":
            self.pos += 1
            node = self._expr()
            if not self._eat(")"):
                raise CalcError("缺少右括号")
            return node
        if kind == "op" and val == "|":
            self.pos += 1
            node = self._expr()
            if not self._eat("|"):
                raise CalcError("缺少 |")
            return ("call", "abs", [node])
        if kind == "id":
            name = val
            self.pos += 1
            if self._is_op("(") and name in self.funcs:
                self.pos += 1
                args = []
                if not self._is_op(")"):
                    args.append(self._expr())
                    while self._eat(","):
                        args.append(self._expr())
                if not self._eat(")"):
                    raise CalcError("函数 %s 缺少右括号" % name)
                return ("call", name, args)
            if self._is_op("("):
                # 未知函数名 + 括号 -> 提示
                raise CalcError("未知函数: %s" % name)
            if name in self.consts:
                return ("num", self.consts[name])
            if name in self.variables:
                return ("var", name)
            raise CalcError("未知变量或函数: %s" % name)
        raise CalcError("表达式不完整")

    # ---- 编译为闭包 (绘图时高频调用) ----
    def compile(self, expr: str):
        node = self.parse(expr)
        return self._compile(node)

    def _compile(self, n):
        op = n[0]
        if op == "num":
            v = n[1]
            return lambda env: v
        if op == "var":
            name = n[1]

            def getter(env, name=name, self=self):
                if name in env:
                    return env[name]
                if name in self.variables:
                    return self.variables[name]
                return _MISS(name)
            return getter
        if op == "add":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: a(env) + b(env)
        if op == "sub":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: a(env) - b(env)
        if op == "mul":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: a(env) * b(env)
        if op == "div":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: _safe_div(a(env), b(env))
        if op == "floordiv":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: float(a(env) // b(env))
        if op == "mod":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: math.fmod(a(env), b(env))
        if op == "pow":
            a, b = self._compile(n[1]), self._compile(n[2])
            return lambda env: a(env) ** b(env)
        if op == "neg":
            a = self._compile(n[1])
            return lambda env: -a(env)
        if op == "fact":
            a = self._compile(n[1])
            return lambda env: _fact(a(env))
        if op == "call":
            name, args = n[1], [self._compile(x) for x in n[2]]
            f = self.funcs[name]
            if len(args) == 1:
                a0 = args[0]
                return lambda env: float(f(a0(env)))
            return lambda env: float(f(*[a(env) for a in args]))
        raise CalcError("内部错误: %s" % op)

    # ---- 求值 ----
    def scalar_function(self, expr: str, var="x"):
        """把表达式编译成 f(标量)->标量 的普通函数 (绘图/求根用)"""
        if var not in self.variables:
            self.variables[var] = 0.0
        fn = self.compile(expr)

        def g(t):
            v = fn({var: t})
            return float(v)

        return g

    def evaluate(self, expr: str, env=None):
        f = self.compile(expr)
        e = dict(self.variables)
        if env:
            e.update(env)
        try:
            v = f(e)
        except CalcError:
            raise
        except ZeroDivisionError:
            raise CalcError("除以零")
        except ValueError as ex:
            raise CalcError("定义域错误: %s" % ex)
        except OverflowError:
            raise CalcError("数值溢出")
        except TypeError as ex:
            raise CalcError("函数参数错误: %s" % ex)
        v = float(v)
        if math.isnan(v):
            raise CalcError("结果无定义 (NaN)")
        return v


def _MISS(name):
    if name == "x":
        return 0.0
    raise CalcError("未知变量: %s" % name)


# ==========================================================================
# 数字格式化
# ==========================================================================
def format_number(v: float, sig: int = 12) -> str:
    if v is None:
        return ""
    if isinstance(v, complex):
        return format_complex(v, sig)
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    if math.isnan(v):
        return "无定义"
    if v == int(v) and abs(v) < 1e16:
        return str(int(v))
    s = "%.*g" % (sig, v)
    low = s.lower()
    if "e" in low:
        mant, _, exp = low.partition("e")
        try:
            e = int(exp)
        except ValueError:
            return s
        return "%s×10^%d" % (mant, e)
    return s


def _trim_float(s: str, sig: int) -> str:
    if "e" in s or "E" in s:
        return s
    if "." in s:
        head, tail = s.split(".")
        keep = max(0, sig - len(head.lstrip("-")))
        tail = tail[:keep].rstrip("0")
        s = head + ("." + tail if tail else "")
    return s


def format_complex(z: complex, sig: int = 10) -> str:
    re, im = z.real, z.imag
    rp = format_number(re, sig) if abs(re) > 1e-12 else ""
    ip = format_number(abs(im), sig)
    if abs(im) < 1e-12:
        return format_number(re, sig)
    if abs(re) < 1e-12:
        return ("-i" if im < 0 else "i") + ("·" + ip if ip != "1" else "")
    return "%s %s %s" % (rp, "-" if im < 0 else "+", "i" + ("·" + ip if ip != "1" else ""))


def fraction_hint(v: float, max_den: int = 4000) -> str:
    """若是简单的有理数/常用无理数, 给出更"漂亮"的等价写法"""
    if not math.isfinite(v) or v == int(v) or abs(v) > 1e9:
        return ""
    fr = Fraction(v).limit_denominator(max_den)
    if fr.denominator != 1 and abs(float(fr) - v) < 1e-9 * max(1.0, abs(v)):
        return "%d/%d" % (fr.numerator, fr.denominator)
    specials = [("√2", 2 ** 0.5), ("√3", 3 ** 0.5), ("√5", 5 ** 0.5), ("π", math.pi),
                ("e", math.e), ("π/2", math.pi / 2), ("π/3", math.pi / 3),
                ("π/4", math.pi / 4), ("π/6", math.pi / 6), ("2π", 2 * math.pi)]
    for name, val in specials:
        for sign in (1, -1):
            for k in range(1, 13):
                if abs(sign * k * val - v) < 1e-10 * max(1.0, abs(v)):
                    return ("-" if sign < 0 else "") + (("%d" % k if k > 1 else "") + name)
    return ""


def int_bases(v: float) -> str:
    if not math.isfinite(v) or v != int(v) or abs(v) > 2 ** 63:
        return ""
    i = int(v)
    return "0x%X  0b%s  0o%o" % (i, format(i, "b"), i)


# ==========================================================================
# 方程求解
# ==========================================================================
def solve_quadratic(a: float, b: float, c: float):
    """ax²+bx+c=0 -> (roots, kind)"""
    if abs(a) < 1e-15:
        if abs(b) < 1e-15:
            raise CalcError("a 和 b 不能同时为 0")
        return [(-c / b, 1.0)], "一元一次"
    d = b * b - 4 * a * c
    if d > 1e-12:
        s = math.sqrt(d)
        return [((-b + s) / (2 * a), 1.0), ((-b - s) / (2 * a), 1.0)], "两个不相等的实根"
    if abs(d) <= 1e-12:
        return [(-b / (2 * a), 1.0)], "两个相等的实根 (重根)"
    s = math.sqrt(-d)
    re, im = -b / (2 * a), s / (2 * a)
    return [(complex(re, im), 1.0), (complex(re, -im), 1.0)], "一对共轭复根"


def poly_roots(coeffs):
    """用 Durand-Kerner 求任意次多项式在复数域的全部根 (coeffs 从高次到低次)"""
    c = [complex(x) for x in coeffs]
    while c and abs(c[0]) < 1e-14:
        c.pop(0)
    if len(c) <= 1:
        return []
    if len(c) == 2:
        return [-c[1] / c[0]]
    n = len(c) - 1
    lead = c[0]
    a = [x / lead for x in c]

    def poly(z):
        r = 0j
        for co in a:
            r = r * z + co
        return r

    radius = 1 + max(abs(x) for x in a[1:]) if len(a) > 1 else 1.0
    seeds = [complex(0.4, 0.9) ** k * (radius * 0.6) for k in range(n)]
    roots = seeds[:]
    for _ in range(600):
        maxdelta = 0.0
        for i in range(n):
            num = poly(roots[i])
            den = 1.0 + 0j
            for j in range(n):
                if i != j:
                    den *= (roots[i] - roots[j])
            if abs(den) < 1e-300:
                den = 1e-300
            delta = num / den
            roots[i] -= delta
            maxdelta = max(maxdelta, abs(delta))
        if maxdelta < 1e-14:
            break
    out = []
    for z in roots:
        if abs(z.imag) < 1e-8:
            z = complex(z.real, 0.0)
        if abs(z.real) < 1e-10:
            z = complex(0.0, z.imag)
        out.append(z)
    out.sort(key=lambda z: (round(z.real, 8), round(z.imag, 8)))
    return out


def solve_cubic(a, b, c, d):
    if abs(a) < 1e-15:
        return solve_quadratic(b, c, d)
    roots = poly_roots([a, b, c, d])
    return [(z, 1.0) for z in roots], "三次方程 (%d 个根)" % len(roots)


def find_roots(fcall, lo=-20.0, hi=20.0, samples=20000):
    """通用数值求根: 扫描符号变化 + 二分细化, 另用牛顿法补切根"""
    if hi <= lo:
        raise CalcError("区间不合法")
    step = (hi - lo) / samples
    roots = []
    prev_x = lo
    prev_y = _tryf(fcall, lo)
    for i in range(1, samples + 1):
        x = lo + i * step
        y = _tryf(fcall, x)
        if y is None:
            prev_x, prev_y = x, y
            continue
        if prev_y is not None:
            if prev_y == 0.0:
                roots.append(prev_x)
            elif y == 0.0:
                roots.append(x)
            elif prev_y * y < 0:
                r = _bisect(fcall, prev_x, x)
                if r is not None:
                    roots.append(r)
        prev_x, prev_y = x, y
    # 牛顿法补充 (处理相切/偶数重根)
    for x0 in [lo + (hi - lo) * k / 40.0 for k in range(1, 40)]:
        r = _newton(fcall, x0)
        if r is not None and lo - 1e-6 <= r <= hi + 1e-6:
            roots.append(r)
    uniq = []
    for r in sorted(roots):
        if 0.0 <= (r - lo) or abs(r - lo) < 1e-9:
            if not uniq or abs(r - uniq[-1]) > max(1e-7, 1e-6 * max(1.0, abs(r))):
                uniq.append(r)
    return uniq


def _tryf(f, x):
    try:
        v = f(x)
        if v is None or math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _bisect(f, a, b, tol=1e-13):
    fa, fb = _tryf(f, a), _tryf(f, b)
    if fa is None or fb is None:
        return None
    for _ in range(200):
        m = (a + b) / 2.0
        fm = _tryf(f, m)
        if fm is None:
            return None
        if abs(fm) < 1e-14 or (b - a) < tol * max(1.0, abs(m)):
            return m
        if fa * fm < 0:
            b, fb = m, fm
        else:
            a, fa = m, fm
    return (a + b) / 2.0


def _newton(f, x0, tol=1e-13, iters=80):
    x = x0
    for _ in range(iters):
        y = _tryf(f, x)
        if y is None:
            return None
        if abs(y) < 1e-13:
            return x
        h = 1e-6 * max(1.0, abs(x))
        y1, y2 = _tryf(f, x + h), _tryf(f, x - h)
        if y1 is None or y2 is None:
            return None
        d = (y1 - y2) / (2 * h)
        if abs(d) < 1e-15:
            return None
        nx = x - y / d
        if not math.isfinite(nx):
            return None
        if abs(nx - x) < tol * max(1.0, abs(nx)):
            return nx
        x = nx
    return None


def parse_linear_equations(text):
    """把 "2x + y - z = 8" 这类自然写法解析为 (A, b, 变量名列表).

    做法: 把等式移项成 expr=0, 用单位向量代入求系数, 并校验线性性.
    """
    import re
    lines = [ln.strip() for ln in str(text).replace(";", "\n").split("\n") if ln.strip()]
    if not lines:
        raise CalcError("请输入至少一个方程")
    names = set()
    for ln in lines:
        for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", ln):
            names.add(m.group(0).lower())
    _ev0 = Evaluator()
    reserved = set(_ev0.funcs) | set(_ev0.consts)
    vars_ = sorted(n for n in names if n not in reserved)
    if not vars_:
        raise CalcError("没有识别到未知数 (可用 x、y、z 或 a、b、c)")
    if len(vars_) > 8:
        raise CalcError("未知数过多 (最多 8 个)")
    A, b = [], []
    for ln in lines:
        parts = ln.split("=")
        if len(parts) != 2:
            raise CalcError("每行必须是一个等式, 例如: 2x + y = 5")
        expr = "(%s)-(%s)" % (parts[0], parts[1])
        ev = Evaluator(variables={v: 0.0 for v in vars_})
        f = ev.compile(expr)
        zero = float(f({v: 0.0 for v in vars_}))
        row = []
        for v in vars_:
            env1 = {u: 0.0 for u in vars_}
            env1[v] = 1.0
            c1 = float(f(env1)) - zero
            env2 = {u: 0.0 for u in vars_}
            env2[v] = 2.0
            c2 = float(f(env2)) - zero
            if abs(c2 - 2 * c1) > 1e-7 * max(1.0, abs(c2)):
                raise CalcError("方程含 %s 的非线性项, 不属于线性方程组" % v)
            row.append(c1)
        A.append(row)
        b.append(-zero)
    return A, b, vars_


def solve_linear_system(A, b):
    """高斯消元 (列主元). 返回 (kind, solution)  kind: unique/none/infinite"""
    n = len(A)
    if n == 0:
        raise CalcError("方程组为空")
    m = len(A[0])
    if any(len(row) != m for row in A):
        raise CalcError("系数矩阵每行长度必须一致")
    if len(b) != n:
        raise CalcError("常数项个数与方程个数不一致")
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    rows, cols = n, m
    piv_col = []
    r = 0
    for c in range(cols):
        p = max(range(r, rows), key=lambda i: abs(M[i][c]))
        if abs(M[p][c]) < 1e-12:
            continue
        M[r], M[p] = M[p], M[r]
        pv = M[r][c]
        M[r] = [v / pv for v in M[r]]
        for i in range(rows):
            if i != r and abs(M[i][c]) > 1e-15:
                f = M[i][c]
                M[i] = [a - f * bb for a, bb in zip(M[i], M[r])]
        piv_col.append(c)
        r += 1
        if r == rows:
            break
    # 检查矛盾行
    for i in range(r, rows):
        if all(abs(v) < 1e-9 for v in M[i][:cols]) and abs(M[i][cols]) > 1e-9:
            return "none", None
    if r < cols:
        return "infinite", (M, piv_col)
    x = [0.0] * cols
    for i, c in enumerate(piv_col):
        x[c] = M[i][cols]
    return "unique", x


# ==========================================================================
# 矩阵
# ==========================================================================
class Matrix:
    def __init__(self, rows):
        self.rows = [[float(v) for v in r] for r in rows]
        if not self.rows:
            raise CalcError("矩阵为空")
        self.n = len(self.rows)
        self.m = len(self.rows[0])
        if any(len(r) != self.m for r in self.rows):
            raise CalcError("矩阵每行元素个数必须一致")

    @staticmethod
    def parse(text: str):
        rows = []
        for line in text.replace(";", "\n").split("\n"):
            line = line.strip().strip("[]")
            if not line:
                continue
            parts = [p for p in line.replace(",", " ").split() if p]
            if not parts:
                continue
            row = []
            for p in parts:
                try:
                    row.append(float(p))
                except ValueError:
                    try:
                        row.append(float(_eval_scalar(p)))
                    except Exception:
                        raise CalcError("无法解析矩阵元素: %s" % p)
            rows.append(row)
        if not rows:
            raise CalcError("矩阵内容为空")
        return Matrix(rows)

    def __str__(self):
        w = max(len(format_number(v, 8)) for r in self.rows for v in r)
        return "\n".join("  ".join(format_number(v, 8).rjust(w) for v in r) for r in self.rows)

    def add(self, o):
        self._same(o)
        return Matrix([[a + b for a, b in zip(r1, r2)] for r1, r2 in zip(self.rows, o.rows)])

    def sub(self, o):
        self._same(o)
        return Matrix([[a - b for a, b in zip(r1, r2)] for r1, r2 in zip(self.rows, o.rows)])

    def mul(self, o):
        if self.m != o.n:
            raise CalcError("矩阵乘法维度不匹配: %d×%d 不能乘 %d×%d" % (self.n, self.m, o.n, o.m))
        out = []
        for i in range(self.n):
            row = []
            for j in range(o.m):
                s = 0.0
                for k in range(self.m):
                    s += self.rows[i][k] * o.rows[k][j]
                row.append(s)
            out.append(row)
        return Matrix(out)

    def scale(self, k):
        return Matrix([[v * k for v in r] for r in self.rows])

    def transpose(self):
        return Matrix([[self.rows[i][j] for i in range(self.n)] for j in range(self.m)])

    def _same(self, o):
        if self.n != o.n or self.m != o.m:
            raise CalcError("矩阵维度不一致: %d×%d 与 %d×%d" % (self.n, self.m, o.n, o.m))

    def det(self):
        if self.n != self.m:
            raise CalcError("只有方阵才有行列式")
        M = [r[:] for r in self.rows]
        n = self.n
        det = 1.0
        for c in range(n):
            p = max(range(c, n), key=lambda i: abs(M[i][c]))
            if abs(M[p][c]) < 1e-14:
                return 0.0
            if p != c:
                M[c], M[p] = M[p], M[c]
                det = -det
            det *= M[c][c]
            for i in range(c + 1, n):
                f = M[i][c] / M[c][c]
                for j in range(c, n):
                    M[i][j] -= f * M[c][j]
        return det

    def trace(self):
        if self.n != self.m:
            raise CalcError("只有方阵才有迹")
        return sum(self.rows[i][i] for i in range(self.n))

    def rref(self):
        M = [r[:] for r in self.rows]
        rows, cols = self.n, self.m
        piv = []
        r = 0
        for c in range(cols):
            p = None
            best = 1e-12
            for i in range(r, rows):
                if abs(M[i][c]) > best:
                    best, p = abs(M[i][c]), i
            if p is None:
                continue
            M[r], M[p] = M[p], M[r]
            pv = M[r][c]
            M[r] = [v / pv for v in M[r]]
            for i in range(rows):
                if i != r and abs(M[i][c]) > 1e-15:
                    f = M[i][c]
                    M[i] = [a - f * b for a, b in zip(M[i], M[r])]
            piv.append(c)
            r += 1
            if r == rows:
                break
        for i in range(rows):
            for j in range(cols):
                if abs(M[i][j]) < 1e-12:
                    M[i][j] = 0.0
        return Matrix(M), piv

    def rank(self):
        _, piv = self.rref()
        return len(piv)

    def inv(self):
        if self.n != self.m:
            raise CalcError("只有方阵才可求逆")
        n = self.n
        M = [self.rows[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        for c in range(n):
            p = max(range(c, n), key=lambda i: abs(M[i][c]))
            if abs(M[p][c]) < 1e-12:
                raise CalcError("矩阵不可逆 (行列式为 0)")
            M[c], M[p] = M[p], M[c]
            pv = M[c][c]
            M[c] = [v / pv for v in M[c]]
            for i in range(n):
                if i != c and abs(M[i][c]) > 1e-15:
                    f = M[i][c]
                    M[i] = [a - f * b for a, b in zip(M[i], M[c])]
        return Matrix([r[n:] for r in M])

    def eigen(self):
        """2×2 / 3×3 特征值 (特征多项式 + 数值求根)"""
        n = self.n
        if n != self.m or n not in (2, 3, 4):
            raise CalcError("特征值仅支持 2×2、3×3、4×4 方阵")
        # 计算特征多项式系数: det(A - λI)
        coeffs = _char_poly(self.rows)
        roots = poly_roots(coeffs)
        return roots


def _char_poly(rows):
    """返回 det(A - λI) 的系数 (从高次到低次)"""
    n = len(rows)

    def det_lambda(lam):
        M = [[rows[i][j] - (lam if i == j else 0.0) for j in range(n)] for i in range(n)]
        d = [[None] * n for _ in range(n)]
        r = 1.0
        for c in range(n):
            p = max(range(c, n), key=lambda i: abs(M[i][c]))
            if abs(M[p][c]) < 1e-300:
                return 0.0
            if p != c:
                M[c], M[p] = M[p], M[c]
                r = -r
            r *= M[c][c]
            for i in range(c + 1, n):
                f = M[i][c] / M[c][c]
                for j in range(c, n):
                    M[i][j] -= f * M[c][j]
        return r

    if n == 2:
        return [1.0, -(rows[0][0] + rows[1][1]), rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]]
    if n == 3:
        t = rows[0][0] + rows[1][1] + rows[2][2]
        m2 = (rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]
              + rows[0][0] * rows[2][2] - rows[0][2] * rows[2][0]
              + rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        d = Matrix(rows).det()
        return [1.0, -t, m2, -d]
    # 4x4: 用拉格朗日插值采样特征多项式
    xs = [i * 1.0 for i in range(5)]
    ys = [det_lambda(x) for x in xs]
    return _interp_coeffs(xs, ys)


def _interp_coeffs(xs, ys):
    n = len(xs)
    coeffs = [0.0] * n
    for i in range(n):
        term = [1.0]
        denom = 1.0
        for j in range(n):
            if i == j:
                continue
            new = [0.0] * (len(term) + 1)
            for k, c in enumerate(term):
                new[k] += c
                new[k + 1] += -c * xs[j]
            term = new
            denom *= (xs[i] - xs[j])
        for k in range(len(term)):
            coeffs[k] += ys[i] * term[k] / denom
    # term 顺序是低次->高次, 转成高次->低次
    return list(reversed(coeffs))


def _eval_scalar(expr):
    return Evaluator().evaluate(expr)


# ==========================================================================
# 统计
# ==========================================================================
def parse_numbers(text: str):
    vals = []
    for part in text.replace(",", " ").replace("，", " ").replace("\n", " ").replace(";", " ").split():
        try:
            vals.append(float(part))
        except ValueError:
            raise CalcError("无法解析数字: %s" % part)
    if not vals:
        raise CalcError("请输入至少一个数字")
    return vals


def _quantile(sorted_vals, p):
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def stats_summary(vals):
    n = len(vals)
    s = sorted(vals)
    mean = sum(vals) / n
    var_p = sum((v - mean) ** 2 for v in vals) / n
    var_s = sum((v - mean) ** 2 for v in vals) / (n - 1) if n > 1 else 0.0
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    best = max(counts.values())
    modes = sorted(k for k, c in counts.items() if c == best) if best > 1 else []
    out = [
        ("个数", "%d" % n),
        ("求和", format_number(sum(vals))),
        ("平均值", format_number(mean)),
        ("中位数", format_number(_quantile(s, 0.5))),
        ("众数", "、".join(format_number(v) for v in modes) if modes else "无"),
        ("最小值", format_number(s[0])),
        ("最大值", format_number(s[-1])),
        ("极差", format_number(s[-1] - s[0])),
        ("总体方差", format_number(var_p)),
        ("样本方差", format_number(var_s)),
        ("总体标准差", format_number(math.sqrt(var_p))),
        ("样本标准差", format_number(math.sqrt(var_s))),
        ("下四分位 Q1", format_number(_quantile(s, 0.25))),
        ("上四分位 Q3", format_number(_quantile(s, 0.75))),
        ("四分位距", format_number(_quantile(s, 0.75) - _quantile(s, 0.25))),
        ("平方和", format_number(sum(v * v for v in vals))),
    ]
    return out


def linear_regression(xs, ys):
    if len(xs) != len(ys):
        raise CalcError("x 与 y 的个数必须相同")
    n = len(xs)
    if n < 2:
        raise CalcError("至少需要 2 组数据")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if abs(sxx) < 1e-15:
        raise CalcError("x 全部相同, 无法拟合")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    syy = sum((y - my) ** 2 for y in ys)
    r = sxy / math.sqrt(sxx * syy) if syy > 1e-15 else 1.0
    return {"slope": b, "intercept": a, "r": r, "r2": r * r, "n": n}


# ==========================================================================
# 单位换算
# ==========================================================================
UNITS = {
    "长度": {"米 m": 1.0, "千米 km": 1000.0, "厘米 cm": 0.01, "毫米 mm": 0.001,
             "微米 μm": 1e-6, "英寸 in": 0.0254, "英尺 ft": 0.3048, "码 yd": 0.9144,
             "英里 mile": 1609.344, "海里 nmi": 1852.0, "市里": 500.0, "市尺": 1 / 3.0},
    "面积": {"平方米 m²": 1.0, "平方千米 km²": 1e6, "公顷 ha": 10000.0, "亩": 666.6666667,
             "平方厘米 cm²": 1e-4, "平方毫米 mm²": 1e-6, "平方英尺 ft²": 0.09290304,
             "平方英里 mile²": 2589988.11, "英亩 acre": 4046.8564224},
    "体积": {"立方米 m³": 1.0, "升 L": 0.001, "毫升 mL": 1e-6, "立方厘米 cm³": 1e-6,
             "立方英尺 ft³": 0.0283168466, "加仑(美) gal": 0.0037854118,
             "加仑(英) galUK": 0.00454609, "桶(石油) bbl": 0.158987295},
    "质量": {"千克 kg": 1.0, "克 g": 0.001, "毫克 mg": 1e-6, "吨 t": 1000.0,
             "磅 lb": 0.45359237, "盎司 oz": 0.0283495231, "斤": 0.5, "两": 0.05},
    "时间": {"秒 s": 1.0, "分 min": 60.0, "小时 h": 3600.0, "天 d": 86400.0,
             "周 wk": 604800.0, "年 (365d)": 31536000.0, "毫秒 ms": 0.001},
    "速度": {"米/秒 m/s": 1.0, "千米/小时 km/h": 1 / 3.6, "英里/小时 mph": 0.44704,
             "节 kn": 0.514444, "英尺/秒 ft/s": 0.3048, "马赫 Ma": 340.29},
    "压强": {"帕斯卡 Pa": 1.0, "千帕 kPa": 1000.0, "兆帕 MPa": 1e6, "巴 bar": 1e5,
             "标准大气压 atm": 101325.0, "毫米汞柱 mmHg": 133.322387415,
             "磅力/平方英寸 psi": 6894.757293168, "千克力/平方厘米 kgf/cm²": 98066.5},
    "能量": {"焦耳 J": 1.0, "千焦 kJ": 1000.0, "卡 cal": 4.184, "千卡 kcal": 4184.0,
             "瓦时 Wh": 3600.0, "千瓦时 kWh": 3.6e6, "电子伏 eV": 1.602176634e-19,
             "英热单位 BTU": 1055.05585262},
    "功率": {"瓦 W": 1.0, "千瓦 kW": 1000.0, "兆瓦 MW": 1e6, "马力 hp": 745.6998715823,
             "卡/秒 cal/s": 4.184},
    "角度": {"度 °": 1.0, "弧度 rad": 57.29577951308232, "分 ′": 1 / 60.0,
             "秒 ″": 1 / 3600.0, "百分度 grad": 0.9, "转 turn": 360.0},
    "数据": {"字节 B": 1.0, "千字节 KB": 1024.0, "兆字节 MB": 1048576.0,
             "吉字节 GB": 1073741824.0, "太字节 TB": 1099511627776.0, "比特 bit": 0.125},
}
_TEMP_UNITS = ["摄氏度 °C", "华氏度 °F", "开尔文 K"]


def unit_list(kind):
    if kind == "温度":
        return _TEMP_UNITS
    return list(UNITS[kind].keys())


def convert_unit(value, kind, src, dst):
    if kind == "温度":
        if src == dst:
            return value
        # 先转摄氏度
        if src == "摄氏度 °C":
            c = value
        elif src == "华氏度 °F":
            c = (value - 32) * 5 / 9
        else:
            c = value - 273.15
        if dst == "摄氏度 °C":
            return c
        if dst == "华氏度 °F":
            return c * 9 / 5 + 32
        return c + 273.15
    table = UNITS.get(kind)
    if not table:
        raise CalcError("未知换算类别: %s" % kind)
    if src not in table or dst not in table:
        raise CalcError("未知单位")
    return value * table[src] / table[dst]
