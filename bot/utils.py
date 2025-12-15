import re
import os
import requests
from io import BytesIO
from bs4 import BeautifulSoup

CHANNEL_LINK = os.environ.get("TELEGRAM_CHANNEL_LINK", "https://t.me/DevModzBeta")
CHANNEL_USERNAME = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "@WhatsApp_Updates_X")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

WHATSAPP_EMOJIS = {
    "Android": "🤖",
    "iOS": "🍎",
    "Windows": "💻",
    "Web": "🌐",
    "General": "📱",
    "Beta": "🧪",
    "Update": "🔄",
    "Feature": "✨",
    "News": "📰",
}

CONTENT_EMOJIS = {
    "whatsapp": "💬",
    "message": "✉️",
    "chat": "💭",
    "call": "📞",
    "video": "🎥",
    "voice": "🎤",
    "audio": "🔊",
    "photo": "📸",
    "image": "🖼️",
    "file": "📁",
    "document": "📄",
    "send": "📤",
    "receive": "📥",
    "download": "⬇️",
    "upload": "⬆️",
    "share": "🔗",
    "link": "🔗",
    "group": "👥",
    "community": "🏘️",
    "channel": "📢",
    "status": "🔄",
    "story": "📖",
    "privacy": "🔒",
    "security": "🛡️",
    "encryption": "🔐",
    "password": "🔑",
    "block": "🚫",
    "mute": "🔇",
    "notification": "🔔",
    "settings": "⚙️",
    "profile": "👤",
    "emoji": "😊",
    "sticker": "🎨",
    "gif": "🎞️",
    "reaction": "👍",
    "forward": "↪️",
    "reply": "↩️",
    "delete": "🗑️",
    "edit": "✏️",
    "search": "🔍",
    "backup": "💾",
    "restore": "♻️",
    "update": "🆕",
    "version": "📋",
    "beta": "🧪",
    "test": "🔬",
    "feature": "✨",
    "new": "🆕",
    "improve": "📈",
    "fix": "🔧",
    "bug": "🐛",
    "user": "👤",
    "admin": "👑",
    "business": "💼",
    "payment": "💳",
    "money": "💰",
    "android": "🤖",
    "ios": "🍎",
    "desktop": "💻",
    "windows": "🖥️",
    "web": "🌐",
    "browser": "🌐",
    "dark": "🌙",
    "light": "☀️",
    "theme": "🎨",
    "release": "🚀",
    "launch": "🚀",
}

HASHTAGS = [
    "#WhatsApp",
    "#WhatsAppUpdate",
    "#WABeta_News",
    "#WhatsAppNews",
    "#Share",
]

def clean_brand_text(text):
    if not text:
        return text
    
    replacements = [
        ("WABetaInfo", "WABeta News"),
        ("wabetainfo", "WABeta News"),
        ("WaBetaInfo", "WABeta News"),
        ("WABETAINFO", "WABeta News"),
        ("WABetaInfo on X", "WABeta News on Telegram"),
        ("wabetainfo on X", "WABeta News on Telegram"),
        (" on X,", " on Telegram,"),
        (" on X.", " on Telegram."),
        (" on X ", " on Telegram "),
        ("Twitter", "Telegram"),
        ("twitter", "Telegram"),
    ]
    
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
    
    result = re.sub(r'\bWABetaInfo\b', 'WABeta News', result, flags=re.IGNORECASE)
    result = re.sub(r'\bon X\b', 'on Telegram', result, flags=re.IGNORECASE)
    
    return result

