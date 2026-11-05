# Configuração do ambiente

Antes de iniciar o projeto, é necessário preparar o ambiente Python e instalar as dependências do sistema.

## 1. Requisitos

- Python 3.10 ou superior
- pip atualizado
- ambiente virtual recomendado
- acesso à pasta do projeto

## 2. Criar ambiente virtual

No Windows, execute:

```bash
cd c:\caminho\para\o\projeto
python -m venv venv
venv\Scripts\activate
```

## 3. Instalar dependências

Caso o projeto tenha um arquivo `requirements.txt`, use:

```bash
pip install -r requirements.txt
```

Se precisar instalar manualmente, os principais módulos podem ser:

```bash
pip install flask pikepdf PyMuPDF pdf2docx PyPDF2
```

## 4. Estrutura de pastas importante

A estrutura principal do projeto geralmente é:

```text
pdfPorQpdf/
├── app.py
├── requirements.txt
├── static/
├── templates/
├── docs/
├── uploads/
├── temp/
└── ...
```

Essas pastas são importantes para:
- `static/`: arquivos CSS, JS e imagens;
- `templates/`: páginas HTML;
- `uploads/`: arquivos enviados pelos usuários;
- `temp/`: arquivos temporários gerados durante o processamento;
- `docs/`: documentação do projeto.

## 5. Rodar a aplicação

Para iniciar o projeto localmente:

```bash
python app.py
```

Se o projeto estiver configurado com Flask:

```bash
set FLASK_APP=app.py
flask run
```

## 6. Variáveis de ambiente

Se o projeto usa configurações externas, elas podem ser salvas em um arquivo `.env` ou definidas no sistema.

Exemplo:

```env
SECRET_KEY=sua_chave
UPLOAD_FOLDER=uploads
```

Se o projeto não usa variáveis de ambiente, essa seção pode ser removida.

## 7. Verificações finais

Depois de configurar o ambiente, teste:

- se o servidor subiu corretamente;
- se a página inicial abre no navegador;
- se o upload de PDF funciona;
- se a conversão, compressão e divisão de arquivos respondem corretamente.

## 8. Solução rápida de problemas

Se aparecer erro como `ModuleNotFoundError`, verifique se o ambiente virtual está ativado e se as dependências foram instaladas.

Se o servidor não iniciar, confirme:
- se o arquivo `app.py` existe;
- se o Python está na versão correta;
- se a porta usada pelo projeto está livre.

## 9. Observações

É recomendado manter o ambiente virtual ativo durante o desenvolvimento e não subir arquivos temporários ou pastas de configuração sensíveis para repositórios públicos.

Se o projeto for hospedado em produção, também é importante configurar corretamente:
- permissões de pasta;
- logs;
- backup de arquivos;
- segurança de upload.