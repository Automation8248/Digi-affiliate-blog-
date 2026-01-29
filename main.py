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

# --- 1. HELPER FUNCTIONS (ADVANCED CLEANER) ---

def clean_text_for_blogger(text):
    # Remove AI thinking process
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # 👉 CRITICAL FIX: Remove markdown code block indicators entirely
    text = text.replace('```html', '').replace('```', '')
    
    # Remove bold/italic markdown
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    
    # Remove "Title:" prefix if present anywhere
    text = re.sub(r'^Title:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    return text.strip()

def get_smart_labels(product):
    niche_keywords = product.get('niche', 'Health').split('&')
    clean_niche = [w.strip() for w in niche_keywords if len(w.strip()) > 3]
    base_labels = ["Health Insights", "Wellness Guide", "User Reviews", product['product_name']]
    all_labels = list(set(clean_niche + base_labels))
    return all_labels[:5]

# --- 2. MEMORY & RANDOM PRODUCT SELECTION ---

def get_eligible_product():
    # Randomly pick a product, considering cooldown
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

# --- 3. AI CONTENT GENERATION (PERSUASIVE & SAFE) ---

def generate_content(product):
    print(f"✍️ Writing High-Converting & Safe Review for: {product['product_name']}...")
    
    # 👉 SYSTEM PROMPT: Highly Persuasive yet Google-Safe
    system_prompt = """
    You are an expert Health Copywriter and Researcher.
    Your goal is to write a convincing, high-converting, yet completely SAFE and compliant review article.

    *** CRITICAL OBJECTIVES ***
    1.  **HOOK TITLE:** Create a title that stops the scroll and creates immense curiosity. Do NOT use the product name in the title.
    2.  **PERSUASION:** The content must make the reader feel understood and gently lead them to realize they *need* this solution.
    3.  **GOOGLE SAFETY (NON-NEGOTIABLE):** To prevent account suspension:
        * NEVER make hard medical claims (e.g., don't say "cures", say "supports").
        * Focus heavily on lifestyle, wellness, and the *struggle* first.
        * The tone must be educational and helpful, not just a hard sell.
    4.  **LENGTH:** The total article must be between 1200 and 1600 words. Go deep.

    *** REQUIRED ARTICLE STRUCTURE ***

    [Title: Insert Hook Title Here - Just the text, no html tags]
    |||
    <h2>[Emotional Heading about the Struggle]</h2>
    <p>[Deep empathy section. Describe the pain/frustration the reader feels regarding their health issue. 3 paragraphs. Make them connect.]</p>

    <h2>Why This Is Happening (The Science Simplified)</h2>
    <p>[Explain the root cause in simple terms. Education builds trust. 2 paragraphs.]</p>

    <h2>The Search for a Solution: Why Most Things Fail</h2>
    <p>[Briefly touch on why standard methods might not be enough, creating a gap.]</p>

    <h2>Discovering [Product Name]: A New Approach</h2>
    <p>[Introduce the product as a breakthrough discovery or interesting option. Build hype safely.]</p>

    <h2>How It Aims to Help (The Mechanism)</h2>
    <p>[Explain how it works softly using words like "supports", "promotes", "helps maintain".]</p>

    <h2>The Ingredients That Matter</h2>
    <ul>
    <li><strong>Ingredient 1:</strong> Why it's included (soft benefit).</li>
    <li><strong>Ingredient 2:</strong> Why it's included (soft benefit).</li>
    <li>(Add 3-4 more key ingredients)</li>
    </ul>

    <h2>Why People Are Choosing This (Key Benefits)</h2>
    <ul>
    <li>[Strong persuasive benefit 1]</li>
    <li>[Strong persuasive benefit 2]</li>
    <li>[Strong persuasive benefit 3]</li>
    <li>[Strong persuasive benefit 4]</li>
    <li>[Strong persuasive benefit 5]</li>
    </ul>

    <h2>Real Talk: Pros and Cons</h2>
    <p><strong>The Good:</strong></p>
    <ul>
    <li>Easy to incorporate into daily routine</li>
    <li>Natural approach</li>
    <li>(Add more persuasive pros)</li>
    </ul>
    <p><strong>The Not-So-Good:</strong></p>
    <ul>
    <li>Stocks can run low due to high demand</li>
    <li>Only available through the official secured route</li>
    </ul>

    <h2>Final Verdict: Is It Worth Trying?</h2>
    <p>[Strong concluding push. Reiterate why action is needed now. Encourage trying it today.]</p>

    <h2>FAQs</h2>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    <p><strong>Q: ...?</strong><br>A: ...</p>

    <p style="font-size: 12px; color: #666; border-top: 1px solid #eee; padding-top: 10px;">
    <em>Transparency Disclosure: We believe in transparency. If you make a purchase through links on this page, we may earn a small commission at no extra cost to you. This supports our research.</em>
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
            temperature=1.0, # High creativity for persuasive writing
            max_tokens=5000 
        )
        raw_text = response.choices[0].message.content
        cleaned_text = clean_text_for_blogger(raw_text)
        
        # Split Title and Body
        if "|||" in cleaned_text:
            parts = cleaned_text.split("|||")
            title = parts[0].strip()
            body = parts[1].strip()
        else:
            # Fallback if separator missing
            lines = cleaned_text.split('\n')
            title = lines[0].strip()
            body = "\n".join(lines[1:])
            
        # Final cleanup of title just in case
        title = title.replace('"', '').replace('*', '').replace('```', '')
        
        # Wrap paragraphs intelligently
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

# --- 4. IMAGE & BUTTON INJECTION (CLEAN DISPLAY) ---

def create_promo_block(image_url, affiliate_link):
    # 👉 AMAZON STYLE BUTTON (High Conversion)
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
    
    # 👉 FIXED: Removed the small text below the button as requested
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
        print("⚠️ No image URLs found in JSON.")
        all_image_urls = []

    # 👉 RANDOM SHUFFLE LOGIC
    # First, shuffle all available images randomly
    random.shuffle(all_image_urls)
    
    # Decide how many to use (2 or 3)
    num_to_pick = random.randint(2, 3)
    
    # Pick the first N images after shuffling (ensures uniqueness if available)
    ready_to_use_images = all_image_urls[:num_to_pick]

    print(f"✅ Selected {len(ready_to_use_images)} random images for this post.")
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    # 1. Hook Title in Body (Styled nicely)
    final_html += f"<h1 style='text-align: center; color: #1a1a1a; margin-bottom: 30px; font-size: 28px; line-height: 1.3;'>{title}</h1>"
    
    # 2. Intro Text
    if paragraphs:
        # Add first 2-3 paragraphs before first image
        pre_image_paras = paragraphs[:3]
        final_html += "\n".join(pre_image_paras)
        remaining_paras = paragraphs[3:]
    else:
        remaining_paras = []
        
    # 3. First Image Block
    if ready_to_use_images:
        final_html += create_promo_block(ready_to_use_images.pop(0), affiliate_link)
        
    # 4. Distribute remaining images evenly in the rest of the text
    if ready_to_use_images and remaining_paras:
        # Calculate gap
        gap = max(4, len(remaining_paras) // (len(ready_to_use_images) + 1))
        idx = 0
        
        for img_url in ready_to_use_images:
            # Add text blocks
            for _ in range(gap):
                if idx < len(remaining_paras):
                    final_html += remaining_paras[idx] + "\n"
                    idx += 1
            # Add Image Block
            final_html += create_promo_block(img_url, affiliate_link)
            
        # Add rest of the text
        while idx < len(remaining_paras):
            final_html += remaining_paras[idx] + "\n"
            idx += 1
    else:
        # If no more images, add rest of text
        final_html += "\n".join(remaining_paras)
        
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
        "token_uri": "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)",
        "scopes": ["[https://www.googleapis.com/auth/blogger](https://www.googleapis.com/auth/blogger)"]
    }

    try:
        socket.setdefaulttimeout(120) 

        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        # Professional Container for the whole post
        final_styled_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; font-size: 17px; line-height: 1.7; color: #333; background-color: #fff; padding: 20px; max-width: 850px; margin: auto;">
            {content_html}
        </div>
        """
        
        body = {
            "kind": "blogger#post",
            "title": title, # Clean title without HTML
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
        # 1. Pick Random Product
        selected_file = get_eligible_product()
        print(f"🚀 Processing Random Product: {selected_file}")
        
        with open(f'products/{selected_file}', 'r') as f:
            product_data = json.load(f)
            
        seo_labels = get_smart_labels(product_data)
        
        # 2. Generate Content (Safe, Persuasive, Long)
        title_text, paras = generate_content(product_data)
        
        if not paras or not title_text:
            print("❌ Error: Content generation failed.")
            exit()
            
        # 3. Merge with Randomly Shuffled Images & Buttons
        final_blog_post = merge_content(title_text, paras, product_data)
        
        # 4. Publish
        post_to_blogger(title_text, final_blog_post, seo_labels)
        update_history(selected_file)
        
    except Exception as e:
        print(f"❌ Main Loop Error: {e}")
