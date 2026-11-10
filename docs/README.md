# Documentação do projeto CTRL-Lab

Esta pasta reúne a documentação técnica e o histórico do desenvolvimento do projeto.

## Objetivo

Centralizar informações sobre a arquitetura, módulos implementados e o estado atual do desenvolvimento do sistema.

## Estrutura

```text
docs/
├── README.md
├── FUNCIONAMENTO_ATUAL.md
├── PENDENCIAS_CONCLUSAO.md
├── GUIA_EXECUCAO.md
├── MATERIAIS_E_MONTAGEM.md
├── PROGRESSO_IMPLEMENTACAO.md
└── STATUS_PROJETO.md
```

## Módulos principais do projeto

- app/: módulos de aquisição de vídeo e visão computacional
- central/: persistência e eventos do sistema central
- raspberry_pi/: monitoramento do ambiente, alertas e controle de atuadores
- tests/: testes automatizados de regressão

## Referência rápida

- [README.md](../README.md): visão geral e objetivos do projeto
- [FUNCIONAMENTO_ATUAL.md](./FUNCIONAMENTO_ATUAL.md): fluxo implementado hoje, modos de operação e diferenças entre arquitetura planejada e runtime padrão
- [PENDENCIAS_CONCLUSAO.md](./PENDENCIAS_CONCLUSAO.md): checklist priorizado com critérios de aceite para concluir e demonstrar o projeto
- [GUIA_EXECUCAO.md](./GUIA_EXECUCAO.md): preparação passo a passo do Raspberry Pi, montagem, runtime e dashboard
- [MATERIAIS_E_MONTAGEM.md](./MATERIAIS_E_MONTAGEM.md): componentes, ligações e cuidados elétricos
- [STATUS_PROJETO.md](./STATUS_PROJETO.md): estado atual e pendências
- [PLANO_DESENVOLVIMENTO.md](../PLANO_DESENVOLVIMENTO.md): planejamento das fases do desenvolvimento
