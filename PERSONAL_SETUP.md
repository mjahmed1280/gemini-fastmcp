# steps.md

## Git Setup Checklist: Personal Project on Work Machine

Use these steps whenever you start a new personal project on a work machine to ensure you use your **personal Git identity and SSH keys**, not your work credentials.

---

## 1. Initialize Repository and Configure Identity (Local Only)

Run the following commands **inside the new project directory**.  
This overrides any global (work) Git configuration for this repository only.

```bash
git init
git config user.name "Jakaria Ahmed"
git config user.email "mjahmed1280@gmail.com"
```

## 2. Add Remote Using SSH Host Alias

Do **not** use the standard GitHub HTTPS or SSH URL.  
Always use the SSH host alias defined in your `~/.ssh/config` (for example: `github-personal`).

```bash
# Format:
# git remote add origin git@<SSH_ALIAS>:<GITHUB_USERNAME>/<REPOSITORY_NAME>.git

git remote add origin git@github-personal:mjahmed1280/repo-name.git
```

## 3. Commit and Push to GitHub

Follow the standard Git workflow to create the initial commit and push it to GitHub.

```bash
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```

## 4. Verify Git Identity Before Committing

At any time, verify which email Git will use for commits in the current repository.

```bash
git config user.email
```
Expected output:

```text
mjahmed1280@gmail.com
```