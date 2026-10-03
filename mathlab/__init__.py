# -*- coding: utf-8 -*-
"""MathLab —— 数学计算软件 (计算器 / 绘图 / 方程 / 矩阵 / 统计 / 单位换算)"""

__version__ = "1.0.0"
__appname__ = "MathLab"

from .engine import (CalcError, Evaluator, Matrix, convert_unit, find_roots,
                     format_complex, format_number, fraction_hint, int_bases,
                     linear_regression, parse_linear_equations, parse_numbers,
                     poly_roots, solve_cubic, solve_linear_system, solve_quadratic,
                     stats_summary, unit_list, UNITS)

__all__ = ["CalcError", "Evaluator", "Matrix", "convert_unit", "find_roots",
           "format_complex", "format_number", "fraction_hint", "int_bases",
           "linear_regression", "parse_linear_equations", "parse_numbers",
           "poly_roots", "solve_cubic", "solve_linear_system", "solve_quadratic",
           "stats_summary", "unit_list", "UNITS", "__version__", "__appname__"]
