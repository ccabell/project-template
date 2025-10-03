# Add these functions to your PowerShell profile for quick project creation
# To find your profile location, run: $PROFILE
# To edit your profile, run: notepad $PROFILE

# Function for creating general collaborative projects
function New-CollaborativeProject {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$false)]
        [string]$Path = "C:\Users\Chris\Projects",
        
        [Parameter(Mandatory=$false)]
        [string]$Description = "A collaborative project",
        
        [Parameter(Mandatory=$false)]
        [switch]$Python,
        
        [Parameter(Mandatory=$false)]
        [switch]$NodeJS = $true,
        
        [Parameter(Mandatory=$false)]
        [switch]$CreateGitHubRepo
    )
    
    $templateScript = "C:\Users\Chris\b360\project-template\scripts\create-new-project.ps1"
    & $templateScript -ProjectName $Name -ProjectPath $Path -ProjectDescription $Description -NodeJS:$NodeJS -Python:$Python -InitializeGit -CreateGitHubRepo:$CreateGitHubRepo -GitHubUsername "ccabell"
}

# Function for creating A360-specific projects
function New-A360Project {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$false)]
        [string]$Description = "A360 ecosystem integration project",
        
        [Parameter(Mandatory=$false)]
        [ValidateSet("api", "web", "integration", "microservice")]
        [string]$Type = "api",
        
        [Parameter(Mandatory=$false)]
        [switch]$Python,
        
        [Parameter(Mandatory=$false)]
        [switch]$NodeJS,
        
        [Parameter(Mandatory=$false)]
        [switch]$CreateGitHubRepo
    )
    
    $a360Script = "C:\Users\Chris\b360\project-template\scripts\create-a360-project.ps1"
    & $a360Script -ProjectName $Name -ProjectDescription $Description -ProjectType $Type -Python:$Python -NodeJS:$NodeJS -CreateGitHubRepo:$CreateGitHubRepo
}

# Function to quickly navigate to A360 projects
function Go-A360 {
    param(
        [Parameter(Mandatory=$false)]
        [string]$Project = ""
    )
    
    if ($Project) {
        Set-Location "C:\Users\Chris\b360\$Project"
    } else {
        Set-Location "C:\Users\Chris\b360"
        Write-Host "A360 Projects:" -ForegroundColor Green
        Get-ChildItem -Directory | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Cyan }
    }
}

# Function for creating production mirror base projects
function New-BaseProject {
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
    
    $baseScript = "C:\Users\Chris\b360\project-template\scripts\new-base-project.ps1"
    & $baseScript -Name $Name -Description $Description -IncludePageCraft:$IncludePageCraft -CreateGitHub:$CreateGitHub -RunAsAdmin:$RunAsAdmin
}

# Function to quickly navigate to template
function Go-Template {
    Set-Location "C:\Users\Chris\b360\project-template"
}

# Function to quickly navigate to PageCraft API
function Go-PageCraft {
    Set-Location "C:\Users\Chris\b360\page-craft-bliss-forge-api"
    Write-Host "PageCraft API Directory:" -ForegroundColor Green
    Get-ChildItem -File | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Cyan }
    if ((Get-ChildItem -File).Count -gt 5) {
        Write-Host "  ... and $((Get-ChildItem -File).Count - 5) more files" -ForegroundColor Gray
    }
}

# Function to create a project with PageCraft integration
function New-PageCraftProject {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$false)]
        [string]$Path = "C:\Users\Chris\Projects",
        
        [Parameter(Mandatory=$false)]
        [string]$Description = "A project with PageCraft integration",
        
        [Parameter(Mandatory=$false)]
        [switch]$Python,
        
        [Parameter(Mandatory=$false)]
        [switch]$NodeJS = $true,
        
        [Parameter(Mandatory=$false)]
        [switch]$CreateGitHubRepo
    )
    
    $templateScript = "C:\Users\Chris\b360\project-template\scripts\create-new-project.ps1"
    & $templateScript -ProjectName $Name -ProjectPath $Path -ProjectDescription $Description -NodeJS:$NodeJS -Python:$Python -IncludePageCraftAccess -InitializeGit -CreateGitHubRepo:$CreateGitHubRepo -GitHubUsername "ccabell"
}

