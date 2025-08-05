#!/usr/bin/env python
"""
Enhanced Reply Bot - Advanced Twitter reply automation with intelligent selection and optimization.
"""

import logging
import pandas as pd
import requests
import google.generativeai as genai
import tweepy
from datetime import datetime, timedelta, UTC
import json
import time
import configparser
import sys
import sqlite3
import os
import re
import hashlib
import random
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import math
from bot_utilities import load_config, reset_daily_counters_if_needed, increment_tweet_count, increment_api_call_count, log_current_stats

# --- Enhanced Configuration ---
config = load_config()
reset_daily_counters_if_needed(config)

# API Keys from config file
api_keys_config = config['API_KEYS']
GEMINI_API_KEYS = [
    api_keys_config['GEMINI_API_KEY_1'],
    api_keys_config['GEMINI_API_KEY_2']
]
TWITTER_API_IO_KEY = api_keys_config['TWITTER_API_IO_KEY']
APP_API_KEY = api_keys_config['APP_API_KEY']
APP_API_KEY_SECRET = api_keys_config['APP_API_KEY_SECRET']
APP_ACCESS_TOKEN = api_keys_config['APP_ACCESS_TOKEN']
APP_ACCESS_TOKEN_SECRET = api_keys_config['APP_ACCESS_TOKEN_SECRET']

# Settings from config file
settings_config = config['SETTINGS']
MY_TWITTER_HANDLE = settings_config['MY_TWITTER_HANDLE']
CSV_FILE_PATH = settings_config.get('CSV_FILE_PATH')
REPLIED_IDS_CACHE_FILE = settings_config['REPLIED_IDS_CACHE_FILE']

# Enhanced Configuration
DB_FILE = 'twitter_bot.db'
ANALYTICS_FILE = 'bot_analytics.json'
PERFORMANCE_FILE = 'reply_performance.json'

# --- Enhanced Persona System ---
ENHANCED_PERSONAS = {
    'system_thinker': {
        'style': 'analytical, connects patterns, uses frameworks',
        'triggers': ['problem', 'pattern', 'system', 'process', 'framework', 'structure'],
        'templates': ['This reminds me of', 'The underlying pattern here', 'From a systems perspective'],
        'weight': 1.0
    },
    'candid_realist': {
        'style': 'direct, honest, no-nonsense, practical',
        'triggers': ['reality', 'truth', 'practical', 'real', 'honest', 'direct'],
        'templates': ['The reality is', 'Let\'s be honest', 'In practice'],
        'weight': 1.0
    },
    'witty_observer': {
        'style': 'clever, humorous, memorable one-liners',
        'triggers': ['irony', 'contradiction', 'humor', 'funny', 'clever'],
        'templates': ['Plot twist:', 'The real question is', 'Ironically'],
        'weight': 1.2  # Higher weight for engagement
    },
    'supportive_mentor': {
        'style': 'encouraging, insightful, builds authority',
        'triggers': ['learn', 'grow', 'improve', 'develop', 'advice'],
        'templates': ['Here\'s what I\'ve learned', 'In my experience', 'Consider this'],
        'weight': 1.1
    },
    'contrarian_challenger': {
        'style': 'respectfully challenges ideas, sparks discussion',
        'triggers': ['but', 'however', 'challenge', 'question', 'alternative'],
        'templates': ['But what if', 'Have you considered', 'The counterargument'],
        'weight': 1.3  # Highest weight for engagement
    }
}

# --- Initializations ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
current_gemini_key_index = 0  # Start with first API key (index 0)
genai.configure(api_key=GEMINI_API_KEYS[current_gemini_key_index])

if not CSV_FILE_PATH:
    logging.critical("🔴 CSV_FILE_PATH is not set in config.ini.")
    sys.exit()

try:
    client = tweepy.Client(
        consumer_key=APP_API_KEY, consumer_secret=APP_API_KEY_SECRET,
        access_token=APP_ACCESS_TOKEN, access_token_secret=APP_ACCESS_TOKEN_SECRET
    )
    logging.info("✅ Successfully initialized Tweepy Client for posting.")
except Exception as e:
    logging.critical(f"🔴 Failed to initialize Tweepy Client. Check credentials in config.ini. Error: {e}")
    sys.exit()

