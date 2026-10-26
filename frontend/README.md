# BookJob frontend

React/Vite single-page interface for the FastAPI backend in `../backend`.

## Development

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to the backend at `http://127.0.0.1:8000`.
Run `npm run lint` and `npm run build` to check and compile the interface.

For deployment, authentication, Google OAuth consent, and Gmail setup, follow the project-level [`README.md`](../README.md). Hosting this frontend by itself does not provide the backend API or secure email sending.