# Function to create a Streamlit project
function New-StreamlitProject {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Name,
        
        [Parameter(Mandatory=$false)]
        [string]$Path = "C:\Users\Chris\Projects",
        
        [Parameter(Mandatory=$false)]
        [string]$Description = "A Streamlit web application project",
        
        [Parameter(Mandatory=$false)]
        [switch]$CreateGitHubRepo
    )
    
    Write-Host "Creating Streamlit project: $Name" -ForegroundColor Green
    
    # Create project directory
    $projectPath = Join-Path $Path $Name
    New-Item -ItemType Directory -Path $projectPath -Force | Out-Null
    
    # Copy Streamlit template files from project-template
    $templatePath = "C:\Users\Chris\b360\project-template"
    Copy-Item "$templatePath\streamlit_app.py" -Destination "$projectPath\app.py"
    Copy-Item "$templatePath\requirements.txt" -Destination $projectPath -ErrorAction SilentlyContinue
    Copy-Item "$templatePath\.streamlit" -Destination $projectPath -Recurse -ErrorAction SilentlyContinue
    
    # Create basic project structure
    New-Item -ItemType Directory -Path "$projectPath\pages" -Force | Out-Null
    New-Item -ItemType Directory -Path "$projectPath\data" -Force | Out-Null
    
    # Initialize git if requested
    Set-Location $projectPath
    git init
    
    Write-Host "Streamlit project created at: $projectPath" -ForegroundColor Cyan
    Write-Host "To run: streamlit run app.py" -ForegroundColor Yellow
}

# Function to quickly navigate to Streamlit template
function Go-StreamlitTemplate {
    Set-Location "C:\Users\Chris\b360\project-template"
    Write-Host "Streamlit Template Directory - Available apps:" -ForegroundColor Green
    Get-ChildItem -Name "*app*.py", "*streamlit*.py" | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
}

# Aliases for even quicker access
Set-Alias -Name "ncp" -Value New-CollaborativeProject
Set-Alias -Name "na360" -Value New-A360Project
Set-Alias -Name "nbp" -Value New-BaseProject
Set-Alias -Name "npc" -Value New-PageCraftProject
Set-Alias -Name "nst" -Value New-StreamlitProject
Set-Alias -Name "goa360" -Value Go-A360
Set-Alias -Name "got" -Value Go-Template
Set-Alias -Name "gopc" -Value Go-PageCraft
Set-Alias -Name "gost" -Value Go-StreamlitTemplate

Write-Host "Collaborative Project Functions Loaded:" -ForegroundColor Green
Write-Host "  New-CollaborativeProject (ncp) - Create general collaborative project" -ForegroundColor Cyan
Write-Host "  New-A360Project (na360)       - Create A360 ecosystem project" -ForegroundColor Cyan
Write-Host "  New-BaseProject (nbp)         - Create production mirror base project" -ForegroundColor Cyan
Write-Host "  New-PageCraftProject (npc)    - Create project with PageCraft integration" -ForegroundColor Cyan
Write-Host "  New-StreamlitProject (nst)    - Create Streamlit web app project" -ForegroundColor Cyan
Write-Host "  Go-A360 (goa360)             - Navigate to A360 projects" -ForegroundColor Cyan
Write-Host "  Go-Template (got)            - Navigate to template directory" -ForegroundColor Cyan
Write-Host "  Go-PageCraft (gopc)          - Navigate to PageCraft API directory" -ForegroundColor Cyan
Write-Host "  Go-StreamlitTemplate (gost)  - Navigate to Streamlit template directory" -ForegroundColor Cyan
