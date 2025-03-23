from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
import requests
import re
from twilio.rest import Client
import praw  # Add praw for Reddit integration
from dotenv import load_dotenv
load_dotenv(".env")
# Initialize FastAPI app
app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY")  # Load from environment
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")  # Load from environment
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")  # Load from environment
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # Load from environment

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Reddit credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")  # Load from environment
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")  # Load from environment
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")  # Load from environment
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")  # Load from environment
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")  # Load from environment


# Initialize Reddit client
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
)

# Trusted domains list
TRUSTED_DOMAINS = [
    'wikipedia.org', 'thehindu.com', 'timesofindia.indiatimes.com',
    'bbc.com', 'reuters.com', 'apnews.com', 'aljazeera.com',
    'theguardian.com', 'nytimes.com', 'washingtonpost.com', 'cnn.com',
    'npr.org', 'pbs.org', 'smithsonianmag.com', 'medium.com',
    'who.int', 'cdc.gov', 'nih.gov', 'fda.gov', 'ema.europa.eu',
    'thelancet.com', 'nejm.org', 'jamanetwork.com', 'bmj.com',
    'nature.com', 'sciencedirect.com', 'medicalnewstoday.com',
    'medlineplus.gov', 'mayoclinic.org', 'clevelandclinic.org'
]

# Serper API Key
SERPER_API_KEY = os.getenv("SERPER_API_KEY")  # Replace with your actual key


# Function to search using Serper API
def search_serper(query, num_results=10):
    """Perform a search using Serper."""
    print(f"Searching for: {query}")
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": num_results})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json().get('organic', [])
    except Exception as e:
        print(f"Error searching with Serper: {e}")
        return []


# Function to extract content from URLs
def extract_content(url):
    """Extract (raw) content from a URL, truncated to 2000 characters."""
    try:
        print(f"Extracting content from: {url}")
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.text[:2000]
    except Exception as e:
        print(f"Error extracting from {url}: {e}")
        return ""


# Function to compose the prompt for the LLM
def compose_prompt(claim, reference_texts):
    """Compose the prompt for the LLM based on the claim and reference texts."""
    prompt = f"""You are a fact-checking assistant. Analyze the following claim and determine if it's true, false, or unverifiable based on the provided sources.

**Claim:**
{claim}

**Reference Sources:**
"""
    for i, (src, cont) in enumerate(reference_texts, 1):
        prompt += f"\nSOURCE {i} ({src}):\n{cont[:300]}...\n"

    prompt += """
**Instructions:**
1. Analyze the claim.
2. Determine if it's true, false, or unverifiable.
3. Provide a reliability score (0-100).
4. Explain your reasoning in JSON format with the following keys:
   - "assessment": "true/false/unverifiable"
   - "reliability_score": (integer 0-100)
   - "reasoning": "Your detailed reasoning"

**Important:**
- Only output valid JSON.
- Do not include any additional text outside the JSON.
- Follow this exact format:

```json
{
    "assessment": "true/false/unverifiable",
    "reliability_score": 0-100,
    "reasoning": "Your detailed reasoning"
}
```"""
    return prompt


# Function to analyze text using Hugging Face Inference API
async def analyze_text_with_mistral(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 500,
                "temperature": 0.1
            }
        }

        # Send the request to Hugging Face API
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        # Extract the generated text
        generated_text = response.json()[0]["generated_text"]

        # Debugging: Print the raw response
        print("Raw Response from Hugging Face API:")
        print(generated_text)

        # Try to extract JSON from the response
        try:
            # Look for the JSON in the "Your Answer:" section
            answer_section = generated_text.split("**Your Answer:**")
            if len(answer_section) > 1:
                # Extract the JSON block after "Your Answer:"
                json_block = answer_section[1].strip()
                # Find content between triple backticks if they exist
                json_match = re.search(r'```json\s*(.*?)\s*```', json_block, re.DOTALL)
                if json_match:
                    json_response = json_match.group(1).strip()
                else:
                    # If no backticks, try to find a JSON object
                    json_match = re.search(r'(\{.*\})', json_block, re.DOTALL)
                    if json_match:
                        json_response = json_match.group(1).strip()
                    else:
                        raise ValueError("No JSON object found in the answer section")
            else:
                # Fallback: try to find the last JSON block in the response
                json_blocks = re.findall(r'```json\s*(.*?)\s*```', generated_text, re.DOTALL)
                if json_blocks:
                    json_response = json_blocks[-1].strip()  # Take the last JSON block
                else:
                    # Last resort: find any JSON-like structure
                    json_match = re.search(r'(\{[^{]*"assessment":\s*"(true|false|unverifiable)"[^}]*\})',
                                           generated_text, re.DOTALL)
                    if json_match:
                        json_response = json_match.group(1).strip()
                    else:
                        raise ValueError("No valid JSON response found")

            print("Extracted JSON Block:")
            print(json_response)

            # Parse the JSON response
            analysis = json.loads(json_response)

            # Validate the required keys
            if not all(key in analysis for key in ["assessment", "reliability_score", "reasoning"]):
                raise ValueError("Missing required keys in JSON response")

            # Ensure reliability_score is an integer
            if isinstance(analysis["reliability_score"], str) and "-" in analysis["reliability_score"]:
                # Handle ranges like "0-100"
                min_val = int(analysis["reliability_score"].split("-")[0])
                analysis["reliability_score"] = min_val

            return analysis
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse JSON response: {e}")
            # Fallback response if JSON parsing fails
            return {
                "assessment": "unverifiable",
                "reliability_score": 0,
                "reasoning": "Unable to parse the analysis. Please try again."
            }
    except Exception as e:
        print(f"Error analyzing text: {str(e)}")
        return {
            "assessment": "error",
            "reliability_score": 0,
            "reasoning": "Error: Unable to analyze the text at this time."
        }


