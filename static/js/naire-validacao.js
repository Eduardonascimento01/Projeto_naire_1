/* ==========================================================================
   NAIRE - avisos campo a campo nos formulários
   Usado no cadastro de funcionário e nas telas de acesso (criar login,
   trocar senha). Mesmas regras em todas as telas.

   Como usar no HTML:
     - campos obrigatórios: required  +  data-msg-obrigatorio="Texto do aviso"
     - regras extras:       data-validar="cpf | telefone | usuario | senha | senha2 | data | inteiro"
     - logo depois do campo: <div class="invalid-feedback">...</div>
     - "Exibir senha":      <input type="checkbox" data-exibir-senha>
     - conferir se o login já existe: data-url-usuario="..." no <form>
   No JavaScript da página:
     NaireValidacao.ativar(form)          -> liga os avisos
     NaireValidacao.validarTudo(form)     -> true se tudo certo (senão foca o 1º erro)

   Os avisos funcionam também em campos criados depois (ex.: o botão "+ 1 filho"):
   o formulário "escuta" os eventos e descobre de qual campo eles vieram.

   O servidor confere tudo de novo: isto só ajuda a pessoa a preencher certo.
   ========================================================================== */
(function () {
    var USUARIO = /^[\w.@+-]{3,150}$/;

    function cpfValido(cpf) {
        cpf = cpf.replace(/\D/g, '');
        if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
        for (var t = 9; t <= 10; t++) {
            var soma = 0;
            for (var i = 0; i < t; i++) soma += Number(cpf[i]) * (t + 1 - i);
            if ((soma * 10) % 11 % 10 !== Number(cpf[t])) return false;
        }
        return true;
    }

    // Mensagem de erro do campo, ou '' se estiver certo.
    function erroDoCampo(campo) {
        var form = campo.form;
        var valor = campo.value.trim();
        // Erro apontado pelo servidor (ex.: CPF já cadastrado) vale até o valor mudar.
        if (campo.dataset.erroServidor && campo.value === campo.dataset.valorServidor) return campo.dataset.erroServidor;
        if (campo.required && !valor) return campo.dataset.msgObrigatorio || 'Campo obrigatório.';
        if (!valor && !campo.required) return '';
        switch (campo.dataset.validar) {
            case 'cpf':
                return cpfValido(valor) ? '' : 'CPF inválido. Confira os números.';
            case 'telefone':
                var n = valor.replace(/\D/g, '').length;
                return n === 10 || n === 11 ? '' : 'Informe o telefone com DDD (10 ou 11 dígitos).';
            case 'usuario':
                if (!USUARIO.test(valor)) return 'Use de 3 a 150 caracteres: letras, números e . @ + - _ (sem espaços).';
                if (campo._situacao && campo._situacao.valor === valor && campo._situacao.disponivel === false)
                    return 'Este nome de usuário já está em uso. Escolha outro.';
                return '';
            case 'senha':
                if (campo.value.length < 8) return 'A senha precisa ter pelo menos 8 caracteres.';
                if (/^\d+$/.test(campo.value)) return 'A senha não pode ter só números.';
                return '';
            case 'senha2':
                var senha = form.querySelector('[data-validar="senha"]');
                return senha && campo.value === senha.value ? '' : 'As senhas não são iguais.';
            case 'data':
                var m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(valor);
                if (!m) return 'Use o formato dd/mm/aaaa.';
                var d = new Date(+m[3], +m[2] - 1, +m[1]);
                if (d.getDate() !== +m[1] || d.getMonth() !== +m[2] - 1) return 'Data inválida.';
                if (d > new Date()) return 'A data não pode ser no futuro.';
                return '';
            case 'inteiro':
                return /^\d{1,3}$/.test(valor) ? '' : 'Use só números (ex.: 28).';
        }
        return '';
    }

    function mostrar(campo) {
        var erro = erroDoCampo(campo);
        var aviso = campo.parentElement.querySelector('.invalid-feedback');
        if (aviso && erro) aviso.textContent = erro;
        campo.classList.toggle('is-invalid', !!erro);
        campo.classList.toggle('is-valid', !erro && campo.value.trim() !== '');
        return !erro;
    }

    function campos(form) {
        return form.querySelectorAll('[required], [data-validar]');
    }

    function conferirUsuario(form, campo) {
        var valor = campo.value.trim();
        if (!form.dataset.urlUsuario || !USUARIO.test(valor)) return;
        fetch(form.dataset.urlUsuario + '?usuario=' + encodeURIComponent(valor), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (resp) {
                campo._situacao = { valor: valor, disponivel: resp.disponivel };
                if (campo.value.trim() === valor) { campo.dataset.tocado = '1'; mostrar(campo); }
            })
            .catch(function () {});  // sem resposta: o servidor confere de novo ao enviar
    }

    function ehCampo(el, form) {
        return el && el.form === form && (el.required || el.dataset.validar !== undefined) &&
               /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName);
    }

    function marcarErrosDoServidor(raiz) {
        // Erros que vieram do servidor: guarda a mensagem até a pessoa mudar o valor.
        raiz.querySelectorAll('.is-invalid').forEach(function (campo) {
            campo.dataset.tocado = '1';
            campo.dataset.valorServidor = campo.value;
            var aviso = campo.parentElement.querySelector('.invalid-feedback');
            if (aviso) campo.dataset.erroServidor = aviso.textContent.trim();
        });
    }

    function ativar(form) {
        marcarErrosDoServidor(form);

        // Clique num BOTÃO do formulário ("Enviar", "+ 1 filho"...): o campo perde o
        // foco ANTES do clique terminar. Se o aviso aparecesse nessa hora, ele
        // empurraria o botão para baixo e o clique se perderia (era preciso clicar
        // duas vezes). Nesse caso o aviso espera: o envio confere tudo de novo.
        form.addEventListener('pointerdown', function (e) {
            var botao = e.target.closest && e.target.closest('button, [type="submit"]');
            if (botao && form.contains(botao)) {
                form._clicandoBotao = true;
                setTimeout(function () { form._clicandoBotao = false; }, 600);
            }
        });

        // Avisa ao SAIR do campo (focusout "sobe" até o formulário, por isso
        // funciona também em campos criados depois).
        form.addEventListener('focusout', function (e) {
            var campo = e.target;
            if (!ehCampo(campo, form)) return;
            campo.dataset.tocado = '1';
            var indoParaBotao = e.relatedTarget && e.relatedTarget.tagName === 'BUTTON' && form.contains(e.relatedTarget);
            if (form._clicandoBotao || indoParaBotao) return;
            mostrar(campo);
            if (campo.dataset.validar === 'usuario') conferirUsuario(form, campo);
        });

        // Depois de "tocado", atualiza a cada tecla (ou a cada escolha, nos selects).
        function aoMudar(e) {
            var campo = e.target;
            if (ehCampo(campo, form)) {
                if (campo.tagName === 'SELECT') campo.dataset.tocado = '1';
                if (campo.dataset.tocado) mostrar(campo);
                if (campo.dataset.validar === 'usuario') {
                    clearTimeout(form._esperaUsuario);
                    form._esperaUsuario = setTimeout(function () { conferirUsuario(form, campo); }, 400);
                }
            }
            // Mudou a senha: a confirmação precisa ser conferida de novo.
            if (campo.dataset && campo.dataset.validar === 'senha') {
                var senha2 = form.querySelector('[data-validar="senha2"]');
                if (senha2 && senha2.dataset.tocado) mostrar(senha2);
            }
        }
        form.addEventListener('input', aoMudar);
        form.addEventListener('change', aoMudar);

        // "Exibir senha": mostra/esconde todas as senhas do formulário.
        form.addEventListener('change', function (e) {
            if (!e.target.matches || !e.target.matches('[data-exibir-senha]')) return;
            form.querySelectorAll('[data-validar="senha"], [data-validar="senha2"]').forEach(function (c) {
                c.type = e.target.checked ? 'text' : 'password';
            });
        });
    }

    function validarTudo(form) {
        var primeiroErro = null;
        campos(form).forEach(function (campo) {
            campo.dataset.tocado = '1';
            if (!mostrar(campo) && !primeiroErro) primeiroErro = campo;
        });
        if (primeiroErro) {
            primeiroErro.focus();
            primeiroErro.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return !primeiroErro;
    }

    window.NaireValidacao = { ativar: ativar, validarTudo: validarTudo, cpfValido: cpfValido };
})();
