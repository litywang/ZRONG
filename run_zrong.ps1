# ZRONG 爬虫启动脚本
# 用途: 被 Windows 定时任务调用，运行爬虫并自动 Git 提交

$ErrorActionPreference = "Stop"

$ZrongPath = "C:\tools\ZRONG"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $ZrongPath "run_$Timestamp.log"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ZRONG Crawler Start" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date)" -ForegroundColor Cyan
Write-Host "Log: $LogPath" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 切换到 ZRONG 目录
Set-Location $ZrongPath

try {
    # 运行爬虫（输出重定向到日志）
    Write-Host "[1/3] Running crawler..." -ForegroundColor Yellow
    python crawler.py 2>&1 | Tee-Object -FilePath $LogPath
    
    if ($LASTEXITCODE -ne 0) {
        throw "Crawler failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "[2/3] Crawler completed successfully!" -ForegroundColor Green
    
    # Git 提交（如果有更改）
    Write-Host "[3/3] Checking Git changes..." -ForegroundColor Yellow
    $GitStatus = git status --porcelain proxies.yaml
    
    if ($GitStatus) {
        Write-Host "Found changes in proxies.yaml, committing..." -ForegroundColor Yellow
        git add proxies.yaml
        git commit -m "Update proxies (auto commit $Timestamp)"
        git push origin main
        Write-Host "Git push completed!" -ForegroundColor Green
    } else {
        Write-Host "No changes to commit." -ForegroundColor Gray
    }
    
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "ZRONG Crawler Finished Successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    
} catch {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "Check log: $LogPath" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
}
