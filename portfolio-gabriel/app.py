from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json
import shutil
import subprocess
import threading
import webbrowser

PORTA = 8000
RAIZ = Path(__file__).resolve().parent
ARQUIVO_MENSAGENS = RAIZ / "mensagens.json"

NAVEGADORES = [
    Path(r"C:\Users\gabri\AppData\Local\Programs\Opera GX\opera.exe"),
    Path(r"C:\Program Files\Opera GX\opera.exe"),
    Path(r"C:\Program Files\Opera\opera.exe"),
]


def abrir_navegador(url):
    for navegador in NAVEGADORES:
        if navegador.exists():
            print(f"Abrindo no Opera GX: {url}")
            subprocess.Popen([str(navegador), "--new-window", url])
            return
    opera = shutil.which("opera")
    if opera:
        subprocess.Popen([opera, "--new-window", url])
        return
    print("Opera GX nao encontrado, abrindo no navegador padrao...")
    webbrowser.open(url)


class Manipulador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(RAIZ), **kwargs)

    def do_POST(self):
        if self.path.rstrip("/") != "/contato":
            self.enviar_json(404, {"ok": False, "erro": "Rota nao encontrada"})
            return
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            mensagem = {
                "nome": str(dados.get("nome", "")).strip()[:120],
                "email": str(dados.get("email", "")).strip()[:160],
                "mensagem": str(dados.get("mensagem", "")).strip()[:2000],
                "recebida_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            }
            if not mensagem["nome"] or not mensagem["mensagem"]:
                raise ValueError("Campos obrigatorios ausentes")
            self.salvar(mensagem)
            print(f"[CONTATO] Nova mensagem de {mensagem['nome']} <{mensagem['email']}>")
            self.enviar_json(200, {
                "ok": True,
                "mensagem": "Mensagem enviada com sucesso! Entrarei em contato em breve.",
            })
        except Exception:
            self.enviar_json(400, {
                "ok": False,
                "erro": "Nao foi possivel processar sua mensagem.",
            })

    def salvar(self, mensagem):
        mensagens = []
        if ARQUIVO_MENSAGENS.exists():
            try:
                mensagens = json.loads(ARQUIVO_MENSAGENS.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                mensagens = []
        mensagens.append(mensagem)
        ARQUIVO_MENSAGENS.write_text(
            json.dumps(mensagens, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def enviar_json(self, codigo, payload):
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    servidor = HTTPServer(("localhost", PORTA), Manipulador)
    url = f"http://localhost:{PORTA}"
    print("=" * 48)
    print("  Portfolio | Gabriel Augusto")
    print(f"  Rodando em: {url}")
    print("  Pressione Ctrl+C para encerrar")
    print("=" * 48)
    threading.Timer(1.0, lambda: abrir_navegador(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado. Ate mais!")
