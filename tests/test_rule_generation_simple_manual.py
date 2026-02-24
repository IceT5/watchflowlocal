import requests
import json
import time
import sys
import io
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Test configuration - using 127.0.0.1 instead of localhost
API_URL = "http://127.0.1:8000/api/v1/rules/recommend-test"
REPO_URL = "https://github.com/IceT5/servlet"
GitHub_Token = os.getenv("GITHUB_TOKEN")

# Test payload
payload = {
    "repo_url": REPO_URL,
    "github_token": GitHub_Token,
    "force_refresh": False
}

print("=" * 60)
print("Testing Automatic Rule Generation (Mock Endpoint)")
print("=" * 60)
print(f"Repository: {REPO_URL}")
print(f"API Endpoint: {API_URL}")
print(f"Using GitHub Token: {GitHub_Token[:10]}...")
print()

try:
    print("Sending request ...")
    response = requests.post(API_URL, json=payload, timeout=30)

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        print("[OK] Request successful.")
        result = response.json()

        print("\n" + "=" * 60)
        print("RESULT SUMMARY")
        print("=" * 60)

        # Count rules
        rules_yaml = result.get('rules_yaml', '')
        rules_count = rules_yaml.count('description:')
        print(f"\n[OK] Rules generated: {rules_count}")

        # Print rules YAML
        print("\n" + "-" * 60)
        print("Generated Rules (YAML)")
        print("-" * 60)
        print(rules_yaml)

        # Print analysis summary
        print("\n" + "-" * 60)
        print("Analysis Summary")
        print("-" * 60)
        summary = result.get('analysis_summary', {})
        for key, value in summary.items():
            print(f"{key}: {value}")

        # Print analysis report
        print("\n" + "-" * 60)
        print("Analysis Report (Mock)")
        print("-" * 60)
        print(result.get('analysis_report', 'No report returned'))

        print("\n" + "-" * 60)
        print("[OK] MOCK TEST COMPLETED SUCCESSFULLY")
        print("-" * 60)

    else:
        print(f"Request failed with status {response.status_code}")
        print(f"Error Response: {response.text}")
    
except requests.exceptions.Timeout:
    print("\n Request timed out after 30 seconds")

except requests.exceptions.RequestException as e:
    print(f"\n Request failed: {str(e)}")

except Exception as e:
    print(f"\n Unexpected error: {str(e)}")
    import traceback
    traceback.print_exc()