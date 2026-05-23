import requests

url = "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
response = requests.get(url, headers=headers, timeout=15)
print("Encoding:", response.encoding)
print("Apparent Encoding:", response.apparent_encoding)
print("Content-Type:", response.headers.get("Content-Type"))
print("First 500 bytes of content:", response.content[:500])
