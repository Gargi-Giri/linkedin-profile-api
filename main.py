import os
import re
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from curl_cffi import requests

load_dotenv()

LI_AT = os.getenv("LINKEDIN_LI_AT", "")
JSESSIONID = os.getenv("LINKEDIN_JSESSIONID", "")

app = FastAPI(title="LinkedIn Profile API")

def parse_date(date_obj: dict) -> str:
    if not date_obj:
        return None
    year = date_obj.get("year")
    month = date_obj.get("month")
    if year and month:
        return f"{year}-{month:02d}"
    if year:
        return str(year)
    return None

def parse_profile_data(raw_data: dict) -> dict:
    """Extracts and formats data from the Voyager 'included' array."""
    included = raw_data.get("included", [])
    
    profile = {
        "first_name": None, "last_name": None, "headline": None,
        "location": None, "about": None, "profile_image_url": None,
        "experience": [], "education": [], "skills": [],
        "certifications": [], "languages": []
    }
    
    for item in included:
        urn = item.get("entityUrn", "")
        type_urn = item.get("$type", "")

        # Profile Basics
        if "fsd_profile:" in urn and item.get("firstName"):
            profile["first_name"] = item.get("firstName")
            profile["last_name"] = item.get("lastName")
            profile["headline"] = item.get("headline")
            profile["about"] = item.get("summary")
            profile["location"] = item.get("locationName")

        # Profile Image
        if "picture" in item and "rootUrl" in item["picture"]:
            root_url = item["picture"].get("rootUrl", "")
            artifacts = item["picture"].get("artifacts", [])
            if root_url and artifacts:
                path = artifacts[-1].get("fileIdentifyingUrlPathSegment", "")
                profile["profile_image_url"] = f"{root_url}{path}"

        # Experience
        if "fsd_position:" in urn or "Position" in type_urn:
            time_period = item.get("timePeriod", {})
            profile["experience"].append({
                "title": item.get("title"),
                "company": item.get("companyName"),
                "description": item.get("description"),
                "start_date": parse_date(time_period.get("startDate")),
                "end_date": parse_date(time_period.get("endDate"))
            })

        # Education
        if "fsd_education:" in urn or "Education" in type_urn:
            time_period = item.get("timePeriod", {})
            profile["education"].append({
                "school": item.get("schoolName"),
                "degree": item.get("degreeName"),
                "field_of_study": item.get("fieldOfStudy"),
                "start_year": time_period.get("startDate", {}).get("year"),
                "end_year": time_period.get("endDate", {}).get("year")
            })

        # Skills
        if "fsd_skill:" in urn or "Skill" in type_urn:
            if item.get("name"):
                profile["skills"].append(item.get("name"))

    return profile

def extract_vanity_name(url: str) -> str:
    """Extracts the vanity name from a LinkedIn profile URL."""
    url = url.strip().rstrip("/")
    match = re.search(r'linkedin\.com/in/([^/]+)', url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid LinkedIn profile URL.")
    return match.group(1)

@app.get("/api/profile")
async def get_profile(url: str):
    """API Endpoint to fetch and parse a LinkedIn profile."""
    if not LI_AT or not JSESSIONID:
        raise HTTPException(status_code=500, detail="Server missing LinkedIn credentials.")

    vanity_name = extract_vanity_name(url)
    csrf_token = JSESSIONID.strip('"')
    
    endpoint_url = (
        f"https://www.linkedin.com/voyager/api/identity/dash/profiles"
        f"?q=memberIdentity&memberIdentity={vanity_name}"
        f"&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93"
    )
    
    headers = {
        "csrf-token": csrf_token,
        "x-restli-protocol-version": "2.0.0",
        "accept": "application/vnd.linkedin.normalized+json+2.1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    }
    
    cookies = {
        "li_at": LI_AT,
        "JSESSIONID": f'"{csrf_token}"'
    }

    try:
        # Impersonating Chrome 116 to bypass TLS Fingerprinting WAF blocks
        async with requests.AsyncSession(impersonate="chrome116") as client:
            response = await client.get(endpoint_url, headers=headers, cookies=cookies, timeout=15.0)
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Profile not found or private.")
            elif response.status_code in [401, 403]:
                raise HTTPException(status_code=401, detail="Authentication failed. Server session expired.")
                
            response.raise_for_status()
            raw_data = response.json()
            
            return parse_profile_data(raw_data)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
