@echo off
chcp 65001 >nul
rem 直接以源码方式启动 MathLab (需要已安装 Python; 用 pythonw 隐藏控制台窗口)
cd /d "%~dp0"
start "" pythonw.exe "%~dp0main.py"
