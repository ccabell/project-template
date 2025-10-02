# Page Craft Bliss Forge API

Backend API for the Page Craft Bliss Forge project - A comprehensive web development platform that integrates with the GenAI platform ecosystem.

## Overview

This API serves as the backend for the page-craft-bliss-forge-main project and is designed to integrate seamlessly with the web-app-develop and genai-platform-develop projects.

## Features

- RESTful API endpoints
- Authentication & Authorization
- Database integration with MongoDB
- File upload capabilities
- Rate limiting and security middleware
- Comprehensive error handling
- Test coverage with Jest
- Code linting with ESLint

## Project Structure

```
page-craft-bliss-forge-api/
├── src/
│   ├── controllers/     # Request handlers
│   ├── middleware/      # Custom middleware
│   ├── models/          # Database models
│   ├── routes/          # API routes
│   ├── services/        # Business logic
│   ├── utils/           # Utility functions
│   └── server.js        # Entry point
├── tests/               # Test files
├── config/              # Configuration files
├── docs/                # Documentation
└── package.json
```

## Getting Started

### Prerequisites

- Node.js >= 18.0.0
- npm >= 8.0.0
- MongoDB (local or cloud instance)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

4. Configure your environment variables in `.env`

5. Start the development server:
   ```bash
   npm run dev
   ```

## Available Scripts

- `npm start` - Start production server
- `npm run dev` - Start development server with hot reload
- `npm test` - Run tests
- `npm run test:watch` - Run tests in watch mode
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues

## API Documentation

API documentation will be available at `/api/docs` when the server is running.

## Integration

This API is designed to integrate with:
- **page-craft-bliss-forge-main** - Frontend application
- **web-app-develop** - Web application development platform
- **genai-platform-develop** - GenAI platform services

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
NODE_ENV=development
PORT=3000
DATABASE_URL=mongodb://localhost:27017/page-craft-bliss-forge
JWT_SECRET=your-super-secret-jwt-key
JWT_EXPIRE=30d
CORS_ORIGIN=http://localhost:3000
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License.