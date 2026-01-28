import os
import json
import random
import re
import time
from datetime import datetime
from openai import OpenAI
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# --- CONFIGURATION (UPDATED) ---
GITHUB_TOKEN = os.environ.get("GH_MARKETPLACE_TOKEN") 

# 👉 Yahan hum .strip() laga rahe hain taaki Space hat jaye
raw_blog_id = os.environ.get("BLOGGER_ID")
BLOGGER_ID = raw_blog_id.strip().replace('"', '') if raw_blog_id else None 

# New Authentication Variables
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

# Debugging Print (Error pakadne ke liye)
print(f"DEBUG: Using Blog ID: '{BLOGGER_ID}'")

# DeepSeek Client
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# --- 1. CLEANER & HELPER FUNCTIONS ---

def clean_text_for_blogger(text):
    # Remove <think> tags
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Remove markdown symbols
    text = text.replace('**', '').replace('*', '').replace('##', '').replace('#', '')
    # Remove explicit "Title:" text
    text = text.replace('Title:', '').strip()
    return text

def get_smart_labels(product):
    niche = product.get('niche', 'General').lower()
    product_name = product['product_name']
    
    base_labels = ["Health Reviews", "Wellness", "Dietary Supplements"]
    specific_labels = []
    
    if "weight" in niche or "fat" in niche or "metabolic" in niche:
        specific_labels = ["Weight Loss", "Fat Burner", "Metabolism Booster"]
    elif "sugar" in niche or "diabetes" in niche:
        specific_labels = ["Blood Sugar Control", "Diabetes Support", "Insulin Health"]
    elif "teeth" in niche or "dental" in niche:
        specific_labels = ["Dental Health", "Oral Hygiene", "Gum Support"]
    elif "gut" in niche or "digest" in niche:
        specific_labels = ["Gut Health", "Digestion", "Probiotics"]
    else:
        specific_labels = ["Health Tips", "Natural Remedies"]
        
    final_labels = [product_name] + base_labels + specific_labels
    return final_labels[:5]

# --- 2. MEMORY & PRODUCT SELECTION ---

def get_eligible_product():
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try: history = json.load(f)
            except: history = {}
    else:
        history = {}

    all_files = [f for f in os.listdir('products') if f.endswith('.json')]
    available_products = []
    today = datetime.now().date()

    print("🔍 Checking 5-Day Cooldown Rule...")
    
    for filename in all_files:
        product_name = filename.replace('.json', '')
        last_used_str = history.get(product_name)
        
        if last_used_str:
            last_used_date = datetime.strptime(last_used_str, "%Y-%m-%d").date()
            days_diff = (today - last_used_date).days
            if days_diff < 5:
                continue 
        
        available_products.append(filename)

    if not available_products:
        print("⚠️ All products in cooldown. Picking oldest used.")
        if all_files:
             return random.choice(all_files)
        else:
             print("❌ No product files found in 'products/' folder!")
             exit()

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
    print(f"✍️ Writing article for: {product['product_name']}...")
    
    system_prompt = """
    You are a professional SEO Health Copywriter.
    Write a high-converting, educational blog post.
    
    STRICT GUIDELINES:
    1. WORD COUNT: Minimum 1200 words.
    2. FORMAT: Use only HTML tags (<p>, <h2>, <ul>, <li>). 
    3. FORBIDDEN: Do NOT use Markdown symbols like '**', '##', or '*'. Do NOT use hashtags.
    4. STRUCTURE: 
       - Catchy SEO Title (inside the response, but separate)
       - Introduction (Hook)
       - The 'Hidden' Problem (Agitation)
       - The Solution (The Product)
       - Scientific Ingredients Analysis
       - Benefits (Bulleted list using <ul>)
       - FAQ Section (Must be sequential and logical)
       - Conclusion with strong CTA.
    5. TONE: Trustworthy, Scientific, Empathetic.
    """
    
    user_prompt = f"Write a detailed review for '{product['product_name']}' targeting {product.get('target_keywords', 'health enthusiasts')}."

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        model="DeepSeek-R1",
        temperature=1.0,
        max_tokens=4000 
    )

    raw_text = response.choices[0].message.content
    cleaned_text = clean_text_for_blogger(raw_text)
    
    lines = cleaned_text.split('\n')
    title = lines[0]
    if len(title) > 60: title = title[:60]
    
    body_text = "\n".join(lines[1:])
    paragraphs = [p for p in body_text.split('\n\n') if len(p) > 50]
    
    return title, paragraphs

