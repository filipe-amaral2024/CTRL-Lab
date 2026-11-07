# Status do projeto CTRL-Lab

## Status geral

Em desenvolvimento ativo.

## Situação atual

- Raspberry Pi: runtime de sensores/alertas e inferência local OpenCV DNN para YOLOv8 ONNX implementados; validação física pendente
- Sistema central: persistência e eventos iniciais implementados
- Câmera: runtime preparado para uma única PS3 Eye USB compartilhada pelos modelos
- Visão computacional: segurança executa continuamente; acesso/EPI pode ser alternado por atalho `A` ou por comando MQTT
- Dashboard: painel web acessível por IP, com estado, sensores, eventos, controle remoto e pré-visualização da câmera protegida por token
- Testes: automatizados cobrindo módulos principais

O runtime está pronto para receber dois modelos ONNX treinados/exportados com classes separadas (segurança e acesso). Os pesos ainda não estão incluídos; sem pesos compatíveis, não há inferência visual funcional. O dashboard já está implementado; sua validação com broker e Raspberry reais permanece pendente.

No modo real, leituras indisponíveis de sensores são publicadas como `null`, em vez de serem substituídas por números aleatórios. O DHT22 requer dependência e ligação corretas. O MQ-2 possui leitura digital DO (limiar configurado no módulo, sem ppm). O botão de emergência tem trava mecânica; com modelo de segurança configurado, o reset reativa a visão e só limpa EMERGENCY após uma inferência segura e a ausência de risco crítico. A solicitação de reset permanece pendente enquanto a verificação executa. Sem o modelo, o reset só pode revalidar sensores e botões; não há confirmação visual. Durante EMERGENCY, visão/câmera e saídas físicas são pausadas, mas sensores, botões, Raspberry Pi e MQTT/status permanecem ativos. Isso é uma parada de software, não uma parada de emergência elétrica/certificada. Confirme tensão e polaridade do DO antes de conectá-lo ao GPIO.

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
