# 🤖 Enhanced Twitter Reply Bot

An intelligent Twitter reply bot that uses AI to find high-quality tweets and generate engaging, personalized replies using different personas.

## ✨ Features

### 🎯 Smart Tweet Selection
- **AI-Powered Filtering**: Uses Gemini AI to filter out low-quality tweets and one-liners
- **Quality Standards**: Prioritizes thought-provoking content, complex questions, and meaningful discussions
- **Time-Based Filtering**: Only considers tweets from the last 12 hours
- **Engagement Scoring**: Ranks tweets by engagement potential

### 🎭 Multiple Personas
- **System Thinker**: Analytical, connects patterns, uses frameworks
- **Candid Realist**: Direct, honest, practical, no-nonsense
- **Witty Observer**: Clever, humorous, memorable observations
- **Supportive Mentor**: Encouraging, insightful, builds authority
- **Contrarian Challenger**: Respectfully challenges ideas, sparks discussion

### 📊 Analytics & Tracking
- **Performance Monitoring**: Tracks reply engagement and persona effectiveness
- **Real-time Dashboard**: Shows live statistics and performance metrics
- **Engagement Tracking**: Monitors likes, retweets, and replies on posted content
- **Quality Scoring**: Evaluates reply quality before posting

### 🛡️ Safety & Quality Control
- **Content Safety**: Built-in toxicity and spam detection
- **Context Appropriateness**: Ensures replies match the tone of original tweets
- **Rate Limiting**: Respects Twitter API limits and posting guidelines
- **Manual Review**: User approval required before posting

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Twitter API credentials
- Gemini API key
- TwitterAPI.io key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mohit-kumawat/twitter-reply-bot.git
cd twitter-reply-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your API keys:
```bash
cp bot_config.ini.example bot_config.ini
# Edit bot_config.ini with your API keys
```

4. Add Twitter handles to monitor:
```bash
cp twitter_handles.csv.example twitter_handles.csv
# Edit twitter_handles.csv with handles you want to monitor
```

5. Run the bot:
```bash
python twitter_reply_bot.py
```

## ⚙️ Configuration

### API Keys Required
- **Twitter API**: Consumer key, secret, access token, access token secret
- **Gemini API**: Two API keys for redundancy
- **TwitterAPI.io**: For enhanced tweet fetching

### Settings
- **MY_TWITTER_HANDLE**: Your Twitter username
- **CSV_FILE_PATH**: Path to CSV file containing Twitter handles to monitor (twitter_handles.csv)
- **REPLIED_IDS_CACHE_FILE**: Cache file to avoid duplicate replies

## 📈 How It Works

1. **Tweet Collection**: Fetches recent tweets from specified Twitter handles
2. **AI Filtering**: Gemini AI evaluates tweets for quality and engagement potential
3. **Reply Generation**: Creates multiple reply options using different personas
4. **Quality Scoring**: Evaluates each reply for relevance, engagement, and appropriateness
5. **User Review**: Presents options to user for manual approval
6. **Performance Tracking**: Monitors engagement on posted replies

## 🎛️ Usage

When you run the bot, you'll see:

```
📱 TWEET #1/15 from @username • 2hrs ago
🔥 Engagement Score: 85.2/100
🤖 Gemini: Thought-provoking discussion about AI ethics
💡 Suggested angle: Share contrasting perspective from industry experience

📝 ORIGINAL TWEET:
┌────────────────────────────────────────┐
│ AI is changing everything, but are we  │
│ considering the ethical implications?  │
└────────────────────────────────────────┘

💬 GENERATED REPLIES:

┌─ OPTION 1 ─ CONTRARIAN CHALLENGER ─ SCORE: 78.5/100 ─┐
│ While ethics are crucial, the bigger question is     │
│ whether we're moving fast enough to stay competitive │
│ globally while maintaining our values.               │
└───────────────────────────────────────────────────────┘

🎯 ACTIONS:
   y1, y2, y3... → Post reply number
   i1, i2, i3... → Improve reply number  
   n → Skip this tweet
   s → Skip all remaining tweets
```

## 📊 Analytics Dashboard

The bot provides real-time analytics:
- Daily posting limits and usage
- Persona performance rankings
- Engagement metrics
- API usage tracking

## 🛡️ Safety Features

- **Content Filtering**: Automatically rejects toxic or inappropriate content
- **Context Awareness**: Ensures replies match the tone of original tweets
- **Rate Limiting**: Respects platform limits (17 replies per 24 hours)
- **Manual Approval**: All replies require user confirmation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This bot is for educational and personal use. Please ensure compliance with Twitter's Terms of Service and API usage guidelines. Use responsibly and respect the Twitter community.

## 🙏 Acknowledgments

- Built with [Gemini AI](https://ai.google.dev/) for intelligent content analysis
- Uses [TwitterAPI.io](https://twitterapi.io/) for enhanced tweet fetching
- Powered by [Tweepy](https://www.tweepy.org/) for Twitter API integration

---

**Made with ❤️ by [Mohit Kumawat](https://github.com/mohit-kumawat)**