import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Test configuration - using 127.0.0.1 instead of localhost
API_URL = "http://127.0.1:8000/api/v1/rules/recommend"
REPO_URL = "https://github.com/IceT5/servlet"
GitHub_Token = os.getenv("GITHUB_TOKEN")

# Test payload
payload = {
    "repo_url": REPO_URL,
    "github_token": GitHub_Token,
    "force_refresh": False
}

print("=" * 60)
print("Testing Automatic Rule Generation")
print("=" * 60)
print(f"Repository: {REPO_URL}")
print(f"API Endpoint: {API_URL}")
print(f"Using GitHub Token: {GitHub_Token[:10]}...") 
print()

try:
    print("Sending request ...")
    # No timeout - wait as long as needed for analysis to complete
    response = requests.post(API_URL, json=payload)

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        print("[OK] Request successful.")
        result = response.json()

        print("\n" + "=" * 60)
        print("RESULT SUMMARY")
        print("=" * 60)

        # Print key information
        print(f"\n[OK] Rules generated: {len(result.get('rules_yaml', '').split('description')) - 1 if 'description:' in result.get('rules_yaml', '') else 0}")

        # Print rules YAML
        print("\n" + "-" * 60)
        print("Generated Rules (YAML):")
        print("-" * 60)
        print(result.get("rules_yaml", "No rules generated"))

        # Print analysis summary
        print("\n" + "-" * 60)
        print("Analysis Summary:")
        print("-" * 60)
        summary = result.get('analysis_summary', {})
        for key, value in summary.items():
            print(f"{key}: {value}")

        # Print warnings if any
        warnings = result.get("warnings", [])
        if warnings:
            print("\n" + "-" * 60)
            print("Warnings:")
            print("-" * 60)
            for warning in warnings:
                print(f"[WARNING] {warning}")
        
        # Print analysis report
        print("\n" + "-" * 60)
        print("ANALYSIS REPORT")
        print("-" * 60)
        print(result.get("analysis_report", "No report generated"))

        print("\n" + "=" * 60)
        print("[OK] Test completed successfully.")
        print("=" * 60)

    else:
        print(f"[ERROR] Request failed with status code {response.status_code}")
        print(f"Error Response: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"\n[ERROR] Request failed: {str(e)}")

except Exception as e:
    print(f"\n[ERROR] Unexpected error: {str(e)}")
    import traceback
    traceback.print_exc()
