#!/usr/bin/env node

/**
 * A360 Scraping Platform - Deployment Script
 * 
 * This script helps deploy the platform to various hosting providers
 * Usage: npm run deploy:help
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PLATFORMS = {
  railway: 'Railway.app',
  vercel: 'Vercel', 
  render: 'Render.com',
  heroku: 'Heroku',
  docker: 'Docker (local)',
  pm2: 'PM2 (server)'
};

const COLORS = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${COLORS[color]}${message}${COLORS.reset}`);
}

function execCommand(command, description) {
  log(`\n🔧 ${description}...`, 'cyan');
  try {
    execSync(command, { stdio: 'inherit' });
    log(`✅ ${description} completed`, 'green');
  } catch (error) {
    log(`❌ ${description} failed: ${error.message}`, 'red');
    process.exit(1);
  }
}

function checkFile(filepath, description) {
  if (!fs.existsSync(filepath)) {
    log(`❌ Missing ${description}: ${filepath}`, 'red');
    return false;
  }
  log(`✅ Found ${description}`, 'green');
  return true;
}

function showHelp() {
  log('\n🚀 A360 Scraping Platform - Deployment Helper\n', 'bright');
  
  log('Available deployment platforms:', 'cyan');
  Object.entries(PLATFORMS).forEach(([key, name]) => {
    log(`  • ${key.padEnd(8)} - ${name}`, 'yellow');
  });
  
  log('\nUsage:', 'cyan');
  log('  npm run deploy:help                 # Show this help', 'yellow');
  log('  npm run deploy:check                # Check deployment readiness', 'yellow');
  log('  npm run deploy:railway              # Deploy to Railway', 'yellow');
  log('  npm run deploy:vercel               # Deploy to Vercel', 'yellow');
  log('  npm run deploy:docker               # Build Docker image', 'yellow');
  log('  npm run deploy:pm2                  # Deploy with PM2', 'yellow');
  
  log('\nPrerequisites:', 'cyan');
  log('  1. Set up Supabase database (run schema from database/supabase-schema.sql)', 'yellow');
  log('  2. Copy .env.example to .env and fill in your Supabase credentials', 'yellow');
  log('  3. Install the CLI for your chosen platform (railway, vercel, etc.)', 'yellow');
  log('  4. Run npm run deploy:check to verify setup', 'yellow');
  
  log('\nFor detailed instructions, see README-A360.md', 'magenta');
  log('');
}

function checkDeploymentReadiness() {
  log('\n🔍 Checking A360 deployment readiness...\n', 'bright');
  
  let issues = 0;
  
  // Check required files
  const requiredFiles = [
    ['package.json', 'Package configuration'],
    ['server.js', 'Main server file'],
    ['src/config/supabase.js', 'Supabase configuration'],
    ['src/services/a360ScrapingService.js', 'Core service'],
    ['src/frontend/App.tsx', 'React frontend'],
    ['database/supabase-schema.sql', 'Database schema'],
    ['.env.example', 'Environment template']
  ];
  
  requiredFiles.forEach(([filepath, description]) => {
    if (!checkFile(filepath, description)) issues++;
  });
  
  // Check environment
  if (!fs.existsSync('.env')) {
    log('⚠️  No .env file found - copy .env.example and fill in your values', 'yellow');
    issues++;
  } else {
    log('✅ Environment file exists', 'green');
  }
  
  // Check package.json scripts
  const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  const requiredScripts = ['build:frontend', 'start', 'dev'];
  
  requiredScripts.forEach(script => {
    if (!packageJson.scripts[script]) {
      log(`❌ Missing npm script: ${script}`, 'red');
      issues++;
    } else {
      log(`✅ Found npm script: ${script}`, 'green');
    }
  });
  
  // Check dependencies
  const requiredDeps = ['express', 'cors', 'helmet', '@supabase/supabase-js'];
  const requiredDevDeps = ['vite', '@vitejs/plugin-react', 'tailwindcss'];
  
  requiredDeps.forEach(dep => {
    if (!packageJson.dependencies || !packageJson.dependencies[dep]) {
      log(`❌ Missing dependency: ${dep}`, 'red');
      issues++;
    }
  });
  
  requiredDevDeps.forEach(dep => {
    if (!packageJson.devDependencies || !packageJson.devDependencies[dep]) {
      log(`❌ Missing dev dependency: ${dep}`, 'red');
      issues++;
    }
  });
  
  if (issues === 0) {
    log('\n🎉 All deployment checks passed! Ready to deploy.', 'green');
    log('   Run npm run deploy:<platform> to deploy to your chosen platform', 'cyan');
  } else {
    log(`\n⚠️  Found ${issues} issue(s) that need attention before deployment.`, 'yellow');
  }
  
  log('\nNext steps:', 'cyan');
  log('  1. Set up your Supabase database with the schema in database/supabase-schema.sql', 'yellow');
  log('  2. Configure your .env file with Supabase credentials', 'yellow');
  log('  3. Choose a deployment platform and follow the setup instructions', 'yellow');
  
  return issues === 0;
}

function deployToRailway() {
  log('\n🚂 Deploying to Railway...\n', 'bright');
  
  if (!checkFile('railway.json', 'Railway configuration')) {
    process.exit(1);
  }
  
  // Check if Railway CLI is installed
  try {
    execSync('railway --version', { stdio: 'ignore' });
  } catch {
    log('❌ Railway CLI not found. Install it with: npm install -g @railway/cli', 'red');
    process.exit(1);
  }
  
  execCommand('npm run build:frontend', 'Building frontend');
  execCommand('railway login', 'Logging in to Railway (if needed)');
  execCommand('railway deploy', 'Deploying to Railway');
  
  log('\n✅ Deployment to Railway completed!', 'green');
  log('   Your app should be available at the URL shown above.', 'cyan');
  log('   Remember to set your environment variables in the Railway dashboard.', 'yellow');
}

function deployToVercel() {
  log('\n▲ Deploying to Vercel...\n', 'bright');
  
  if (!checkFile('vercel.json', 'Vercel configuration')) {
    process.exit(1);
  }
  
  // Check if Vercel CLI is installed
  try {
    execSync('vercel --version', { stdio: 'ignore' });
  } catch {
    log('❌ Vercel CLI not found. Install it with: npm install -g vercel', 'red');
    process.exit(1);
  }
  
  execCommand('npm run build:frontend', 'Building frontend');
  execCommand('vercel --prod', 'Deploying to Vercel');
  
  log('\n✅ Deployment to Vercel completed!', 'green');
  log('   Remember to set your environment variables in the Vercel dashboard.', 'yellow');
}

function buildDocker() {
  log('\n🐳 Building Docker image...\n', 'bright');
  
  if (!checkFile('Dockerfile', 'Docker configuration')) {
    process.exit(1);
  }
  
  execCommand('docker build -t a360-scraping-platform .', 'Building Docker image');
  
  log('\n✅ Docker image built successfully!', 'green');
  log('   To run: docker run -p 5000:5000 --env-file .env a360-scraping-platform', 'cyan');
  log('   Or use: docker-compose up', 'cyan');
}

function deployWithPM2() {
  log('\n⚡ Deploying with PM2...\n', 'bright');
  
  // Check if PM2 is installed
  try {
    execSync('pm2 --version', { stdio: 'ignore' });
  } catch {
    log('❌ PM2 not found. Install it with: npm install -g pm2', 'red');
    process.exit(1);
  }
  
  execCommand('npm run build:frontend', 'Building frontend');
  execCommand('pm2 stop a360-app', 'Stopping existing PM2 process (if any)');
  execCommand('pm2 delete a360-app', 'Deleting existing PM2 process (if any)');
  execCommand('pm2 start server.js --name a360-app', 'Starting with PM2');
  execCommand('pm2 save', 'Saving PM2 configuration');
  
  log('\n✅ PM2 deployment completed!', 'green');
  log('   Manage with: pm2 status, pm2 logs a360-app, pm2 restart a360-app', 'cyan');
}

// Main script
const command = process.argv[2];

switch (command) {
  case 'help':
    showHelp();
    break;
  case 'check':
    checkDeploymentReadiness();
    break;
  case 'railway':
    if (checkDeploymentReadiness()) deployToRailway();
    break;
  case 'vercel':
    if (checkDeploymentReadiness()) deployToVercel();
    break;
  case 'docker':
    if (checkDeploymentReadiness()) buildDocker();
    break;
  case 'pm2':
    if (checkDeploymentReadiness()) deployWithPM2();
    break;
  default:
    log('❌ Unknown command. Use npm run deploy:help for available options.', 'red');
    process.exit(1);
}