# --- Database Setup ---
class BotDatabase:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.setup_database()
    
    def setup_database(self):
        """Initialize SQLite database with required tables."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Tweet analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tweet_analysis (
                tweet_id TEXT PRIMARY KEY,
                author TEXT,
                text TEXT,
                engagement_score REAL,
                created_at TEXT,
                likes INTEGER,
                retweets INTEGER,
                replies INTEGER,
                analyzed_at TEXT
            )
        ''')
        
        # Reply performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reply_performance (
                reply_id TEXT PRIMARY KEY,
                original_tweet_id TEXT,
                persona TEXT,
                reply_text TEXT,
                posted_at TEXT,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                last_checked TEXT
            )
        ''')
        
        # Author interaction history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS author_interactions (
                author TEXT,
                interaction_count INTEGER DEFAULT 0,
                last_interaction TEXT,
                avg_engagement REAL DEFAULT 0,
                best_persona TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_tweet_analysis(self, tweet_data):
        """Store tweet analysis in database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO tweet_analysis 
            (tweet_id, author, text, engagement_score, created_at, likes, retweets, replies, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tweet_data['id'], tweet_data['author'], tweet_data['text'],
            tweet_data['engagement_score'], tweet_data['created_at'],
            tweet_data['likes'], tweet_data['retweets'], tweet_data['replies'],
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def store_reply_performance(self, reply_data):
        """Store reply performance data in database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO reply_performance 
            (reply_id, original_tweet_id, persona, reply_text, posted_at, likes, retweets, replies, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reply_data['reply_id'], reply_data['original_tweet_id'], reply_data['persona'],
            reply_data['reply_text'], reply_data['posted_at'], reply_data['likes'],
            reply_data['retweets'], reply_data['replies'], reply_data['last_checked']
        ))
        
        conn.commit()
        conn.close()
    
    def get_replies_for_engagement_check(self, hours_old=1):
        """Get replies that need engagement metrics updated."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Get replies posted at least 1 hour ago that haven't been checked recently
        cutoff_time = (datetime.now() - timedelta(hours=hours_old)).isoformat()
        
        cursor.execute('''
            SELECT reply_id, original_tweet_id, persona, reply_text, posted_at, likes, retweets, replies
            FROM reply_performance 
            WHERE posted_at < ? AND (last_checked IS NULL OR last_checked < ?)
            ORDER BY posted_at DESC
        ''', (cutoff_time, cutoff_time))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            'reply_id': row[0],
            'original_tweet_id': row[1],
            'persona': row[2],
            'reply_text': row[3],
            'posted_at': row[4],
            'likes': row[5],
            'retweets': row[6],
            'replies': row[7]
        } for row in results]
    
    def update_reply_engagement(self, reply_id, likes, retweets, replies):
        """Update engagement metrics for a specific reply."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE reply_performance 
            SET likes = ?, retweets = ?, replies = ?, last_checked = ?
            WHERE reply_id = ?
        ''', (likes, retweets, replies, datetime.now().isoformat(), reply_id))
        
        conn.commit()
        conn.close()
    
    def get_persona_performance_stats(self):
        """Get performance statistics for each persona."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT persona, 
                   COUNT(*) as total_replies,
                   AVG(likes + retweets * 2 + replies * 3) as avg_engagement,
                   SUM(likes + retweets * 2 + replies * 3) as total_engagement
            FROM reply_performance 
            WHERE last_checked IS NOT NULL
            GROUP BY persona
            ORDER BY avg_engagement DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            'persona': row[0],
            'total_replies': row[1],
            'avg_engagement': row[2] or 0,
            'total_engagement': row[3] or 0
        } for row in results]

    def get_author_history(self, author):
        """Get interaction history with specific author."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT interaction_count, last_interaction, avg_engagement, best_persona
            FROM author_interactions WHERE author = ?
        ''', (author,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'interaction_count': result[0],
                'last_interaction': result[1],
                'avg_engagement': result[2],
                'best_persona': result[3]
            }
        return None

# --- Rate Limiting System ---
class RateLimiter:
    def __init__(self):
        self.api_calls_per_minute = 60
        self.tweets_per_hour = 50
        self.last_api_call = 0
        self.last_tweet_post = 0
        self.api_call_count = 0
        self.tweet_count = 0
        self.reset_time = time.time()
    
    def can_make_api_call(self):
        """Check if we can make an API call."""
        now = time.time()
        
        # Reset counters every minute
        if now - self.reset_time > 60:
            self.api_call_count = 0
            self.reset_time = now
        
        return self.api_call_count < self.api_calls_per_minute
    
    def can_post_tweet(self):
        """Check if we can post a tweet."""
        now = time.time()
        return now - self.last_tweet_post > 72  # 72 seconds between tweets
    
    def record_api_call(self):
        """Record an API call."""
        self.api_call_count += 1
        self.last_api_call = time.time()
    
    def record_tweet_post(self):
        """Record a tweet post."""
        self.tweet_count += 1
        self.last_tweet_post = time.time()

# --- Content Safety System ---
class ContentSafety:
    def __init__(self):
        self.toxic_patterns = [
            r'\b(hate|stupid|idiot|moron)\b',
            r'\b(kill|die|death)\b',
            r'\b(fuck|shit|damn)\b'
        ]
        self.spam_patterns = [
            r'(follow me|check out|link in bio)',
            r'(buy now|limited time|act fast)',
            r'(dm me|message me)'
        ]
    
    def check_toxicity(self, text):
        """Check if text contains toxic content."""
        text_lower = text.lower()
        for pattern in self.toxic_patterns:
            if re.search(pattern, text_lower):
                return False
        return True
    
    def check_spam_patterns(self, text):
        """Check if text contains spam patterns."""
        text_lower = text.lower()
        for pattern in self.spam_patterns:
            if re.search(pattern, text_lower):
                return False
        return True
    
    def check_context_appropriateness(self, reply_text, original_tweet):
        """Check if reply is contextually appropriate."""
        # Basic sentiment matching
        original_lower = original_tweet.lower()
        reply_lower = reply_text.lower()
        
        # Don't reply with humor to serious topics
        serious_keywords = ['death', 'tragedy', 'accident', 'disaster', 'crisis']
        humor_keywords = ['lol', 'haha', 'funny', 'joke']
        
        if any(keyword in original_lower for keyword in serious_keywords):
            if any(keyword in reply_lower for keyword in humor_keywords):
                return False
        
        return True
    
    def safety_check(self, reply_text, original_tweet):
        """Comprehensive safety check."""
        checks = [
            self.check_toxicity(reply_text),
            self.check_spam_patterns(reply_text),
            self.check_context_appropriateness(reply_text, original_tweet)
        ]
        return all(checks)

# --- Analytics System ---
class BotAnalytics:
    def __init__(self, analytics_file=ANALYTICS_FILE):
        self.analytics_file = analytics_file
        self.load_analytics()
    
    def load_analytics(self):
        """Load analytics from file."""
        try:
            with open(self.analytics_file, 'r') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {
                'persona_performance': {},
                'posting_times': [],
                'engagement_rates': [],
                'best_performing_replies': [],
                'author_success_rates': {}
            }
    
    def save_analytics(self):
        """Save analytics to file."""
        with open(self.analytics_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def track_reply_performance(self, reply_data):
        """Track performance of a posted reply."""
        persona = reply_data['persona']
        if persona not in self.data['persona_performance']:
            self.data['persona_performance'][persona] = {
                'total_replies': 0,
                'total_engagement': 0,
                'avg_engagement': 0
            }
        
        self.data['persona_performance'][persona]['total_replies'] += 1
        self.save_analytics()
    
    def get_best_performing_personas(self, db=None):
        """Get personas ranked by performance from database."""
        if db:
            # Get real performance data from database
            return db.get_persona_performance_stats()
        else:
            # Fallback to file-based data
            personas = self.data['persona_performance']
            return sorted(personas.items(), key=lambda x: x[1]['avg_engagement'], reverse=True)
    
    def update_persona_weights(self):
        """Update persona weights based on performance."""
        best_personas = self.get_best_performing_personas()
        for persona_name, performance in best_personas:
            if persona_name in ENHANCED_PERSONAS:
                # Boost weight for high-performing personas
                base_weight = ENHANCED_PERSONAS[persona_name]['weight']
                performance_multiplier = 1 + (performance['avg_engagement'] / 100)
                ENHANCED_PERSONAS[persona_name]['weight'] = base_weight * performance_multiplier

# --- Enhanced Tweet Analysis ---
def calculate_engagement_score(tweet):
    """Calculate comprehensive engagement score for a tweet."""
    likes = tweet.get('likeCount', 0)
    retweets = tweet.get('retweetCount', 0)
    replies = tweet.get('replyCount', 0)
    
    # Get tweet age
    created_at_str = tweet.get('createdAt', '')
    if created_at_str:
        try:
            # Handle different date formats from Twitter API
            if 'T' in created_at_str and ('Z' in created_at_str or '+' in created_at_str[-6:]):
                # ISO format: 2025-07-23T01:13:50+00:00 or 2025-07-23T01:13:50Z
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            else:
                # Twitter format: Wed Jul 23 01:13:50 +0000 2025
                # Replace +0000 with +00:00 for proper timezone parsing
                date_str = created_at_str.replace('+0000', '+00:00')
                created_at = datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
            
            age_hours = (datetime.now(UTC) - created_at).total_seconds() / 3600
            recency_multiplier = max(0.1, 1 - (age_hours / 24))  # Decay over 24 hours
        except (ValueError, TypeError):
            recency_multiplier = 0.5
    else:
        recency_multiplier = 0.5
    
    # Calculate engagement rate
    author_followers = tweet.get('author', {}).get('followersCount', 1)
    if author_followers == 0:
        author_followers = 1
    
    # Weight different engagement types
    weighted_engagement = (likes * 1) + (retweets * 3) + (replies * 5)
    engagement_rate = weighted_engagement / max(author_followers, 1)
    
    # Boost score for tweets with questions or controversial topics
    text = tweet.get('text', '').lower()
    question_boost = 1.2 if '?' in text else 1.0
    controversy_keywords = ['disagree', 'wrong', 'unpopular', 'controversial', 'debate']
    controversy_boost = 1.3 if any(keyword in text for keyword in controversy_keywords) else 1.0
    
    # Final score calculation
    base_score = engagement_rate * 1000 * recency_multiplier
    final_score = base_score * question_boost * controversy_boost
    
    return min(final_score, 100)  # Cap at 100

def analyze_tweet_content(tweet_text):
    """Analyze tweet content for persona selection."""
    text_lower = tweet_text.lower()
    
    # Count trigger words for each persona
    persona_scores = {}
    for persona_name, persona_data in ENHANCED_PERSONAS.items():
        score = 0
        for trigger in persona_data['triggers']:
            score += text_lower.count(trigger)
        persona_scores[persona_name] = score * persona_data['weight']
    
    return persona_scores

def get_tweet_age_hours(tweet):
    """Get tweet age in hours."""
    created_at_str = tweet.get('createdAt', '')
    if created_at_str:
        try:
            # Handle different date formats from Twitter API
            if 'T' in created_at_str and ('Z' in created_at_str or '+' in created_at_str[-6:]):
                # ISO format: 2025-07-23T01:13:50+00:00 or 2025-07-23T01:13:50Z
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            else:
                # Twitter format: Wed Jul 23 01:13:50 +0000 2025
                # Replace +0000 with +00:00 for proper timezone parsing
                date_str = created_at_str.replace('+0000', '+00:00')
                created_at = datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
            
            return (datetime.now(UTC) - created_at).total_seconds() / 3600
        except (ValueError, TypeError):
            return 24
    return 24

# --- Enhanced Reply Generation ---
def select_optimal_persona(tweet_text, author_history=None):
    """Select the best persona for a tweet based on content and history."""
    content_scores = analyze_tweet_content(tweet_text)
    
    # If we have author history, prefer personas that worked well before
    if author_history and author_history['best_persona']:
        best_persona = author_history['best_persona']
        if best_persona in content_scores:
            content_scores[best_persona] *= 1.5  # Boost historical best performer
    
    # Select top 2 personas
    sorted_personas = sorted(content_scores.items(), key=lambda x: x[1], reverse=True)
    return [persona[0] for persona in sorted_personas[:2]]

def generate_batch_replies(tweets_batch):
    """Generate replies for multiple tweets in a single API call."""
    if not tweets_batch:
        return {}
    
    # Prepare batch prompt
    tweets_for_prompt = []
    for tweet in tweets_batch:
        tweet_id = str(tweet['id'])
        tweet_text = tweet.get('text', '')
        # Extract author with better fallback logic
        author_info = tweet.get('author', {})
        author = (
            author_info.get('username') or 
            author_info.get('userName') or 
            author_info.get('screen_name') or
            tweet.get('username') or
            tweet.get('userName') or
            'unknown_user'
        )
        
        # Get optimal personas for this tweet
        optimal_personas = select_optimal_persona(tweet_text)
        
        tweets_for_prompt.append({
            'tweet_id': tweet_id,
            'text': tweet_text,
            'author': author,
            'suggested_personas': optimal_personas[:2]
        })
    
    prompt = f"""
    You are an expert Twitter reply generator. Generate high-quality, substantive replies for the following tweets.
    
    For each tweet, create 2 replies using the suggested personas. Each reply must:
    - Be substantive (50-250 characters) - avoid one-liners unless exceptionally clever
    - Add genuine value, insight, or perspective to the conversation
    - Directly engage with the tweet's core message or theme
    - Feel authentic and human, not generic or robotic
    - Avoid hashtags, excessive questions, and promotional language
    - Be engaging and likely to generate meaningful discussion
    
    QUALITY STANDARDS:
    - Don't just agree or disagree - add WHY or HOW
    - Share relevant experience, frameworks, or alternative perspectives
    - Build on the original thought rather than just restating it
    - Use specific examples or concrete details when possible
    - Avoid generic phrases like "great point", "so true", "exactly this"
    
    Available personas and their styles:
    - system_thinker: Analytical, connects patterns, uses frameworks, sees bigger picture
    - candid_realist: Direct, honest, practical, cuts through fluff with real-world perspective
    - witty_observer: Clever, insightful humor, memorable observations with substance
    - supportive_mentor: Encouraging, shares wisdom, builds on ideas constructively
    - contrarian_challenger: Respectfully questions assumptions, offers alternative viewpoints
    
    Input tweets:
    {json.dumps(tweets_for_prompt, indent=2)}
    
    Output format - JSON object with tweet_id as keys:
    {{
      "tweet_id_1": {{
        "reply_a": {{"persona": "persona_name", "text": "reply text"}},
        "reply_b": {{"persona": "persona_name", "text": "reply text"}}
      }},
      "tweet_id_2": {{
        "reply_a": {{"persona": "persona_name", "text": "reply text"}},
        "reply_b": {{"persona": "persona_name", "text": "reply text"}}
      }}
    }}
    """
    
    try:
        response = gemini_request_with_retry(prompt)
        cleaned = response.text.strip().replace('```json', '').replace('```', '').strip()
        reply_options = json.loads(cleaned)
        return reply_options
    except Exception as e:
        logging.error(f"🔴 Batch reply generation failed: {e}")
        return {}

def score_reply_quality(reply_text, original_tweet):
    """Score reply quality based on multiple factors."""
    scores = {}
    
    # Relevance score (keyword overlap) - more lenient
    original_words = set(original_tweet.lower().split())
    reply_words = set(reply_text.lower().split())
    common_words = original_words.intersection(reply_words)
    relevance_ratio = len(common_words) / max(len(original_words), 1)
    scores['relevance'] = min(relevance_ratio * 150, 100)  # Boost relevance scoring
    
    # Length score (optimal length around 50-250 chars) - more flexible
    length = len(reply_text)
    if 50 <= length <= 250:
        scores['length'] = 100
    elif length < 50:
        scores['length'] = max(70, length / 50 * 100)  # Increased minimum for short replies
    else:
        scores['length'] = max(70, 100 - (length - 250) / 4)  # More lenient for long replies
    
    # Engagement potential - improved detection
    engagement_indicators = ['?', '!', 'what', 'how', 'why', 'think', 'agree', 'consider', 'perspective', 'interesting']
    engagement_count = sum(1 for indicator in engagement_indicators if indicator in reply_text.lower())
    scores['engagement'] = min(engagement_count * 15 + 40, 100)  # Base score of 40
    
    # Uniqueness (avoid generic responses) - less harsh
    generic_phrases = ['great point', 'totally agree', 'so true', 'exactly', 'this is']
    generic_count = sum(1 for phrase in generic_phrases if phrase in reply_text.lower())
    scores['uniqueness'] = max(50, 100 - generic_count * 20)  # Minimum 50, less penalty
    
    # Content quality bonus
    quality_indicators = ['because', 'however', 'actually', 'specifically', 'example', 'experience']
    quality_count = sum(1 for indicator in quality_indicators if indicator in reply_text.lower())
    scores['content_quality'] = min(quality_count * 10 + 70, 100)  # Base score of 70
    
    return sum(scores.values()) / len(scores)

def fetch_tweet_engagement(tweet_id):
    """Fetch engagement metrics for a specific tweet using Twitter API."""
    try:
        # Use the tweet lookup endpoint to get specific tweet by ID
        url = "https://api.twitterapi.io/twitter/tweet/lookup"
        headers = {"X-API-Key": TWITTER_API_IO_KEY}
        
        # Look up the specific tweet by ID
        params = {"id": str(tweet_id)}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if we got the tweet data
        if 'tweet' in data:
            tweet = data['tweet']
            return {
                'likes': tweet.get('likeCount', 0),
                'retweets': tweet.get('retweetCount', 0),
                'replies': tweet.get('replyCount', 0)
            }
        elif 'tweets' in data and len(data['tweets']) > 0:
            # Sometimes the API returns tweets array
            tweet = data['tweets'][0]
            return {
                'likes': tweet.get('likeCount', 0),
                'retweets': tweet.get('retweetCount', 0),
                'replies': tweet.get('replyCount', 0)
            }
        else:
            # Fallback: try searching for the tweet from our account
            logging.info(f"🔄 Tweet lookup failed, trying search for {tweet_id}")
            return fetch_tweet_engagement_fallback(tweet_id)
        
    except Exception as e:
        logging.error(f"🔴 Failed to fetch engagement for tweet {tweet_id}: {e}")
        # Try fallback method
        return fetch_tweet_engagement_fallback(tweet_id)

def fetch_tweet_engagement_fallback(tweet_id):
    """Fallback method to fetch tweet engagement using search."""
    try:
        url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
        headers = {"X-API-Key": TWITTER_API_IO_KEY}
        
        # Search for tweets from our account
        params = {
            "query": f"from:{MY_TWITTER_HANDLE}",
            "queryType": "Latest"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        tweets = data.get('tweets', [])
        
        # Look for our specific tweet ID
        for tweet in tweets:
            if str(tweet.get('id')) == str(tweet_id):
                return {
                    'likes': tweet.get('likeCount', 0),
                    'retweets': tweet.get('retweetCount', 0),
                    'replies': tweet.get('replyCount', 0)
                }
        
        logging.warning(f"🟡 Tweet {tweet_id} not found in search results")
        return None
        
    except Exception as e:
        logging.error(f"🔴 Fallback engagement fetch failed for tweet {tweet_id}: {e}")
        return None

def update_reply_engagement_metrics(db):
    """Update engagement metrics for all recent replies."""
    logging.info("📊 Updating engagement metrics for recent replies...")
    
    # Get replies that need engagement updates
    replies_to_check = db.get_replies_for_engagement_check(hours_old=1)
    
    if not replies_to_check:
        logging.info("✅ No replies need engagement updates.")
        return
    
    logging.info(f"🔍 Checking engagement for {len(replies_to_check)} replies...")
    
    updated_count = 0
    for reply in replies_to_check:
        try:
            # Fetch current engagement metrics
            engagement = fetch_tweet_engagement(reply['reply_id'])
            
            if engagement:
                # Update database with new metrics
                db.update_reply_engagement(
                    reply['reply_id'],
                    engagement['likes'],
                    engagement['retweets'],
                    engagement['replies']
                )
                
                updated_count += 1
                logging.info(f"✅ Updated {reply['persona']} reply: {engagement['likes']} likes, {engagement['retweets']} retweets, {engagement['replies']} replies")
                
                # Rate limiting - don't overwhelm the API
                time.sleep(1)
            
        except Exception as e:
            logging.error(f"🔴 Error updating engagement for reply {reply['reply_id']}: {e}")
            continue
    
    logging.info(f"📊 Updated engagement metrics for {updated_count}/{len(replies_to_check)} replies.")

# --- Enhanced API Management ---
def gemini_request_with_retry(prompt_text, max_retries=3):
    """Enhanced Gemini request with exponential backoff and retry logic."""
    global current_gemini_key_index
    
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
            response = model.generate_content(prompt_text, request_options={"timeout": 20})
            
            # Track API call
            increment_api_call_count(config, current_gemini_key_index)
            
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "quota" in error_str or "api_key" in error_str:
                # Try next API key
                if current_gemini_key_index < len(GEMINI_API_KEYS) - 1:
                    current_gemini_key_index += 1
                    logging.warning(f"🟡 Switching to API key {current_gemini_key_index + 1}")
                    genai.configure(api_key=GEMINI_API_KEYS[current_gemini_key_index])
                else:
                    logging.error("🔴 All API keys exhausted")
                    raise
            
            elif "rate_limit" in error_str:
                # Exponential backoff
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logging.warning(f"🟡 Rate limited, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
            
            else:
                logging.error(f"🔴 Unexpected API error: {e}")
                if attempt == max_retries - 1:
                    raise
    
    raise Exception("Max retries exceeded for Gemini API")

# --- Enhanced Helper Functions ---
def get_twitter_handles(csv_path):
    """Reads Twitter handles from the specified CSV file."""
    try:
        df = pd.read_csv(csv_path)
        handles = df['Handle'].str.replace('@', '').tolist()
        logging.info(f"✅ Found {len(handles)} handles from CSV.")
        return handles
    except Exception as e:
        logging.error(f"🔴 Could not read CSV at {csv_path}. Error: {e}")
        return []

def fetch_tweets_from_handles(handles, chunk_size=25):
    """Enhanced tweet fetching with better error handling."""
    all_tweets = []
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    headers = {"X-API-Key": TWITTER_API_IO_KEY}
    
    logging.info(f"📡 Fetching candidate tweets in chunks of {chunk_size}...")
    
    for i in range(0, len(handles), chunk_size):
        chunk = handles[i:i + chunk_size]
        logging.info(f"--> Processing chunk {i//chunk_size + 1} for {len(chunk)} handles...")
        
        # Create query for this chunk
        handle_queries = [f"from:{handle}" for handle in chunk]
        full_query = " OR ".join(handle_queries)
        params = {"query": full_query, "queryType": "Latest"}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status() 
            
            chunk_tweets = response.json().get("tweets", [])
            
            # Add engagement scores to tweets
            for tweet in chunk_tweets:
                tweet['engagement_score'] = calculate_engagement_score(tweet)
            
            all_tweets.extend(chunk_tweets)
            logging.info(f"    Found {len(chunk_tweets)} tweets from this chunk.")
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            logging.error(f"🔴 Error fetching tweets for chunk {i//chunk_size + 1}: {e}")
            continue
    
    logging.info(f"✅ Total tweets fetched: {len(all_tweets)}")
    return all_tweets

def format_time_ago(created_at_str):
    """Format timestamp as human-readable time ago (e.g., '2 min ago', '6hrs ago')."""
    if not created_at_str:
        return "unknown"
    
    try:
        # Handle different date formats from Twitter API
        if 'T' in created_at_str and ('Z' in created_at_str or '+' in created_at_str[-6:]):
            # ISO format: 2025-07-23T01:13:50+00:00 or 2025-07-23T01:13:50Z
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        else:
            # Twitter format: Wed Jul 23 01:13:50 +0000 2025
            # Replace +0000 with +00:00 for proper timezone parsing
            date_str = created_at_str.replace('+0000', '+00:00')
            created_at = datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
        
        # Calculate time difference
        now = datetime.now(UTC)
        diff = now - created_at
        
        total_seconds = int(diff.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s ago"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} min ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}hrs ago"
        else:
            days = total_seconds // 86400
            return f"{days}d ago"
            
    except (ValueError, TypeError):
        return "unknown"

def filter_and_rank_candidates(tweets, replied_to_ids, db):
    """Enhanced filtering and ranking of candidate tweets."""
    candidates = []
    now = datetime.now(UTC)
    cutoff_time = now - timedelta(hours=12)  # Changed to 12 hours
    
    for tweet in tweets:
        try:
            # Skip if already replied
            if str(tweet.get('id', '')) in replied_to_ids:
                continue
            
            # Skip if it's a reply itself
            if tweet.get('isReply', False):
                continue
            
            # Check if tweet is recent enough
            created_at_str = tweet.get('createdAt', '')
            if created_at_str:
                try:
                    # Handle different date formats from Twitter API
                    if 'T' in created_at_str and ('Z' in created_at_str or '+' in created_at_str[-6:]):
                        # ISO format: 2025-07-23T01:13:50+00:00 or 2025-07-23T01:13:50Z
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        # Twitter format: Wed Jul 23 01:13:50 +0000 2025
                        # Replace +0000 with +00:00 for proper timezone parsing
                        date_str = created_at_str.replace('+0000', '+00:00')
                        created_at = datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
                    
                    if created_at < cutoff_time:
                        continue
                except (ValueError, TypeError) as e:
                    logging.warning(f"🟡 Could not parse date '{created_at_str}' for tweet {tweet.get('id', 'unknown')}: {e}")
                    continue
            
            # Enhanced engagement filtering
            engagement_score = tweet.get('engagement_score', 0)
            if engagement_score < 60:  # Only show high-quality tweets (60+ score)
                continue
            
            # Store tweet analysis in database
            # Extract author with better fallback logic
            author_info = tweet.get('author', {})
            author = (
                author_info.get('username') or 
                author_info.get('userName') or 
                author_info.get('screen_name') or
                tweet.get('username') or
                tweet.get('userName') or
                'unknown_user'
            )
            
            tweet_data = {
                'id': str(tweet['id']),
                'author': author,
                'text': tweet.get('text', ''),
                'engagement_score': engagement_score,
                'created_at': created_at_str,
                'likes': tweet.get('likeCount', 0),
                'retweets': tweet.get('retweetCount', 0),
                'replies': tweet.get('replyCount', 0)
            }
            db.store_tweet_analysis(tweet_data)
            
            candidates.append(tweet)
            
        except Exception as e:
            logging.error(f"Error processing tweet {tweet.get('id', 'unknown')}: {e}")
            continue
    
    # Sort by engagement score
    candidates.sort(key=lambda x: x.get('engagement_score', 0), reverse=True)
    
    logging.info(f"✅ Found {len(candidates)} candidate tweets, ranked by engagement.")
    return candidates

def select_quality_tweets_with_gemini(candidates, max_tweets=15):
    """Use Gemini to select high-quality tweets and filter out one-liners and low-quality content."""
    if not candidates:
        return []
    
    # Limit candidates to process (to avoid token limits)
    candidates_to_analyze = candidates[:30]  # Analyze top 30 by engagement score
    
    # Prepare tweets for Gemini analysis
    tweets_for_prompt = []
    for i, tweet in enumerate(candidates_to_analyze, 1):
        tweet_id = str(tweet['id'])
        tweet_text = tweet.get('text', '')
        author_info = tweet.get('author', {})
        author = (
            author_info.get('username') or 
            author_info.get('userName') or 
            author_info.get('screen_name') or
            tweet.get('username') or
            tweet.get('userName') or
            'unknown_user'
        )
        engagement_score = tweet.get('engagement_score', 0)
        time_ago = format_time_ago(tweet.get('createdAt', ''))
        
        tweets_for_prompt.append({
            'index': i,
            'tweet_id': tweet_id,
            'author': author,
            'text': tweet_text,
            'engagement_score': round(engagement_score, 1),
            'time_ago': time_ago
        })
    
    # Create the improved Gemini prompt
    prompt = f"""
