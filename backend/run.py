import subprocess
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv isn't installed yet on first run (before requirements are
    # installed below); env vars can still be set manually in that case.
    pass

def install_requirements():
    """Install Python requirements"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Successfully installed Python dependencies")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False
    return True

def run_server():
    """Run the FastAPI server"""
    try:
        if not os.environ.get("HF_TOKEN"):
            print("⚠️  HF_TOKEN is not set. AI enhancement will be skipped (base composite "
                  "image will be returned). Copy backend/.env.example to backend/.env and "
                  "set HF_TOKEN to enable AI enhancement.")

        subprocess.run([sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Failed to run server: {e}")

if __name__ == "__main__":
    print("🚀 Starting Festive AI Greetings Backend")
    print("📦 Installing dependencies...")
    
    if install_requirements():
        print("🌟 Starting FastAPI server...")
        run_server()
    else:
        print("❌ Failed to start server due to dependency issues")