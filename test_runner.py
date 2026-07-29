"""
Test runner to compare heuristic vs Gemini mode on sample files.
"""
import os
import json
from dotenv import load_dotenv
from bughound_agent import BugHoundAgent
from llm_client import MockClient, GeminiClient

# Load environment
load_dotenv()

# Sample files to test
SAMPLE_FILES = [
    "sample_code/print_spam.py",
    "sample_code/mixed_issues.py",
]

def load_sample(filepath):
    with open(filepath, "r") as f:
        return f.read()

def run_test():
    print("=" * 80)
    print("BUGHOUND TEST: Heuristic vs Gemini Mode")
    print("=" * 80)

    for sample_file in SAMPLE_FILES:
        code = load_sample(sample_file)
        print(f"\n{'='*80}")
        print(f"Testing: {sample_file}")
        print(f"{'='*80}")
        print(f"Code:\n{code}\n")

        # Test 1: Heuristic mode
        print("\n--- HEURISTIC MODE ---")
        heuristic_agent = BugHoundAgent(client=MockClient())
        heuristic_result = heuristic_agent.run(code)
        heuristic_issues = heuristic_result.get("issues", [])

        print(f"Issues found: {len(heuristic_issues)}")
        for issue in heuristic_issues:
            print(f"  - {issue['type']} ({issue['severity']}): {issue['msg']}")

        print(f"\nAgent logs:")
        for log in heuristic_result.get("logs", []):
            print(f"  {log['step']}: {log['message']}")

        # Test 2: Gemini mode
        print("\n--- GEMINI MODE ---")
        try:
            gemini_agent = BugHoundAgent(client=GeminiClient())
            gemini_result = gemini_agent.run(code)
            gemini_issues = gemini_result.get("issues", [])

            print(f"Issues found: {len(gemini_issues)}")
            for issue in gemini_issues:
                print(f"  - {issue['type']} ({issue['severity']}): {issue['msg']}")

            print(f"\nAgent logs:")
            for log in gemini_result.get("logs", []):
                print(f"  {log['step']}: {log['message']}")

            # Compare
            print("\n--- COMPARISON ---")
            heuristic_count = len(heuristic_issues)
            gemini_count = len(gemini_issues)
            print(f"Heuristic found: {heuristic_count} issues")
            print(f"Gemini found: {gemini_count} issues")
            if heuristic_count != gemini_count:
                print(f"Difference: {abs(gemini_count - heuristic_count)} issues")

        except Exception as e:
            print(f"Gemini mode failed: {e}")
            print("(This is expected if API key is invalid or quota exceeded)")

if __name__ == "__main__":
    run_test()
