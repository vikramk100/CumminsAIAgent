<# 
.SYNOPSIS
    Deploy Cummins AI Agent to Google Cloud Run
.DESCRIPTION
    This script deploys the backend API to Cloud Run and optionally
    deploys the frontend to Cloud Storage for static hosting.
.PARAMETER ProjectId
    GCP Project ID (default: workorderaiagent)
.PARAMETER Region
    GCP Region (default: us-central1)
.PARAMETER SkipSecrets
    Skip creating secrets (if already created)
.EXAMPLE
    .\deploy-gcp.ps1
.EXAMPLE
    .\deploy-gcp.ps1 -ProjectId "my-project" -Region "us-east1"
#>

param(
    [string]$ProjectId = "workorderaiagent",
    [string]$Region = "us-central1",
    [switch]$SkipSecrets,
    [switch]$FrontendOnly,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cummins AI Agent - GCP Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project: $ProjectId"
Write-Host "Region:  $Region"
Write-Host ""

# Check if gcloud is installed
try {
    $null = Get-Command gcloud -ErrorAction Stop
} catch {
    Write-Host "ERROR: gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Red
    exit 1
}

# Set project
Write-Host "Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Enable required APIs
Write-Host "Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Create secrets (if not skipping)
if (-not $SkipSecrets) {
    Write-Host ""
    Write-Host "Setting up secrets..." -ForegroundColor Yellow
    
    # Load .env file
    $envFile = Join-Path $PSScriptRoot ".env"
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile
        
        foreach ($line in $envContent) {
            if ($line -match "^MONGODB_PASSWORD=(.+)$") {
                $mongoPassword = $Matches[1]
                Write-Host "Creating MONGODB_PASSWORD secret..."
                echo $mongoPassword | gcloud secrets create mongodb-password --data-file=- 2>$null
                if ($LASTEXITCODE -ne 0) {
                    echo $mongoPassword | gcloud secrets versions add mongodb-password --data-file=-
                }
            }
            if ($line -match "^MONGODB_URI=(.+)$") {
                $mongoUri = $Matches[1]
                Write-Host "Creating MONGODB_URI secret..."
                echo $mongoUri | gcloud secrets create mongodb-uri --data-file=- 2>$null
                if ($LASTEXITCODE -ne 0) {
                    echo $mongoUri | gcloud secrets versions add mongodb-uri --data-file=-
                }
            }
        }
    } else {
        Write-Host "WARNING: .env file not found. You'll need to set secrets manually." -ForegroundColor Yellow
    }
}

# Deploy Backend to Cloud Run
if (-not $FrontendOnly) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Deploying Backend to Cloud Run..." -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    # Build and deploy using Cloud Build
    gcloud builds submit --config cloudbuild.yaml --substitutions=COMMIT_SHA=$(git rev-parse --short HEAD)
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Backend deployed successfully!" -ForegroundColor Green
        
        # Get the service URL
        $serviceUrl = gcloud run services describe cummins-ai-agent --region $Region --format "value(status.url)"
        Write-Host "Backend URL: $serviceUrl" -ForegroundColor Cyan
        Write-Host "API Docs:    $serviceUrl/docs" -ForegroundColor Cyan
    } else {
        Write-Host "Backend deployment failed!" -ForegroundColor Red
        exit 1
    }
}

# Deploy Frontend to Cloud Storage (optional)
if (-not $BackendOnly) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan  
    Write-Host "Deploying Frontend to Cloud Storage..." -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    $bucketName = "$ProjectId-frontend"
    
    # Create bucket if not exists
    gsutil ls -b gs://$bucketName 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creating storage bucket: $bucketName"
        gsutil mb -p $ProjectId -l $Region gs://$bucketName
        gsutil web set -m index.html -e index.html gs://$bucketName
        gsutil iam ch allUsers:objectViewer gs://$bucketName
    }
    
    # Update manifest.json with backend URL
    $manifestPath = Join-Path $PSScriptRoot "webapp\manifest.json"
    if (Test-Path $manifestPath) {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        
        # Get backend URL
        $backendUrl = gcloud run services describe cummins-ai-agent --region $Region --format "value(status.url)" 2>$null
        if ($backendUrl) {
            # Update dataSources URI
            if ($manifest.psobject.Properties["sap.app"]) {
                $manifest."sap.app".dataSources.mainService.uri = "$backendUrl/api/v1/"
            }
            $manifest | ConvertTo-Json -Depth 10 | Set-Content $manifestPath
            Write-Host "Updated manifest.json with backend URL: $backendUrl"
        }
    }
    
    # Upload frontend files
    Write-Host "Uploading frontend files..."
    gsutil -m rsync -r -d webapp/ gs://$bucketName/
    
    Write-Host ""
    Write-Host "Frontend deployed successfully!" -ForegroundColor Green
    Write-Host "Frontend URL: https://storage.googleapis.com/$bucketName/index.html" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Test the API: $serviceUrl/docs"
Write-Host "2. Update frontend API URL if needed"
Write-Host "3. Set up custom domain (optional)"
Write-Host ""
