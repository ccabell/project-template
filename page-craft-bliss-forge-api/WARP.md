# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is the **Page Craft Bliss Forge API** - a Node.js/Express backend API that serves as part of a comprehensive web development platform ecosystem. It integrates with:
- **page-craft-bliss-forge-main** (Frontend application)
- **web-app-develop** (Web application development platform) 
- **genai-platform-develop** (GenAI platform services)

The API is currently in early development with basic server setup, middleware, and placeholder routes.

## Essential Commands

### Development
```bash
npm run dev          # Start development server with hot reload (nodemon)
npm start           # Start production server
```

### Testing
```bash
npm test            # Run all tests with Jest
npm run test:watch  # Run tests in watch mode
```

### Code Quality
```bash
npm run lint        # Check code with ESLint
npm run lint:fix    # Auto-fix ESLint issues
```

### Single Test Execution
```bash
npx jest tests/server.test.js              # Run specific test file
npx jest --testNamePattern="health"        # Run tests matching pattern
npx jest --watch tests/server.test.js      # Watch specific test file
```

## Architecture & Structure

### Current Architecture
The codebase follows a layered Express.js architecture with separation of concerns:

- **Entry Point**: `src/server.js` - Express app setup with comprehensive middleware stack
- **Middleware Layer**: Security (helmet), CORS, rate limiting, logging (morgan), error handling
- **Route Layer**: Currently placeholder routes in `src/routes/index.js` 
- **Utility Layer**: Database connection utilities in `src/utils/database.js`
- **Planned Layers**: Controllers, Models, Services (directory structure exists but not implemented)

### Key Architectural Patterns
- **Modular routing** - Routes are organized by feature/resource
- **Centralized error handling** - Custom error middleware with environment-aware responses
- **Configuration-driven** - Extensive use of environment variables
- **Database abstraction** - MongoDB with Mongoose (connection utility implemented)

### Middleware Stack (in order)
1. Helmet (security headers)
2. CORS (configurable origins)
3. Rate limiting (configurable, applied to /api routes)
4. Morgan logging
5. Body parsing (JSON/URL-encoded, 10MB limit)
6. Custom routes
7. 404 handler
8. Global error handler

## Environment Setup

### Required Environment Variables
Copy `.env.example` to `.env` and configure:
- `NODE_ENV` - Environment (development/production)
- `PORT` - Server port (default: 3000)
- `DATABASE_URL` - MongoDB connection string
- `JWT_SECRET` - JWT signing key
- `CORS_ORIGIN` - Allowed CORS origins
- Rate limiting and file upload configurations

### Prerequisites
- Node.js >= 18.0.0
- npm >= 8.0.0
- MongoDB (local or cloud)

## Development Patterns

### Error Handling
The application uses a comprehensive error handling strategy:
- Custom error middleware in `src/middleware/errorHandler.js`
- Handles Mongoose errors (CastError, ValidationError, duplicate keys)
- Handles JWT errors (invalid/expired tokens)
- Development vs production error responses (stack traces only in dev)

### Code Style
- ESLint with Standard config
- Space before function parentheses required
- No trailing commas
- Console statements allowed in development, warnings in production

### API Structure
- Base API route: `/api/v1`
- Health check: `/health`
- Rate limiting applied to all `/api` routes
- Standardized JSON responses with success/error structure

## Integration Notes

### External Platform Integration Points
Environment variables are pre-configured for integration with:
- GenAI Platform API (`GENAI_PLATFORM_API_URL`, `GENAI_PLATFORM_API_KEY`)
- Web App Develop API (`WEB_APP_DEVELOP_API_URL`, `WEB_APP_DEVELOP_API_KEY`)

### Database Strategy
- MongoDB with Mongoose ODM
- Connection utility with graceful shutdown handling
- Database connection logging with host/port/database name display

### Development Status
The project is in early setup phase:
- Basic Express server with middleware configured
- Placeholder API routes (not yet implementing business logic)
- Test structure established
- Directory structure ready for MVC implementation
- Database connection utilities ready but not yet used in routes

When implementing new features, follow the established patterns:
1. Create models in `src/models/`
2. Implement business logic in `src/services/`
3. Create controllers in `src/controllers/`
4. Add routes to `src/routes/` and mount in `src/routes/index.js`
5. Add corresponding tests in `tests/`