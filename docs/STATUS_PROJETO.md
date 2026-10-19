# Status do projeto CTRL-Lab

## Status geral

Em desenvolvimento ativo.

## Situação atual

- Raspberry Pi: sensores/alertas e inferência local OpenCV DNN para YOLOv8 ONNX implementados
- Sistema central: persistência e eventos iniciais implementados
- Câmeras: estrutura para entrada e laboratório pronta
- Visão computacional: detector ONNX, avaliação de EPI e risco de fumaça/fogo integrados ao runtime do Raspberry
- Testes: automatizados cobrindo módulos principais

O runtime está pronto para receber um modelo ONNX treinado/exportado com as classes esperadas. O modelo e a interface gráfica ainda não estão incluídos no repositório; sem pesos compatíveis, não há inferência visual funcional.

## Fases concluídas

- Fase 0: organização inicial do projeto
- Fase 1: primeira câmera de entrada
- Fase 2: suporte à segunda câmera e múltiplos streams
- Fase 3: inferência YOLOv8 ONNX no Raspberry com OpenCV DNN
- Integração de decisões visuais com sensores, atuadores e status MQTT

## Fases pendentes

- Modelo ONNX próprio para classes de EPI, fumaça e fogo
- Comunicação e instalação de broker MQTT no Raspberry
- Interface gráfica e conexão com os streams IP
- Testes com Raspberry e câmeras reais
- Testes finais e apresentação

## Observação

O projeto continua seguindo a sequência planejada em [PLANO_DESENVOLVIMENTO.md](../PLANO_DESENVOLVIMENTO.md), com arquitetura modular e preparação para expansão das funcionalidades.
