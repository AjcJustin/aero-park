import requests
import datetime
import time

def check_time():
    print(f"System Time: {datetime.datetime.now()}")
    print(f"System UTC Time: {datetime.datetime.utcnow()}")
    
    try:
        response = requests.get("https://google.com")
        google_date = response.headers.get("Date")
        print(f"Google Server Time: {google_date}")
    except Exception as e:
        print(f"Error connecting to Google: {e}")

if __name__ == "__main__":
    check_time()
