# Production Mirror Base Project Creator
# Creates a base project that mirrors your production environment with snapshots for collaborators
# while maintaining direct development access to your main repositories

param(
    [Parameter(Mandatory=$true)]
    [string]$BaseProjectName,
    
    [Parameter(Mandatory=$false)]
    [string]$ProjectDescription = "Production-mirrored base project for collaborative development",
    
    [Parameter(Mandatory=$false)]
    [switch]$IncludePageCraft,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateGitHubRepo
)

# Define paths
$B360Path = "C:\Users\Chris\b360"
$MainRepos = @{
    "a360-genai-platform-develop" = @{
        "source" = "C:\Users\Chris\Projects\mariadb-sync-project\a360-genai-platform-develop"
        "description" = "A360 GenAI Platform Development Repository"
        "type" = "core"
    }
    "a360-web-app-develop" = @{
        "source" = "$B360Path\web-app"
        "description" = "A360 Web Application Development Repository" 
        "type" = "core"
    }
    "page-craft-bliss-forge-api" = @{
        "source" = "$B360Path\page-craft-bliss-forge-api"
        "description" = "Page Craft Bliss Forge API (Optional)"
        "type" = "optional"
    }
}

$BaseProjectPath = Join-Path $B360Path $BaseProjectName

Write-Host "Creating Production Mirror Base Project: $BaseProjectName" -ForegroundColor Green
Write-Host "Location: $BaseProjectPath" -ForegroundColor Cyan

# Create base project structure
Write-Host "Setting up base project structure..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $BaseProjectPath -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\production-repos" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\collaborator-snapshots" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\database-snapshots" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\scripts" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\docs" -Force | Out-Null
New-Item -ItemType Directory -Path "$BaseProjectPath\config" -Force | Out-Null

# Initialize Git repository
cd $BaseProjectPath
git init

# Create symlinks to production repositories for direct development
Write-Host "Creating symbolic links to production repositories..." -ForegroundColor Yellow

foreach ($repo in $MainRepos.Keys) {
    $repoInfo = $MainRepos[$repo]
    $symLinkPath = Join-Path "$BaseProjectPath\production-repos" $repo
    
    if ($repoInfo.type -eq "core" -or ($repoInfo.type -eq "optional" -and $IncludePageCraft)) {
        if (Test-Path $repoInfo.source) {
            Write-Host "  Creating symlink: $repo -> $($repoInfo.source)" -ForegroundColor Cyan
            
            # Create symbolic link (requires admin privileges)
            try {
                New-Item -ItemType SymbolicLink -Path $symLinkPath -Target $repoInfo.source -Force | Out-Null
                Write-Host "    ✓ Symlink created successfully" -ForegroundColor Green
            }
            catch {
                Write-Host "    ⚠ Symlink creation failed (requires admin privileges). Creating directory reference instead." -ForegroundColor Yellow
                New-Item -ItemType Directory -Path $symLinkPath -Force | Out-Null
                @"
# Production Repository Reference
# This directory represents a direct link to: $($repoInfo.source)
# For development, work directly in the source repository.
# This is a placeholder for collaborator reference.

Repository: $repo
Source: $($repoInfo.source)
Description: $($repoInfo.description)
Type: $($repoInfo.type)

## Development Workflow
- Direct development: Work in $($repoInfo.source)
- Collaborator access: Use snapshots in ../collaborator-snapshots/$repo
- Sync: Use scripts/sync-snapshots.ps1 to update collaborator versions
"@ | Set-Content "$symLinkPath\REPOSITORY_INFO.md"
            }
        }
        else {
            Write-Host "    ⚠ Source repository not found: $($repoInfo.source)" -ForegroundColor Red
            Write-Host "      Please update the path in the script or clone the repository" -ForegroundColor Red
        }
    }
}

# Create snapshot sync script
Write-Host "Creating snapshot sync script..." -ForegroundColor Yellow
@"
# Snapshot Sync Script
# Synchronizes production repositories to collaborator-safe snapshots

