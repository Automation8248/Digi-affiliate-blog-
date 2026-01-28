import os
import json
import random
import re
import time
import requests # Catbox ke liye zaroori
from datetime import datetime
from openai import OpenAI
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import socket

# --- CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GH_MARKETPLACE_TOKEN")

# 👉 HARDCODED BLOG ID
BLOGGER_ID = "8697171360337652733"

# Authentication Variables
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

# DeepSeek Client
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# --- 1. HELPER FUNCTIONS ---

def clean_text_for_blogger(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    text = re.sub(r'^Title:\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

def get_smart_labels(product):
    niche_keywords = product.get('niche', 'Health').split('&')
    clean_niche = [w.strip() for w in niche_keywords if len(w.strip()) > 3]
    base_labels = ["Health Review", "Wellness Tips"]
    product_label = [product['product_name']]
    all_labels = list(set(product_label + clean_niche + base_labels))
    return all_labels[:5]

# 👉 FUNCTION: Upload to CATBOX.MOE (Images 100% dikhengi)
def upload_to_catbox(image_url):
    print(f"⬇️ Processing Image: {image_url[:40]}...")
    try:
        # 1. Download Image
        headers = {'User-Agent': 'Mozilla/5.0'}
        img_resp = requests.get(image_url, headers=headers, timeout=15)
        
        if img_resp.status_code != 200:
            print(f"❌ Download Failed: {img_resp.status_code}")
            return None
            
        # 2. Upload to Catbox
        catbox_api = "https://catbox.moe/user/api.php"
        data = {'reqtype': 'fileupload'}
        files = {
            'fileToUpload': ('image.jpg', img_resp.content, 'image/jpeg')
        }
        
        upload_resp = requests.post(catbox_api, data=data, files=files, timeout=30)
        
        if upload_resp.status_code == 200:
            new_url = upload_resp.text.strip()
            print(f"✅ Catbox Link Created: {new_url}")
            return new_url
        else:
            print(f"❌ Catbox Failed: {upload_resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ Image Error: {e}")
        return None

# --- 2. MEMORY & PRODUCT SELECTION ---

def get_eligible_product():
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try: history = json.load(f)
            except: history = {}
    else: history = {}

    all_files = [f for f in os.listdir('products') if f.endswith('.json')]
    
    if not all_files:
        print("❌ CRITICAL: No JSON files found in 'products/' folder.")
        exit()

    available_products = []
    today = datetime.now().date()
    
    for filename in all_files:
        product_name = filename.replace('.json', '')
        last_used_str = history.get(product_name)
        if last_used_str:
            last_used_date = datetime.strptime(last_used_str, "%Y-%m-%d").date()
            if (today - last_used_date).days < 5:
                continue 
        available_products.append(filename)

    if not available_products:
        print("⚠️ All products in cooldown. Picking random.")
        return random.choice(all_files)

    return random.choice(available_products)

def update_history(filename):
    product_name = filename.replace('.json', '')
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try: history = json.load(f)
            except: history = {}
    else: history = {}
    history[product_name] = datetime.now().strftime("%Y-%m-%d")
    with open('history.json', 'w') as f: json.dump(history, f, indent=4)

# --- 3. AI CONTENT GENERATION (STRICT HUMANIZED PROMPT) ---

def generate_content(product):
    print(f"✍️ Writing article for: {product['product_name']}...")
    
    # 👉 YOUR ORIGINAL HUMANIZED PROMPT IS BACK
    system_prompt = """
    You are a professional Health Affiliate Content Writer for US and UK audiences.
    Your goal is to educate first and softly review products without making medical claims.

    *** STRICT & NON-NEGOTIABLE RULES (TO AVOID BAN) ***
    1. LANGUAGE: Use very simple, clear English (Grade 7-8 level). Write for normal people.
    2. TONE: Informational, neutral, and helpful. NEVER aggressive or salesy.
    3. PARAGRAPHS: Each paragraph must contain ONLY 2–3 short sentences.
    4. CLAIMS: NEVER say "cure", "treat", "prevent", "fix", or "guaranteed results".
       - Use ONLY soft words like: "may help", "supports", "designed to", "can be useful".
    5. COMPLIANCE: Content must feel like an educational blog, not a sales page.
    6. FORMATTING: Use ONLY clean HTML tags (<p>, <h2>, <ul>, <li>, <strong>). NO Markdown.
    7. VOCABULARY: Do NOT use AI words like "Delve", "Realm", "Unlock", "Revolutionary".

    *** CONTENT STRATEGY (Hybrid Blog + Review) ***
    - 60% Education & General Advice (This keeps the blog safe).
    - 30% Neutral Product Review.
    - 10% Soft Call-to-Action.

    *** REQUIRED STRUCTURE (FOLLOW EXACTLY) ***

    Title: [Curiosity-based, safe title. Do NOT start with Product Name]
    |||
    <h2>[Heading: Introduce the Problem, e.g., Why Energy Drops Afternoon]</h2>
    <p>Introduce the common problem in a general, educational way. Show empathy.</p>

    <h2>Why This Is a Common Issue</h2>
    <p>Explain why many people face this issue (lifestyle, diet, age) in simple terms.</p>

    <h2>General Ways to Support This Health Area</h2>
    <p>Talk about water, sleep, or habits FIRST. Do NOT mention the product yet. (This builds trust).</p>

    <h2>An Option People Are Talking About: [Product Name]</h2>
    <p>Introduce the product softly as one possible option people consider for extra support.</p>

    <h2>What is [Product Name] Designed For?</h2>
    <p>Explain what it aims to do, using words like "supports" or "promotes". No hype.</p>

    <h2>Potential Benefits</h2>
    <ul>
    <li>[Benefit 1 - One short sentence]</li>
    <li>[Benefit 2 - One short sentence]</li>
    <li>[Benefit 3 - One short sentence]</li>
    <li>[Benefit 4 - One short sentence]</li>
    <li>[Benefit 5 - One short sentence]</li>
    </ul>

    <h2>Pros and Cons</h2>
    <p><strong>Pros:</strong></p>
    <ul>
    <li>Natural ingredients</li>
    <li>Easy to use</li>
    <li>(Add 1-2 more real pros)</li>
    </ul>
    <p><strong>Cons:</strong></p>
    <ul>
    <li>Only available online</li>
    <li>Results may vary from person to person</li>
    </ul>

    <h2>Who Should Consider This?</h2>
    <p>Define the audience gently using "may" and "might". (e.g., "People who want extra support with X").</p>

    <h2>Final Thoughts</h2>
    <p>Wrap up warmly. Add a soft CTA like: "If you are interested, you can check the official details below."</p>

    <h2>Frequently Asked Questions</h2>
    <p><strong>Q: [Insert Question]?</strong><br>A: [Short, neutral answer].</p>
    <p><strong>Q: [Insert Question]?</strong><br>A: [Short, neutral answer].</p>
    <p><strong>Q: [Insert Question]?</strong><br>A: [Short, neutral answer].</p>

    <p><em><small>Disclaimer: This article is for informational purposes only and does not replace professional medical advice. Individual results may vary.</small></em></p>
    """
    
    user_prompt = f"Write a simple, human-like review for '{product['product_name']}' in the niche '{product['niche']}'."

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="DeepSeek-R1",
            temperature=0.9, # Thoda creative taki human lage
            max_tokens=4000 
        )
        raw_text = response.choices[0].message.content
        cleaned_text = clean_text_for_blogger(raw_text)
        
        if "|||" in cleaned_text:
            parts = cleaned_text.split("|||")
            title = parts[0].replace("Title:", "").strip()
            body = parts[1].strip()
        else:
            lines = cleaned_text.split('\n')
            title = lines[0].replace("Title:", "").strip()
            body = "\n".join(lines[1:])
            
        title = title.replace('"', '').replace('*', '')
        paragraphs = [p.strip() for p in re.split(r'</p>|\n\n', body) if len(p.strip()) > 20]
        cleaned_paras = []
        for p in paragraphs:
            if not p.startswith('<p>'): p = f"<p>{p}"
            if not p.endswith('</p>'): p = f"{p}</p>"
            cleaned_paras.append(p)
            
        return title, cleaned_paras
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"Review: {product['product_name']}", ["Content generation failed."]

# --- 4. IMAGE & BUTTON INJECTION ---

def create_promo_block(image_url, affiliate_link):
    # 👉 AMAZON STYLE BUTTON (Yellow/Orange)
    btn_style = """
        background: linear-gradient(to bottom, #f8c147 0%, #f7dfa5 100%);
        background-color: #f0c14b;
        border: 1px solid #a88734;
        color: #111 !important;
        padding: 12px 24px;
        font-size: 18px;
        font-weight: bold;
        text-decoration: none;
        border-radius: 4px;
        display: inline-block;
        margin: 20px 0;
        cursor: pointer;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset;
    """
    img_style = "width: 100%; max-width: 600px; height: auto; border: 1px solid #eee; margin-bottom: 15px; border-radius: 8px;"
    
    html = f"""
    <div style="text-align: center; margin: 35px 0;">
        <a href="{affiliate_link}" target="_blank" rel="nofollow">
            <img src="{image_url}" style="{img_style}" alt="Product View">
        </a>
        <br>
        <a href="{affiliate_link}" target="_blank" rel="nofollow" style="{btn_style}">
            BUY NOW
        </a>
    </div>
    """
    return html

def merge_content(title, paragraphs, product):
    all_image_urls = product.get('image_urls', [])
    if not all_image_urls:
        print("⚠️ No image URLs found.")
        all_image_urls = []

    # Select 2 or 3 random URLs
    num_images_to_use = random.randint(2, 3)
    selected_urls = random.sample(all_image_urls, min(len(all_image_urls), num_images_to_use))
    
    # 👉 UPLOAD TO CATBOX
    ready_to_use_images = []
    for url in selected_urls:
        catbox_url = upload_to_catbox(url)
        if catbox_url:
            ready_to_use_images.append(catbox_url)

    print(f"✅ Images Ready (Catbox): {len(ready_to_use_images)}")
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    # 1. Add Title in Body
    final_html += f"<h1 style='text-align: center; color: #2c3e50; margin-bottom: 25px;'>{title}</h1>"
    
    # 2. Add First Paragraph
    if paragraphs:
        final_html += paragraphs[0]
        remaining_paras = paragraphs[1:]
    else:
        remaining_paras = []
        
    # 3. Add First Catbox Image & Button
    if ready_to_use_images:
        final_html += create_promo_block(ready_to_use_images.pop(0), affiliate_link)
        
    # 4. Mix remaining images
    if ready_to_use_images and remaining_paras:
        gap = max(1, len(remaining_paras) // (len(ready_to_use_images) + 1))
        idx = 0
        
        for img_url in ready_to_use_images:
            for _ in range(gap):
                if idx < len(remaining_paras):
                    final_html += remaining_paras[idx]
                    idx += 1
            final_html += create_promo_block(img_url, affiliate_link)
            
        while idx < len(remaining_paras):
            final_html += remaining_paras[idx]
            idx += 1
    else:
        for p in remaining_paras: final_html += p
        
    return final_html

# --- 5. PUBLISH TO BLOGGER ---

def post_to_blogger(title, content_html, labels):
    print(f"🔑 Authenticating... (Target Blog ID: {BLOGGER_ID})")
    
    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        print("❌ ERROR: Secrets missing (CLIENT_ID/SECRET/REFRESH_TOKEN)")
        return

    creds_info = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/blogger"]
    }

    try:
        # Increase timeout
        socket.setdefaulttimeout(120) 

        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        # 👉 PROFESSIONAL HTML STYLING (Restore kiya gaya hai)
        final_styled_body = f"""
        <div style="font-family: Verdana, sans-serif; font-size: 16px; line-height: 1.6; color: #333; background-color: #fff; padding: 15px; max-width: 800px; margin: auto;">
            {content_html}
            <br><hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 13px; color: #777; text-align: center;">
                <i>Transparency: This article contains affiliate links. We may earn a small commission if you purchase through them.</i>
            </p>
        </div>
        """
        
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": final_styled_body,
            "labels": labels 
        }
        
        print("🚀 Uploading post to Blogger...")
        posts = service.posts()
        result = posts.insert(blogId=BLOGGER_ID, body=body).execute()
        print(f"✅ SUCCESS! Published: '{title}'")
        print(f"🔗 URL: {result['url']}")
        
    except HttpError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"🔍 Reason: {e.error_details}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

# --- MAIN ---
if __name__ == "__main__":
    try:
        selected_file = get_eligible_product()
        print(f"🚀 Processing: {selected_file}")
        
        with open(f'products/{selected_file}', 'r') as f:
            product_data = json.load(f)
            
        seo_labels = get_smart_labels(product_data)
        
        title_text, paras = generate_content(product_data)
        
        if not paras:
            print("❌ Error: No content generated.")
            exit()
            
        # Catbox Logic enabled
        final_blog_post = merge_content(title_text, paras, product_data)
        
        post_to_blogger(title_text, final_blog_post, seo_labels)
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
