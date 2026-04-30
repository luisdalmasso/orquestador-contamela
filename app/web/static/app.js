document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("tool-runner-form");
    if (!form) {
        return;
    }

    const output = document.getElementById("tool-runner-output");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const tool = document.getElementById("tool-name").value;
        const rawArguments = document.getElementById("tool-arguments").value;

        let parsedArguments = {};
        try {
            parsedArguments = JSON.parse(rawArguments || "{}");
        } catch (error) {
            output.textContent = `JSON inválido: ${error}`;
            return;
        }

        output.textContent = "Ejecutando…";
        try {
            const response = await fetch("/mcp/call", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({tool, arguments: parsedArguments}),
            });
            const payload = await response.json();
            output.textContent = JSON.stringify(payload, null, 2);
        } catch (error) {
            output.textContent = `Error ejecutando tool: ${error}`;
        }
    });
});
