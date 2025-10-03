# Project Template Creator
# This script creates a new project from the template structure

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    
    [Parameter(Mandatory=$true)]
    [string]$ProjectPath,
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectDescription = "A new project created from template",
    
    [Parameter(Mandatory=$false)]
    [string]$AuthorName = $env:USERNAME,
    
    [Parameter(Mandatory=$false)]
    [string]$GitHubUsername = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$NodeJS,
    
    [Parameter(Mandatory=$false)]
    [switch]$Python,
    
    [Parameter(Mandatory=$false)]
    [switch]$InitializeGit,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateGitHubRepo,
    
    [Parameter(Mandatory=$false)]
    [switch]$IncludeReferenceDatabase,
    
    [Parameter(Mandatory=$false)]
    [switch]$IncludePageCraftAccess,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateBaseProject
)

# Template source directory (where this script is located)
$TemplateDir = Split-Path -Parent $PSScriptRoot
$NewProjectPath = Join-Path $ProjectPath $ProjectName

Write-Host "Creating new project: $ProjectName" -ForegroundColor Green
Write-Host "Location: $NewProjectPath" -ForegroundColor Cyan

# Rule 1: Ask about reference database access
if (-not $IncludeReferenceDatabase -and -not $PSBoundParameters.ContainsKey('IncludeReferenceDatabase')) {
    Write-Host "`n📊 Reference Database Access" -ForegroundColor Yellow
    Write-Host "Would you like to include access to the reference database (pma.nextnlp.com)?" -ForegroundColor White
    Write-Host "⚠️  IMPORTANT: This database is for development reference only!" -ForegroundColor Red
    Write-Host "   - NOT available in production environment" -ForegroundColor Red
    Write-Host "   - Any functionality using this data must export supporting data for production" -ForegroundColor Red
    $dbChoice = Read-Host "Include reference database access? (y/N)"
    $IncludeReferenceDatabase = ($dbChoice -eq "y" -or $dbChoice -eq "Y")
}

# Rule 2: Ask about PageCraft access
if (-not $IncludePageCraftAccess -and -not $PSBoundParameters.ContainsKey('IncludePageCraftAccess')) {
    Write-Host "`n🎨 PageCraft Integration" -ForegroundColor Yellow
    Write-Host "Would you like to include access to the page-craft-bliss-forge-api project?" -ForegroundColor White
    Write-Host "   This adds API integration capabilities for the PageCraft system" -ForegroundColor Gray
    $pageCraftChoice = Read-Host "Include PageCraft access? (y/N)"
    $IncludePageCraftAccess = ($pageCraftChoice -eq "y" -or $pageCraftChoice -eq "Y")
}

# Rule 3: Ask about base project creation
if (-not $CreateBaseProject -and -not $PSBoundParameters.ContainsKey('CreateBaseProject')) {
    Write-Host "`n🏗️  Base Project Creation" -ForegroundColor Yellow
    Write-Host "Would you like to create this as a production mirror base project?" -ForegroundColor White
    Write-Host "   This creates symlinks to production repositories for direct development" -ForegroundColor Gray
    $baseChoice = Read-Host "Create as base project? (y/N)"
    $CreateBaseProject = ($baseChoice -eq "y" -or $baseChoice -eq "Y")
}

# Check if project directory already exists
if (Test-Path $NewProjectPath) {
    $response = Read-Host "Project directory already exists. Overwrite? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "Project creation cancelled." -ForegroundColor Yellow
        exit
    }
    Remove-Item $NewProjectPath -Recurse -Force
}

# Create project directory structure
Write-Host "Creating directory structure..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $NewProjectPath -Force | Out-Null
New-Item -ItemType Directory -Path "$NewProjectPath\src" -Force | Out-Null
New-Item -ItemType Directory -Path "$NewProjectPath\config" -Force | Out-Null
New-Item -ItemType Directory -Path "$NewProjectPath\docs" -Force | Out-Null
New-Item -ItemType Directory -Path "$NewProjectPath\scripts" -Force | Out-Null
New-Item -ItemType Directory -Path "$NewProjectPath\tests" -Force | Out-Null
New-Item -ItemType Directory -Path "$NewProjectPath\database" -Force | Out-Null

