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
    # Remove AI thinking process
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # 👉 CRITICAL FIX: Remove markdown code block indicators
    text = text.replace('```html', '').replace('```', '')
    
    # Remove bold/italic markdown
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    
    # Remove "Title:" prefix
    text = re.sub(r'^Title:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    return text.strip()

def get_smart_labels(product):
    niche_keywords = product.get('niche', 'Health').split('&')
    clean_niche = [w.strip() for w in niche_keywords if len(w.strip()) > 3]
    base_labels = ["Health Insights", "Wellness Guide", "User Reviews", product['product_name']]
    all_labels = list(set(clean_niche + base_labels))
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

# --- 3. AI CONTENT GENERATION ---

def generate_content(product):
    print(f"✍️ Writing High-Converting & Safe Review for: {product['product_name']}...")
    
    # 👉 SYSTEM PROMPT: High Conversion + Safe + Educational
    system_prompt = """
    You are an expert Health Copywriter.
    Your goal is to write a persuasive, high-converting, yet GOOGLE-SAFE review.

    *** CRITICAL RULES ***
    1.  **HOOK TITLE:** Create immense curiosity. Do NOT use the product name in the title.
    2.  **GOOGLE SAFETY:**
        * NEVER say "cures" or "treats". Use "supports", "promotes".
        * Start with lifestyle & the problem (Education first).
    3.  **LENGTH:** 1200 - 1600 words.

    *** REQUIRED STRUCTURE ***

    [Title: Insert Hook Title Here - No HTML tags]
    |||
    <h2>[Emotional Heading about the Struggle]</h2>
    <p>[Deep empathy section. Describe the pain. 3 paragraphs.]</p>

    <h2>Why This Is Happening (The Science)</h2>
    <p>[Explain root causes simply. Education builds trust.]</p>

    <h2>The Search for a Solution</h2>
    <p>[Why standard methods fail, creating a gap.]</p>

    <h2>Discovering [Product Name]: A New Approach</h2>
    <p>[Introduce product gently as an interesting option.]</p>

    <h2>How It Aims to Help</h2>
    <p>[Explain mechanism safely.]</p>

    <h2>The Ingredients That Matter</h2>
    <ul>
    <li><strong>Ingredient 1:</strong> Benefit.</li>
    <li><strong>Ingredient 2:</strong> Benefit.</li>
    <li>(Add 3-4 more)</li>
    </ul>

    <h2>Why People Are Choosing This (Benefits)</h2>
    <ul>
    <li>[Benefit 1]</li>
    <li>[Benefit 2]</li>
    <li>[Benefit 3]</li>
    <li>[Benefit 4]</li>
    </ul>

    <h2>Real Talk: Pros and Cons</h2>
    <p><strong>The Good:</strong></p>
    <ul>
    <li>Easy to use</li>
    <li>Natural approach</li>
    </ul>
    <p><strong>The Not-So-Good:</strong></p>
    <ul>
    <li>High demand</li>
    <li>Online only</li>
    </ul>

    <h2>Final Verdict: Is It Worth Trying?</h2>
    <p>[Strong concluding push. Encourage action.]</p>

    <h2>FAQs</h2>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>

    <p style="font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 10px;">
    <em>Transparency Disclosure: We believe in transparency. If you make a purchase through links on this page, we may earn a small commission at no extra cost to you.</em>
    </p>
    """
    
    user_prompt = f"Write a long, high-converting review for '{product['product_name']}' in the niche '{product['niche']}'."

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
            title = parts[0].strip()
            body = parts[1].strip()
        else:
            lines = cleaned_text.split('\n')
            title = lines[0].strip()
            body = "\n".join(lines[1:])
            
            # Yeh line title se "Title:", brackets, aur har tarah ke quotes ko saaf kar degi
            title = title.replace('Title:', '').replace('[', '').replace(']', '').replace('"', '').replace("'", "").replace('*', '').strip()
        
        paragraphs = []
        for p in re.split(r'\n\n+', body):
            p = p.strip()
            if len(p) > 20:
                 if not p.startswith('<') and not p.startswith('Transparency'):
                     p = f"<p>{p}</p>"
                 paragraphs.append(p)
            
        return title, paragraphs
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"Review: {product['product_name']}", ["Content generation failed."]

# --- 4. IMAGE & BUTTON INJECTION ---

def create_promo_block(image_url, affiliate_link):
    # 👉 AMAZON STYLE BUTTON
    btn_style = """
        background: linear-gradient(to bottom, #f8c147 0%, #f7dfa5 100%);
        background-color: #f0c14b;
        border: 1px solid #a88734;
        color: #111 !important;
        padding: 15px 30px;
        font-size: 19px;
        font-weight: bold;
        text-decoration: none;
        border-radius: 5px;
        display: inline-block;
        margin: 25px 0;
        cursor: pointer;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
    """
    img_style = "width: 100%; max-width: 650px; height: auto; border: 1px solid #eee; margin-bottom: 15px; border-radius: 8px;"
    
    html = f"""
    <div style="text-align: center; margin: 45px 0; padding: 25px; background-color: #fff; border: 1px solid #f0f0f0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
        <img src="{image_url}" style="{img_style}" alt="Product Insight">
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

    # Shuffle & Select
    random.shuffle(all_image_urls)
    num_to_pick = random.randint(2, 3)
    ready_to_use_images = all_image_urls[:num_to_pick]

    print(f"✅ Selected {len(ready_to_use_images)} random images.")
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    # Title Hook
    final_html += f"<h1 style='text-align: center; color: #1a1a1a; margin-bottom: 30px; font-size: 28px; line-height: 1.3;'>{title}</h1>"
    
    # Intro
    if paragraphs:
        pre_image_paras = paragraphs[:3]
        final_html += "\n".join(pre_image_paras)
        remaining_paras = paragraphs[3:]
    else:
        remaining_paras = []
        
    # First Image
    if ready_to_use_images:
        final_html += create_promo_block(ready_to_use_images.pop(0), affiliate_link)
        
    # Mix Remaining
    if ready_to_use_images and remaining_paras:
        gap = max(4, len(remaining_paras) // (len(ready_to_use_images) + 1))
        idx = 0
        
        for img_url in ready_to_use_images:
            for _ in range(gap):
                if idx < len(remaining_paras):
                    final_html += remaining_paras[idx] + "\n"
                    idx += 1
            final_html += create_promo_block(img_url, affiliate_link)
            
        while idx < len(remaining_paras):
            final_html += remaining_paras[idx] + "\n"
            idx += 1
    else:
        final_html += "\n".join(remaining_paras)
        
    return final_html

# --- 5. PUBLISH TO BLOGGER ---

def post_to_blogger(title, content_html, labels):
    print(f"🔑 Authenticating... (Target Blog ID: {BLOGGER_ID})")
    
    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        print("❌ ERROR: Secrets missing (CLIENT_ID/SECRET/REFRESH_TOKEN)")
        return

    # 👉 FIX: 'scopes' removed to prevent 'invalid_scope' error with old tokens
    creds_info = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "token_uri": "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
        # "scopes" line removed - This fixes the error!
    }

    try:
        socket.setdefaulttimeout(120) 

        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        final_styled_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; font-size: 17px; line-height: 1.7; color: #333; background-color: #fff; padding: 20px; max-width: 850px; margin: auto;">
            {content_html}
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
        print(f"🚀 Processing Random Product: {selected_file}")
        
        with open(f'products/{selected_file}', 'r') as f:
            product_data = json.load(f)
            
        seo_labels = get_smart_labels(product_data)
        
        title_text, paras = generate_content(product_data)
        
        if not paras or not title_text:
            print("❌ Error: Content generation failed.")
            exit()
            
        final_blog_post = merge_content(title_text, paras, product_data)
        
        post_to_blogger(title_text, final_blog_post, seo_labels)
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
