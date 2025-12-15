import sqlite3
import feedparser
import asyncio
import os
import requests
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from utils import get_image, build_caption, download_image, build_full_article, split_message

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "-1003318199741")
CHANNEL_USERNAME = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "WhatsApp_Updates_X")
ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", "5095434008"))

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required!")
FEED_URL = "https://wabetainfo.com/feed/"
CHECK_INTERVAL = 300
DB_FILE = "posts_history.db"

CATEGORIES = ["Android", "iOS", "Windows", "Web", "General"]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
        published TEXT,
        share_count INTEGER DEFAULT 0,
        category TEXT,
        channel_message_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    try:
        cur.execute("ALTER TABLE posts ADD COLUMN channel_message_id INTEGER")
    except:
        pass
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_id INTEGER,
        category TEXT,
        PRIMARY KEY(user_id, category)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS post_shares (
        user_id INTEGER,
        post_id TEXT,
        shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, post_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notifications_enabled INTEGER DEFAULT 1,
        language TEXT DEFAULT 'en',
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookmarks (
        user_id INTEGER,
        post_id TEXT,
        bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, post_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending'
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def fetch_rss_feed():
    try:
        response = requests.get(FEED_URL, headers={"User-Agent": USER_AGENT}, timeout=15)
        if response.status_code == 200:
            return feedparser.parse(response.content)
    except Exception as e:
        print(f"Error fetching RSS feed: {e}")
    return feedparser.parse(FEED_URL)

def db_connect():
    return sqlite3.connect(DB_FILE)

def has_post(post_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM posts WHERE id=?", (post_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def save_post(post_id, title, link, published, category="General", channel_message_id=None):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO posts (id, title, link, published, category, channel_message_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (post_id, title, link, published, category, channel_message_id))
    conn.commit()
    conn.close()

def update_post_message_id(post_id, channel_message_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE posts SET channel_message_id=? WHERE id=?", (channel_message_id, post_id))
    conn.commit()
    conn.close()

def increment_share_count(post_id, user_id=None):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE posts SET share_count = share_count + 1 WHERE id=?", (post_id,))
    if user_id:
        cur.execute("INSERT OR IGNORE INTO post_shares (user_id, post_id) VALUES (?, ?)", (user_id, post_id))
    conn.commit()
    conn.close()

def get_stats():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM posts")
    posts_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM user_profiles")
    users_count = cur.fetchone()[0]
    cur.execute("SELECT title, share_count FROM posts ORDER BY share_count DESC LIMIT 5")
    top_posts = cur.fetchall()
    conn.close()
    return posts_count, users_count, top_posts

def get_or_create_user(user_id, username=None, first_name=None):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM user_profiles WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("""
            INSERT INTO user_profiles (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        conn.commit()
    else:
        cur.execute("UPDATE user_profiles SET last_active=CURRENT_TIMESTAMP WHERE user_id=?", (user_id,))
        conn.commit()
    conn.close()

def get_user_profile(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,))
    profile = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM post_shares WHERE user_id=?", (user_id,))
    shares = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bookmarks WHERE user_id=?", (user_id,))
    bookmarks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=?", (user_id,))
    subs = cur.fetchone()[0]
    conn.close()
    return profile, shares, bookmarks, subs

def get_user_subscriptions(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT category FROM subscriptions WHERE user_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def toggle_subscription(user_id, category):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM subscriptions WHERE user_id=? AND category=?", (user_id, category))
    if cur.fetchone():
        cur.execute("DELETE FROM subscriptions WHERE user_id=? AND category=?", (user_id, category))
        result = False
    else:
        cur.execute("INSERT INTO subscriptions (user_id, category) VALUES (?, ?)", (user_id, category))
        result = True
    conn.commit()
    conn.close()
    return result

def get_user_bookmarks(user_id, limit=10, offset=0):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.link, p.category 
        FROM bookmarks b 
        JOIN posts p ON b.post_id = p.id 
        WHERE b.user_id=? 
        ORDER BY b.bookmarked_at DESC 
        LIMIT ? OFFSET ?
    """, (user_id, limit, offset))
    rows = cur.fetchall()
    conn.close()
    return rows

def toggle_bookmark(user_id, post_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bookmarks WHERE user_id=? AND post_id=?", (user_id, post_id))
    if cur.fetchone():
        cur.execute("DELETE FROM bookmarks WHERE user_id=? AND post_id=?", (user_id, post_id))
        result = False
    else:
        cur.execute("INSERT INTO bookmarks (user_id, post_id) VALUES (?, ?)", (user_id, post_id))
        result = True
    conn.commit()
    conn.close()
    return result

def is_bookmarked(user_id, post_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bookmarks WHERE user_id=? AND post_id=?", (user_id, post_id))
    result = cur.fetchone() is not None
    conn.close()
    return result

def get_recent_posts(limit=10, offset=0, category=None):
    conn = db_connect()
    cur = conn.cursor()
    if category:
        cur.execute("""
            SELECT id, title, link, category, share_count 
            FROM posts 
            WHERE category=?
            ORDER BY rowid DESC 
            LIMIT ? OFFSET ?
        """, (category, limit, offset))
    else:
        cur.execute("""
            SELECT id, title, link, category, share_count 
            FROM posts 
            ORDER BY rowid DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_posts_count(category=None):
    conn = db_connect()
    cur = conn.cursor()
    if category:
        cur.execute("SELECT COUNT(*) FROM posts WHERE category=?", (category,))
    else:
        cur.execute("SELECT COUNT(*) FROM posts")
    count = cur.fetchone()[0]
    conn.close()
    return count

def save_feedback(user_id, message):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO feedback (user_id, message) VALUES (?, ?)", (user_id, message))
    conn.commit()
    conn.close()

def get_pending_feedback():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, message, created_at FROM feedback WHERE status='pending' ORDER BY created_at DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    return rows

def toggle_notifications(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT notifications_enabled FROM user_profiles WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row:
        new_val = 0 if row[0] == 1 else 1
        cur.execute("UPDATE user_profiles SET notifications_enabled=? WHERE user_id=?", (new_val, user_id))
        conn.commit()
        result = new_val == 1
    else:
        result = True
    conn.close()
    return result

def get_notifications_status(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT notifications_enabled FROM user_profiles WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] == 1 if row else True

def get_subscribed_users(category):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.user_id FROM subscriptions s 
        JOIN user_profiles u ON s.user_id = u.user_id 
        WHERE s.category=? AND u.notifications_enabled=1
    """, (category,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def log_activity(user_id, action):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO user_activity (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()
    conn.close()

def get_admin_stats():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM user_profiles")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM posts")
    total_posts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bookmarks")
    total_bookmarks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM post_shares")
    total_shares = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM feedback WHERE status='pending'")
    pending_feedback = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_activity WHERE created_at >= datetime('now', '-1 day')")
    daily_activity = cur.fetchone()[0]
    conn.close()
    return {
        "users": total_users,
        "posts": total_posts,
        "bookmarks": total_bookmarks,
        "shares": total_shares,
        "pending_feedback": pending_feedback,
        "daily_activity": daily_activity
    }

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "WABeta News Bot is Online!"

@flask_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    flask_app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

waiting_for_feedback = {}
waiting_for_broadcast = {}

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)
    log_activity(user.id, "start")
    
    welcome_text = f"""
📱 <b>Welcome to WABeta News Bot!</b>

━━━━━━━━━━━━━━━

👋 Hello <b>{user.first_name}</b>!

Stay updated with the latest WhatsApp news, beta updates, and features across all platforms.

━━━━━━━━━━━━━━━
✨ <b>What I can do:</b>
━━━━━━━━━━━━━━━

📰 Browse latest news
🔔 Subscribe to categories
🔖 Bookmark favorite articles
📊 Track your activity
💬 Get instant notifications

👇 Tap the button below to explore!
"""
    keyboard = [
        [InlineKeyboardButton("🚀 Open Main Menu", callback_data="main_menu")],
    ]
    await update.message.reply_text(
        welcome_text, 
        parse_mode="HTML", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update.message, update.effective_user.id)

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("This command is only for admins.")
        return
    
    await update.message.reply_text("Fetching latest post from WABeta News...")
    
    try:
        feed = fetch_rss_feed()
        if not feed.entries:
            await update.message.reply_text("No posts found in the RSS feed.")
            return
        
        latest = feed.entries[0]
        caption, categories = build_caption(latest)
        full_article, _ = build_full_article(latest)
        
        save_post(
            latest.id,
            getattr(latest, "title", ""),
            getattr(latest, "link", ""),
            getattr(latest, "published", ""),
            categories[0] if categories else "General",
        )
        
        image_data = download_image(latest)
        if image_data:
            if len(full_article) > 1024:
                full_article = full_article[:1021] + "..."
            
            sent_msg = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_data,
                caption=full_article,
                parse_mode="HTML",
            )
            
            update_post_message_id(latest.id, sent_msg.message_id)
            
            await update.message.reply_text(f"Latest post sent to channel!\n\nTitle: {latest.title}")
        else:
            await update.message.reply_text("Could not download image. Please try again.")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def show_main_menu(message_or_query, user_id, edit=False):
    menu_text = """
📱 <b>WABeta News Bot</b>

━━━━━━━━━━━━━━━
🏠 <b>Main Menu</b>
━━━━━━━━━━━━━━━

Choose an option below:
"""
    keyboard = [
        [
            InlineKeyboardButton("📰 Latest News", callback_data="menu_news"),
            InlineKeyboardButton("📂 Categories", callback_data="menu_categories"),
        ],
        [
            InlineKeyboardButton("👤 My Profile", callback_data="menu_profile"),
            InlineKeyboardButton("🔖 Bookmarks", callback_data="menu_bookmarks"),
        ],
        [
            InlineKeyboardButton("🔔 Subscriptions", callback_data="menu_subscriptions"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("📊 Channel Stats", callback_data="menu_stats"),
            InlineKeyboardButton("ℹ️ About", callback_data="menu_about"),
        ],
        [InlineKeyboardButton("💬 Send Feedback", callback_data="menu_feedback")],
    ]
    
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel")])
    
    if edit:
        await message_or_query.edit_message_text(
            menu_text, 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message_or_query.reply_text(
            menu_text, 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    get_or_create_user(user_id, query.from_user.username, query.from_user.first_name)
    
    if data == "main_menu":
        if user_id in waiting_for_feedback:
            del waiting_for_feedback[user_id]
        if user_id in waiting_for_broadcast:
            del waiting_for_broadcast[user_id]
        await show_main_menu(query, user_id, edit=True)
        return
    
    if data == "admin_panel":
        if user_id in waiting_for_broadcast:
            del waiting_for_broadcast[user_id]
    
    if data == "menu_news":
        await show_news_menu(query, user_id, page=0)
        return
    
    if data.startswith("news_page_"):
        page = int(data.split("_")[2])
        await show_news_menu(query, user_id, page=page)
        return
    
    if data.startswith("news_cat_"):
        parts = data.split("_")
        cat = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 0
        await show_category_news(query, user_id, cat, page)
        return
    
    if data == "menu_categories":
        await show_categories_menu(query)
        return
    
    if data == "menu_profile":
        await show_profile(query, user_id)
        return
    
    if data == "menu_bookmarks":
        await show_bookmarks(query, user_id, page=0)
        return
    
    if data.startswith("bookmarks_page_"):
        page = int(data.split("_")[2])
        await show_bookmarks(query, user_id, page=page)
        return
    
    if data.startswith("bookmark_"):
        post_id = data[9:]
        added = toggle_bookmark(user_id, post_id)
        status = "added to" if added else "removed from"
        await query.answer(f"Post {status} bookmarks!", show_alert=True)
        return
    
    if data == "menu_subscriptions":
        await show_subscriptions(query, user_id)
        return
    
    if data.startswith("toggle_sub_"):
        category = data[11:]
        subscribed = toggle_subscription(user_id, category)
        status = "subscribed to" if subscribed else "unsubscribed from"
        await query.answer(f"You {status} {category}!", show_alert=True)
        await show_subscriptions(query, user_id)
        return
    
    if data == "menu_settings":
        await show_settings(query, user_id)
        return
    
    if data == "toggle_notifications":
        enabled = toggle_notifications(user_id)
        status = "enabled" if enabled else "disabled"
        await query.answer(f"Notifications {status}!", show_alert=True)
        await show_settings(query, user_id)
        return
    
    if data == "menu_stats":
        await show_channel_stats(query)
        return
    
    if data == "menu_about":
        await show_about(query)
        return
    
    if data == "menu_feedback":
        await show_feedback_prompt(query, user_id)
        return
    
    if data.startswith("view_post_"):
        post_id = data[10:]
        await show_post_detail(query, user_id, post_id)
        return
    
    if data.startswith("share_post_"):
        post_id = data[11:]
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT title, link, channel_message_id FROM posts WHERE id=?", (post_id,))
        post = cur.fetchone()
        conn.close()
        
        if post:
            title, link, channel_msg_id = post
            
            if channel_msg_id:
                post_link = f"https://t.me/{CHANNEL_USERNAME}/{channel_msg_id}"
            else:
                post_link = f"https://t.me/{CHANNEL_USERNAME}"
            
            share_text = f"📰 {title}\n\n🔗 Read more: {post_link}\n\n📢 Join @{CHANNEL_USERNAME} for more WhatsApp news!"
            
            increment_share_count(post_id, user_id)
            
            await query.message.reply_text(
                f"<b>Share this post:</b>\n\n{share_text}\n\n👆 <i>Forward this message to share with friends!</i>",
                parse_mode="HTML"
            )
            await query.answer("Share message sent! Forward it to share.", show_alert=True)
        else:
            await query.answer("Post not found!", show_alert=True)
        return
    
    if data == "admin_panel" and user_id == ADMIN_ID:
        await show_admin_panel(query)
        return
    
    if data == "admin_feedback" and user_id == ADMIN_ID:
        await show_admin_feedback(query)
        return
    
    if data == "admin_users" and user_id == ADMIN_ID:
        await show_admin_users(query)
        return
    
    if data == "admin_refresh" and user_id == ADMIN_ID:
        await query.answer("Refreshing feed...", show_alert=False)
        try:
            await process_feed(context.application)
            await query.answer("Feed refreshed successfully!", show_alert=True)
        except Exception as e:
            await query.answer(f"Error: {str(e)[:50]}", show_alert=True)
        return
    
    if data == "admin_test_post" and user_id == ADMIN_ID:
        await admin_send_test_post(query, context)
        return
    
    if data == "admin_broadcast" and user_id == ADMIN_ID:
        await show_broadcast_prompt(query, user_id)
        return

async def show_news_menu(query, user_id, page=0):
    posts = get_recent_posts(limit=5, offset=page*5)
    total = get_posts_count()
    total_pages = max(1, (total + 4) // 5)
    
    if not posts:
        text = "<b>Latest News</b>\n\nNo posts available yet."
        keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="main_menu")]]
    else:
        text = f"<b>Latest News</b> (Page {page+1}/{total_pages})\n\n"
        keyboard = []
        for post in posts:
            post_id, title, link, category, shares = post
            short_title = title[:30] + "..." if len(title) > 30 else title
            keyboard.append([InlineKeyboardButton(f"{short_title}", callback_data=f"view_post_{post_id}")])
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("Previous", callback_data=f"news_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Next", callback_data=f"news_page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_categories_menu(query):
    text = "<b>Browse by Category</b>\n\nSelect a category to view posts:"
    keyboard = []
    for cat in CATEGORIES:
        count = get_posts_count(cat)
        keyboard.append([InlineKeyboardButton(f"{cat} ({count} posts)", callback_data=f"news_cat_{cat}_0")])
    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_category_news(query, user_id, category, page=0):
    posts = get_recent_posts(limit=5, offset=page*5, category=category)
    total = get_posts_count(category)
    total_pages = max(1, (total + 4) // 5)
    
    if not posts:
        text = f"<b>{category} News</b>\n\nNo posts in this category yet."
    else:
        text = f"<b>{category} News</b> (Page {page+1}/{total_pages})\n\n"
    
    keyboard = []
    for post in posts:
        post_id, title, link, cat, shares = post
        short_title = title[:30] + "..." if len(title) > 30 else title
        keyboard.append([InlineKeyboardButton(f"{short_title}", callback_data=f"view_post_{post_id}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("Previous", callback_data=f"news_cat_{category}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next", callback_data=f"news_cat_{category}_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("Back to Categories", callback_data="menu_categories")])
    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_profile(query, user_id):
    profile, shares, bookmarks, subs = get_user_profile(user_id)
    
    if profile:
        username = profile[1] or "Not set"
        first_name = profile[2] or "User"
        joined = profile[3][:10] if profile[3] else "Unknown"
        
        text = f"""
👤 <b>Your Profile</b>

━━━━━━━━━━━━━━━

📛 <b>Name:</b> {first_name}
🔗 <b>Username:</b> @{username}
📅 <b>Joined:</b> {joined}

━━━━━━━━━━━━━━━
📊 <b>Activity Stats:</b>
━━━━━━━━━━━━━━━

🔗 Posts Shared: {shares}
🔖 Bookmarks: {bookmarks}
🔔 Subscriptions: {subs}
"""
    else:
        text = "Profile not found. Send /start to register."
    
    keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="main_menu")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_bookmarks(query, user_id, page=0):
    bookmarks = get_user_bookmarks(user_id, limit=5, offset=page*5)
    
    if not bookmarks:
        text = "<b>🔖 Your Bookmarks</b>\n\nNo bookmarks yet. Browse news to save articles!"
        keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="main_menu")]]
    else:
        text = f"<b>🔖 Your Bookmarks</b>\n\n"
        keyboard = []
        for bm in bookmarks:
            post_id, title, link, category = bm
            short_title = title[:30] + "..." if len(title) > 30 else title
            keyboard.append([InlineKeyboardButton(f"{short_title}", callback_data=f"view_post_{post_id}")])
        
        keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_subscriptions(query, user_id):
    subs = get_user_subscriptions(user_id)
    
    text = """
🔔 <b>Subscriptions</b>

━━━━━━━━━━━━━━━

Toggle categories to receive notifications for new posts:
"""
    
    keyboard = []
    for cat in CATEGORIES:
        status = "✅" if cat in subs else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {cat}", callback_data=f"toggle_sub_{cat}")])
    
    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="main_menu")])
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_settings(query, user_id):
    notifications = get_notifications_status(user_id)
    notif_status = "🔔 ON" if notifications else "🔕 OFF"
    
    text = f"""
⚙️ <b>Settings</b>

━━━━━━━━━━━━━━━

<b>Notifications:</b> {notif_status}
"""
    
    keyboard = [
        [InlineKeyboardButton(f"Toggle Notifications ({notif_status})", callback_data="toggle_notifications")],
        [InlineKeyboardButton("Back to Menu", callback_data="main_menu")],
    ]
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_channel_stats(query):
    posts, users, top_posts = get_stats()
    
    text = f"""
📊 <b>Channel Statistics</b>

━━━━━━━━━━━━━━━

📰 Total Posts: {posts}
👥 Total Users: {users}

━━━━━━━━━━━━━━━
🔥 <b>Top Shared Posts:</b>
━━━━━━━━━━━━━━━
"""
    
    for i, (title, shares) in enumerate(top_posts[:5], 1):
        short_title = title[:25] + "..." if len(title) > 25 else title
        text += f"\n{i}. {short_title} ({shares} shares)"
    
    keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="main_menu")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_about(query):
    text = """
ℹ️ <b>About WABeta News Bot</b>

━━━━━━━━━━━━━━━

📱 Your source for WhatsApp news and updates!

✨ <b>Features:</b>
• Latest WhatsApp news and updates
• Category-based browsing
• Bookmark your favorite articles
• Subscribe for notifications
• Share posts with friends

━━━━━━━━━━━━━━━

🔗 Channel: @WhatsApp_Updates_X
💬 Feedback welcome!

━━━━━━━━━━━━━━━
"""
    
    keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="main_menu")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_feedback_prompt(query, user_id):
    waiting_for_feedback[user_id] = True
    
    text = """
💬 <b>Send Feedback</b>

━━━━━━━━━━━━━━━

Please type your feedback message below.
We appreciate your input!

━━━━━━━━━━━━━━━
"""
    
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="main_menu")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_post_detail(query, user_id, post_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT id, title, link, category, share_count FROM posts WHERE id=?", (post_id,))
    post = cur.fetchone()
    conn.close()
    
    if not post:
        await query.answer("Post not found!", show_alert=True)
        return
    
    pid, title, link, category, shares = post
    bookmarked = is_bookmarked(user_id, post_id)
    bm_text = "❌ Remove Bookmark" if bookmarked else "🔖 Bookmark"
    
    text = f"""
📰 <b>{title}</b>

━━━━━━━━━━━━━━━

📂 Category: {category}
🔗 Shares: {shares}

━━━━━━━━━━━━━━━
"""
    
    keyboard = [
        [InlineKeyboardButton("🔗 Read Article", url=link)],
        [
            InlineKeyboardButton(bm_text, callback_data=f"bookmark_{post_id}"),
            InlineKeyboardButton("📤 Share", callback_data=f"share_post_{post_id}"),
        ],
        [InlineKeyboardButton("Back to News", callback_data="menu_news")],
        [InlineKeyboardButton("Back to Menu", callback_data="main_menu")],
    ]
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_admin_panel(query):
    stats = get_admin_stats()
    
    text = f"""
🔐 <b>Admin Panel</b>

━━━━━━━━━━━━━━━
📊 <b>Statistics:</b>
━━━━━━━━━━━━━━━

👥 Users: {stats['users']}
📰 Posts: {stats['posts']}
🔖 Bookmarks: {stats['bookmarks']}
🔗 Shares: {stats['shares']}
💬 Pending Feedback: {stats['pending_feedback']}
📈 Daily Activity: {stats['daily_activity']}

━━━━━━━━━━━━━━━
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Feed", callback_data="admin_refresh")],
        [InlineKeyboardButton("📝 Test Post", callback_data="admin_test_post")],
        [InlineKeyboardButton("💬 View Feedback", callback_data="admin_feedback")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("Back to Menu", callback_data="main_menu")],
    ]
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_admin_feedback(query):
    feedback = get_pending_feedback()
    
    if not feedback:
        text = "<b>💬 Feedback</b>\n\nNo pending feedback."
    else:
        text = "<b>💬 Pending Feedback</b>\n\n"
        for fb in feedback:
            fid, uid, msg, created = fb
            text += f"━━━━━━━━━━━━━━━\n"
            text += f"👤 User: {uid}\n"
            text += f"💬 {msg[:100]}...\n" if len(msg) > 100 else f"💬 {msg}\n"
    
    keyboard = [[InlineKeyboardButton("Back to Admin", callback_data="admin_panel")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_admin_users(query):
    stats = get_admin_stats()
    text = f"<b>👥 User Statistics</b>\n\nTotal Users: {stats['users']}"
    keyboard = [[InlineKeyboardButton("Back to Admin", callback_data="admin_panel")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_broadcast_prompt(query, user_id):
    waiting_for_broadcast[user_id] = True
    
    text = """
📢 <b>Broadcast Message</b>

━━━━━━━━━━━━━━━

Type your broadcast message below.
It will be sent to all users with notifications enabled.

━━━━━━━━━━━━━━━
"""
    
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="admin_panel")]]
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_send_test_post(query, context):
    await query.answer("Sending test post to channel...", show_alert=False)
    
    try:
        feed = fetch_rss_feed()
        if not feed.entries:
            await query.answer("No posts found in feed!", show_alert=True)
            return
        
        latest = feed.entries[0]
        full_article, categories = build_full_article(latest)
        
        save_post(
            latest.id,
            getattr(latest, "title", ""),
            getattr(latest, "link", ""),
            getattr(latest, "published", ""),
            categories[0] if categories else "General",
        )
        
        image_data = download_image(latest)
        if image_data:
            if len(full_article) > 1024:
                full_article = full_article[:1021] + "..."
            
            sent_msg = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_data,
                caption=full_article,
                parse_mode="HTML",
            )
            
            update_post_message_id(latest.id, sent_msg.message_id)
            await query.answer("Test post sent successfully!", show_alert=True)
        else:
            await query.answer("Failed to download image!", show_alert=True)
    except Exception as e:
        await query.answer(f"Error: {str(e)[:50]}", show_alert=True)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id in waiting_for_feedback:
        del waiting_for_feedback[user_id]
        save_feedback(user_id, text)
        await update.message.reply_text(
            "✅ Thank you for your feedback! We appreciate it.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Menu", callback_data="main_menu")]])
        )
        return
    
    if user_id in waiting_for_broadcast and user_id == ADMIN_ID:
        del waiting_for_broadcast[user_id]
        
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM user_profiles WHERE notifications_enabled=1")
        users = [r[0] for r in cur.fetchall()]
        conn.close()
        
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 <b>Broadcast Message</b>\n\n{text}",
                    parse_mode="HTML"
                )
                sent += 1
            except:
                pass
        
        await update.message.reply_text(
            f"✅ Broadcast sent to {sent} users!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Admin", callback_data="admin_panel")]])
        )
        return

async def process_feed(app):
    print("Processing RSS feed...")
    feed = fetch_rss_feed()
    
    if not feed.entries:
        print("No entries in feed")
        return
    
    for entry in feed.entries[:5]:
        post_id = entry.id
        
        if has_post(post_id):
            continue
        
        print(f"New post found: {entry.title}")
        
        full_article, categories = build_full_article(entry)
        main_cat = categories[0] if categories else "General"
        
        save_post(
            post_id,
            getattr(entry, "title", ""),
            getattr(entry, "link", ""),
            getattr(entry, "published", ""),
            main_cat,
        )
        
        if app:
            try:
                image_data = download_image(entry)
                if image_data:
                    if len(full_article) > 1024:
                        full_article = full_article[:1021] + "..."
                    
                    sent_msg = await app.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=image_data,
                        caption=full_article,
                        parse_mode="HTML",
                    )
                    
                    update_post_message_id(post_id, sent_msg.message_id)
                    print(f"Posted to channel: {entry.title}")
                    
                    subscribed = get_subscribed_users(main_cat)
                    for uid in subscribed:
                        try:
                            await app.bot.send_message(
                                chat_id=uid,
                                text=f"🔔 New {main_cat} post!\n\n📰 {entry.title}\n\n👆 Check the channel for details!",
                                parse_mode="HTML"
                            )
                        except:
                            pass
            except Exception as e:
                print(f"Error posting to channel: {e}")
        
        await asyncio.sleep(2)

async def feed_check_job(context: ContextTypes.DEFAULT_TYPE):
    await process_feed(context.application)

def main():
    print("Initializing database...")
    init_database()
    
    print("Starting Flask keep-alive server...")
    keep_alive()
    
    print(f"Starting bot with token: {TOKEN[:20]}...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", panel_cmd))
    app.add_handler(CommandHandler("panel", panel_cmd))
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    job_queue = app.job_queue
    job_queue.run_repeating(feed_check_job, interval=CHECK_INTERVAL, first=10)
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
