import os
import json
import random
import re
import time
import requests # Image processing ke liye zaroori
import base64   # ImgBB upload ke liye zaroori
from datetime import datetime
from openai import OpenAI
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import socket

# --- CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GH_MARKETPLACE_TOKEN")

# 👉 HARDCODED IMGBB API KEY (Direct Laga Diya Hai)
IMGBB_API_KEY = "d1f8b09182b05dec467a15db11f072f6"

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
    base_labels = ["Health Review", "Wellness Tips", "Honest Reviews"]
    product_label = [product['product_name']]
    all_labels = list(set(product_label + clean_niche + base_labels))
    return all_labels[:5]

# 👉 FEATURE: Upload to ImgBB (Using Hardcoded Key)
def upload_to_imgbb(image_url):
    print(f"⬇️ Processing Image for Blog: {image_url[:40]}...")
    try:
        # 1. Download Image
        headers = {'User-Agent': 'Mozilla/5.0'}
        img_resp = requests.get(image_url, headers=headers, timeout=20)
        
        if img_resp.status_code != 200:
            print(f"❌ Download Failed. Status: {img_resp.status_code}")
            return None
            
        # 2. Convert to Base64
        img_base64 = base64.b64encode(img_resp.content).decode('utf-8')

        # 3. Upload to ImgBB
        url = "https://api.imgbb.com/1/upload"
        payload = {
            'key': IMGBB_API_KEY, # Hardcoded key use ho rahi hai
            'image': img_base64,
        }
        
        upload_resp = requests.post(url, data=payload, timeout=45)
        
        if upload_resp.status_code == 200:
            data = upload_resp.json()
            if data['success']:
                new_url = data['data']['url']
                print(f"✅ Image Ready (ImgBB): {new_url}")
                return new_url
            else:
                print(f"❌ ImgBB Error: {data['error']['message']}")
                return None
        else:
            print(f"❌ Upload Failed. Status: {upload_resp.status_code}")
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

# --- 3. AI CONTENT GENERATION (SAFE & LONG FORM) ---

def generate_content(product):
    print(f"✍️ Writing 1200+ word review for: {product['product_name']}...")
    
    # 👉 SYSTEM PROMPT (SAFE + LONG FORM + HUMANIZED)
    system_prompt = """
    You are a professional Health Affiliate Content Writer.
    Your goal is to write a COMPREHENSIVE (1200–1800 words), SAFE, and HONEST review.

    *** STRICT RULES (TO AVOID BAN & RANK HIGH) ***
    1. WORD COUNT: The article MUST be long, detailed, and cover every aspect. Aim for 1500 words.
    2. LANGUAGE: Simple, clear English (Grade 7-8 level).
    3. TONE: Informational, neutral, and helpful. NEVER aggressive.
    4. CLAIMS: NEVER say "cure", "treat", "fix". Use "supports", "may help".
    5. FORMATTING: Use ONLY clean HTML tags (<p>, <h2>, <ul>, <li>, <strong>).
    6. STRUCTURE: Mix education with review.

    *** REQUIRED STRUCTURE (EXPAND EACH SECTION) ***

    Title: [Curiosity-based, safe title. Do NOT start with Product Name]
    |||
    <h2>[Heading: Describe the Core Problem deeply]</h2>
    <p>[Write 2-3 detailed paragraphs about the struggle/problem]</p>

    <h2>Why This Issue Happens (The Science)</h2>
    <p>[Explain the root causes in simple terms - 2 paragraphs]</p>

    <h2>General Ways to Support Health (Lifestyle)</h2>
    <p>[Discuss diet, sleep, and habits first - 2 paragraphs]</p>

    <h2>Introducing [Product Name]: A Potential Solution?</h2>
    <p>[Introduce the product gently. What is the story behind it?]</p>

    <h2>How [Product Name] Is Designed to Work</h2>
    <p>[Explain the mechanism/working logic in detail]</p>

    <h2>Key Ingredients Analysis</h2>
    <ul>
    <li><strong>Ingredient 1:</strong> What it does (softly).</li>
    <li><strong>Ingredient 2:</strong> What it does (softly).</li>
    <li><strong>Ingredient 3:</strong> What it does (softly).</li>
    <li>(Add more ingredients)</li>
    </ul>

    <h2>Potential Benefits</h2>
    <ul>
    <li>[Benefit 1 - Detailed explanation]</li>
    <li>[Benefit 2 - Detailed explanation]</li>
    <li>[Benefit 3 - Detailed explanation]</li>
    <li>[Benefit 4 - Detailed explanation]</li>
    <li>[Benefit 5 - Detailed explanation]</li>
    </ul>

    <h2>Pros and Cons (Honest Look)</h2>
    <p><strong>Pros:</strong></p>
    <ul>
    <li>Natural ingredients</li>
    <li>Easy to use</li>
    <li>(Add 2-3 more)</li>
    </ul>
    <p><strong>Cons:</strong></p>
    <ul>
    <li>Only available online</li>
    <li>Individual results vary</li>
    </ul>

    <h2>Who Should Consider This?</h2>
    <p>[Define the audience clearly]</p>

    <h2>Final Verdict</h2>
    <p>[Summarize everything. Add a soft call to action to check the official site.]</p>

    <h2>Frequently Asked Questions</h2>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>

    <p><em><small>Disclaimer: This article is for informational purposes only. Consult a doctor before starting any supplement.</small></em></p>
    """
    
    user_prompt = f"Write a long, detailed review for '{product['product_name']}' in the niche '{product['niche']}'."

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="DeepSeek-R1",
            temperature=1.0, # High creativity for length
            max_tokens=5000  # Allowed max length
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
            if not p.startswith('<') and not p.startswith('Consider'): 
                 p = f"<p>{p}</p>"
            elif p.startswith('<p>') and not p.endswith('</p>'):
                 p = f"{p}</p>"
            cleaned_paras.append(p)
            
        return title, cleaned_paras
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"Review: {product['product_name']}", ["Content generation failed."]