You are an expert social media strategist. Your task is to analyze {len(tweets_for_prompt)} tweets and select up to {max_tweets} tweets that are BEST for generating meaningful replies that will drive engagement.

**CRITICAL FILTERING CRITERIA - REJECT tweets that are:**
- One-liners or very short posts (under 15 words) unless exceptionally thought-provoking
- Simple statements without depth ("Great day!", "Love this!", "So true!")
- Pure promotional content or obvious marketing
- Vague or generic content that doesn't invite discussion
- Just emoji reactions or single-word responses
- News headlines without commentary or insight
- Simple questions with obvious yes/no answers

**PRIORITIZE tweets that are:**
- Thought-provoking insights or observations (25+ words preferred)
- Complex questions that invite detailed responses
- Personal experiences with broader relevance
- Controversial or debate-worthy topics (handled respectfully)
- Industry insights, lessons learned, or professional advice
- Stories or anecdotes that others can relate to
- Technical discussions that benefit from additional perspectives
- Philosophical or strategic thinking that can be expanded upon

**QUALITY INDICATORS:**
- Tweet length: Prefer 20+ words (shows more substance)
- Engagement potential: Can this generate meaningful discussion?
- Reply value: Can I add genuine insight or perspective?
- Authenticity: Does this feel human and genuine?
- Relevance: Is this topic worth engaging with?