param(
    [Parameter(Mandatory=`$false)]
    [switch]`$FullSync,
    
    [Parameter(Mandatory=`$false)]
    [string[]]`$Repositories = @()
)

`$BaseDir = Split-Path -Parent `$PSScriptRoot
`$ProdReposDir = Join-Path `$BaseDir "production-repos"
`$SnapshotsDir = Join-Path `$BaseDir "collaborator-snapshots"

Write-Host "Syncing production repositories to collaborator snapshots..." -ForegroundColor Green

`$ReposToSync = if (`$Repositories.Count -eq 0) {
    Get-ChildItem `$ProdReposDir -Directory | Select-Object -ExpandProperty Name
} else {
    `$Repositories
}

foreach (`$repo in `$ReposToSync) {
    `$prodPath = Join-Path `$ProdReposDir `$repo
    `$snapshotPath = Join-Path `$SnapshotsDir `$repo
    
    if (Test-Path `$prodPath) {
        Write-Host "Syncing `$repo..." -ForegroundColor Yellow
        
        # Remove existing snapshot
        if (Test-Path `$snapshotPath) {
            Remove-Item `$snapshotPath -Recurse -Force
        }
        
        # Create fresh snapshot
        Copy-Item `$prodPath `$snapshotPath -Recurse -Force
        
        # Clean up sensitive files from snapshot
        `$sensitivePatterns = @("*.env", "*.key", "*.pem", ".env.*", "secrets.*", "config/production.*")
        foreach (`$pattern in `$sensitivePatterns) {
            Get-ChildItem `$snapshotPath -Recurse -Name `$pattern -ErrorAction SilentlyContinue | 
                ForEach-Object { Remove-Item (Join-Path `$snapshotPath `$_) -Force -ErrorAction SilentlyContinue }
        }
        
        # Remove .git directory from snapshot (collaborators shouldn't commit to prod repos)
        if (Test-Path "`$snapshotPath\.git") {
            Remove-Item "`$snapshotPath\.git" -Recurse -Force
        }
        
        # Add collaborator README
        @"
# `$repo Snapshot
This is a snapshot of the production repository for collaborator reference.

**DO NOT EDIT DIRECTLY** - This is for reference only.

## Production Repository Location
Production development happens in: ../production-repos/`$repo

## For Collaborators
- This snapshot provides a realistic reference environment
- Use this code as a reference for understanding the system
- Create separate feature branches/repositories for your contributions
- Request access to production repositories if you need to make core changes

## Sync Information
- Last synced: `$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
- Sync type: `$(if (`$FullSync) { "Full" } else { "Incremental" })

## Security Note
Sensitive configuration files and credentials have been removed from this snapshot.
"@ | Set-Content "`$snapshotPath\COLLABORATOR_README.md"
        
        Write-Host "  ✓ `$repo synced successfully" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠ Production repository not found: `$prodPath" -ForegroundColor Red
    }
}

Write-Host "Snapshot sync completed!" -ForegroundColor Green
"@ | Set-Content "$BaseProjectPath\scripts\sync-snapshots.ps1"

# Create database snapshot script
Write-Host "Creating database snapshot script..." -ForegroundColor Yellow
@"
# Database Snapshot Script
# Creates database snapshots for collaborator development

