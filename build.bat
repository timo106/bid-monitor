@echo off
chcp 65001 >nul
echo ========================================
echo   招标信息监控 - 打包工具
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 清理旧的构建文件...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [2/3] 开始打包...
pyinstaller --noconfirm app.spec

echo.
if exist "dist\招标信息监控.exe" (
    echo ========================================
    echo   打包成功！
    echo   文件位置: dist\招标信息监控.exe
    echo ========================================
    echo.
    echo 提示：
    echo   - 首次运行需要 config_local.py（放在 exe 同目录）
    echo   - 需要安装 Playwright 浏览器: playwright install chromium
    echo.
) else (
    echo ========================================
    echo   打包失败，请检查错误信息
    echo ========================================
)

pause