# Copy and process template files
Write-Host "Copying template files..." -ForegroundColor Yellow

# Files to copy directly without modification
$DirectCopyFiles = @(
    ".gitignore",
    "config\database.example.json",
    "database\schema-reference.md",
    "docs\api-documentation.md",
    "docs\database-schema.md",
    "docs\infrastructure.md"
)

foreach ($file in $DirectCopyFiles) {
    $sourcePath = Join-Path $TemplateDir $file
    $destPath = Join-Path $NewProjectPath $file
    if (Test-Path $sourcePath) {
        Copy-Item $sourcePath $destPath -Force
    }
}

# Process template files with variable substitution
Write-Host "Processing template files with project-specific values..." -ForegroundColor Yellow

# Process README.md
$readmeTemplate = Get-Content "$TemplateDir\README.md" -Raw
$readmeContent = $readmeTemplate -replace '\{\{PROJECT_NAME\}\}', $ProjectName
Set-Content "$NewProjectPath\README.md" $readmeContent

# Process .env.example
$envTemplate = Get-Content "$TemplateDir\.env.example" -Raw
Set-Content "$NewProjectPath\.env.example" $envTemplate

# Process package.json (if Node.js selected)
if ($NodeJS -or (!$Python -and !$NodeJS)) {  # Default to Node.js if neither specified
    Write-Host "Setting up Node.js configuration..." -ForegroundColor Cyan
    $packageTemplate = Get-Content "$TemplateDir\package.json.template" -Raw
    $packageContent = $packageTemplate -replace '\{\{PROJECT_NAME\}\}', $ProjectName.ToLower()
    $packageContent = $packageContent -replace '\{\{PROJECT_DESCRIPTION\}\}', $ProjectDescription
    $packageContent = $packageContent -replace '\{\{AUTHOR_NAME\}\}', $AuthorName
    $packageContent = $packageContent -replace '\{\{GITHUB_USERNAME\}\}', $GitHubUsername
    Set-Content "$NewProjectPath\package.json" $packageContent
    
    # Create basic source files from template
    $nodeJsTemplate = Get-Content "$TemplateDir\src\index.js.template" -Raw
    Set-Content "$NewProjectPath\src\index.js" $nodeJsTemplate
}

# Process requirements.txt (if Python selected)
if ($Python) {
    Write-Host "Setting up Python configuration..." -ForegroundColor Cyan
    Copy-Item "$TemplateDir\requirements.txt.template" "$NewProjectPath\requirements.txt"
    
    # Create basic Python source files from template
    $pythonTemplate = Get-Content "$TemplateDir\src\main.py.template" -Raw
    $pythonContent = $pythonTemplate -replace '\{\{PROJECT_NAME\}\}', $ProjectName
    Set-Content "$NewProjectPath\src\main.py" $pythonContent
}

# Add PageCraft configuration if included
if ($IncludePageCraftAccess) {
    Write-Host "Adding PageCraft integration..." -ForegroundColor Yellow
    
    # Copy PageCraft configuration file
    Copy-Item "$TemplateDir\config\pagecraft.example.json" "$NewProjectPath\config\pagecraft.json" -Force
    
    # Add PageCraft environment variables to .env.example
    $pagecraftEnvVars = "`n# PageCraft Integration`nPAGECRAFT_API_URL=http://localhost:8080/api`nPAGECRAFT_API_KEY=your_pagecraft_api_key`nPAGECRAFT_ENABLED=true"
    Add-Content "$NewProjectPath\.env.example" $pagecraftEnvVars
}

# Create base project if requested
if ($CreateBaseProject) {
    Write-Host "Creating as production mirror base project..." -ForegroundColor Yellow
    $baseScript = Join-Path (Split-Path $TemplateDir -Parent) "scripts\create-production-mirror-base.ps1"
    if (Test-Path $baseScript) {
        & $baseScript -BaseProjectName $ProjectName -ProjectDescription $ProjectDescription -IncludePageCraft:$IncludePageCraftAccess
        Write-Host "Base project created with production repository integration" -ForegroundColor Green
        return
    } else {
        Write-Host "Warning: Base project script not found, continuing with regular project creation" -ForegroundColor Yellow
    }
}

