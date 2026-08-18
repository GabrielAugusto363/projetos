// Troca de abas
const botoesAba = document.querySelectorAll(".aba-btn");
const conteudosAba = document.querySelectorAll(".aba-conteudo");

botoesAba.forEach((botao) => {
    botao.addEventListener("click", () => {
        botoesAba.forEach((b) => b.classList.remove("ativo"));
        conteudosAba.forEach((c) => c.classList.remove("ativo"));

        botao.classList.add("ativo");
        document.getElementById(botao.dataset.aba).classList.add("ativo");
    });
});

// Função genérica para enviar um formulário e baixar o arquivo de resposta
async function enviarFormulario(formId, url, statusId, nomeArquivoPadrao) {
    const form = document.getElementById(formId);
    const status = document.getElementById(statusId);

    form.addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const dados = new FormData(form);

        status.textContent = "Processando... aguarde.";
        status.className = "status carregando";

        try {
            const resposta = await fetch(url, {
                method: "POST",
                body: dados,
            });

            if (!resposta.ok) {
                const erroJson = await resposta.json().catch(() => null);
                const mensagem = erroJson?.erro || "Ocorreu um erro ao processar o arquivo.";
                status.textContent = mensagem;
                status.className = "status erro";
                return;
            }

            // Descobre o nome do arquivo pelo cabeçalho, se existir
            const disposicao = resposta.headers.get("Content-Disposition");
            let nomeArquivo = nomeArquivoPadrao;
            if (disposicao && disposicao.includes("filename=")) {
                nomeArquivo = disposicao.split("filename=")[1].replaceAll('"', "");
            }

            const blob = await resposta.blob();
            const urlBlob = window.URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = urlBlob;
            link.download = nomeArquivo;
            document.body.appendChild(link);
            link.click();
            link.remove();

            status.textContent = "Pronto! O download começou automaticamente.";
            status.className = "status sucesso";

        } catch (erro) {
            status.textContent = "Erro de conexão com o servidor.";
            status.className = "status erro";
        }
    });
}

enviarFormulario("form-juntar", "/api/juntar", "status-juntar", "juntado.pdf");
enviarFormulario("form-dividir", "/api/dividir", "status-dividir", "paginas_divididas.zip");
enviarFormulario("form-comprimir", "/api/comprimir", "status-comprimir", "comprimido.pdf");
enviarFormulario("form-pdf-word", "/api/pdf-para-word", "status-pdf-word", "convertido.docx");
enviarFormulario("form-word-pdf", "/api/word-para-pdf", "status-word-pdf", "convertido.pdf");
