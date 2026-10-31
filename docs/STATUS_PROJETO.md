# Status do projeto CTRL-Lab

## Status geral

Em desenvolvimento ativo.

## Situação atual

- Raspberry Pi: sensores/alertas e inferência local OpenCV DNN para YOLOv8 ONNX implementados
- Sistema central: persistência e eventos iniciais implementados
- Câmera: runtime preparado para uma única PS3 Eye USB compartilhada pelos modelos
- Visão computacional: segurança executa continuamente; acesso/EPI pode ser alternado por atalho `A` ou por comando MQTT
- Dashboard: painel web acessível por IP, com estado, sensores, eventos, controle remoto e pré-visualização da câmera protegida por token
- Testes: automatizados cobrindo módulos principais

O runtime está pronto para receber dois modelos ONNX treinados/exportados com classes separadas (segurança e acesso). Os pesos ainda não estão incluídos; sem pesos compatíveis, não há inferência visual funcional. O dashboard já está implementado; sua validação com broker e Raspberry reais permanece pendente.

## Fases concluídas

- Fase 0: organização inicial do projeto
- Fase 1: captura local de câmera preparada
- Fase 2: frame compartilhado e dois estados de execução dos modelos implementados
- Fase 3: inferência YOLOv8 ONNX no Raspberry com OpenCV DNN
- Integração de decisões visuais com sensores, atuadores e status MQTT

## Fases pendentes

- Modelo ONNX próprio para classes de EPI, fumaça e fogo
- Comunicação e instalação de broker MQTT no Raspberry
- Validação do dashboard e dos comandos com broker e Raspberry reais
- Testes físicos da PS3 Eye e medição de desempenho no Raspberry
- Testes com Raspberry e câmera real
- Testes finais e apresentação

## Observação

O projeto continua seguindo a sequência planejada em [PLANO_DESENVOLVIMENTO.md](../PLANO_DESENVOLVIMENTO.md), com arquitetura modular e preparação para expansão das funcionalidades.
