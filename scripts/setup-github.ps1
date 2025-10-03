# GitHub Setup Script for Project Template
# This script helps configure GitHub integration for new projects

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,
    
    [Parameter(Mandatory=$false)]
    [string]$GitHubUsername,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateRepo
)

Write-Host "Setting up GitHub integration for project: $ProjectName" -ForegroundColor Green

# Configure git if not already configured
$gitUser = git config --global user.name
$gitEmail = git config --global user.email

if (-not $gitUser) {
    $username = Read-Host "Enter your Git username"
    git config --global user.name $username
}

if (-not $gitEmail) {
    $email = Read-Host "Enter your Git email"
    git config --global user.email $email
}

# Add initial commit
if (Test-Path ".git") {
    Write-Host "Adding initial files to git..." -ForegroundColor Yellow
    git add .
    git commit -m "Initial project setup with template"
    
    # Set default branch to main
    git branch -M main
    
    if ($CreateRepo) {
        if (Get-Command gh -ErrorAction SilentlyContinue) {
            Write-Host "Creating GitHub repository..." -ForegroundColor Yellow
            gh repo create $ProjectName --public --source=. --remote=origin --push
        } else {
            Write-Host "GitHub CLI not found. Please install it or create repository manually:" -ForegroundColor Red
            Write-Host "1. Install GitHub CLI: winget install --id GitHub.cli" -ForegroundColor Cyan
            Write-Host "2. Or create repository manually at: https://github.com/new" -ForegroundColor Cyan
            Write-Host "3. Then run: git remote add origin https://github.com/$GitHubUsername/$ProjectName.git" -ForegroundColor Cyan
            Write-Host "4. And push: git push -u origin main" -ForegroundColor Cyan
        }
    } else {
        Write-Host "To connect to GitHub repository later:" -ForegroundColor Cyan
        Write-Host "git remote add origin https://github.com/[USERNAME]/$ProjectName.git" -ForegroundColor Cyan
        Write-Host "git push -u origin main" -ForegroundColor Cyan
    }
} else {
    Write-Host "No git repository found. Run 'git init' first." -ForegroundColor Red
}

Write-Host "GitHub setup completed!" -ForegroundColor Green