def fetch_full_article_content(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            
            article_content = soup.find('div', class_='entry-content')
            if not article_content or not hasattr(article_content, 'find_all'):
                article_content = soup.find('article')
            if not article_content or not hasattr(article_content, 'find_all'):
                article_content = soup.find('div', class_='post-content')
            if not article_content or not hasattr(article_content, 'find_all'):
                article_content = soup.find('main')
            
            if article_content and hasattr(article_content, 'find_all'):
                paragraphs = article_content.find_all(['p', 'h2', 'h3', 'h4', 'li', 'blockquote'])
                
                full_text_parts = []
                for elem in paragraphs:
                    if hasattr(elem, 'get_text'):
                        text = elem.get_text().strip()
                        if text and len(text) > 10:
                            if elem.name in ['h2', 'h3', 'h4']:
                                full_text_parts.append(f"\n\n<b>📌 {text}</b>\n")
                            elif elem.name == 'blockquote':
                                full_text_parts.append(f"\n<i>「{text}」</i>\n")
                            elif elem.name == 'li':
                                full_text_parts.append(f"• {text}")
                            else:
                                full_text_parts.append(text)
                
                full_text = '\n\n'.join(full_text_parts)
                return clean_brand_text(full_text)
    except Exception as e:
        print(f"Error fetching full article: {e}")
    return ""

def format_full_article_with_emojis(title, article_text, link, categories, main_cat, max_chars=1024):
    emoji, _ = get_category_emoji(categories)
    
    extra_hashtags = []
    if "beta" in title.lower():
        extra_hashtags.append("#Beta")
    if "android" in title.lower() or main_cat == "Android":
        extra_hashtags.append("#Android")
    if "ios" in title.lower() or main_cat == "iOS":
        extra_hashtags.append("#iOS")
    
    all_hashtags = extra_hashtags.copy()
    base_hashtags = ["#WhatsApp", "#WhatsAppUpdate", "#WABeta_News", "#WhatsAppNews"]
    for tag in base_hashtags:
        if tag not in all_hashtags:
            all_hashtags.append(tag)
    
    hashtag_text = " ".join(all_hashtags[:6])
    
    header = f"""📰 {title}

{emoji} Summary:
<i>"""
    
    footer = f"""</i>

━━━━━━━━━━━━━━━

{hashtag_text}

━━━━━━━━━━━━━━━

📢 Join Our Channel:
{CHANNEL_USERNAME}"""

    available_chars = max_chars - len(header) - len(footer)
    
    summary_text = article_text if article_text else ""
    
    if len(summary_text) > available_chars:
        sentences = re.split(r'(?<=[.!?])\s+', summary_text.strip())
        truncated = []
        current_len = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if current_len + len(sentence) + 1 <= available_chars:
                truncated.append(sentence)
                current_len += len(sentence) + 1
            else:
                break
        summary_text = ' '.join(truncated)
        if not summary_text.endswith('.') and not summary_text.endswith('!') and not summary_text.endswith('?'):
            summary_text = summary_text.rstrip() + '.'
    
    full_article = header + summary_text + footer

    return full_article

def fetch_article_content(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            
            article_content = soup.find('div', class_='entry-content')
            if not article_content or not hasattr(article_content, 'find_all'):
                article_content = soup.find('article')
            if not article_content or not hasattr(article_content, 'find_all'):
                article_content = soup.find('div', class_='post-content')
            
            if article_content and hasattr(article_content, 'find_all'):
                paragraphs = article_content.find_all('p')
                text = ' '.join([p.get_text().strip() for p in paragraphs if hasattr(p, 'get_text') and p.get_text().strip()])
                return clean_brand_text(text)
    except Exception as e:
        print(f"Error fetching article: {e}")
    return ""

def get_article_image(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            
            article_content = soup.find('div', class_='entry-content')
            if not article_content or not hasattr(article_content, 'find_all'):
                article_content = soup.find('article')
            
            if article_content and hasattr(article_content, 'find_all'):
                images = article_content.find_all('img')
                for img in images:
                    if hasattr(img, 'get'):
                        src = img.get('src', '') or img.get('data-src', '')
                        if src and isinstance(src, str) and 'wabetainfo.com' in src:
                            if 'wp-content/uploads' in src and 'logo' not in src.lower():
                                print(f"Found article image: {src}")
                                return src
            
            og_image = soup.find('meta', attrs={'property': 'og:image'})
            if og_image and hasattr(og_image, 'get'):
                img_url = og_image.get('content', '')
                if img_url and isinstance(img_url, str) and 'logo' not in img_url.lower():
                    print(f"Found og:image: {img_url}")
                    return img_url
    except Exception as e:
        print(f"Error getting article image: {e}")
    return None

def summarize_with_huggingface(text, max_length=1500, min_length=500):
    if not text or len(text) < 200:
        return text
    
    try:
        api_url = "https://router.huggingface.co/hf-inference/models/facebook/bart-large-cnn"
        
        hf_token = os.environ.get("HUGGINGFACE_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        
        input_text = text[:4000]
        
        payload = {
            "inputs": input_text,
            "parameters": {
                "max_length": max_length,
                "min_length": min_length,
                "do_sample": False
            },
            "options": {
                "wait_for_model": True
            }
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                summary = result[0].get('summary_text', '')
                if summary:
                    print(f"HuggingFace summarization successful: {len(summary)} chars")
                    return summary
        elif response.status_code == 503:
            print("HuggingFace model loading, using fallback...")
        else:
            print(f"HuggingFace API error: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"HuggingFace summarization failed: {e}")
    
    return None

def extract_key_sentences(text, max_sentences=8):
    if not text:
        return []
    
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    key_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        if any(skip in sentence.lower() for skip in ['click here', 'subscribe', 'follow us', 'read more', 'advertisement']):
            continue
        
        importance = 0
        important_words = ['new', 'update', 'feature', 'fix', 'bug', 'add', 'remove', 'change', 'improve', 'support', 'enable', 'disable', 'option', 'setting', 'version', 'beta', 'stable', 'release', 'whatsapp', 'android', 'ios', 'now', 'can', 'will', 'allow', 'introduce']
        for word in important_words:
            if word in sentence.lower():
                importance += 1
        
        if importance > 0 or len(key_sentences) < 3:
            key_sentences.append((importance, sentence))
    
    key_sentences.sort(key=lambda x: x[0], reverse=True)
    
    result = [s[1] for s in key_sentences[:max_sentences]]
    return result

def summarize_text(text, target_words=2500):
    if not text or len(text) < 100:
        return clean_brand_text(text) if text else text
    
    hf_summary = summarize_with_huggingface(text)
    if hf_summary and len(hf_summary) > 200:
        return clean_brand_text(hf_summary)
    
    key_sentences = extract_key_sentences(text, max_sentences=8)
    if key_sentences:
        return clean_brand_text(' '.join(key_sentences))
    
    words = text.split()
    if len(words) > target_words:
        summary = ' '.join(words[:target_words])
    else:
        summary = text
    
    sentences = re.split(r'(?<=[.!?])\s+', summary)
    if sentences:
        summary = ' '.join(sentences[:-1]) if len(sentences) > 1 else summary
    
    return clean_brand_text(summary)

def get_image(entry):
    link = getattr(entry, "link", "")
    if link:
        article_img = get_article_image(link)
        if article_img:
            return article_img
    
    if hasattr(entry, "media_content") and entry.media_content:
        url = entry.media_content[0]["url"]
        if 'logo' not in url.lower():
            return url
    
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", ""):
                url = enc.get("url", "")
                if url and 'logo' not in url.lower():
                    return url
    
    if hasattr(entry, "content"):
        for content in entry.content:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content.value)
            if img_match:
                url = img_match.group(1)
                if 'logo' not in url.lower():
                    return url
    
    if hasattr(entry, "summary"):
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary)
        if img_match:
            url = img_match.group(1)
            if 'logo' not in url.lower():
                return url
    
    return None

def download_image(entry):
    url = get_image(entry)
    
    if not url:
        print("No image URL found, using fallback")
        url = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/WhatsApp.svg/512px-WhatsApp.svg.png"
    
    print(f"Attempting to download image from: {url}")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://wabetainfo.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        content_type = response.headers.get('content-type', '')
        print(f"Response status: {response.status_code}, Content-Type: {content_type}, Size: {len(response.content)}")
        
        if response.status_code == 200 and 'image' in content_type:
            img_data = BytesIO(response.content)
            img_data.name = 'image.jpg'
            return img_data
    except Exception as e:
        print(f"Error downloading image: {e}")
    
    fallback_urls = [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/WhatsApp.svg/512px-WhatsApp.svg.png",
    ]
    
    for fallback_url in fallback_urls:
        try:
            print(f"Trying fallback: {fallback_url}")
            response = requests.get(fallback_url, headers=headers, timeout=15)
            content_type = response.headers.get('content-type', '')
            if response.status_code == 200 and 'image' in content_type:
                img_data = BytesIO(response.content)
                img_data.name = 'image.png'
                return img_data
        except Exception as e:
            print(f"Error downloading fallback: {e}")
    
    return None

def get_description(entry):
    if hasattr(entry, "summary"):
        text = re.sub(r'<[^>]+>', '', entry.summary)
        text = clean_brand_text(text.strip())
        if len(text) > 150:
            text = text[:147] + "..."
        return text
    return "Stay updated with the latest WhatsApp news and features!"

def get_category_emoji(categories):
    for cat in categories:
        cat_lower = cat.lower()
        if "android" in cat_lower:
            return "🤖", "Android"
        elif "ios" in cat_lower or "iphone" in cat_lower:
            return "🍎", "iOS"
        elif "windows" in cat_lower or "desktop" in cat_lower:
            return "💻", "Windows"
        elif "web" in cat_lower:
            return "🌐", "Web"
        elif "beta" in cat_lower:
            return "🧪", "Beta"
    return "📱", "General"

def build_caption(entry):
    title = clean_brand_text(getattr(entry, "title", "WhatsApp Update"))
    link = getattr(entry, "link", "")
    
    categories = []
    if hasattr(entry, "tags"):
        categories = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
    
    emoji, main_cat = get_category_emoji(categories)
    description = get_description(entry)
    
    caption = f"""📰 <b>{title}</b>

{emoji} {description}

━━━━━━━━━━━━━━━

#WhatsApp #WhatsAppUpdate #WABeta_News

━━━━━━━━━━━━━━━

📢 {CHANNEL_USERNAME}"""
    
    return caption, categories

def build_full_article(entry):
    title = clean_brand_text(getattr(entry, "title", "WhatsApp Update"))
    link = getattr(entry, "link", "")
    
    categories = []
    if hasattr(entry, "tags"):
        categories = [tag.term for tag in entry.tags if hasattr(tag, 'term')]
    
    emoji, main_cat = get_category_emoji(categories)
    
    article_content = ""
    if link:
        article_content = fetch_article_content(link)
    
    if article_content:
        summary = summarize_text(article_content)
    else:
        summary = get_description(entry)
    
    full_article = format_full_article_with_emojis(title, summary, link, categories, main_cat)
    
    return full_article, categories

def split_message(text, max_length=4096):
    if len(text) <= max_length:
        return [text]
    
    messages = []
    while len(text) > max_length:
        split_point = text.rfind('\n', 0, max_length)
        if split_point == -1:
            split_point = max_length
        messages.append(text[:split_point])
        text = text[split_point:].lstrip()
    
    if text:
        messages.append(text)
    
    return messages
