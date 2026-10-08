# Kulya frontend

Next.js App Router with React and TypeScript. Run `npm ci`, then `npm run dev`.
The API proxy uses `BACKEND_URL` (default `http://localhost:8000`); see the root
README for database setup and synthetic demo accounts.

## Code ownership

- `src/app`: route entry points. Patient, nurse and doctor URLs remain stable.
- `src/features`: clinical records, notifications and nutrition workflows.
- `src/components`: shared frame, feedback, forms and UI primitives.
- `src/lib/api.ts`: HTTP transport and tab-scoped credentials.
- `src/lib/types.ts` and feature `types.ts`: API contracts, with no transport or UI.
- `src/lib`: authentication, loading hooks, localization, formatting and validation.

Import the module that owns a symbol directly. Feature components may use shared
components and library code; shared components must not depend on feature UI.
Keep numerical and validation rules separate from React and browser APIs.
All authorization remains enforced by Django.

## Verification

```sh
npm run typecheck
npm run lint
npm run format:check
npm test
npm run e2e
```

Use `npm run format` when editing. Browser tests need the isolated API/frontend
described in [NUTRITION_WORKFLOW.md](../NUTRITION_WORKFLOW.md). Architecture tests
protect dependency directions and reject runtime import cycles.
