# ferramentas PDF

Site em Flask para comprimir, dividir, juntar e converter arquivos PDF, JPG, JPEG e PNG.

## Estrutura do projeto

```
pdfPorQpdf/
│
├── app.py                 # backend Flask (todas as rotas da API)
├── requirements.txt        # dependências Python
├── README.md
│
├── templates/
│   └── index.html          # página principal
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
│
├── uploads/                 # arquivos temporários enviados (esvaziada automaticamente)
└── outputs/                 # arquivos gerados para download
```

## 1. Requisitos do sistema

Todas as funcionalidades rodam com **Python + bibliotecas Python** (instaladas via `pip install -r requirements.txt`). **Nenhum programa externo** (Ghostscript, LibreOffice etc.) é necessário:

| Funcionalidade | Dependência (biblioteca Python) |
|---|---|
| Comprimir PDF | **pikepdf** (usa o QPDF por baixo) |
| Juntar / Dividir PDF | **pypdf** |
| PDF → Word | **pdf2docx** |
| JPG/JPEG/PNG → PDF | **PyMuPDF** |

> O site oferece conversão apenas de PDF para Word. Não há funcionalidade de Word para PDF.

## 2. Configurar o ambiente (no PyCharm)

1. Abra a pasta `pdfPorQpdf` no PyCharm como novo projeto.
2. No PyCharm, crie um ambiente virtual: `File > Settings > Project > Python Interpreter > Add Interpreter > Venv`.
3. Abra o terminal integrado do PyCharm e rode:

```
pip install -r requirements.txt
```

No servidor Windows, configure um ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Configure as credenciais do painel antes de iniciar o serviço:

```powershell
$env:SECRET_KEY="gere-uma-chave-longa-e-aleatoria"
$env:USUARIO_ADM="usuario-do-painel"
$env:SENHA_ADM="senha-forte"
$env:COOKIE_SECURE="1"
```

As variáveis `SECRET_KEY`, `USUARIO_ADM` e `SENHA_ADM` devem ser definidas em produção.
Sem as credenciais do administrador, o painel de logs permanece indisponível.
Use `COOKIE_SECURE=1` quando a aplicação estiver atrás de HTTPS.

## 3. Como rodar

Existem dois jeitos: **para testar** (desenvolvimento) e **para colocar no ar** (produção). O app é o mesmo, só muda o servidor.

### 3.1 Testar / desenvolver (PyCharm)

O servidor de desenvolvimento do Flask mostra erros direto no terminal e recarrega
as alterações sozinho (com `FLASK_DEBUG=1`):

```powershell
python app.py
```

> Use este jeito enquanto estiver editando o código. Não é indicado para uso contínuo
> no servidor — sob carga ele é instável.

### 3.2 Produção (Waitress)

O Waitress é apropriado para servir a aplicação Flask e aguentou bem os testes de carga:

```powershell
waitress-serve --host=0.0.0.0 --port=5000 --threads=32 app:app
```

- `--threads=32` aumenta o número de atendentes simultâneos (o padrão é 4, que é baixo).
- Sem `--threads`, o site funciona, mas fica lento com muitos usuários ao mesmo tempo.

Para o serviço ficar sempre ligado no Windows, crie uma tarefa agendada ou um serviço
(por exemplo com NSSM) apontando para `waitress-serve`. Evite rodar `python app.py`
como "serviço".

Depois valide no navegador ou no monitoramento interno:

```text
http://IP_DO_SERVIDOR:5000/health
```

O endpoint deve retornar `{"status":"ok"}`. Garanta que o usuário do serviço tenha
permissão de escrita nas pastas `uploads/`, `outputs/` e `logs/`. Faça backup periódico
do arquivo `logs/acessos.db`.

Por padrão, cada operação aceita até 200 MB somando todos os arquivos enviados. Para
alterar esse limite no servidor, configure `MAX_UPLOAD_MB` antes de iniciar o serviço.

## 5. Como funciona

- O `app.py` serve o `index.html` e expõe 5 rotas de API (`/api/juntar`, `/api/dividir`, `/api/comprimir`, `/api/pdf-para-word`, `/api/jpg-para-pdf`).
- O JavaScript (`script.js`) envia os arquivos via `fetch()` para essas rotas e baixa automaticamente o resultado.
- Arquivos enviados ficam em `uploads/` só durante o processamento e são apagados logo depois.
- Arquivos gerados ficam em `outputs/` até o download.

## Próximos passos possíveis
- Adicionar limite de tamanho de arquivo mais visível no front-end
- Adicionar barra de progresso real (upload grande)
- Fazer deploy (Render, Railway, PythonAnywhere, etc.)
