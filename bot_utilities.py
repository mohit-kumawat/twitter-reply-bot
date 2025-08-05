#!/usr/bin/env python
"""
Shared utility functions for tracking tweets and API calls across both bot scripts.
"""

import configparser
import logging
import os
from datetime import datetime, timedelta

def load_config():
    """Load configuration from bot_config.ini"""
    config = configparser.ConfigParser()
    # Try new filename first, fallback to old one for compatibility
    if os.path.exists('bot_config.ini'):
        config.read('bot_config.ini')
    else:
        config.read('config.ini')
    return config

def save_config(config):
    """Save configuration back to bot_config.ini"""
    config_file = 'bot_config.ini' if os.path.exists('bot_config.ini') else 'config.ini'
    with open(config_file, 'w') as configfile:
        config.write(configfile)

def reset_daily_counters_if_needed(config):
    """Reset daily counters if 24 hours have passed"""
    try:
        last_reset_str = config.get('TRACKING', 'LAST_TWEET_RESET', fallback='2025-01-01 00:00:00')
        last_reset = datetime.strptime(last_reset_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        
        # If more than 24 hours have passed, reset counters
        if now - last_reset >= timedelta(hours=24):
            config.set('TRACKING', 'TWEETS_LAST_24H', '0')
            config.set('TRACKING', 'API_CALLS_GEMINI_KEY_1', '0')
            config.set('TRACKING', 'API_CALLS_GEMINI_KEY_2', '0')
            config.set('TRACKING', 'LAST_TWEET_RESET', now.strftime('%Y-%m-%d %H:%M:%S'))
            config.set('TRACKING', 'LAST_API_RESET', now.strftime('%Y-%m-%d %H:%M:%S'))
            save_config(config)
            logging.info("🔄 Daily counters reset - new 24h period started")
            return True
    except Exception as e:
        logging.error(f"Error resetting daily counters: {e}")
    return False

def increment_tweet_count(config, count=1):
    """Increment the tweet count and save to config"""
    try:
        current_count = config.getint('TRACKING', 'TWEETS_LAST_24H', fallback=0)
        new_count = current_count + count
        config.set('TRACKING', 'TWEETS_LAST_24H', str(new_count))
        save_config(config)
        logging.info(f"📊 Tweet count updated: {new_count} tweets in last 24h")
        return new_count
    except Exception as e:
        logging.error(f"Error incrementing tweet count: {e}")
        return 0

def increment_api_call_count(config, api_key_index):
    """Increment API call count for specific Gemini key"""
    try:
        key_name = f'API_CALLS_GEMINI_KEY_{api_key_index + 1}'
        current_count = config.getint('TRACKING', key_name, fallback=0)
        new_count = current_count + 1
        config.set('TRACKING', key_name, str(new_count))
        save_config(config)
        logging.info(f"📊 API calls for key {api_key_index + 1}: {new_count}")
        return new_count
    except Exception as e:
        logging.error(f"Error incrementing API call count: {e}")
        return 0

def get_current_stats(config):
    """Get current tracking statistics"""
    try:
        tweets_24h = config.getint('TRACKING', 'TWEETS_LAST_24H', fallback=0)
        api_calls_key1 = config.getint('TRACKING', 'API_CALLS_GEMINI_KEY_1', fallback=0)
        api_calls_key2 = config.getint('TRACKING', 'API_CALLS_GEMINI_KEY_2', fallback=0)
        total_api_calls = api_calls_key1 + api_calls_key2
        
        last_reset = config.get('TRACKING', 'LAST_TWEET_RESET', fallback='Unknown')
        
        return {
            'tweets_24h': tweets_24h,
            'api_calls_key1': api_calls_key1,
            'api_calls_key2': api_calls_key2,
            'total_api_calls': total_api_calls,
            'last_reset': last_reset
        }
    except Exception as e:
        logging.error(f"Error getting current stats: {e}")
        return {
            'tweets_24h': 0,
            'api_calls_key1': 0,
            'api_calls_key2': 0,
            'total_api_calls': 0,
            'last_reset': 'Unknown'
        }

def log_current_stats(config):
    """Log current tracking statistics"""
    stats = get_current_stats(config)
    logging.info("📊 Current 24h Stats:")
    logging.info(f"   Tweets posted: {stats['tweets_24h']}")
    logging.info(f"   API calls (Key 1): {stats['api_calls_key1']}")
    logging.info(f"   API calls (Key 2): {stats['api_calls_key2']}")
    logging.info(f"   Total API calls: {stats['total_api_calls']}")
    logging.info(f"   Last reset: {stats['last_reset']}")