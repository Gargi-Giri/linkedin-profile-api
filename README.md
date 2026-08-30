# LinkedIn Profile API (Reverse Engineering Challenge)

A fast, headless API that accepts a LinkedIn profile URL and returns structured JSON containing the user's name, headline, location, experience, education, skills, and profile image. Built for the Tross Careers Hiring Challenge.

# LinkedIn Profile API (Reverse Engineering Challenge)

**🚀 Live Demo Endpoint:** `https://linkedin-profile-api-lfmf.onrender.com/api/profile`

## Approach & The Debugging Journey

The challenge required a **purely reverse-engineered solution without headless browsers**. This meant interacting directly with LinkedIn's internal Rest.li/Voyager API via standard HTTP requests. 

This process involved overcoming several layers of LinkedIn's security:

1. **410 Gone (Endpoint Deprecation):** Initially targeted the classic `/identity/profiles/{vanity}/profileView` endpoint, which returned a `410 Gone`. I reverse-engineered the newer 2026 Dash frontend to locate the active endpoint: `/identity/dash/profiles`.
2. **Session Invalidation (User-Agent & CSRF mismatch):** Early tests resulted in LinkedIn aggressively logging out my session. I debugged this by strictly formatting the `JSESSIONID` cookie (which requires double quotes) while sending the `csrf-token` header (which strictly requires *no* quotes), and matching macOS `User-Agent` strings.
3. **WAF & TLS Fingerprinting:** Even with perfect headers, Python's standard `httpx` library was flagged by Akamai's WAF because its TLS handshake fingerprint differs from real browsers. **Solution:** I swapped the HTTP client to `curl_cffi`, which spoofs the exact TLS and HTTP/2 fingerprint of Google Chrome, successfully bypassing the WAF without needing a heavy Selenium instance.
4. **Denormalization:** The API returns a flat array of interconnected entities. I built a custom parser to locate the `fsd_profile` root, and link `Position`, `Education`, and `Skill` URNs back into a clean JSON structure.

## Setup & Deployment Instructions

### Local Setup
1. Clone the repository and navigate to the directory.
2. Create a virtual environment and install dependencies:
   \`\`\`bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   \`\`\`
3. Create a `.env` file in the root directory and add your session cookies (from a burner LinkedIn account):
   \`\`\`env
   LINKEDIN_LI_AT=your_li_at_cookie
   LINKEDIN_JSESSIONID="ajax:your_jsessionid"
   \`\`\`
4. Run the API:
   \`\`\`bash
   uvicorn main:app --reload
   \`\`\`

## API Documentation

**Endpoint:** `GET /api/profile`

**Query Parameters:**
* `url` (string, required): The full LinkedIn profile URL.

**Example Request:**
```bash
curl -G "https://linkedin-profile-api-lfmf.onrender.com/api/profile" \
  --data-urlencode "url=https://www.linkedin.com/in/gargi-giri-a2067a261/"

\`\`\`

**Testing in a Web Browser:**
If you prefer to test the GET request directly in a web browser, ensure the target LinkedIn URL is fully URL-encoded. Otherwise, the browser may misinterpret the nested `https://` as a search query.

Use this formatted link to test the live deployment:
`https://linkedin-profile-api-lfmf.onrender.com/api/profile?url=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fgargi-giri-a2067a261%2F`
## Known Limitations & Scraping Realities

* **Datacenter IP Flagging:** While `curl_cffi` fixes the TLS fingerprint, deploying this to a cloud host (Render, AWS) means requests originate from a datacenter IP. LinkedIn may eventually flag the IP and return a 401/403. In production, this requires routing through residential proxies.
* **Cookie Expiry:** The `li_at` token is static in the environment variables. In a production environment, an automated pool of service accounts using Playwright + stealth plugins would handle logging in and refreshing these cookies in a database (like Redis) for the API to consume.
* **Pagination:** The Dash API surfaces the most relevant top entities. For profiles with 20+ jobs, secondary paginated queries to `/positions` would be required for a complete historical scrape.
