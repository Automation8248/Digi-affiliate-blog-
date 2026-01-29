import os
import json
import random
import re
import time
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
    base_labels = ["Health Tips", "Wellness Guide", "Product Reviews"]
    product_label = [product['product_name']]
    all_labels = list(set(product_label + clean_niche + base_labels))
    return all_labels[:5]

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

# --- 3. AI CONTENT GENERATION (ACCOUNT SAFETY MODE) ---

def generate_content(product):
    print(f"✍️ Writing Safe & Detailed Review for: {product['product_name']}...")
    
    # 👉 SYSTEM PROMPT: Designed to prevent Ban. Focuses on Education First.
    system_prompt = """
    You are a professional Health Content Writer.
    Your goal is to write a helpful, educational blog post that softly introduces a product.
    
    *** CRITICAL SAFETY RULES (TO PREVENT GOOGLE BAN) ***
    1. NO FAKE PROMISES: Never say "Cure", "Treat", "Fix", "Gone in 2 days".
    2. SOFT LANGUAGE: Always use "may help", "supports", "designed to", "aims to".
    3. EDUCATE FIRST: The first 40% of the article must be general health advice (Diet, Sleep, Water).
    4. LENGTH: 1200 - 1500 Words.
    5. TONE: Helpful neighbor, not a salesman.
    6. FORMAT: Clean HTML tags (<p>, <h2>, <ul>, <li>).

    *** ARTICLE STRUCTURE (Must Follow) ***

    Title: [Write a Curiosity Hook Title. Do NOT start with Product Name.]
    |||
    <h2>[Heading: Describe the Health Struggle]</h2>
    <p>[Empathize with the reader about the problem (e.g., weight gain, dental issues). Write 2-3 paragraphs.]</p>

    <h2>The Science: Why This Happens</h2>
    <p>[Explain the root cause simply. Education builds trust.]</p>

    <h2>Natural Ways to Support Your Health (Lifestyle)</h2>
    <p>[Discuss drinking water, sleeping better, and diet FIRST. Do NOT mention the product here.]</p>

    <h2>Introducing [Product Name]: A Helping Hand?</h2>
    <p>[Transition gently. Introduce the product as an option for those needing extra support.]</p>

    <h2>How It Works</h2>
    <p>[Explain the mechanism safely.]</p>

    <h2>Key Ingredients Breakdown</h2>
    <ul>
    <li><strong>Ingredient 1:</strong> Benefits (softly stated).</li>
    <li><strong>Ingredient 2:</strong> Benefits (softly stated).</li>
    <li>(Add more)</li>
    </ul>

    <h2>Potential Benefits</h2>
    <ul>
    <li>[Benefit 1]</li>
    <li>[Benefit 2]</li>
    <li>[Benefit 3]</li>
    <li>[Benefit 4]</li>
    </ul>

    <h2>Pros and Cons (Honesty helps SEO)</h2>
    <p><strong>Pros:</strong></p>
    <ul>
    <li>Natural ingredients</li>
    <li>Easy to use</li>
    <li>(Add more)</li>
    </ul>
    <p><strong>Cons:</strong></p>
    <ul>
    <li>Only available on official site</li>
    <li>Results vary by individual</li>
    </ul>

    <h2>Who Is This For?</h2>
    <p>[Define the ideal user]</p>

    <h2>Final Thoughts</h2>
    <p>[Summarize warmly. Add a soft suggestion to check the details.]</p>

    <h2>Frequently Asked Questions</h2>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>

    <p><em><small>Disclaimer: This content is for informational purposes only. It is not medical advice.</small></em></p>
    """
    
    user_prompt = f"Write a long, educational review for '{product['product_name']}' in the niche '{product['niche']}'."

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="DeepSeek-R1",
            temperature=1.0, 
            max_tokens=5000 
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

# --- 4. IMAGE & BUTTON INJECTION (NO IMAGE LINK - ONLY BUTTON LINK) ---

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
    
    # 👉 CHANGE IMPLEMENTED: Image tag has NO <a> link. Only Button has <a> link.
    html = f"""
    <div style="text-align: center; margin: 40px 0; padding: 20px; background-color: #fdfdfd; border: 1px solid #eee;">
        <img src="{image_url}" style="{img_style}" alt="Product Insight">
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

    # Select 2 or 3 random images from GitHub Raw Links
    num_images_to_use = random.randint(2, 3)
    
    if len(all_image_urls) < num_images_to_use:
         ready_to_use_images = all_image_urls * 2
         ready_to_use_images = ready_to_use_images[:num_images_to_use]
    else:
         ready_to_use_images = random.sample(all_image_urls, num_images_to_use)

    print(f"✅ Selected {len(ready_to_use_images)} Images.")
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    # Title Hook in Body
    final_html += f"<h1 style='text-align: center; color: #2c3e50; margin-bottom: 25px;'>{title}</h1>"
    
    # First paragraphs
    if paragraphs:
        final_html += paragraphs[0]
        if len(paragraphs) > 1: final_html += paragraphs[1]
        remaining_paras = paragraphs[2:]
    else:
        remaining_paras = []
        
    # First Image Block
    if ready_to_use_images:
        final_html += create_promo_block(ready_to_use_images.pop(0), affiliate_link)
        
    # Mix remaining images
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
        
        # Styled Container
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
        
        # Generate Safe, Long-Form Content
        title_text, paras = generate_content(product_data)
        
        if not paras:
            print("❌ Error: No content generated.")
            exit()
            
        # Merge with Non-Clickable Images & Clickable Buttons
        final_blog_post = merge_content(title_text, paras, product_data)
        
        post_to_blogger(title_text, final_blog_post, seo_labels)
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