# Update project.json with current information
$features = @(
    "GitHub integration",
    "Database configuration with development reference",
    "Environment-based configuration", 
    "API documentation structure",
    "Collaboration-ready documentation",
    "Security best practices",
    "Testing setup"
)

if ($IncludePageCraftAccess) {
    $features += "PageCraft API integration"
}

$projectConfig = @{
    template = @{
        name = "Collaborative Project Template"
        version = "1.0.0"
        description = "Generated from template"
        created = (Get-Date -Format "yyyy-MM-dd")
        author = $AuthorName
        type = "collaborative-project"
    }
    project = @{
        name = $ProjectName
        description = $ProjectDescription
        created = (Get-Date -Format "yyyy-MM-dd")
        language = if ($Python) { "python" } else { "nodejs" }
        pagecraft_integration = $IncludePageCraftAccess
    }
    features = $features
} | ConvertTo-Json -Depth 10

Set-Content "$NewProjectPath\project.json" $projectConfig

# Copy this script to the new project
Copy-Item $PSCommandPath "$NewProjectPath\scripts\create-new-project.ps1" -Force

# Copy GitHub setup script
Copy-Item "$TemplateDir\scripts\setup-github.ps1" "$NewProjectPath\scripts\setup-github.ps1" -Force

# Initialize Git repository if requested
if ($InitializeGit) {
    Write-Host "Initializing Git repository..." -ForegroundColor Yellow
    Push-Location $NewProjectPath
    try {
        git init
        git add .
        git commit -m "Initial project setup from template"
        git branch -M main
        
        if ($CreateGitHubRepo -and $GitHubUsername) {
            Write-Host "Setting up GitHub integration..." -ForegroundColor Yellow
            & "$NewProjectPath\scripts\setup-github.ps1" -ProjectName $ProjectName -GitHubUsername $GitHubUsername -CreateRepo
        }
    }
    catch {
        Write-Host "Git initialization failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    finally {
        Pop-Location
    }
}

# Create setup instructions from template
$setupTemplate = Get-Content "$TemplateDir\SETUP.md.template" -Raw
$installCommands = if ($Python) { '   ```bash' + "`n" + '   pip install -r requirements.txt' + "`n" + '   ```' } else { '   ```bash' + "`n" + '   npm install' + "`n" + '   ```' }
$runCommands = if ($Python) { '   ```bash' + "`n" + '   python -m uvicorn src.main:app --reload' + "`n" + '   ```' } else { '   ```bash' + "`n" + '   npm run dev' + "`n" + '   ```' }
$language = if ($Python) { "Python/FastAPI" } else { "Node.js/Express" }

$setupContent = $setupTemplate -replace '\{\{PROJECT_NAME\}\}', $ProjectName
$setupContent = $setupContent -replace '\{\{PROJECT_PATH\}\}', $NewProjectPath
$setupContent = $setupContent -replace '\{\{INSTALL_COMMANDS\}\}', $installCommands
$setupContent = $setupContent -replace '\{\{RUN_COMMANDS\}\}', $runCommands
$setupContent = $setupContent -replace '\{\{LANGUAGE\}\}', $language
$setupContent = $setupContent -replace '\{\{AUTHOR_NAME\}\}', $AuthorName
$setupContent = $setupContent -replace '\{\{CREATED_DATE\}\}', (Get-Date -Format "yyyy-MM-dd HH:mm")

Set-Content "$NewProjectPath\SETUP.md" $setupContent

Write-Host "`nProject creation completed successfully!" -ForegroundColor Green
Write-Host "Project location: $NewProjectPath" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. cd `"$NewProjectPath`"" -ForegroundColor White
Write-Host "2. Read SETUP.md for detailed setup instructions" -ForegroundColor White
Write-Host "3. Copy .env.example to .env and configure" -ForegroundColor White
Write-Host "4. Install dependencies and start developing!" -ForegroundColor White

if (!$InitializeGit) {
    Write-Host "`nTo initialize Git repository later, run:" -ForegroundColor Cyan
    Write-Host "git init; git add .; git commit -m 'Initial commit'" -ForegroundColor White
}