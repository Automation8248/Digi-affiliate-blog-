import os
import json
import random
import re
import time
import requests # New dependency for downloading images
import base64   # For encoding images
from datetime import datetime
from openai import OpenAI
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GH_MARKETPLACE_TOKEN") 

# 👉 HARDCODED BLOG ID (Error Free)
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
    # Remove markdown formatting
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    # Remove "Title:" prefix if AI adds it
    text = re.sub(r'^Title:\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

def get_smart_labels(product):
    # Simple SEO Labels
    niche_keywords = product.get('niche', 'Health').split('&')
    clean_niche = [w.strip() for w in niche_keywords if len(w.strip()) > 3]
    base_labels = ["Health Review", "Wellness Tips"]
    product_label = [product['product_name']]
    all_labels = list(set(product_label + clean_niche + base_labels))
    return all_labels[:5]

# 👉 NEW: Function to Download Image and Convert to Base64 code
# Ye function image ko download karke HTML ke andar embed karne layak banata hai
def download_and_encode_image(image_url):
    try:
        print(f"⬇️ Downloading image... {image_url[:30]}...")
        # Image download karo (10 second timeout ke sath)
        response = requests.get(image_url, timeout=10)
        response.raise_for_status() # Agar error aaye to batao
        
        # Pata karo ki image JPEG hai ya PNG
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        # Image ko text code (Base64) mein badlo
        encoded_string = base64.b64encode(response.content).decode('utf-8')
        
        # Final data string return karo jo HTML img tag mein lagegi
        return f"data:{content_type};base64,{encoded_string}"
        
    except Exception as e:
        print(f"❌ Error downloading image: {e}")
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

# --- 3. AI CONTENT GENERATION (SIMPLE ENGLISH & SHORT PARAS) ---

def generate_content(product):
    print(f"✍️ Writing article for: {product['product_name']}...")
    
    # 👉 Updated Prompt for Simple Language and Short Paragraphs
    system_prompt = """
    You are a friendly, empathetic health enthusiast sharing advice with a neighbor. You are NOT a salesperson and NOT an AI.

    *** CRITICAL "HUMAN-WRITING" RULES (MUST FOLLOW) ***
    1. TONE: Casual, conversational, and empathetic. Use "I", "You", and "We".
       - BAD: "Obesity is a growing concern globally."
       - GOOD: "Let's be real—losing those last few pounds feels impossible, right?"
    2. VOCABULARY: Use Grade 6 level English.
       - FORBIDDEN WORDS (NEVER USE): "Delve", "Realm", "Tapestry", "Unleash", "Unlock", "Game-changer", "Revolutionary", "Landscape", "In conclusion", "Moreover", "Firstly/Secondly".
       - Instead of "Utilize", say "Use". Instead of "Facilitate", say "Help".
    3. SENTENCE STRUCTURE: vary your sentence length. Use short, punchy sentences.
       - Example: "It works. Plain and simple."
    4. PARAGRAPHS: Keep them TINY. Max 2-3 sentences per paragraph. Huge blocks of text scare readers.
    5. NO HYPE: Don't overpromise. Don't say "Magical cure". Say "It might help you support your goals".

    *** HTML FORMATTING RULES ***
    - Use ONLY these tags: <p>, <h2>, <ul>, <li>, <strong>.
    - NO Markdown (No **, No ##).
    - Bold key phrases using <strong> for skimmability.

    *** ARTICLE STRUCTURE ***
    1. HOOK TITLE: A question or curiosity gap (Do not start with product name).
    2. THE STRUGGLE (Intro): Connect with the reader's pain. Show you understand how hard it is.
    3. THE "WHY": briefly explain why their current methods failed (it's not their fault).
    4. THE DISCOVERY: Introduce the product as something you found that helps.
    5. BENEFITS (Bulleted): 5-6 real-life benefits (e.g., "Fits into your busy morning").
    6. HOW TO USE: Simple instructions.
    7. WHO IS THIS FOR?: Be specific.
    8. FAQ: 3-5 common questions with short, honest answers.
    9. FINAL WORDS: A warm, encouraging sign-off (No "In summary").

    *** OUTPUT FORMAT (STRICT) ***
    Title: [Insert Human-Style Hook Title]
    |||
    <h2>[Heading: Focus on the Problem]</h2>
    <p>...</p>

    <h2>[Heading: Why it happens]</h2>
    <p>...</p>

    <h2>[Heading: A New Way to Handle It]</h2>
    <p>...</p>

    <h2>Key Benefits You Might Notice</h2>
    <ul>
    <li><strong>Benefit 1:</strong> ...</li>
    <li><strong>Benefit 2:</strong> ...</li>
    </ul>

    <h2>How to Use It</h2>
    <p>...</p>

    <h2>Common Questions</h2>
    <p><strong>Q: ...?</strong><br>A: ...</p>
    """
    
    user_prompt = f"Write a simple review for '{product['product_name']}' in the niche '{product['niche']}'. Focus on benefits."

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="DeepSeek-R1",
            temperature=0.8, # Thoda creative kam kiya taki simple likhe
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
        
        # Break body into paragraphs by double newlines or closing p tags
        paragraphs = [p.strip() for p in re.split(r'</p>|\n\n', body) if len(p.strip()) > 20]
        # Add back <p> tags if missing after split, ensure they are wrapped
        cleaned_paras = []
        for p in paragraphs:
            if not p.startswith('<p>'): p = f"<p>{p}"
            if not p.endswith('</p>'): p = f"{p}</p>"
            cleaned_paras.append(p)
            
        return title, cleaned_paras
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"Review: {product['product_name']}", ["Content generation failed."]

# --- 4. IMAGE & BUTTON INJECTION (AMAZON STYLE) ---

# 👉 Note: image_data here is now Base64 code, not a URL
def create_promo_block(image_data_base64, affiliate_link):
    # Amazon Style Button (Orange/Yellow Gradient)
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
    
    # Image style
    img_style = "width: 100%; max-width: 600px; height: auto; border: 1px solid #eee; margin-bottom: 15px; border-radius: 8px;"
    
    # 👉 Image src is now Base64 data, wrapped in a link
    html = f"""
    <div style="text-align: center; margin: 35px 0;">
        <a href="{affiliate_link}" target="_blank" rel="nofollow">
            <img src="{image_data_base64}" style="{img_style}" alt="Product Check">
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

    # 👉 Logic: Select randomly 2 or 3 unique URLs
    num_images_to_use = random.randint(2, 3)
    selected_urls = random.sample(all_image_urls, min(len(all_image_urls), num_images_to_use))
    
    # 👉 NEW STEP: Download and Encode images before placing them
    ready_to_use_images = []
    for url in selected_urls:
        encoded_img = download_and_encode_image(url)
        if encoded_img:
            ready_to_use_images.append(encoded_img)

    print(f"✅ Successfully downloaded and encoded {len(ready_to_use_images)} images.")
    
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
        
    # 3. Add First Downloaded Image & Button
    if ready_to_use_images:
        final_html += create_promo_block(ready_to_use_images.pop(0), affiliate_link)
        
    # 4. Mix remaining images
    if ready_to_use_images and remaining_paras:
        gap = max(1, len(remaining_paras) // (len(ready_to_use_images) + 1))
        idx = 0
        
        for img_data in ready_to_use_images:
            for _ in range(gap):
                if idx < len(remaining_paras):
                    final_html += remaining_paras[idx]
                    idx += 1
            final_html += create_promo_block(img_data, affiliate_link)
            
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
        # Increased timeout for posting because images make payload bigger
        import socket
        socket.setdefaulttimeout(60) 

        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        # Professional Container
        final_styled_body = f"""
        <div style="font-family: Verdana, sans-serif; font-size: 16px; line-height: 1.6; color: #333; background-color: #fff; padding: 15px; max-width: 800px; margin: auto;">
            {content_html}
            <br><hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 13px; color: #777; text-align: center;">
                <i>Transparency: This article may contain affiliate links. If you purchase through them, we may earn a small commission at no extra cost to you.</i>
            </p>
        </div>
        """
        
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": final_styled_body,
            "labels": labels 
        }
        
        print("🚀 Uploading post (this might take a few seconds due to images)...")
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
