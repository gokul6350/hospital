import socket
import json
from datetime import datetime, timedelta

def create_sample_reminders():
    now = datetime.now()
    return {
        "status": "success",
        "reminders": [
            {
                "id": "1",
                "title": "Team Meeting",
                "description": "Weekly team sync",
                "datetime": (now + timedelta(hours=1)).isoformat(),
                "priority": "high"
            },
            {
                "id": "2",
                "title": "Lunch Break",
                "description": "Take lunch break",
                "datetime": (now + timedelta(minutes=30)).isoformat(),
                "priority": "medium"
            }
        ]
    }

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 8000))
    server_socket.listen(1)
    
    print("Server started on localhost:8000")
    
    while True:
        conn, addr = server_socket.accept()
        with conn:
            data = conn.recv(1024)
            if data == b'GET_REMINDERS':
                response = create_sample_reminders()
                conn.sendall(json.dumps(response).encode())

if __name__ == "__main__":
    start_server() 