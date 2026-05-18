"""Iniciador local da interface web do MarkItDown."""

import sys
import time
import webbrowser
import subprocess
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    """Iniciar o servidor e abrir o navegador"""
    
    print("""
    ============================================
        DocFlow
        Iniciando interface local
    ============================================
    """)
    
    # Configurações
    venv_python = Path('.venv/Scripts/python.exe')
    app_file = 'app.py'
    url = 'http://127.0.0.1:5000'
    
    if not venv_python.exists():
        print("Erro: ambiente virtual não encontrado.")
        print("   Execute: python -m venv .venv")
        sys.exit(1)
    
    if not Path(app_file).exists():
        print("Erro: app.py não encontrado.")
        sys.exit(1)
    
    print("Verificando dependências...")
    try:
        result = subprocess.run(
            [str(venv_python), '-c', 'import flask, markitdown'],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            print("Dependências faltando.")
            if result.stderr:
                print(result.stderr.strip())
            sys.exit(1)
        print("Dependências OK\n")
    except Exception as e:
        print(f"Aviso: {e}")
    
    print("Iniciando servidor Flask...")
    print(f"Abrindo: {url}\n")
    
    # Iniciar servidor em processo separado
    try:
        # Iniciar Flask
        flask_process = subprocess.Popen(
            [str(venv_python), app_file]
        )
        
        # Aguardar o servidor iniciar
        time.sleep(3)
        
        # Verificar se o servidor iniciou
        try:
            import urllib.request
            urllib.request.urlopen(url, timeout=2)
        except Exception:
            print("⏳ Aguardando servidor...", end='', flush=True)
            for i in range(10):
                time.sleep(1)
                try:
                    urllib.request.urlopen(url, timeout=1)
                    print("\rServidor iniciado.")
                    break
                except Exception:
                    print(".", end='', flush=True)
        
        # Abrir no navegador
        print(f"Abrindo navegador em {url}...")
        webbrowser.open(url)
        
        # Obter IP local para exibição
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"
            
        print(f"""
    ┌──────────────────────────────────────────┐
    │  Servidor rodando com sucesso!           │
    │                                          │
    │  Acesso Local: http://localhost:5000     │
    │  Acesso Rede:  http://{local_ip}:5000     │
    │                                          │
    │  Use Ctrl+C para parar                   │
    └──────────────────────────────────────────┘
        """)
        
        # Manter processo ativo
        flask_process.wait()
        
    except KeyboardInterrupt:
        print("\n\nServidor interrompido pelo usuário.")
        flask_process.terminate()
        flask_process.wait(timeout=5)
    except Exception as e:
        print(f"\nErro: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
