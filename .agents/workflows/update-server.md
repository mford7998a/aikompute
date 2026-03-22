---
description: How to log changes, push code, and update the remote server
---
# Logging and Pushing Changes

Whenever a task modifies the project codebase, you must explicitly perform these steps in order:

1. **Log the Changes**: Open `AGENT_LOG.md` and append a new section at the top of the "Change Log" detailing the files modified and the reason for the changes. Use the current date.
2. **Push to GitHub**: Commit the changes with an appropriate message and push them to the configured GitHub origin remote. Use the following command structure:
// turbo
```bash
git add .
git commit -m "docs: agent update to <description>"
git push origin main
```
3. **Provide Server Update Script**: At the very end of your final chat response to the user, you MUST explicitly provide them with this script block so they can update the production gateway.

```bash
cd ~/aikompute && sudo git stash && sudo git pull origin main && sudo docker compose -f docker-compose.prod.yml up -d --build && docker restart antigravity2api
```
