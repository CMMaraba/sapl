# SAPL modern - pacotes do sistema

Esta branch usa o Python, Django e dependências da distribuição. O ambiente validado é Ubuntu 26.04.1, Python 3.14.4 e Django 5.2.9. As versões são as fornecidas pelo APT; não se instala um Python isolado nem dependências via pip/virtualenv.

## Instalação reproduzível

O manifesto é `system-dependencies-apt.txt`. Como root, executar `scripts/install_system_dependencies.sh`. Pacotes de testes também constam no manifesto para permitir repetir a validação. A instalação não configura banco, SMTP, Solr ou permissões de mídia e não inicia a aplicação automaticamente.

Os arquivos antigos de `requirements/`, `Dockerfile.dev`, `docker/Dockerfile` e as instruções pip/virtualenv em `docs/instalacao31.rst` pertencem ao deploy legado. Eles não constituem um método suportado de instalar esta branch modern. Reutilizar os pins Django 2.2/Python 3.6 desses caminhos não reproduz o ambiente nativo. Os arquivos permanecem para facilitar comparação com upstream; uma imagem Docker moderna exige trabalho e validação próprios.

## Configuração

Usar as variáveis de ambiente ou `sapl/.env`, que não deve ser versionado. Continuam obrigatórios SECRET_KEY, DATABASE_URL e ALLOWED_HOSTS. Preservar configuração SMTP original; EMAIL_BACKEND permite selecionar explicitamente um backend de testes. O padrão continua SMTP, ou console com DEBUG.

Redis é necessário para o cache atômico do django-ratelimit. REDIS_CACHE_URL seleciona o destino; padrão `redis://127.0.0.1:6379/1`. Banco/cache precisam estar disponíveis para os processos do serviço. USE_SOLR, SOLR_URL e SOLR_COLLECTION continuam configuráveis; quando USE_SOLR é falso, o backend simple do Haystack evita um engine vazio. O projeto não força desativação de Solr nem host/IP de testes.

O isolamento do CT 110 é externo à lógica distribuída: suas próprias variáveis, firewall, SMTP em memória, Solr desativado e jobs de produção bloqueados. Não copiar esses valores indiscriminadamente para produção.

## Migrações, assets e validação

Antes de modificar uma instalação real, revisar as migrações com `python3 manage.py migrate --plan` e `sqlmigrate`. No clone de referência, sete migrações modern_system_runtime registraram 21 AlterField sem DDL; as migrações auth/authtoken das dependências também foram aplicadas. Esse resultado depende do estado do banco existente e não substitui revisão em outra instalação.

Executar como o usuário da aplicação, também para manter a propriedade dos logs: `python3 manage.py check`, `python3 manage.py makemigrations --check --dry-run`, `python3 manage.py collectstatic --noinput`. O manifesto webpack foi adaptado para o webpack-loader atual, reutilizando os bundles existentes. Alterações no frontend podem exigir recompilação JavaScript pelo fluxo upstream.

Os componentes locais em `sapl/modern_components` substituem dependências sem pacote APT equivalente. Executar seus testes com `python3 manage.py test sapl.modern_components.tests`. A suíte usa pytest do sistema: `python3 -m pytest -q -o addopts='' --create-db -r s --tb=short --ignore=sapl/crud/tests/test_base.py`. O banco de testes é recriado com migrações reais; não usar --nomigrations como substituto dessa validação. pytest.ini já exclui legacy e crud; test_base.py também tem sintaxe inválida na origem. Os skips herdados devem ser revisados separadamente, sem serem apresentados como testes executados. conftest.py direciona uploads de cada teste a tmp_path, preservando a mídia da aplicação. REDIS_CACHE_URL deve selecionar um banco Redis descartável, separado do cache do serviço. Consultar o relatório da migração para cobertura efetivamente verificada.

Depois de configurar o serviço e reiniciar, testar consultas, permissões, login/logout com CSRF, formulários, anexos, PDFs, APIs e OAI. Logs e estáticos são arquivos operacionais, não backups. Registrar a quantidade e o tamanho de quaisquer backups/snapshots/temporários criados, e remover os temporários autorizados depois da validação.

A apresentação Bootstrap do admin e quatro helpers HTML Crispy antigos foram preservados localmente com as licenças correspondentes. O helper localize_legacy usa pytz do APT para reproduzir a escolha original is_dst=False em horários históricos ambíguos, adaptando ZoneInfo do Django. CrudDeleteView.form_valid encaminha a exclusão validada por delete para manter hooks, cascatas e tratamento de ProtectedError.

## Atualizações upstream

As alterações são mantidas na branch modern. Atualizar contra um commit upstream explícito, revisar conflitos e executar a comparação funcional novamente. Substitutos locais de imagens/OAI/OpenAPI e diferenças das APIs de Django/DRF exigem revisão quando upstream modificar esses caminhos. Não misturar o deploy legado pip com o nativo APT para resolver conflitos.

## Proteções de mídia no nginx

O deploy nativo deve preservar as restrições do nginx da instalação original. Além dos aliases static/media, manter `location ~* ^/media/.*\.(backup|sql|dump|tar|gz|tgz|zip|7z|env|py|sh|ini)$ { return 404; }` e `location ^~ /media/pauta/ { return 404; }`. A revisão do CT 110 identificou essas regras ausentes na configuração nativa, restaurou-as e confirmou o bloqueio por HTTP com arquivos de teste existentes. Validar com nginx -t e aguardar a troca dos workers após reload antes da prova HTTP.
