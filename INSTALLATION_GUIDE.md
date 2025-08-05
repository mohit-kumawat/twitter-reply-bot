# 🚀 Repository Setup Guide

## Step 1: Create GitHub Repository

1. Go to [GitHub](https://github.com/mohit-kumawat)
2. Click the "+" icon in the top right corner
3. Select "New repository"
4. Fill in the details:
   - **Repository name**: `twitter-reply-bot`
   - **Description**: `🤖 Enhanced Twitter Reply Bot with AI-powered tweet selection and persona-based replies`
   - **Visibility**: Public (or Private if you prefer)
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click "Create repository"

## Step 2: Push to GitHub

After creating the repository on GitHub, run these commands in your terminal:

```bash
# Add the remote origin (replace with your actual repository URL)
git remote add origin https://github.com/mohit-kumawat/twitter-reply-bot.git

# Push the code to GitHub
git push -u origin main
```

## Step 3: Configure Your Bot

1. Copy the example config file:
   ```bash
   cp config.ini.example config.ini
   ```

2. Edit `config.ini` with your API keys:
   - Get Gemini API keys from [Google AI Studio](https://ai.google.dev/)
   - Get Twitter API keys from [Twitter Developer Portal](https://developer.twitter.com/)
   - Get TwitterAPI.io key from [TwitterAPI.io](https://twitterapi.io/)

3. Copy and customize the Twitter handles file:
   ```bash
   cp Top_Twitter_usernames.csv.example Top_Twitter_usernames.csv
   ```
   Then edit it with the Twitter handles you want to monitor.

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 5: Run the Bot

```bash
python reply_bot_new.py
```

## 🎉 You're Ready!

Your repository is now set up and ready to use. The bot will:
- Fetch tweets from your specified handles
- Use AI to filter for high-quality content
- Generate persona-based replies
- Show you options for approval before posting

## 📝 Next Steps

- Star the repository if you find it useful
- Consider adding more Twitter handles to monitor
- Customize the personas to match your style
- Monitor the analytics to optimize performance

---

**Need help?** Open an issue on GitHub or check the README for detailed documentation.