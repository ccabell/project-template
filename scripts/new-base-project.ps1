# Quick Base Project Creator
# Convenient wrapper for creating production mirror base projects

param(
    [Parameter(Mandatory=$true)]
    [string]$Name,
    
    [Parameter(Mandatory=$false)]
    [string]$Description = "Production-mirrored base project",
    
    [Parameter(Mandatory=$false)]
    [switch]$IncludePageCraft,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateGitHub,
    
    [Parameter(Mandatory=$false)]
    [switch]$RunAsAdmin
)

Write-Host "Creating Base Project: $Name" -ForegroundColor Green

# Check if running as administrator (needed for symlinks)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin -and -not $RunAsAdmin) {
    Write-Host "⚠️  For best results, run as administrator to create symbolic links." -ForegroundColor Yellow
    Write-Host "   This enables direct development in production repositories." -ForegroundColor Yellow
    Write-Host "   Alternatively, use -RunAsAdmin to restart with elevated privileges." -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        Write-Host "Cancelled. Run as administrator for full functionality." -ForegroundColor Red
        exit
    }
} elseif ($RunAsAdmin -and -not $isAdmin) {
    Write-Host "Restarting with administrator privileges..." -ForegroundColor Yellow
    $scriptPath = $PSCommandPath
    $arguments = "-Name '$Name' -Description '$Description'"
    if ($IncludePageCraft) { $arguments += " -IncludePageCraft" }
    if ($CreateGitHub) { $arguments += " -CreateGitHub" }
    
    Start-Process PowerShell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File '$scriptPath' $arguments"
    exit
}

# Call the main creation script
$mainScript = Join-Path $PSScriptRoot "create-production-mirror-base.ps1"
$params = @{
    BaseProjectName = $Name
    ProjectDescription = $Description
}

if ($IncludePageCraft) { $params.IncludePageCraft = $true }
if ($CreateGitHub) { $params.CreateGitHubRepo = $true }

$projectPath = & $mainScript @params

# Post-creation setup
if ($projectPath) {
    Write-Host "`n🚀 Quick Start Commands:" -ForegroundColor Green
    Write-Host "cd `"$projectPath`"" -ForegroundColor Cyan
    Write-Host ".\scripts\sync-snapshots.ps1" -ForegroundColor Cyan
    Write-Host ".\scripts\create-db-snapshot.ps1" -ForegroundColor Cyan
    
    Write-Host "`n📋 Development Workflow:" -ForegroundColor Green
    Write-Host "• Core development: Work in production-repos/ directories" -ForegroundColor White
    Write-Host "• Collaborator prep: Run sync scripts before sharing" -ForegroundColor White
    Write-Host "• Real-time sync: Changes reflect immediately in B360" -ForegroundColor White
}