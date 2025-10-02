# Multi-stage Dockerfile for A360 Scraping Platform
# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY package*.json ./
RUN npm ci --only=production

# Copy frontend source and build
COPY src/frontend ./src/frontend/
COPY vite.config.js ./
COPY tailwind.config.js ./
RUN npm run build:frontend

# Stage 2: Production backend + built frontend
FROM node:18-alpine AS production

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create app directory and user
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
WORKDIR /app

# Copy package files and install production dependencies
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy backend source code
COPY src/ ./src/
COPY database/ ./database/
COPY server.js ./

# Copy built frontend from previous stage
COPY --from=frontend-build /app/dist/frontend ./dist/frontend

# Set ownership to nodejs user
RUN chown -R nodejs:nodejs /app
USER nodejs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "http.get('http://localhost:5000/health', (res) => { process.exit(res.statusCode === 200 ? 0 : 1) })" || exit 1

# Start application with dumb-init
CMD ["dumb-init", "node", "server.js"]