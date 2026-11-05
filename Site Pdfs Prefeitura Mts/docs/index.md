# Ferramentas PDF

**Documentação do projeto Ferramentas PDF**  
*Prefeitura de Monte Santo de Minas*

---

## O que é?

O site **Ferramentas PDF** é uma aplicação web desenvolvida em Flask para manipulação de arquivos PDF no ambiente interno da Prefeitura. Oferece ferramentas para:

- **Juntar** vários PDFs em um único arquivo
- **Dividir** um PDF em páginas separadas ou intervalos
- **Comprimir** PDFs para reduzir tamanho
- **Converter** PDF para Word (.docx)
- **Converter** JPG para PDF (.pdf)

---
---

## Como rodar

### Para testar (desenvolvimento)

```bash
python app.py
```

### Para produção (servidor)

```bash
waitress-serve --host=0.0.0.0 --port=5000 --threads=32 app:app
```

---

## Documentação

Explore as seções no menu lateral para detalhes sobre cada componente do projeto.