**RESPONSE FORMAT:** Return a JSON array with selected tweets. Each object must contain:
- "tweet_id": the unique ID
- "reason": brief explanation (max 25 words) why it's worth replying to
- "reply_angle": suggested approach for the reply (e.g., "share experience", "ask follow-up", "provide framework")

**EXAMPLE:**
[
  {{
    "tweet_id": "123456789",
    "reason": "Deep insight about remote work challenges that invites sharing experiences",
    "reply_angle": "share contrasting perspective from different industry"
  }}
]

If no tweets meet the quality standards, return an empty array: []

**TWEETS TO ANALYZE:**
{json.dumps(tweets_for_prompt, indent=2)}
"""
    
    try:
        logging.info(f"🤖 Using Gemini to select quality tweets from {len(candidates_to_analyze)} candidates...")
        response = gemini_request_with_retry(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        selected_tweets_info = json.loads(cleaned_response)
        
        # Map selected tweets back to original tweet objects
        tweet_dict = {str(tweet['id']): tweet for tweet in candidates_to_analyze}
        selected_tweets = []
        
        for selection in selected_tweets_info:
            tweet_id = str(selection.get('tweet_id', ''))
            if tweet_id in tweet_dict:
                tweet = tweet_dict[tweet_id]
                # Add Gemini's analysis to the tweet object
                tweet['gemini_reason'] = selection.get('reason', '')
                tweet['gemini_reply_angle'] = selection.get('reply_angle', '')
                selected_tweets.append(tweet)
        
        logging.info(f"✅ Gemini selected {len(selected_tweets)} high-quality tweets for replies")
        return selected_tweets
        
    except Exception as e:
        logging.error(f"🔴 Gemini tweet selection failed: {e}")
        # Fallback to original filtering
        logging.info("🔄 Falling back to engagement-based selection...")
        return candidates[:max_tweets]

def improve_reply_with_ai(original_reply, original_tweet, improvement_suggestion):
    """Improve a reply based on user feedback using AI."""
    prompt = f"""
    You are an expert Twitter reply optimizer. Improve the following reply based on the user's suggestion.
    
    Original Tweet: {original_tweet}
    
    Current Reply: {original_reply}
    
    User's Improvement Suggestion: {improvement_suggestion}
    
    Please rewrite the reply to incorporate the user's feedback while maintaining:
    - Relevance to the original tweet
    - Engaging and natural tone
    - Under 280 characters
    - High quality and value
    
    Return only the improved reply text, nothing else.
    """
    
    try:
        response = gemini_request_with_retry(prompt)
        improved_reply = response.text.strip()
        
        # Basic validation
        if len(improved_reply) > 280:
            improved_reply = improved_reply[:277] + "..."
        
        return improved_reply
    except Exception as e:
        logging.error(f"🔴 Failed to improve reply: {e}")
        return None

def post_reply_with_tracking(tweet_id, reply_text, persona, analytics, db):
    """Enhanced reply posting with performance tracking."""
    try:
        response = client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        reply_id = response.data['id']
        
        logging.info(f"✅ Successfully posted reply to tweet {tweet_id}")
        
        # Track the posted reply
        increment_tweet_count(config, 1)
        
        # Store in database for later engagement tracking
        db.store_reply_performance({
            'reply_id': str(reply_id),
            'original_tweet_id': str(tweet_id),
            'persona': persona,
            'reply_text': reply_text,
            'posted_at': datetime.now().isoformat(),
            'likes': 0,
            'retweets': 0,
            'replies': 0,
            'last_checked': None
        })
        
        # Track in analytics
        reply_data = {
            'reply_id': reply_id,
            'original_tweet_id': tweet_id,
            'persona': persona,
            'reply_text': reply_text,
            'posted_at': datetime.now().isoformat()
        }
        analytics.track_reply_performance(reply_data)
        
        return reply_id
        
    except Exception as e:
        logging.error(f"🔴 Failed to post reply to tweet {tweet_id}: {e}")
        return None

def show_live_dashboard(analytics, db):
    """Display live bot performance dashboard."""
    print("\n" + "="*60)
    print("📊 LIVE BOT PERFORMANCE DASHBOARD")
    print("="*60)
    
    # Current session stats
    stats = log_current_stats(config)
    
    # Best performing personas from database
    best_personas = analytics.get_best_performing_personas(db)
    if best_personas:
        print("\n🏆 Top Performing Personas:")
        for i, persona_data in enumerate(best_personas[:3], 1):
            if isinstance(persona_data, dict):
                # Database format
                persona = persona_data['persona']
                avg_engagement = persona_data['avg_engagement']
                total_replies = persona_data['total_replies']
                print(f"  {i}. {persona}: {avg_engagement:.1f} avg engagement ({total_replies} replies)")
            else:
                # Legacy format
                persona, data = persona_data
                print(f"  {i}. {persona}: {data['avg_engagement']:.1f}% avg engagement")
    else:
        print("\n🏆 Top Performing Personas:")
        print("1. system_thinker: 0.0 avg engagement")
        print("2. candid_realist: 0.0 avg engagement") 
        print("3. contrarian_challenger: 0.0 avg engagement")
    
    # Recent activity summary
    print(f"\n⚡ Recent Activity:")
    print(f"  • API calls made: {sum([config.getint('TRACKING', f'API_CALLS_GEMINI_KEY_{i}', fallback=0) for i in [1,2]])}")
    print(f"  • Replies posted: {config.getint('TRACKING', 'TWEETS_LAST_24H', fallback=0)}")
    
    print("="*60 + "\n")

# --- Main Enhanced Function ---
def main():
    """Enhanced main function with all improvements."""
    print("--- 🚀 Enhanced Twitter Reply Bot ---")
    
    # Initialize systems
    db = BotDatabase()
    analytics = BotAnalytics()
    safety = ContentSafety()
    rate_limiter = RateLimiter()
    
    # Update persona weights based on performance
    analytics.update_persona_weights()
    
    # Show live dashboard
    show_live_dashboard(analytics, db)
    
    # Load replied-to IDs cache
    replied_to_ids = set()
    try:
        with open(REPLIED_IDS_CACHE_FILE, 'r') as f:
            replied_to_ids = set(json.load(f))
        logging.info(f"✅ Loaded {len(replied_to_ids)} replied-to IDs from cache.")
    except FileNotFoundError:
        logging.info("🟡 Cache file not found. A new one will be created.")
    
    # Update cache with recent activity
    logging.info(f"📡 Fetching your recent activity for @{MY_TWITTER_HANDLE} to update cache...")
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    headers = {"X-API-Key": TWITTER_API_IO_KEY}
    my_activity_query = f"from:{MY_TWITTER_HANDLE} include:nativeretweets"
    params = {"query": my_activity_query, "queryType": "Latest"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        my_tweets = response.json().get("tweets", [])
        for tweet in my_tweets:
            if tweet.get('isReply') and tweet.get('inReplyToId'):
                replied_to_ids.add(str(tweet['inReplyToId']))
        logging.info(f"📖 Cache updated. Total unique replied-to IDs: {len(replied_to_ids)}.")
    except Exception as e:
        logging.error(f"🔴 Error updating cache with recent activity: {e}")
    
    # Get Twitter handles from CSV
    handles = get_twitter_handles(CSV_FILE_PATH)
    if not handles:
        logging.error("🔴 No handles found. Exiting.")
        return
    
    # Fetch tweets from handles
    all_tweets = fetch_tweets_from_handles(handles)
    if not all_tweets:
        logging.error("🔴 No tweets fetched. Exiting.")
        return
    
    # Filter and rank candidate tweets
    candidates = filter_and_rank_candidates(all_tweets, replied_to_ids, db)
    if not candidates:
        logging.info("🟡 No suitable candidate tweets found.")
        return
    
    # Use Gemini to select high-quality tweets
    quality_candidates = select_quality_tweets_with_gemini(candidates, max_tweets=15)
    if not quality_candidates:
        logging.info("🟡 No quality tweets selected by Gemini.")
        return
    
    logging.info(f"🎯 Processing {len(quality_candidates)} Gemini-selected quality tweets...")
    candidates = quality_candidates  # Replace candidates with Gemini-selected ones
    
    # Process candidates in batches
    max_replies = 17  # Twitter API free tier limit: 17 replies per 24 hours
    batch_size = 3
    processed = 0
    skip_all = False  # Flag to break out of all loops
    
    for i in range(0, len(candidates), batch_size):
        if skip_all:  # Check flag before processing each batch
            break
        # Continue processing all candidates, but limit actual posting
        
        batch = candidates[i:i + batch_size]
        logging.info(f"🎯 Processing batch {i//batch_size + 1} with {len(batch)} tweets...")
        
        # Generate replies for batch
        if rate_limiter.can_make_api_call():
            batch_replies = generate_batch_replies(batch)
            rate_limiter.record_api_call()
        else:
            logging.warning("🟡 API rate limit reached, processing individually...")
            batch_replies = {}
        
        # Process each tweet in batch
        for batch_tweet_idx, tweet in enumerate(batch):
            if skip_all:  # Check flag before processing each tweet
                break
                
            try:
                tweet_id = str(tweet['id'])
                tweet_text = tweet.get('text', '')
                # Extract author with better fallback logic
                author_info = tweet.get('author', {})
                author = (
                    author_info.get('username') or 
                    author_info.get('userName') or 
                    author_info.get('screen_name') or
                    tweet.get('username') or
                    tweet.get('userName') or
                    'unknown_user'
                )
                engagement_score = tweet.get('engagement_score', 0)
                
                # Debug: Log tweet structure if author is still unknown
                if author == 'unknown_user':
                    logging.warning(f"🔍 Debug - Tweet structure: {json.dumps(tweet.get('author', {}), indent=2)}")
                
                logging.info(f"🎯 Processing tweet from @{author} (score: {engagement_score:.1f})")
                logging.info(f"   Tweet: {tweet_text[:100]}...")
                
                # Get replies from batch or generate individually
                reply_options = batch_replies.get(tweet_id, {})
                
                if not reply_options:
                    # Fallback to individual generation
                    logging.info("   Generating individual replies...")
                    optimal_personas = select_optimal_persona(tweet_text, db.get_author_history(author))
                    # Individual generation logic here (simplified for space)
                    continue
                
                # Select best reply based on quality score
                best_reply = None
                best_score = 0
                best_persona = None
                
                for reply_key in ['reply_a', 'reply_b']:
                    if reply_key in reply_options:
                        reply_data = reply_options[reply_key]
                        reply_text = reply_data.get('text', '')
                        persona = reply_data.get('persona', '')
                        
                        # Safety check
                        if not safety.safety_check(reply_text, tweet_text):
                            logging.warning(f"   ⚠️ Reply failed safety check: {reply_text[:50]}...")
                            continue
                        
                        # Quality score
                        quality_score = score_reply_quality(reply_text, tweet_text)
                        
                        if quality_score > best_score:
                            best_reply = reply_text
                            best_score = quality_score
                            best_persona = persona
                
                # Collect all quality replies (not just the best one)
                quality_replies = []
                for reply_key in ['reply_a', 'reply_b']:
                    if reply_key in reply_options:
                        reply_data = reply_options[reply_key]
                        reply_text = reply_data.get('text', '')
                        persona = reply_data.get('persona', '')
                        
                        # Safety check
                        if not safety.safety_check(reply_text, tweet_text):
                            continue
                        
                        # Quality score
                        quality_score = score_reply_quality(reply_text, tweet_text)
                        
                        if quality_score >= 50:  # Lowered threshold since Gemini pre-filters tweets
                            quality_replies.append({
                                'text': reply_text,
                                'persona': persona,
                                'score': quality_score
                            })
                
                if quality_replies:
                    # Sort by score (best first)
                    quality_replies.sort(key=lambda x: x['score'], reverse=True)
                    
                    # Calculate progress information
                    current_tweet_index = i + batch_tweet_idx + 1
                    total_candidates = len(candidates)
                    replies_posted_so_far = processed
                    max_replies_allowed = max_replies
                    remaining_reply_slots = max_replies_allowed - replies_posted_so_far
                    
                    # Display tweet and all quality replies with improved formatting
                    time_ago = format_time_ago(tweet.get('createdAt', ''))
                    print("\n" + "="*80)
                    print(f"📱 TWEET #{current_tweet_index}/{total_candidates} from @{author} • {time_ago}")
                    print(f"🔥 Engagement Score: {engagement_score:.1f}/100")
                    
                    # Show Gemini's reasoning if available
                    if tweet.get('gemini_reason'):
                        print(f"🤖 Gemini: {tweet['gemini_reason']}")
                    if tweet.get('gemini_reply_angle'):
                        print(f"💡 Suggested angle: {tweet['gemini_reply_angle']}")
                    
                    print("="*80)
                    print()
                    
                    # Display tweet with proper wrapping
                    print("📝 ORIGINAL TWEET:")
                    print("┌" + "─"*78 + "┐")
                    # Word wrap the tweet text
                    import textwrap
                    wrapped_tweet = textwrap.fill(tweet_text, width=76)
                    for line in wrapped_tweet.split('\n'):
                        print(f"│ {line:<76} │")
                    print("└" + "─"*78 + "┘")
                    print()
                    
                    print("💬 GENERATED REPLIES:")
                    print()
                    
                    for idx, reply in enumerate(quality_replies, 1):
                        print(f"┌─ OPTION {idx} ─ {reply['persona'].upper().replace('_', ' ')} ─ SCORE: {reply['score']:.1f}/100 " + "─"*(35-len(reply['persona'])) + "┐")
                        # Word wrap the reply text
                        wrapped_reply = textwrap.fill(reply['text'], width=76)
                        for line in wrapped_reply.split('\n'):
                            print(f"│ {line:<76} │")
                        print("└" + "─"*78 + "┘")
                        print()
                    
                    print("📊 PROGRESS:")
                    print(f"   • Tweets processed: {current_tweet_index}/{total_candidates}")
                    print(f"   • Replies posted today: {replies_posted_so_far}/17")
                    print(f"   • Remaining slots: {17 - replies_posted_so_far}")
                    print()
                    
                    # Enhanced input options
                    print("🎯 ACTIONS:")
                    print("   y1, y2, y3... → Post reply number")
                    print("   i1, i2, i3... → Improve reply number")  
                    print("   n → Skip this tweet")
                    print("   s → Skip all remaining tweets")
                    
                    choice = input("\nYour choice: ").lower().strip()
                    
                    if choice.startswith('y') and len(choice) > 1:
                        # Post specific reply
                        try:
                            reply_num = int(choice[1:]) - 1
                            if 0 <= reply_num < len(quality_replies):
                                selected_reply = quality_replies[reply_num]
                                if processed >= 17:
                                    print("⚠️ Daily posting limit reached (17 replies). Cannot post more today.")
                                else:
                                    reply_id = post_reply_with_tracking(tweet_id, selected_reply['text'], selected_reply['persona'], analytics, db)
                                    if reply_id:
                                        replied_to_ids.add(tweet_id)
                                        processed += 1
                                        time.sleep(3)  # Brief pause between posts
                            else:
                                print("❌ Invalid reply number")
                        except ValueError:
                            print("❌ Invalid format. Use y1, y2, etc.")
                    
                    elif choice.startswith('i') and len(choice) > 1:
                        # Improve specific reply
                        try:
                            reply_num = int(choice[1:]) - 1
                            if 0 <= reply_num < len(quality_replies):
                                selected_reply = quality_replies[reply_num]
                                improvement_suggestion = input("💡 How should this reply be improved? ")
                                
                                improved_reply = improve_reply_with_ai(selected_reply['text'], tweet_text, improvement_suggestion)
                                if improved_reply:
                                    print("\n" + "="*60)
                                    print("🔄 IMPROVED REPLY:")
                                    print("="*60)
                                    print("┌" + "─"*58 + "┐")
                                    import textwrap
                                    wrapped_improved = textwrap.fill(improved_reply, width=56)
                                    for line in wrapped_improved.split('\n'):
                                        print(f"│ {line:<56} │")
                                    print("└" + "─"*58 + "┘")
                                    print()
                                    
                                    post_choice = input("Post improved reply? (y/n): ").lower().strip()
                                    if post_choice == 'y':
                                        if processed >= 17:
                                            print("⚠️ Daily posting limit reached (17 replies). Cannot post more today.")
                                        else:
                                            reply_id = post_reply_with_tracking(tweet_id, improved_reply, selected_reply['persona'], analytics, db)
                                            if reply_id:
                                                replied_to_ids.add(tweet_id)
                                                processed += 1
                                                time.sleep(3)  # Brief pause between posts
                            else:
                                print("❌ Invalid reply number")
                        except ValueError:
                            print("❌ Invalid format. Use i1, i2, etc.")
                    
                    elif choice == 's':
                        skip_all = True  # Set flag to skip all remaining tweets
                        break
                    elif choice == 'n':
                        continue
                elif best_reply and best_score < 50:
                    logging.info(f"🔄 Skipping low-quality reply (score: {best_score:.1f}): {best_reply[:50]}...")
                    continue
                else:
                    logging.error(f"🔴 No suitable reply generated for tweet {tweet_id}")
                    
            except Exception as e:
                logging.error(f"🔴 Error processing tweet {tweet.get('id', 'unknown')}: {e}")
                continue
        
        # Batch delay
        if i + batch_size < len(candidates):
            time.sleep(3)
    
    # Save updated cache
    try:
        with open(REPLIED_IDS_CACHE_FILE, 'w') as f:
            json.dump(list(replied_to_ids), f)
        logging.info(f"💾 Saved {len(replied_to_ids)} replied-to IDs to cache.")
    except Exception as e:
        logging.error(f"🔴 Error saving cache: {e}")
    
    # Update engagement metrics for recent replies
    update_reply_engagement_metrics(db)
    
    # Final dashboard
    logging.info(f"✅ Enhanced reply bot completed. Posted {processed} replies.")
    show_live_dashboard(analytics, db)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🚫 Operation cancelled by user. Exiting.")
    except Exception as e:
        logging.error(f"🔴 Unexpected error: {e}")
        print("\n❌ Bot encountered an error. Check logs for details.")