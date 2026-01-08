# 🔄 Auto-Sync Setup Guide

## Overview
This guide will help you set up automatic synchronization from `news_feed` repository to `personal_blogv1/static/news_feed/`.

## What This Does
1. ✅ Daily news update runs in `news_feed` repo (via `update-news.yml`)
2. ✅ After successful update, automatically sync files to `personal_blogv1` repo (via `sync-to-blog.yml`)
3. ✅ Your website at https://zennote.app/news_feed/ always shows the latest news

## Prerequisites
You need to create a **GitHub Personal Access Token (PAT)** to allow the `news_feed` repo to push to `personal_blogv1` repo.

## Step 1: Create GitHub Personal Access Token

1. Go to GitHub Settings: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Fill in the form:
   - **Note**: `news_feed to personal_blogv1 sync`
   - **Expiration**: `No expiration` (or choose a long period)
   - **Select scopes**:
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)

4. Click **"Generate token"**
5. **IMPORTANT**: Copy the token immediately (you won't be able to see it again!)

## Step 2: Add Token to news_feed Repository Secrets

1. Go to your `news_feed` repository: https://github.com/yopitek/news_feed
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Fill in:
   - **Name**: `PERSONAL_BLOG_TOKEN`
   - **Secret**: Paste the token you just created
5. Click **"Add secret"**

## Step 3: Push the New Workflow File

Run these commands in your local `news_feed` repository:

```bash
cd "/Users/goooolai/Downloads/n8n project/1.RSSNews"

# Add the new workflow file
git add .github/workflows/sync-to-blog.yml

# Commit
git commit -m "Add auto-sync workflow to personal_blogv1"

# Push to GitHub
git push origin main
```

## Step 4: Test the Workflow

### Option A: Wait for Next Scheduled Update
The sync will automatically run after tomorrow's daily news update (00:00 UTC / 08:00 GMT+8).

### Option B: Manual Trigger (Immediate Test)
1. Go to: https://github.com/yopitek/news_feed/actions
2. Click on **"📰 Daily News Update"** workflow
3. Click **"Run workflow"** → **"Run workflow"** (green button)
4. Wait for it to complete
5. The **"🔄 Sync to Personal Blog"** workflow should automatically trigger
6. Check https://zennote.app/news_feed/ after a few minutes

## Step 5: Verify the Sync

After the workflow runs:
1. Check https://zennote.app/news_feed/ - should show today's date (2026-01-08)
2. Verify the news content is updated
3. Check the commit history in `personal_blogv1` repo for the auto-sync commit

## Workflow Explanation

### How It Works:
```yaml
workflow_run:
  workflows: ["📰 Daily News Update"]
  types:
    - completed
```
This triggers the sync workflow **after** the news update completes.

### What Gets Synced:
- `index.html` - Main news page
- `docs/*` - All files in docs directory (if exists)
- `output/*` - Generated news files (if exists)

### Where It Goes:
All files are copied to: `personal_blogv1/static/news_feed/`

## Troubleshooting

### Issue: Sync workflow doesn't trigger
**Solution**: 
- Make sure `PERSONAL_BLOG_TOKEN` secret is set correctly
- Check if the "Daily News Update" workflow completed successfully
- Manually trigger the sync workflow from Actions tab

### Issue: Permission denied when pushing
**Solution**:
- Verify the PAT has `repo` and `workflow` scopes
- Regenerate the token if needed
- Update the `PERSONAL_BLOG_TOKEN` secret

### Issue: Files not appearing on website
**Solution**:
- Check if Hugo builds the `static/` directory correctly
- Verify the files are in the correct path: `static/news_feed/`
- Clear browser cache and check https://zennote.app/news_feed/ again
- Check if your Hugo deployment workflow is running

## Manual Sync (If Needed)

If you need to manually sync files without waiting for automation:

```bash
# In news_feed directory
cd "/Users/goooolai/Downloads/n8n project/1.RSSNews"

# Go to Actions tab and manually trigger "🔄 Sync to Personal Blog"
# OR trigger via GitHub CLI:
gh workflow run sync-to-blog.yml
```

## Success Indicators

✅ You'll know it's working when:
1. Commits appear in `personal_blogv1` repo with message: "🔄 Auto-sync news_feed - YYYY-MM-DD"
2. https://zennote.app/news_feed/ shows today's date
3. News content is updated daily

## Next Steps

1. ✅ Create GitHub Personal Access Token
2. ✅ Add token to repository secrets as `PERSONAL_BLOG_TOKEN`
3. ✅ Push the `sync-to-blog.yml` workflow file
4. ✅ Test the workflow manually
5. ✅ Verify your website is updated

---

**Last Updated**: 2026-01-08  
**Status**: Ready to deploy