# Function to perform fact-checking
async def fact_check(claim):
    # Step 1: Search for relevant sources
    search_results = search_serper(claim)

    # Step 2: Filter trusted sources
    trusted_results = [r for r in search_results if any(domain in r.get('link', '') for domain in TRUSTED_DOMAINS)]
    print(f"Filtered to {len(trusted_results)} trusted sources")

    # Step 3: Extract content from trusted sources
    reference_texts = []
    source_links = []
    for r in trusted_results[:5]:  # Limit to top 5 sources
        url = r.get('link')
        title = r.get('title', url)
        content = extract_content(url)
        if content:
            reference_texts.append((title, content))
            source_links.append(url)
    print(f"Extracted content from {len(reference_texts)} sources")

    # Step 4: Compose the prompt
    prompt = compose_prompt(claim, reference_texts)

    # Step 5: Analyze the claim using Mistral via Hugging Face API
    analysis = await analyze_text_with_mistral(prompt)

    # Step 6: Return the result with sources
    return {
        "assessment": analysis.get("assessment", "unverifiable"),
        "reliability_score": analysis.get("reliability_score", 0),
        "reasoning": analysis.get("reasoning", "No reasoning provided"),
        "sources": source_links
    }


# Main route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# General text check route
@app.post("/check", response_class=HTMLResponse)
async def check_text(request: Request, text: str = Form(...)):
    # Analyze text using Mistral via Hugging Face API
    result = await fact_check(text)

    # Render the result.html template with the result
    return templates.TemplateResponse("result.html", {
        "request": request,
        "text": text,
        "result": {
            "label": result["assessment"],
            "confidence": result["reliability_score"] / 100,  # Convert to a 0-1 range for the template
            "reasoning": result["reasoning"],
            "sources": result["sources"]
        }
    })


# Reddit verification route
@app.post("/reddit", response_class=HTMLResponse)
async def reddit_verify(request: Request, post_url: str = Form(...)):
    try:
        print(f"Received Reddit URL: {post_url}")  # Debugging
        post_id = post_url.split("/comments/")[1].split("/")[0]
        print(f"Extracted Post ID: {post_id}")  # Debugging
        submission = reddit.submission(id=post_id)
        print(f"Fetched Submission: {submission.title}")  # Debugging

        # Analyze the post title and content
        claim = f"{submission.title}\n\n{submission.selftext}"
        result = await fact_check(claim)

        # Render the result.html template with the result
        return templates.TemplateResponse("result.html", {
            "request": request,
            "text": claim,
            "result": {
                "label": result["assessment"],
                "confidence": result["reliability_score"] / 100,
                "reasoning": result["reasoning"],
                "sources": result["sources"]
            }
        })
    except Exception as e:
        print(f"Error: {str(e)}")  # Debugging
        raise HTTPException(status_code=400, detail=f"Error processing Reddit post: {str(e)}")


# WhatsApp route
@app.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request):
    return templates.TemplateResponse("whatsapp.html", {"request": request})


@app.post("/whatsapp/submit", response_class=HTMLResponse)
async def whatsapp_submit(request: Request, phone_number: str = Form(...), message: str = Form(...)):
    # Format phone number for WhatsApp
    if not phone_number.startswith("whatsapp:"):
        phone_number = f"whatsapp:{phone_number}"

    # Analyze text using Mistral via Hugging Face API
    result = await fact_check(message)

    # Format the response for WhatsApp
    response_text = (
        f"Fact-Checking Analysis:\n\n"
        f"Assessment: {result['assessment']}\n"
        f"Reliability Score: {result['reliability_score']}\n"
        f"Reasoning: {result['reasoning']}\n"
        f"Sources: {', '.join(result['sources']) if result['sources'] else 'No sources found'}"
    )

    # Split the message if it exceeds 4096 characters
    message_parts = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]

    try:
        # Send each part of the message
        for part in message_parts:
            message = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=part,
                to=phone_number
            )
        status = "Message sent successfully!"
    except Exception as e:
        status = f"Error sending message: {str(e)}"

    return templates.TemplateResponse("whatsapp_result.html", {
        "request": request,
        "status": status,
        "result": result,
        "message": message
    })


# Twilio webhook handler
@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    body = form_data.get("Body", "")
    from_number = form_data.get("From", "")

    if not body or not from_number:
        return {"status": "error", "message": "No message received"}

    # Analyze text using Mistral via Hugging Face API
    result = await fact_check(body)

    # Format the response for WhatsApp
    message_text = (
        f"Fact-Checking Analysis:\n\n"
        f"Assessment: {result['assessment']}\n"
        f"Reliability Score: {result['reliability_score']}\n"
        f"Reasoning: {result['reasoning']}\n"
        f"Sources: {', '.join(result['sources']) if result['sources'] else 'No sources found'}"
    )

    # Split the message if it exceeds 4096 characters
    message_parts = [message_text[i:i+4096] for i in range(0, len(message_text), 4096)]

    try:
        # Send each part of the message
        for part in message_parts:
            message = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=part,
                to=from_number
            )
        return {"status": "success", "message_sid": message.sid}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
