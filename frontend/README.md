# RAG Pipeline Frontend

Modern React TypeScript frontend for the RAG Pipeline API.

## Features

- 🚀 Built with Vite for fast development
- ⚛️ React 18 with TypeScript
- 🎨 Tailwind CSS for styling
- 🔄 Real-time updates via WebSocket
- 📊 React Query for data fetching
- 🌙 Dark mode support

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment

The frontend proxies API requests to `http://localhost:8000` during development. This is configured in `vite.config.ts`.

## Structure

```
src/
├── components/     # Reusable UI components
├── hooks/         # Custom React hooks
├── lib/           # API client and utilities
├── pages/         # Page components
├── styles/        # CSS files
└── types/         # TypeScript type definitions
```

## Pages

- **Dashboard** - Overview statistics and recent activity
- **Search** - Search code snippets with filters
- **Sources** - Browse documentation sources
- **Crawl Jobs** - Monitor and manage crawls
- **Settings** - Configure the application

## WebSocket

The app connects to the WebSocket endpoint for real-time updates. The connection is managed by the `useWebSocket` hook which handles:

- Auto-reconnection
- Message parsing
- Subscription management
- Connection state

## Styling

The app uses Tailwind CSS with a custom color palette that supports both light and dark modes. Colors are defined as CSS variables in `src/styles/index.css`.