import requests

url = "https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
response = requests.get(url, headers=headers, timeout=15)
idx = response.content.find(b"Presid")
if idx != -1:
    slice_bytes = response.content[idx:idx+20]
    print("Bytes:", slice_bytes)
    # Check what character is at index 6 (after "Presid")
    char_byte = slice_bytes[6]
    print(f"Byte at index 6: hex={hex(char_byte)}, int={char_byte}")
    
    # Try decoding with cp1252, latin1, and utf-8
    for enc in ['latin1', 'cp1252', 'utf-8', 'iso-8859-15', 'windows-1250', 'iso-8859-2']:
        try:
            dec = slice_bytes.decode(enc)
            print(f"{enc} decoded: {dec}")
        except Exception as e:
            print(f"{enc} error: {e}")
