from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import json

ARQUIVO = Path("/tmp/mensagens.json")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
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
            print(f"[CONTATO] {mensagem['nome']} <{mensagem['email']}>: {mensagem['mensagem']}")
            self.responder(200, {
                "ok": True,
                "mensagem": "Mensagem enviada com sucesso! Entrarei em contato em breve.",
            })
        except Exception:
            self.responder(400, {
                "ok": False,
                "erro": "Nao foi possivel processar sua mensagem.",
            })

    def salvar(self, mensagem):
        mensagens = []
        if ARQUIVO.exists():
            try:
                mensagens = json.loads(ARQUIVO.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                mensagens = []
        mensagens.append(mensagem)
        ARQUIVO.write_text(
            json.dumps(mensagens, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def responder(self, codigo, payload):
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args):
        pass
