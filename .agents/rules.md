# Antigravity Agent Rules for AI Inference Gateway

These are the primary directives for the Antigravity agent when working on this repository:

1. **Log All Changes**: After completing any task or making modifications to the codebase, system configuration, or infrastructure, you MUST automatically append an entry to `AGENT_LOG.md` detailing the changes. Use the proper date format and be specific about the files changed and the purpose of the modifications.

2. **Push to GitHub**: After writing to the `AGENT_LOG.md`, you MUST automatically create a commit summarizing the changes and push them to the GitHub remote repository. Do not wait for the user to ask you to do this.

3. **Provide Server Update Script**: At the very end of your task completion message (after writing to the log and pushing to GitHub), you MUST provide the user with the exact script below so they can easily copy and paste it to update their remote server and restart the gateway containers:

```bash
cd ~/aikompute && sudo git stash && sudo git pull origin main && sudo docker compose -f docker-compose.prod.yml up -d --build && docker restart antigravity2api
```

This ensures the remote production server stays perfectly in sync with the repository.