# --- 4. IMAGE & BUTTON INJECTION ---

def create_promo_block(image_url, affiliate_link):
    btn_style = """
        background-color: #ff0000; 
        color: white !important; 
        padding: 16px 32px; 
        font-size: 22px; 
        font-weight: 900; 
        text-transform: uppercase; 
        text-decoration: none; 
        border-radius: 6px; 
        display: inline-block; 
        margin: 20px 0; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
    """
    img_style = "width: 100%; max-width: 700px; height: auto; border: 1px solid #ddd; margin-bottom: 15px;"
    
    html = f"""
    <div style="text-align: center; margin: 40px 0; clear: both;">
        <a href="{affiliate_link}" target="_blank" rel="nofollow">
            <img src="{image_url}" style="{img_style}" alt="Official Product Image">
        </a>
        <br>
        <a href="{affiliate_link}" target="_blank" rel="nofollow" style="{btn_style}">
            BUY NOW (OFFICIAL SITE)
        </a>
    </div>
    """
    return html

def merge_content(paragraphs, product):
    all_images = product.get('image_urls', [])
    
    if len(all_images) < 3: selected_images = all_images * 4
    else: selected_images = list(all_images)
    
    random.shuffle(selected_images)
    final_images = selected_images[:4]
    
    affiliate_link = product['affiliate_link']
    final_html = ""
    
    if paragraphs: 
        final_html += f"<p>{paragraphs[0]}</p>" 
    
    if final_images:
        final_html += create_promo_block(final_images[0], affiliate_link)
        final_images.pop(0)
        
    remaining_paras = paragraphs[1:]
    
    if final_images and remaining_paras:
        gap = max(2, len(remaining_paras) // (len(final_images) + 1))
        p_idx = 0
        
        for img in final_images:
            for _ in range(gap):
                if p_idx < len(remaining_paras):
                    final_html += f"<p>{remaining_paras[p_idx]}</p>"
                    p_idx += 1
            final_html += create_promo_block(img, affiliate_link)
            
        while p_idx < len(remaining_paras):
            final_html += f"<p>{remaining_paras[p_idx]}</p>"
            p_idx += 1
    else:
        for p in remaining_paras: final_html += f"<p>{p}</p>"
        
    return final_html

# --- 5. PUBLISH TO BLOGGER (UPDATED AUTH) ---

def post_to_blogger(title, content_html, labels):
    print("🔑 Authenticating with Google using Split Secrets...")
    
    # Manually constructing the credentials dictionary from Environment Variables
    creds_info = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/blogger"]
    }

    # Validate if secrets are present
    if not CLIENT_ID or not CLIENT_SECRET or not REFRESH_TOKEN:
        print("❌ ERROR: Missing one or more Google Secrets (CLIENT_ID, SECRET, REFRESH_TOKEN).")
        return

    try:
        creds = Credentials.from_authorized_user_info(creds_info)
        service = build('blogger', 'v3', credentials=creds)
        
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": content_html,
            "labels": labels 
        }
        
        posts = service.posts()
        result = posts.insert(blogId=BLOGGER_ID, body=body).execute()
        print(f"✅ PUBLISHED SUCCESSFULLY! URL: {result['url']}")
        print(f"🏷️ Labels Used: {labels}")
        
    except Exception as e:
        print(f"❌ Failed to publish: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    try:
        # 1. Select Product
        selected_file = get_eligible_product()
        print(f"🚀 Starting automation for: {selected_file}")
        
        with open(f'products/{selected_file}', 'r') as f:
            product_data = json.load(f)
            
        # 2. Get Smart Labels
        seo_labels = get_smart_labels(product_data)
        
        # 3. Generate Clean Content
        title_text, paras = generate_content(product_data)
        
        # 4. Mix Images & Buttons
        final_blog_post = merge_content(paras, product_data)
        
        # 5. Publish
        post_to_blogger(title_text, final_blog_post, seo_labels)
        
        # 6. Update History
        update_history(selected_file)
        
    except Exception as e:
        print(f"Error in Main Loop: {e}")
