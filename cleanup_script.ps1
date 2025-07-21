# PowerShell script for cleaning up cache directories and temporary files
# Run this script periodically to keep your development environment clean

Write-Host "🧹 Cleaning up development environment..." -ForegroundColor Green

# Clean Python cache directories
Write-Host "🗑️  Removing Python cache directories..." -ForegroundColor Yellow
Remove-Item -Path "app\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "app\core\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "tests\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue

# Clean pytest cache
Write-Host "🗑️  Removing pytest cache..." -ForegroundColor Yellow
Remove-Item -Path ".pytest_cache" -Recurse -Force -ErrorAction SilentlyContinue

# Clean any log files
Write-Host "🗑️  Removing log files..." -ForegroundColor Yellow
Remove-Item -Path "*.log" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "logs\*.log" -Force -ErrorAction SilentlyContinue

# Clean any temporary files
Write-Host "🗑️  Removing temporary files..." -ForegroundColor Yellow
Remove-Item -Path "*.tmp" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "*.temp" -Force -ErrorAction SilentlyContinue

# Clean any .pyc files that might be leftover
Write-Host "🗑️  Removing .pyc files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "✅ Cleanup completed successfully!" -ForegroundColor Green
Write-Host "📁 Your development environment is now clean." -ForegroundColor Cyan 