import os
import sys
import shutil
import subprocess
import asyncio
from dotenv import load_dotenv

# Reconfigure stdout to use UTF-8 if possible to support emojis/cyrillic,
# or fall back to safe text prefixes if encoding fails.
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def check_executable(name):
    path = shutil.which(name)
    if path:
        print(f"[OK] {name} found: {path}")
        return True
    
    if name == "yt-dlp":
        # Fallback check for python module yt_dlp
        try:
            subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, check=True)
            print("[OK] yt-dlp found as Python module (sys.executable -m yt_dlp)")
            return True
        except Exception:
            pass
            
    print(f"[ERROR] {name} NOT found in PATH. Please install it.")
    return False

async def test_sdk():
    print("\nTesting Claude Agent SDK import and simple call...")
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
        print("[OK] claude-agent-sdk imported successfully.")
    except ImportError as e:
        print(f"[ERROR] Failed to import claude-agent-sdk: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

    # Check for CLAUDE_CODE_OAUTH_TOKEN
    token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        print("[WARN] CLAUDE_CODE_OAUTH_TOKEN is not set in bridge/.env. Skipping SDK connectivity test.")
        return True

    # Try simple query
    try:
        options = ClaudeAgentOptions(
            model="claude-sonnet-5",
            allowed_tools=["Read"],
            max_turns=2,
            effort="low"
        )
        print("Sending simple 'respond OK' query to agent...")
        # Since query is an async generator, iterate over it
        async for msg in query(prompt="Respond with exactly 'OK' and nothing else.", options=options):
            print(f"Agent message received: {msg}")
        print("[OK] Claude Agent SDK connectivity test finished.")
        return True
    except Exception as e:
        print(f"[ERROR] Claude Agent SDK connectivity test failed: {e}")
        return False

def main():
    print("=== LOCUS Bridge Smoke Test ===")
    
    # Load dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[OK] Loaded environment from {env_path}")
    else:
        print(f"[ERROR] No .env file found at {env_path}")
        sys.exit(1)

    # Check env vars
    required_vars = ["GROQ_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "BOT_TOKEN", "OWNER_CHAT_ID"]
    all_vars_ok = True
    for var in required_vars:
        val = os.getenv(var)
        if val:
            # Mask sensitive values
            masked = val[:6] + "..." if len(val) > 6 else "set"
            print(f"[OK] Environment variable {var} is set ({masked})")
        else:
            print(f"[ERROR] Environment variable {var} is NOT set!")
            all_vars_ok = False

    # Check executables
    executables_ok = True
    for exe in ["ffmpeg", "yt-dlp", "git"]:
        if not check_executable(exe):
            executables_ok = False

    # Run SDK test
    sdk_ok = asyncio.run(test_sdk())

    print("\n=== Smoke Test Summary ===")
    if all_vars_ok and executables_ok and sdk_ok:
        print("All checks passed! LOCUS bridge is ready.")
    else:
        print("[WARN] Some checks failed. Please review the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
