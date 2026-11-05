// troca as abas do painel de ferramentas
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

// Função padrão para enviar formularios
async function enviarFormulario(formId, url, statusId, nomeArquivoPadrao) {
    const form = document.getElementById(formId);
    const status = document.getElementById(statusId);

    form.addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const dados = new FormData(form);
        const botaoEnviar = form.querySelector('button[type="submit"]');

        status.textContent = "Processando... aguarde.";
        status.className = "status carregando";
        botaoEnviar.disabled = true;

        try {
            const resposta = await fetch(url, {
                method: "POST",
                body: dados,
            });

            if (!resposta.ok) {
                const erroJson = await resposta.json().catch(() => null);
                const mensagem = resposta.status === 413
                    ? "Os arquivos selecionados ultrapassam o limite permitido para uma operação. Tente dividir em grupos menores."
                    : erroJson?.erro || "Ocorreu um erro ao processar o arquivo.";
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
            window.URL.revokeObjectURL(urlBlob);

            status.textContent = "Pronto! O download começou automaticamente.";
            status.className = "status sucesso";

        } catch (erro) {
            status.textContent = "Erro de conexão com o servidor.";
            status.className = "status erro";
        } finally {
            botaoEnviar.disabled = false;
        }
    });
}

enviarFormulario("form-juntar", "/api/juntar", "status-juntar", "juntado.pdf");
enviarFormulario("form-dividir", "/api/dividir", "status-dividir", "paginas_divididas.zip");
enviarFormulario("form-comprimir", "/api/comprimir", "status-comprimir", "comprimido.pdf");
enviarFormulario("form-pdf-word", "/api/pdf-para-word", "status-pdf-word", "convertido.docx");
enviarFormulario("form-jpg-pdf", "/api/jpg-para-pdf", "status-jpg-pdf", "convertido.pdf");

// ---------------------------------------------------------------------
// Tem o heartbeat para contar entradas/saidas no painel do admin, mas não coleta nada além disso.
// ---------------------------------------------------------------------
function enviarHeartbeat() {
    fetch("/api/heartbeat", { method: "POST", keepalive: true }).catch(() => {});
}

enviarHeartbeat();
setInterval(enviarHeartbeat, 30 * 1000); // a cada 30 segundos

window.addEventListener("beforeunload", () => {
    navigator.sendBeacon("/api/heartbeat/saida");
});