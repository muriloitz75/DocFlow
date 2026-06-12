import requests
import json

session = requests.Session()

# Log in
login_response = session.post("http://localhost:5000/api/auth/login", json={
    "username": "admin",
    "password": "admin"
})
print("Login Status:", login_response.status_code)
print("Login Body:", login_response.json())

# Index gazette URL
gazette_url = "https://diariooficial.imperatriz.ma.gov.br/upload/diario_oficial/5B7EE2EABE7C52293F4591DC7A985C88A26FD8AD0.pdf"
print("\nIndexing gazette URL...")
index_response = session.post("http://localhost:5000/api/gazette/index", json={
    "url": gazette_url
})
print("Index Status:", index_response.status_code)
index_data = index_response.json()
if not index_data.get("success"):
    print("Failed to index:", index_data)
    exit(1)

cache_id = index_data["cache_id"]
total_pages = index_data["total_pages"]
norms = index_data["norms"]
print(f"Success! Cache ID: {cache_id}, Total Pages: {total_pages}, Norms Found: {len(norms)}")

# Print the first 5 norms
for i, norm in enumerate(norms[:5]):
    print(f"Norm {i}: {norm['tipo']} Nº {norm['numero']} (Pages {norm['start_page']}-{norm['end_page']})")
    print(f"  Ementa: {norm['ementa']}")

# Extract the first norm
if norms:
    print("\nExtracting the third norm (index 2: PORTARIA Nº 5.777)...")
    extract_response = session.post("http://localhost:5000/api/gazette/extract", json={
        "cache_id": cache_id,
        "norm_id": 2,
        "option": "standard"
    })
    print("Extract Status:", extract_response.status_code)
    extract_data = extract_response.json()
    if extract_data.get("success"):
        print("\n--- CONTENT ---")
        print(extract_data["content"][:2000])
        print("--- END CONTENT ---")
    else:
        print("Failed to extract:", extract_data)
