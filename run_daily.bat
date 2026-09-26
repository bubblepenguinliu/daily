@echo off
rem ============================================================
rem  技术情报日报 —— 每日一键运行
rem  直接双击即可；也可挂到 Windows 任务计划程序做定时执行
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================
echo   技术情报日报  开始运行  %date% %time%
echo ============================================
echo.

".venv\Scripts\python.exe" -m src.main
set RC=%ERRORLEVEL%

if "%RC%"=="0" (
  echo [OK] 生成完成，正在打开日报...
  start "" "output\latest.html"
) else if "%RC%"=="2" (
  echo [!!] 抓取失败：检查代理是否开启（默认 http://127.0.0.1:7897）
) else (
  echo [!!] 运行异常，退出码 %RC%
)

echo.
pause
