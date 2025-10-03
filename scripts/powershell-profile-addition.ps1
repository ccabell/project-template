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
    
    $templateScript = "C:\Users\Chris\Projects\project-template-master\scripts\create-new-project.ps1"
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
    
    $a360Script = "C:\Users\Chris\Projects\project-template-master\scripts\create-a360-project.ps1"
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
    
    $baseScript = "C:\Users\Chris\Projects\project-template-master\scripts\new-base-project.ps1"
    & $baseScript -Name $Name -Description $Description -IncludePageCraft:$IncludePageCraft -CreateGitHub:$CreateGitHub -RunAsAdmin:$RunAsAdmin
}

# Function to quickly navigate to template
function Go-Template {
    Set-Location "C:\Users\Chris\Projects\project-template-master"
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
    
    $templateScript = "C:\Users\Chris\Projects\project-template-master\scripts\create-new-project.ps1"
    & $templateScript -ProjectName $Name -ProjectPath $Path -ProjectDescription $Description -NodeJS:$NodeJS -Python:$Python -IncludePageCraftAccess -InitializeGit -CreateGitHubRepo:$CreateGitHubRepo -GitHubUsername "ccabell"
}

# Aliases for even quicker access
Set-Alias -Name "ncp" -Value New-CollaborativeProject
Set-Alias -Name "na360" -Value New-A360Project
Set-Alias -Name "nbp" -Value New-BaseProject
Set-Alias -Name "npc" -Value New-PageCraftProject
Set-Alias -Name "goa360" -Value Go-A360
Set-Alias -Name "got" -Value Go-Template
Set-Alias -Name "gopc" -Value Go-PageCraft

Write-Host "Collaborative Project Functions Loaded:" -ForegroundColor Green
Write-Host "  New-CollaborativeProject (ncp) - Create general collaborative project" -ForegroundColor Cyan
Write-Host "  New-A360Project (na360)       - Create A360 ecosystem project" -ForegroundColor Cyan
Write-Host "  New-BaseProject (nbp)         - Create production mirror base project" -ForegroundColor Cyan
Write-Host "  New-PageCraftProject (npc)    - Create project with PageCraft integration" -ForegroundColor Cyan
Write-Host "  Go-A360 (goa360)             - Navigate to A360 projects" -ForegroundColor Cyan
Write-Host "  Go-Template (got)            - Navigate to template directory" -ForegroundColor Cyan
Write-Host "  Go-PageCraft (gopc)          - Navigate to PageCraft API directory" -ForegroundColor Cyan
