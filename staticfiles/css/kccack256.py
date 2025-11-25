import requests
from Crypto.Hash import keccak

# Define the URL of the website you want to hash
url = "https://labs.nobitex.ir/"

# Send an HTTP GET request to the URL to retrieve the website content
try:
    response = requests.get(url)
    response.raise_for_status()  # Check for successful response
    website_content = response.text
except requests.exceptions.RequestException as e:
    print("Error:", e)
    exit(1)

# Convert the website content to bytes
website_bytes = website_content.encode('utf-8')

# Calculate the Keccak-256 hash
keccak_hash = keccak.new(data=website_bytes, digest_bits=256)
keccak256_hash = keccak_hash.hexdigest()

print("Keccak-256 Hash:", keccak256_hash)