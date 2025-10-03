# Advanced Snapshot Sync for Active Development
# Designed for environments with frequent commits that affect remote developers

param(
    [Parameter(Mandatory=$false)]
    [switch]$WatchMode,
    
    [Parameter(Mandatory=$false)]
    [int]$CheckIntervalMinutes = 30,
    
    [Parameter(Mandatory=$false)]
    [string[]]$Repositories = @(),
    
    [Parameter(Mandatory=$false)]
    [switch]$ForceSync,
    
    [Parameter(Mandatory=$false)]
    [switch]$NotifyCollaborators
)

$BaseDir = Split-Path -Parent $PSScriptRoot
$ProdReposDir = Join-Path $BaseDir "production-repos"
$SnapshotsDir = Join-Path $BaseDir "collaborator-snapshots"
$LogFile = Join-Path $BaseDir "sync-log.txt"

function Write-SyncLog {
    param($Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Write-Host $logEntry -ForegroundColor Cyan
    Add-Content $LogFile $logEntry
}

function Get-LastCommitHash {
    param($RepoPath)
    if (Test-Path "$RepoPath\.git") {
        Push-Location $RepoPath
        try {
            return (git rev-parse HEAD).Trim()
        }
        catch {
            return $null
        }
        finally {
            Pop-Location
        }
    }
    return $null
}

function Test-RepoNeedsSync {
    param($RepoName, $ProdPath, $SnapshotPath)
    
    # Force sync if requested
    if ($ForceSync) { return $true }
    
    # Sync if snapshot doesn't exist
    if (-not (Test-Path $SnapshotPath)) { return $true }
    
    # Check if production repo has new commits
    $prodCommit = Get-LastCommitHash $ProdPath
    $lastSyncFile = Join-Path $SnapshotPath ".last-sync-commit"
    
    if (Test-Path $lastSyncFile) {
        $lastSyncCommit = Get-Content $lastSyncFile -Raw
        if ($prodCommit -ne $lastSyncCommit.Trim()) {
            Write-SyncLog "New commits detected in $RepoName"
            return $true
        }
    } else {
        # No sync record, assume needs sync
        return $true
    }
    
    return $false
}

function Sync-Repository {
    param($RepoName, $ProdPath, $SnapshotPath)
    
    Write-SyncLog "Syncing $RepoName..."
    
    # Pull latest changes from remote first
    if (Test-Path "$ProdPath\.git") {
        Write-Host "  Updating from remote repository..." -ForegroundColor Yellow
        Push-Location $ProdPath
        try {
            git fetch origin 2>&1 | Out-Null
            $pullResult = git pull origin main 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ Repository updated from remote" -ForegroundColor Green
            } else {
                Write-Host "  ⚠ Could not pull from remote (using local state): $pullResult" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "  ⚠ Git pull failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        finally {
            Pop-Location
        }
    }
    
    # Remove existing snapshot
    if (Test-Path $SnapshotPath) {
        Remove-Item $SnapshotPath -Recurse -Force
    }
    
    # Create fresh snapshot
    Copy-Item $ProdPath $SnapshotPath -Recurse -Force
    
    # Clean up sensitive files
    $sensitivePatterns = @("*.env", "*.key", "*.pem", ".env.*", "secrets.*", "config/production.*", "node_modules", "__pycache__", ".pytest_cache", "*.log")
    foreach ($pattern in $sensitivePatterns) {
        Get-ChildItem $SnapshotPath -Recurse -Name $pattern -ErrorAction SilentlyContinue | 
            ForEach-Object { 
                $itemPath = Join-Path $SnapshotPath $_
                if (Test-Path $itemPath) {
                    Remove-Item $itemPath -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
    }
    
    # Remove .git directory
    if (Test-Path "$SnapshotPath\.git") {
        Remove-Item "$SnapshotPath\.git" -Recurse -Force
    }
    
    # Record the commit hash for tracking
    $currentCommit = Get-LastCommitHash $ProdPath
    if ($currentCommit) {
        Set-Content (Join-Path $SnapshotPath ".last-sync-commit") $currentCommit
    }
    
    # Add enhanced collaborator README
    $currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    @"
# $RepoName Snapshot - UPDATED

This is an **updated** snapshot of the production repository for collaborator reference.

🔄 **ACTIVE DEVELOPMENT NOTICE**
This repository is being actively developed with frequent commits. This snapshot was automatically updated to reflect the latest changes.

**DO NOT EDIT DIRECTLY** - This is for reference only.

## Production Repository Location
Production development happens in: ../production-repos/$RepoName

## Snapshot Information
- **Last Updated**: $currentTime
- **Commit Hash**: $currentCommit
- **Sync Type**: $(if ($ForceSync) { "Forced Manual Sync" } else { "Automatic Update" })
- **Source**: Live production repository

## For Collaborators
- ✅ This snapshot provides the LATEST realistic reference environment
- ✅ Use this code as a reference for understanding the current system state
- ✅ Check this snapshot regularly as it updates with active development
- ✅ Create separate feature branches/repositories for your contributions
- ⚠️  Request access to production repositories if you need to make core changes

## Development Notes
Since this is an actively developed project:
1. **Check for updates regularly** - New snapshots may be available
2. **Reference latest commits** - Your work should align with current state
3. **Coordinate changes** - Communicate with core team about major features
4. **Stay synchronized** - Pull latest snapshots before starting new work

## File Changes
The following types of files have been automatically removed for security:
- Environment files (.env, .env.*)
- Secrets and keys (*.key, *.pem, secrets.*)
- Production configuration files
- Build artifacts (node_modules, __pycache__)
- Log files

## Need Updates?
If you need a more recent snapshot, contact the core team or check if automated sync is running.

---
*Auto-generated by Active Development Sync System*
"@ | Set-Content "$SnapshotPath\COLLABORATOR_README.md"
    
    Write-SyncLog "✓ $RepoName synced successfully"
    return $true
}

function Start-WatchMode {
    Write-SyncLog "Starting watch mode (checking every $CheckIntervalMinutes minutes)..."
    Write-Host "Press Ctrl+C to stop watching" -ForegroundColor Yellow
    
    while ($true) {
        try {
            $syncCount = 0
            $ReposToCheck = if ($Repositories.Count -eq 0) {
                Get-ChildItem $ProdReposDir -Directory | Select-Object -ExpandProperty Name
            } else {
                $Repositories
            }
            
            foreach ($repo in $ReposToCheck) {
                $prodPath = Join-Path $ProdReposDir $repo
                $snapshotPath = Join-Path $SnapshotsDir $repo
                
                if ((Test-Path $prodPath) -and (Test-RepoNeedsSync $repo $prodPath $snapshotPath)) {
                    Sync-Repository $repo $prodPath $snapshotPath
                    $syncCount++
                }
            }
            
            if ($syncCount -gt 0) {
                Write-SyncLog "Watch cycle completed: $syncCount repositories updated"
                if ($NotifyCollaborators) {
                    # Here you could add notification logic (email, Slack, etc.)
                    Write-SyncLog "Collaborator notification would be sent here"
                }
            } else {
                Write-Host "." -NoNewline -ForegroundColor DarkGray  # Quiet heartbeat
            }
            
            Start-Sleep -Seconds ($CheckIntervalMinutes * 60)
        }
        catch {
            Write-SyncLog "Error in watch mode: $($_.Exception.Message)"
            Start-Sleep -Seconds 60  # Wait before retrying
        }
    }
}

# Main execution
Write-SyncLog "Starting Active Development Sync"

if ($WatchMode) {
    Start-WatchMode
} else {
    # Single sync run
    $ReposToSync = if ($Repositories.Count -eq 0) {
        Get-ChildItem $ProdReposDir -Directory | Select-Object -ExpandProperty Name
    } else {
        $Repositories
    }
    
    $syncedCount = 0
    foreach ($repo in $ReposToSync) {
        $prodPath = Join-Path $ProdReposDir $repo
        $snapshotPath = Join-Path $SnapshotsDir $repo
        
        if (Test-Path $prodPath) {
            if (Test-RepoNeedsSync $repo $prodPath $snapshotPath) {
                if (Sync-Repository $repo $prodPath $snapshotPath) {
                    $syncedCount++
                }
            } else {
                Write-SyncLog "$repo is up to date (no new commits)"
            }
        } else {
            Write-SyncLog "⚠ Production repository not found: $prodPath"
        }
    }
    
    Write-SyncLog "Sync completed: $syncedCount repositories updated"
}