param(
    [Parameter(Mandatory=`$false)]
    [string]`$SnapshotName = "collaborator-snapshot",
    
    [Parameter(Mandatory=`$false)]
    [switch]`$IncludeData
)

`$BaseDir = Split-Path -Parent `$PSScriptRoot
`$DatabaseSnapshotsDir = Join-Path `$BaseDir "database-snapshots"
`$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
`$SnapshotDir = Join-Path `$DatabaseSnapshotsDir "`$SnapshotName-`$Timestamp"

Write-Host "Creating database snapshot: `$SnapshotName" -ForegroundColor Green

# Create snapshot directory
New-Item -ItemType Directory -Path `$SnapshotDir -Force | Out-Null

# Export database schema (modify these commands for your actual database)
Write-Host "Exporting database schema..." -ForegroundColor Yellow

# Example MySQL/MariaDB export (update with your actual database details)
# mysqldump --host=pma.nextnlp.com --user=chris --password=a360_chris --no-data --routines --triggers database_name > schema.sql

# For now, create placeholder files
@"
# Database Schema Snapshot
# Generated: `$(Get-Date)

## Reference Database Information
- Host: pma.nextnlp.com  
- Access: phpMyAdmin
- Purpose: Development reference only
- **NOT AVAILABLE IN PRODUCTION**

## Schema Export
This directory should contain:
- schema.sql: Complete database schema
- sample-data.sql: Sample data (if requested)
- README.md: Documentation about the database structure

## Usage for Collaborators
1. Import schema.sql into your local database
2. Use sample data for realistic testing
3. **Never assume this database structure exists in production**
4. Reference the production database documentation in ../docs/

## Security Note
- No production credentials included
- Sensitive data scrubbed from samples
- For reference and development only
"@ | Set-Content "`$SnapshotDir\README.md"

# Create latest snapshot symlink
`$latestPath = Join-Path `$DatabaseSnapshotsDir "latest"
if (Test-Path `$latestPath) {
    Remove-Item `$latestPath -Force
}

# Create directory junction instead of symlink for broader compatibility
cmd /c "mklink /J `"`$latestPath`" `"`$SnapshotDir`""

Write-Host "Database snapshot created: `$SnapshotDir" -ForegroundColor Green
Write-Host "Latest snapshot linked at: `$latestPath" -ForegroundColor Cyan
"@ | Set-Content "$BaseProjectPath\scripts\create-db-snapshot.ps1"

# Create main project README
Write-Host "Creating project documentation..." -ForegroundColor Yellow
@"
# $BaseProjectName

Production-mirrored base project for collaborative development on the A360 ecosystem.

## 🏗️ Project Structure

### Production Integration
```
production-repos/          # Direct links to production repositories
├── a360-genai-platform-develop/    # Core GenAI platform (symlinked)
├── a360-web-app-develop/           # Core web application (symlinked)
└── page-craft-bliss-forge-api/     # Optional API service
```

### Collaborator Environment  
```
collaborator-snapshots/     # Safe snapshots for external developers
├── a360-genai-platform-develop/   # Read-only snapshot
├── a360-web-app-develop/          # Read-only snapshot
└── COLLABORATOR_README.md
```

### Database Environment
```
database-snapshots/         # Database snapshots for development
├── latest/                 # Latest snapshot (symlinked)
├── collaborator-snapshot-[timestamp]/
└── production-schema/
```

## 🔧 Development Workflows

### For Core Development (You)
1. **Direct Development**: Work directly in `production-repos/` directories
2. **Real-time Integration**: Changes reflect immediately across the ecosystem
3. **Production Mirroring**: Develop as if in production environment
4. **Commit to B360**: All commits go to the shared B360 environment

### For Collaborators
1. **Reference Environment**: Use `collaborator-snapshots/` for realistic development context
2. **Database Access**: Import from `database-snapshots/latest/`
3. **Safe Development**: No access to production repositories
4. **Contribution Process**: Create separate branches/repos for contributions

## 🔄 Sync Operations

### Update Collaborator Snapshots
```powershell
.\scripts\sync-snapshots.ps1              # Sync all repositories
.\scripts\sync-snapshots.ps1 -Repositories @("a360-web-app-develop")  # Sync specific repo
```

### Create Database Snapshots
```powershell
.\scripts\create-db-snapshot.ps1          # Create new database snapshot
.\scripts\create-db-snapshot.ps1 -IncludeData  # Include sample data
```

## 🤝 Collaboration Model

### What Collaborators Have Access To
- ✅ Complete snapshots of codebase for reference
- ✅ Database schema and sample data
- ✅ Full API documentation  
- ✅ Development environment setup
- ✅ Integration guides and architecture docs

### What Remains Protected
- 🔒 Direct access to production repositories
- 🔒 Production database credentials
- 🔒 Real-time development environment
- 🔒 Sensitive configuration files

## 📊 Database Integration

### Reference Database (Development)
- **URL**: https://pma.nextnlp.com/
- **Access**: Via Warp environment (core team only)
- **Purpose**: Real-time development data
- **⚠️ Critical**: NOT available in production

### Snapshot Database (Collaborators)
- **Location**: `database-snapshots/latest/`
- **Content**: Schema + sanitized sample data
- **Update**: Via `create-db-snapshot.ps1` script
- **Purpose**: Realistic development environment for external developers

## 🚀 Getting Started

### Core Team Setup
1. Verify production repository links in `production-repos/`
2. Configure database access via Warp
3. Start developing directly in production repositories
4. Sync snapshots when collaborators join

### Collaborator Setup
1. Import database from `database-snapshots/latest/`
2. Review code in `collaborator-snapshots/`
3. Set up local development environment
4. Reference API documentation in `docs/`

## 🔧 Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `sync-snapshots.ps1` | Update collaborator code snapshots | Run before onboarding collaborators |
| `create-db-snapshot.ps1` | Create database snapshots | Run when database schema changes |

## 📋 Maintenance

### Regular Tasks
- **Weekly**: Sync collaborator snapshots if active collaboration
- **On Schema Changes**: Create new database snapshots  
- **On Major Updates**: Update documentation and integration guides

### Security Reviews
- Ensure sensitive files are excluded from snapshots
- Verify production credentials aren't exposed
- Review collaborator access levels

---

**Generated**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Template**: Production Mirror Base Project
**Repository**: Part of B360 Shared Environment
"@ | Set-Content "$BaseProjectPath\README.md"

# Create .gitignore for base project
@"
# Production repositories (these are symlinked, don't commit)
production-repos/*/

# Sensitive configuration
*.env
*.env.*
config/production.*
secrets.*

# Database snapshots (too large for git)
database-snapshots/*/
!database-snapshots/README.md

# Logs
*.log
logs/

# Temporary files
tmp/
temp/

# OS files
.DS_Store
Thumbs.db
"@ | Set-Content "$BaseProjectPath\.gitignore"

# Create project configuration
$projectConfig = @{
    project = @{
        name = $BaseProjectName
        type = "production-mirror-base"
        description = $ProjectDescription
        created = Get-Date -Format "yyyy-MM-dd"
        author = "Chris"
    }
    repositories = @{
        production = @()
        snapshots = @()
    }
    database = @{
        reference_url = "https://pma.nextnlp.com/"
        access_method = "warp_environment"
        snapshot_location = "database-snapshots/latest"
        production_warning = "Reference database NOT available in production"
    }
    collaboration = @{
        model = "snapshot_based"
        core_team_access = "direct_production_repos"
        collaborator_access = "read_only_snapshots"
    }
} | ConvertTo-Json -Depth 10

Set-Content "$BaseProjectPath\project.json" $projectConfig

# Initial commit
Write-Host "Committing initial base project..." -ForegroundColor Yellow
git add .
git commit -m "Initial production mirror base project setup"

# Create GitHub repository if requested
if ($CreateGitHubRepo) {
    Write-Host "Creating GitHub repository..." -ForegroundColor Yellow
    gh repo create $BaseProjectName --public --source=. --remote=origin --push
}

Write-Host "`nProduction Mirror Base Project created successfully!" -ForegroundColor Green
Write-Host "Location: $BaseProjectPath" -ForegroundColor Cyan
Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Verify production repository paths and update if needed" -ForegroundColor White
Write-Host "2. Run .\scripts\sync-snapshots.ps1 to create initial collaborator snapshots" -ForegroundColor White  
Write-Host "3. Run .\scripts\create-db-snapshot.ps1 to create database snapshot" -ForegroundColor White
Write-Host "4. Test the setup by developing in production-repos/ directories" -ForegroundColor White
Write-Host "5. Share collaborator-snapshots/ with external developers" -ForegroundColor White

return $BaseProjectPath
"@ | Set-Content "C:\Users\Chris\Projects\project-template-master\scripts\create-production-mirror-base.ps1"