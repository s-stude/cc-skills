# Express.js MVC Project with Geo-Controller

## Project Overview
Express.js framework with MVC architecture using Handlebars view engine for airport job-related dynamic routing.

## Architecture
- **Framework**: Express.js
- **View Engine**: Handlebars
- **Testing**: Jest + Supertest
- **Structure**: MVC (Model-View-Controller)

## Key Features
- Dynamic geo-routing for airport job searches
- Multiple URL patterns for same content
- Comprehensive route listing at `/_urls`
- Empty views displaying original URLs

## Testing Commands
```bash
npm test
```

## Key Dependencies
- express
- express-handlebars
- jest
- supertest

## Notes
- Always think about the tasks and what steps you need to take to solve it. then write a todo list that will describe steps to solve the task. then solve the task by implementing todo items.
- All geo views are empty and display original URL
- Multiple URL patterns consolidated into single controller methods
- Error handling middleware implemented
- Static file serving configured
- Conditional server startup for testing