// PM2 Ecosystem Configuration for A360 Scraping Platform

module.exports = {
  apps: [
    {
      name: 'a360-scraping-platform',
      script: 'server.js',
      instances: 'max',
      exec_mode: 'cluster',
      
      // Environment variables
      env: {
        NODE_ENV: 'development',
        PORT: 5000,
        CORS_ORIGIN: 'http://localhost:3000'
      },
      
      env_production: {
        NODE_ENV: 'production',
        PORT: 5000,
        CORS_ORIGIN: 'https://yourdomain.com'
      },
      
      env_staging: {
        NODE_ENV: 'staging',
        PORT: 5001,
        CORS_ORIGIN: 'https://staging.yourdomain.com'
      },
      
      // Logging
      log_file: './logs/a360-combined.log',
      out_file: './logs/a360-out.log',
      error_file: './logs/a360-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // Auto-restart configuration
      watch: false,
      ignore_watch: ['node_modules', 'logs', 'dist', '.git'],
      max_memory_restart: '500M',
      
      // Advanced settings
      kill_timeout: 5000,
      wait_ready: true,
      listen_timeout: 8000,
      
      // Health monitoring
      health_check_grace_period: 10000,
      
      // Auto-restart on crash
      autorestart: true,
      max_restarts: 10,
      min_uptime: 10000,
      
      // Cron-style restarts (optional)
      // cron_restart: '0 2 * * *', // Restart daily at 2 AM
      
      // Environment loading
      source_map_support: true,
      
      // Combine logs when using cluster mode
      merge_logs: true
    }
  ],

  // Deployment configuration
  deploy: {
    production: {
      user: 'deploy',
      host: ['your-server.com'],
      ref: 'origin/main',
      repo: 'git@github.com:yourusername/a360-scraping-platform.git',
      path: '/var/www/a360-scraping-platform',
      'pre-deploy-local': '',
      'post-deploy': 'npm install && npm run build:frontend && pm2 reload ecosystem.config.js --env production',
      'pre-setup': 'apt-get update && apt-get install -y git nodejs npm',
      env: {
        NODE_ENV: 'production'
      }
    },

    staging: {
      user: 'deploy', 
      host: ['staging-server.com'],
      ref: 'origin/develop',
      repo: 'git@github.com:yourusername/a360-scraping-platform.git',
      path: '/var/www/a360-scraping-staging',
      'post-deploy': 'npm install && npm run build:frontend && pm2 reload ecosystem.config.js --env staging',
      env: {
        NODE_ENV: 'staging'
      }
    }
  }
};