# --- 4. IMAGE & BUTTON INJECTION (AMAZON STYLE) ---

def create_promo_block(image_url, affiliate_link):
    # 👉 AMAZON STYLE BUTTON (Yellow/Orange)
    btn_style = """
        background: linear-gradient(to bottom, #f8c147 0%, #f7dfa5 100%);
        background-color: #f0c14b;
        border: 1px solid #a88734;
        color: #111 !important;
        padding: 14px 28px;
        font-size: 18px;
        font-weight: bold;
        text-decoration: none;
        border-radius: 4px;
        display: inline-block;
        margin: 20px 0;
        cursor: pointer;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset;
        font-family: Arial, sans-serif;
    """
    img_style = "width: 100%; max-width: 600px; height: auto; border: 1px solid #ddd; margin-bottom: 15px; border-radius: 8px;"
    
    html = f"""
    <div style="text-align: center; margin: 40px 0; padding: 20px; background-color: #fdfdfd; border: 1px solid #eee;">
        <a href="{affiliate_link}" target="_blank" rel="nofollow">
            <img src="{image_url}" style="{img_style}" alt="Product Insight">
        </a>
        <br>
        <a href="{affiliate_link}" target="_blank" rel="nofollow" style="{btn_style}">
            BUY NOW
        </a>
        <br>
        <small style="color: #888;">Official Site | 100% Safe & Secure</small>
    </div>
    """
    return html

def merge_content(title, paragraphs, product):
    all_image_urls = product.get('image_urls', [])
    if not all_image_urls:
        print("⚠️ No image URLs found.")
        all_image_urls = []

    num_images_to_use = random.randint(2, 3)
    selected_urls = random.sample(all_image_urls, min(len(all_image_urls), num_images_to_use))
    
    # 👉 UPLOAD TO IMGBB (Direct)
    ready_to_use_images = []
    for url in selected_urls:
        imgbb_url = upload_to_imgbb(url)
        if imgbb_url:
            ready_to_use_images.append(imgbb_url)

    print(f"✅ Images Ready to Inject: {len(ready_to_use_images)}")
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    final_html += f"<h1 style='text-align: center; color: #2c3e50; margin-bottom: 25px;'>{title}</h1>"
    
    if paragraphs:
        final_html += paragraphs[0]
        if len(paragraphs) > 1: final_html += paragraphs[1]
        remaining_paras = paragraphs[2:]
    else:
        remaining_paras = []
        
    if ready_to_use_images:
        final_html += create_promo_block(ready_to_use_images.pop(0), affiliate_link)
        
    if ready_to_use_images and remaining_paras:
        gap = max(3, len(remaining_paras) // (len(ready_to_use_images) + 1))
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
        socket.setdefaulttimeout(120) 

        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        final_styled_body = f"""
        <div style="font-family: Verdana, sans-serif; font-size: 16px; line-height: 1.8; color: #222; background-color: #fff; padding: 20px; max-width: 800px; margin: auto;">
            {content_html}
            <br><hr style="border: 0; border-top: 1px solid #eee; margin: 40px 0;">
            <p style="font-size: 14px; color: #666; text-align: center; background: #f9f9f9; padding: 10px;">
                <i>Transparency Disclosure: This content is reader-supported. We may earn a commission if you click through and make a purchase, at no additional cost to you.</i>
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
            
        final_blog_post = merge_content(title_text, paras, product_data)
        
        post_to_blogger(title_text, final_blog_post, seo_labels)
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
