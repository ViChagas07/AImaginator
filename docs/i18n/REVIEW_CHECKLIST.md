# Checklist de revisão nativa

Para cada locale: marcar `reviewed` em `apps/web/messages/_review.json` somente
após conferir os itens abaixo.

- [ ] Placeholders ICU idênticos aos do `pt-BR.json` (`{count}`, `{name}`).
- [ ] Termos do glossário respeitados.
- [ ] Textos de erro não prometem sucesso nem expõem detalhes internos.
- [ ] Botões e mensagens cabem em 360 px sem overflow horizontal.
- [ ] Árabe: layout RTL, pontuação e números corretos.
- [ ] Russo: plural de créditos/gerações correto.
- [ ] Japonês/chinês/coreano: sem espaços artificiais e com contagem natural.
- [ ] Datas e números formatados via `Intl`, não manualmente.
- [ ] Conteúdo de moderação (sexual, gore, hate, self-harm) com tom adequado.
- [ ] Nenhum texto fixo em componente; tudo vem de `messages/*.json`.

Data da revisão, revisor e observações devem ser registrados no `_review.json`.
