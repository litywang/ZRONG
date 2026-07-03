@echo off
chcp 65001 >nul
echo 检查 ZRONG 输出质量...
echo.

set PROXIES_FILE=C:\tools\ZRONG\proxies.yaml

if not exist "%PROXIES_FILE%" (
    echo ❌ 错误: 找不到 proxies.yaml 文件
    echo 期望路径: %PROXIES_FILE%
    echo.
    echo 可能的原因:
    echo 1. 爬虫尚未运行
    echo 2. 输出路径不正确
    echo 3. 文件被删除或移动
    exit /b 1
)

echo [OK] 找到 proxies.yaml 文件
echo.

REM 这里需要 Python 来解析 YAML，暂时只检查文件是否存在
echo 文件大小: 
for %%A in ("%PROXIES_FILE%") do echo %%~zA bytes

echo.
echo ⚠️ 完整质量检查需要 Python 环境
echo 建议: 安装 Python 并修复 heartbeat_quality_check.py 脚本
