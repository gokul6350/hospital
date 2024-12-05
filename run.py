from app import create_app
import subprocess
import threading
import sys
import os
import signal

def run_streamlit():
    # Get the absolute path to pharmacy_app.py
    pharmacy_path = os.path.join(os.path.dirname(__file__), 'pharmacy', 'pharmacy_app.py')
    # Use a flag file to prevent multiple instances
    if not os.path.exists('.streamlit_running'):
        with open('.streamlit_running', 'w') as f:
            f.write('1')
        try:
            subprocess.run([sys.executable, '-m', 'streamlit', 'run', pharmacy_path])
        finally:
            # Clean up flag file when Streamlit exits
            if os.path.exists('.streamlit_running'):
                os.remove('.streamlit_running')

def run_flask():
    app = create_app()
    # Disable Flask reloader when running with Streamlit
    app.run(debug=True, port=5000, use_reloader=False)

if __name__ == '__main__':
    # Clean up any existing flag file
    if os.path.exists('.streamlit_running'):
        os.remove('.streamlit_running')
        
    # Start Streamlit in a separate thread
    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()
    
    # Run Flask in the main thread
    try:
        run_flask()
    except KeyboardInterrupt:
        # Clean up on CTRL+C
        if os.path.exists('.streamlit_running'):
            os.remove('.streamlit_running')
        sys.exit(0)