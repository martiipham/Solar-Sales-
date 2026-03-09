# ☀️ Solar Swarm — Agent Command Board

Persistent Kanban board for orchestrating your autonomous AI agent swarm.  
Drag-and-drop tasks, assign agents, use AI to generate new tasks.

## Deploy to Vercel (5 minutes, free)

### Option A — GitHub + Vercel (recommended, auto-deploys on every push)

1. Push this folder to a GitHub repo:
   ```bash
   cd solar-swarm-board
   git init
   git add .
   git commit -m "Solar Swarm board"
   git remote add origin https://github.com/YOUR_USERNAME/solar-swarm-board.git
   git push -u origin main
   ```

2. Go to [vercel.com](https://vercel.com) → **Add New Project** → Import your repo  
3. Framework: **Vite** (auto-detected) — click **Deploy**  
4. Done. You'll get a URL like `https://solar-swarm-board.vercel.app`

### Option B — Vercel CLI (one command)

```bash
npm install -g vercel
cd solar-swarm-board
vercel
```
Follow the prompts. Takes ~90 seconds.

### Option C — Netlify drag-and-drop

```bash
cd solar-swarm-board
npm install
npm run build
```
Then drag the `dist/` folder to [app.netlify.com/drop](https://app.netlify.com/drop).

---

## Local development

```bash
npm install
npm run dev
# Opens at http://localhost:5173
```

## Adding your Anthropic API key

Click **⚙** in the top-right → paste your key from [console.anthropic.com](https://console.anthropic.com).  
The key is stored in your browser's `localStorage` only — never sent anywhere except Anthropic's API.

## Features

- **Drag & drop** tasks between 6 columns (Backlog → Queued → In Progress → Review → Done → Blocked)
- **WIP limits** on In Progress (4) and Queued (8) to enforce focus
- **Agent assignment** — assign each task to one of 12 Solar Swarm agents
- **✦ AI Tasks** — describe what you're working on and Claude generates 5 specific tasks
- **Persistent** — all changes auto-save to `localStorage`, survives refreshes and restarts
- **Filter** by agent, priority, or search text
- **⚙ Settings** — configure your Anthropic API key for AI task generation

## Data persistence

All board data lives in `localStorage` under the key `swarm-kanban-tasks`.  
If you want cloud sync across devices, the next step is wiring in Supabase or Firebase
(see `src/App.jsx` — the `store` object is the only thing you'd need to replace).
