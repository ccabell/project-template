# Simple Base Project Setup for B360
# Creates a base project structure for collaborative development

param(
    [Parameter(Mandatory=$true)]
    [string]$BaseProjectName,
    
    [Parameter(Mandatory=$false)]
    [string]$Description = "B360 base project for collaborative development"
)

$B360Path = "C:\Users\Chris\b360"
$BaseProjectPath = Join-Path $B360Path $BaseProjectName

Write-Host "Setting up B360 Base Project: $BaseProjectName" -ForegroundColor Green
Write-Host "Location: $BaseProjectPath" -ForegroundColor Cyan

# Create base project directory structure
Write-Host "Creating project structure..." -ForegroundColor Yellow

New-Item -ItemType Directory -Path $BaseProjectPath -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\docs" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\scripts" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\config" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\web-portal" -Force | Out-Null

# Copy web portal to base project
Write-Host "Setting up web portal..." -ForegroundColor Yellow
$TemplatePortalPath = "C:\Users\Chris\b360\project-template\web-portal"

if (Test-Path $TemplatePortalPath) {
    Copy-Item "$TemplatePortalPath\*" "$BaseProjectPath\web-portal" -Recurse -Force
    Write-Host "  ✓ Web portal copied successfully" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Template web portal not found" -ForegroundColor Yellow
}

# Create project README from template
$readmeTemplate = Get-Content "C:\Users\Chris\b360\project-template\README-base.md.template" -Raw
$readmeContent = $readmeTemplate -replace '\{\{PROJECT_NAME\}\}', $BaseProjectName
$readmeContent = $readmeContent -replace '\{\{DESCRIPTION\}\}', $Description
$readmeContent = $readmeContent -replace '\{\{CREATED_DATE\}\}', (Get-Date -Format 'yyyy-MM-dd HH:mm')

Set-Content "$BaseProjectPath\README.md" $readmeContent

# Create project configuration
$projectConfig = @{
    name = $BaseProjectName
    description = $Description
    type = "b360-base-project"
    created = (Get-Date -Format "yyyy-MM-dd")
    features = @(
        "A360 Portal",
        "User Management", 
        "Project Tracking",
        "Agent Testing",
        "B360 Integration",
        "Collaborative Development"
    )
    b360_components = @(
        "mariadb-sync-project",
        "n8n-interface-project", 
        "page-craft-bliss-forge-api",
        "firecrawl-project",
        "warp-work-tracker",
        "a360-data-lake",
        "a360-data-science",
        "a360-notes-ios",
        "a360-transcription-service-evaluator"
    )
} | ConvertTo-Json -Depth 10

Set-Content "$BaseProjectPath\project.json" $projectConfig

# Initialize Git repository
Write-Host "Initializing Git repository..." -ForegroundColor Yellow
Push-Location $BaseProjectPath
try {
    git init
    git add .
    git commit -m "Initial B360 base project setup"
    git branch -M main
    Write-Host "  ✓ Git repository initialized" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Git initialization failed: $($_.Exception.Message)" -ForegroundColor Yellow
} finally {
    Pop-Location
}

Write-Host "`nBase project setup completed successfully!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. cd `"$BaseProjectPath`"" -ForegroundColor White
Write-Host "2. Configure web portal: cd web-portal && .\run.ps1 -Install" -ForegroundColor White
Write-Host "3. Set up Supabase configuration in web-portal\.env" -ForegroundColor White
Write-Host "4. Launch portal: .\run.ps1 -Dev" -ForegroundColor White

Write-Host "`nProject created at: $BaseProjectPath" -ForegroundColor Cyan