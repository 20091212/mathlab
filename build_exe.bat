@echo off
chcp 65001 >nul
rem ============================================================
rem  MathLab 打包脚本 —— 生成单文件 MathLab.exe (无需安装 Python)
rem  依赖: pip install pyinstaller
rem ============================================================
cd /d "%~dp0"

echo [1/4] 生成图标...
python make_icon.py || goto :err

echo [2/4] 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] 开始打包 (首次约需 1-3 分钟)...
python -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name MathLab ^
  --icon assets\mathlab.ico ^
  --paths . ^
  --hidden-import mathlab ^
  --hidden-import mathlab.engine ^
  --hidden-import mathlab.gui ^
  --hidden-import mathlab.plot ^
  --hidden-import mathlab.history ^
  --exclude-module numpy ^
  --exclude-module matplotlib ^
  --exclude-module PIL.ImageQt ^
  main.py
if errorlevel 1 goto :err

echo [4/4] 完成!
echo.
echo   可执行文件: %~dp0dist\MathLab.exe
echo   双击即可运行, 可复制到任何 Windows 电脑使用 (无需 Python)
echo.
pause
exit /b 0

:err
echo.
echo *** 打包失败, 请把上面的报错信息发给开发者 ***
pause
exit /b 1
