@echo off
REM 简单的批处理检测脚本
REM detect_simple.bat

if "%~1"=="" (
    echo 用法: detect_simple.bat ^<图片目录^>
    echo 示例: detect_simple.bat test_images
    exit /b 1
)

set SCRIPT_DIR=%~dp0
set SOURCE=%~1
set CONF=%~2
if "%CONF%"=="" set CONF=0.25

REM 激活虚拟环境
call "%SCRIPT_DIR%venv\Scripts\activate.bat"

REM 生成时间戳
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%

set MODEL=%SCRIPT_DIR%models\yolov8s-obb-potato-v22_best.pt
set RULES=%SCRIPT_DIR%config\grading_rules.json
set OUTPUT=%SCRIPT_DIR%results\%TIMESTAMP%

echo =========================================
echo 开始检测
echo =========================================
echo 输入: %SOURCE%
echo 输出: %OUTPUT%
echo.

python "%SCRIPT_DIR%scripts\grade_with_potato_label.py" ^
    --model "%MODEL%" ^
    --source "%SOURCE%" ^
    --rules "%RULES%" ^
    --out "%OUTPUT%" ^
    --conf %CONF%

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =========================================
    echo 检测完成！
    echo =========================================
    echo.
    echo 结果位置: %OUTPUT%
    echo   - CSV: %OUTPUT%\potatoes.csv
    echo   - JSONL: %OUTPUT%\potatoes.jsonl
    echo   - 可视化: %OUTPUT%\visualizations\
    echo.
) else (
    echo.
    echo 检测失败，请检查错误信息
)

pause

